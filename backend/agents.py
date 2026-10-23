"""Bounded, durable agent workflows. Python owns tools, permissions, and transitions."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from intelligence import Intelligence
from checkpoints import Checkpoints
from operations import Operations, audit, canonical, uid
from product_models import InvestigationBrief, PolicyAnalysis
from providers import PROMPT_VERSION, problem, verify_citations
from store import now


def transaction_input_scope(context):
    """Summarize the final bounded sample without model arithmetic or FX mixing."""
    totals = {}
    for transaction in context["transactions"]:
        currency = transaction["currency"]
        amount = Decimal(str(transaction["amount"]))
        if not amount.is_finite():
            raise ValueError("Invalid transaction amount in retained evidence")
        totals[currency] = totals.get(currency, Decimal(0)) + amount
    return {
        "record_count": len(context["transactions"]),
        "totals_by_currency": {
            currency: format(total, "f") for currency, total in sorted(totals.items())
        },
        "scope": context["transaction_scope"],
    }


CATALOG = [
    {
        "id": "investigation",
        "name": "Investigation agent",
        "target": "case",
        "description": "Collect transactions, control hits, policy evidence, and fresh sanctions results; prepare a cited investigation brief.",
        "model_calls": 1,
    },
    {
        "id": "screening",
        "name": "Screening research agent",
        "target": "customer",
        "description": "Screen names against every enabled official list and prepare an evidence-linked review recommendation.",
        "model_calls": 1,
    },
    {
        "id": "policy_analyst",
        "name": "Policy analyst",
        "target": "policy",
        "description": "Extract cited obligations and proposed control types for human interpretation. Never activates controls.",
        "model_calls": 1,
    },
    {
        "id": "policy_change",
        "name": "Policy-change analyst",
        "target": "policy_change",
        "description": "Compare archived versions and propose obligations for an explicitly identified candidate population.",
        "model_calls": 1,
    },
    {
        "id": "report",
        "name": "Reporting agent",
        "target": "case",
        "description": "Draft a reviewable investigation narrative and evidence pack. Does not file reports or contact third parties.",
        "model_calls": 1,
    },
    {
        "id": "evidence_verifier",
        "name": "Evidence verifier",
        "target": "automatic",
        "description": "Deterministic quotation/ID checks, source freshness checks, and match consistency checks in every relevant workflow.",
        "model_calls": 0,
    },
]


def chunks_for_policy(policy, max_chars=12000):
    text = policy["content"]
    words = text[:max_chars].split()
    chunks = []
    for i, start in enumerate(range(0, len(words), 250)):
        chunks.append(
            {
                "chunk_id": f"{policy['id']}:{policy['version']}:agent:{i}",
                "policy_id": policy["id"],
                "title": policy["title"],
                "version": policy["version"],
                "source_url": policy.get("source_url", ""),
                "text": " ".join(words[start : start + 300]),
            }
        )
    return chunks, {
        "document_characters": len(text),
        "included_characters": min(len(text), max_chars),
        "complete": len(text) <= max_chars,
    }


class AgentEngine:
    def __init__(self, hub, settings, client):
        self.hub, self.settings, self.client = hub, settings, client
        self.stopping = False
        self.model_lock = asyncio.Lock()
        self.checkpoints = Checkpoints(hub, settings)

    def enqueue(self, store, kind, target_id, actor, *, agent_policy=None):
        if agent_policy and agent_policy.get("prompt_version") != PROMPT_VERSION:
            raise problem(
                409,
                "agent_prompt_version_changed",
                "The agent key references a different prompt version; reissue it after review.",
            )
        ops = Operations(store)
        if kind in ("investigation", "report"):
            ops.get("case", target_id)
        elif kind == "screening":
            ops.get("customer", target_id)
        elif kind == "policy_analyst":
            if not store.policy(target_id):
                raise problem(404, "not_found", "Policy not found.")
        elif kind == "policy_change":
            ops.get("policy_change", target_id)
        elif kind != "maintenance":
            raise problem(422, "invalid_agent", "Unknown agent workflow.")
        Intelligence(
            self.settings, store, self.client
        ).require_ai() if kind != "maintenance" else None
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute(
                "SELECT id FROM jobs WHERE kind=? AND target_id=? AND state IN ('queued','running','paused')",
                (kind, target_id),
            ).fetchone()
            if pending:
                raise problem(
                    409,
                    "job_exists",
                    "This target already has an active run. Open Agent operations to resume or cancel it.",
                )
            if kind != "maintenance":
                if agent_policy:
                    key = self.hub.agent_keys.active(agent_policy["key_id"])
                    if not key:
                        raise problem(
                            403,
                            "agent_key_revoked",
                            "The requesting agent is no longer authorized.",
                        )
                    count = db.execute(
                        "SELECT count(*) FROM jobs WHERE actor=? AND kind!='maintenance' AND created_at>=?",
                        (actor, datetime.now(timezone.utc).date().isoformat()),
                    ).fetchone()[0]
                    if count >= agent_policy["daily_runs"]:
                        raise problem(
                            429,
                            "agent_key_budget",
                            "This agent's daily run budget is exhausted.",
                        )
                count = db.execute(
                    "SELECT count(*) FROM jobs WHERE kind!='maintenance' AND created_at>=?",
                    (datetime.now(timezone.utc).date().isoformat(),),
                ).fetchone()[0]
                if count >= self.settings.agent_daily_runs:
                    raise problem(
                        429,
                        "agent_budget",
                        "The workspace daily agent-run budget is exhausted.",
                    )
            job = {
                "id": uid(),
                "kind": kind,
                "target_id": target_id,
                "state": "queued",
                "created_at": now(),
                "updated_at": now(),
                "actor": actor,
                "payload": {
                    "model": self.settings.groq_model,
                    "model_revision": self.settings.groq_model_revision,
                    "prompt_version": PROMPT_VERSION,
                    "pseudonymize": self.settings.pseudonymize_model_calls,
                    "max_model_calls": 0 if kind == "maintenance" else 1,
                    "requested_by": actor,
                    **(
                        {
                            "agent_key": agent_policy["key_id"],
                            "model": agent_policy["model"],
                            "model_revision": agent_policy["model_revision"],
                            "pseudonymize": agent_policy["pseudonymize"],
                        }
                        if agent_policy
                        else {}
                    ),
                },
            }
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
                (
                    job["id"],
                    kind,
                    target_id,
                    "queued",
                    job["created_at"],
                    job["updated_at"],
                    actor,
                    canonical(job["payload"]),
                ),
            )
            audit(
                db,
                actor,
                "agent_queued",
                {
                    "id": job["id"],
                    "kind": kind,
                    "target_id": target_id,
                    "model": job["payload"]["model"],
                    "model_revision": job["payload"]["model_revision"],
                    "prompt_version": job["payload"]["prompt_version"],
                },
            )
        return job

    @staticmethod
    def get(store, job_id):
        with store.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise problem(404, "not_found", "Agent run not found.")
            job = dict(row)
            job["payload"] = json.loads(job["payload"])
            job["steps"] = [
                {
                    "step": r["step"],
                    "created_at": r["created_at"],
                    "output": json.loads(r["payload"]),
                }
                for r in db.execute(
                    "SELECT * FROM job_steps WHERE job_id=? ORDER BY created_at",
                    (job_id,),
                )
            ]
        return job

    @staticmethod
    def list(store, target_id=None):
        with store.connect() as db:
            return [
                {**dict(r), "payload": json.loads(r["payload"])}
                for r in db.execute(
                    "SELECT * FROM jobs WHERE (? IS NULL OR target_id=?) ORDER BY created_at DESC LIMIT 1000",
                    (target_id, target_id),
                )
            ]

    def control(self, store, job_id, action, actor):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT state,payload FROM jobs WHERE id=?", (job_id,)
            ).fetchone()
            if not row:
                raise problem(404, "not_found", "Agent run not found.")
            state = row["state"]
            allowed = {
                "pause": ("queued", "running"),
                "resume": ("paused", "failed", "interrupted"),
                "cancel": ("queued", "running", "paused", "failed", "interrupted"),
            }
            if state not in allowed[action]:
                raise problem(
                    409, "invalid_transition", f"Cannot {action} a {state} run."
                )
            next_state = {"pause": "paused", "resume": "queued", "cancel": "cancelled"}[
                action
            ]
            payload = json.loads(row["payload"])
            if action == "resume" and payload.get("model_attempts", 0):
                draft = db.execute(
                    "SELECT 1 FROM job_steps WHERE job_id=? AND step='draft_analysis'",
                    (job_id,),
                ).fetchone()
                if not draft or state == "failed":
                    raise problem(
                        409,
                        "agent_attempt_used",
                        "This run has used its model attempt. Start a new run to preserve its evidence history and budget.",
                    )
            payload.pop("error", None)
            db.execute(
                "UPDATE jobs SET state=?,updated_at=?,payload=? WHERE id=?",
                (next_state, now(), canonical(payload), job_id),
            )
            audit(
                db,
                actor,
                "agent_" + action,
                {"id": job_id, "from": state, "to": next_state},
            )
        return self.get(store, job_id)

    def recover(self, store):
        with store.connect() as db:
            db.execute(
                "UPDATE jobs SET state='interrupted',updated_at=? WHERE state='running'",
                (now(),),
            )

    def claim(self, store):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE state='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                return None
            db.execute(
                "UPDATE jobs SET state='running',updated_at=? WHERE id=? AND state='queued'",
                (now(), row["id"]),
            )
        return self.get(store, row["id"])

    def is_running(self, store, job_id):
        with store.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM jobs WHERE id=? AND state='running'", (job_id,)
                ).fetchone()
                is not None
            )

    def step(self, store, job_id, name, output):
        with store.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO job_steps VALUES (?,?,?,?)",
                (job_id, name, now(), canonical(output)),
            )

    def finish(self, store, job_id, state, result=None, error=None):
        with store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload,actor FROM jobs WHERE id=? AND state='running'",
                (job_id,),
            ).fetchone()
            if not row:
                return
            payload = json.loads(row[0])
            if result is not None:
                payload["result"] = result
            if error:
                payload["error"] = error
            db.execute(
                "UPDATE jobs SET state=?,updated_at=?,payload=? WHERE id=?",
                (state, now(), canonical(payload), job_id),
            )
            audit(
                db,
                row["actor"]
                if row["actor"].startswith("agent:")
                else "agent:" + job_id,
                "agent_" + state,
                {
                    "id": job_id,
                    "error_code": error.get("code") if error else None,
                    "model": payload.get("model"),
                    "model_revision": payload.get("model_revision"),
                    "requested_by": payload.get("requested_by"),
                },
            )

    async def execute(self, org_id, job):
        store = self.hub.store(org_id)
        ops = Operations(store)
        pinned = self.settings.model_copy(
            update={
                "groq_model": job["payload"]["model"],
                "groq_model_revision": job["payload"].get(
                    "model_revision", "provider-unreported"
                ),
                "pseudonymize_model_calls": job["payload"].get("pseudonymize", False),
                "pseudonymization_scope": job["id"],
            }
        )
        provider = Intelligence(pinned, store, self.client)
        cached = {s["step"]: s["output"] for s in job["steps"]}
        try:
            if (
                job["kind"] != "maintenance"
                and job["payload"].get("prompt_version") != PROMPT_VERSION
            ):
                raise problem(
                    409,
                    "agent_prompt_version_changed",
                    "This run's prompt version is unavailable. Start a reviewed new run; no model attempt was made.",
                )
            key_id = job["payload"].get("agent_key")
            if key_id and not self.hub.agent_keys.active(key_id):
                raise problem(
                    403,
                    "agent_key_revoked",
                    "The requesting agent is no longer authorized.",
                )
            if job["kind"] == "maintenance":
                result = await self.maintenance(store, provider, ops, job["id"])
                if result is None:
                    return
                self.finish(store, job["id"], "completed", result)
                return
            context = cached.get("collect_evidence")
            if not context:
                kind = job["kind"]
                target = job["target_id"]
                coverage = {}
                case = None
                if kind in ("policy_analyst", "policy_change"):
                    if kind == "policy_change":
                        change = ops.get("policy_change", target)
                        versions = ops.policy_versions(change["policy_id"])
                        policy = next(
                            (
                                v
                                for v in versions
                                if v["version"] == change["new_version"]
                            ),
                            None,
                        )
                        old = next(
                            (
                                v
                                for v in versions
                                if v["version"] == change["old_version"]
                            ),
                            None,
                        )
                        if not old or not policy:
                            raise problem(
                                409,
                                "version_missing",
                                "The archived prior policy version is unavailable.",
                            )
                        candidates = ops.list("customer", 2000)
                        extra = {
                            "previous_policy_excerpt": old["content"][:6000],
                            "change": change,
                            "candidate_customer_ids": [c["id"] for c in candidates],
                            "candidate_count": len(candidates),
                            "scope": "These are candidates for human impact review, not confirmed affected customers.",
                        }
                    else:
                        policy = store.policy(target)
                        extra = {}
                    if not policy:
                        raise problem(404, "not_found", "Policy no longer exists.")
                    chunks, coverage = chunks_for_policy(
                        policy, 10000 if kind == "policy_change" else 14000
                    )
                    context = {
                        "task": "Extract up to five prioritized obligation themes from supplied policy excerpts, grouping closely related requirements. Keep the summary under 120 words, each obligation concise, and each quotation to one exact supporting sentence. Identify exceptions, ambiguity, omitted requirements, and missing coverage in limitations. This is not an exhaustive obligation inventory. All proposed controls require human review. Do not invent legal requirements or thresholds.",
                        "policies": chunks,
                        "coverage": coverage,
                        **extra,
                    }
                else:
                    if kind in ("investigation", "report"):
                        case = ops.get("case", target)
                        customer = ops.get("customer", case["customer_id"])
                        alerts = ops.case_alerts(target)[:12]
                    else:
                        customer = ops.get("customer", target)
                        alerts = []
                    txns = ops.customer_transactions(customer["id"], 50)
                    chunks = store.search(
                        "transaction transfer sanctions AML KYC "
                        + (case["title"] if case else customer["name"])
                    )[:4]
                    if not chunks:
                        raise problem(
                            409,
                            "no_policy_evidence",
                            "Add relevant policies before asking an agent to investigate.",
                        )
                    context = {
                        "task": "Prepare an evidence-grounded investigation brief. Distinguish observations from suspicion. Recommend human action, never legal approval. Consider the explicit source and sample limitations. draft_disposition is a nonbinding suggestion: confirmed means the supplied policy breach is supported, false_positive means the alert is explained by supplied evidence, insufficient_evidence means missing evidence prevents a conclusion. Use null to abstain. No suggestion changes or closes the case.",
                        "customer": customer,
                        "case": case,
                        "transactions": txns,
                        "transaction_scope": "Latest 50 transactions; not necessarily the full history.",
                        "alerts": [
                            {
                                "rule": a["rule_snapshot"],
                                "facts": a["facts"],
                                "transaction_id": a["transaction_id"],
                            }
                            for a in alerts
                        ],
                        "policies": chunks,
                    }
                self.step(store, job["id"], "collect_evidence", context)
            if not self.is_running(store, job["id"]):
                return
            kind = job["kind"]
            if kind in ("investigation", "screening", "report"):
                screening = cached.get("sanctions_screening")
                # Resume never silently reuses an expired snapshot.
                if screening:
                    fresh = all(
                        provider.status(s["id"])["status"] == "ready"
                        and provider.status(s["id"]).get("sha256") == s.get("sha256")
                        for s in screening["sources"]
                    )
                    if not fresh:
                        raise problem(
                            409,
                            "evidence_changed",
                            "Sanctions evidence changed or expired. Cancel this run and start a new one to collect current evidence.",
                        )
                else:
                    screening = await run_in_threadpool(
                        provider.screen_names, {"customer": context["customer"]["name"]}
                    )
                    self.step(store, job["id"], "sanctions_screening", screening)
                context = {**context, "sanctions_screening": screening}
            if not self.is_running(store, job["id"]):
                return
            input_scope = cached.get("model_input_scope")
            result = cached.get("draft_analysis")
            if not result:
                encoded = canonical(context)
                if len(encoded) > self.settings.agent_max_context_chars:
                    # Reduce transaction sampling, never silently truncate policies or JSON.
                    if "transactions" in context:
                        context["transactions"] = context["transactions"][:10]
                        context["transaction_scope"] = (
                            "Latest 10 transactions due to the configured context budget."
                        )
                    if len(canonical(context)) > self.settings.agent_max_context_chars:
                        raise problem(
                            422,
                            "agent_context_budget",
                            "This case exceeds the free-tier context budget. Narrow the evidence scope before starting a new run.",
                        )
                if "transactions" in context:
                    input_scope = transaction_input_scope(context)
                    self.step(store, job["id"], "model_input_scope", input_scope)
                async with self.model_lock:
                    if not self.is_running(store, job["id"]):
                        return
                    with store.connect() as db:
                        db.execute("BEGIN IMMEDIATE")
                        row = db.execute(
                            "SELECT payload FROM jobs WHERE id=?", (job["id"],)
                        ).fetchone()
                        payload = json.loads(row["payload"])
                        if payload.get("model_attempts", 0) >= 1:
                            raise problem(
                                409,
                                "agent_attempt_used",
                                "This run has used its model attempt. Start a new run.",
                            )
                        payload["model_attempts"] = 1
                        db.execute(
                            "UPDATE jobs SET payload=?,updated_at=? WHERE id=?",
                            (canonical(payload), now(), job["id"]),
                        )
                    schema = (
                        PolicyAnalysis
                        if kind in ("policy_analyst", "policy_change")
                        else InvestigationBrief
                    )
                    if key_id and not self.hub.agent_keys.active(key_id):
                        raise problem(
                            403,
                            "agent_key_revoked",
                            "The requesting agent is no longer authorized.",
                        )
                    result = await provider.complete(schema, context)
                    self.step(
                        store, job["id"], "model_identity", provider.last_model_identity
                    )
                self.step(store, job["id"], "draft_analysis", result)
            if not self.is_running(store, job["id"]):
                return
            if kind in ("policy_analyst", "policy_change"):
                obligations = []
                for obligation in result["obligations"]:
                    citation = verify_citations(
                        {"citations": [obligation["citation"]]}, context["policies"]
                    )[0]
                    obligations.append({**obligation, "citation": citation})
                verified = {
                    **result,
                    "obligations": obligations,
                    "output_scope": "Prioritized suggested obligations, not an exhaustive inventory. Review the full source document before implementation.",
                    "coverage": context.get("coverage", {}),
                    "requires_approval": True,
                }
            else:
                verified = {
                    **result,
                    "citations": verify_citations(result, context["policies"]),
                    "model_input_scope": input_scope,
                    "requires_approval": True,
                }
                if (
                    context["sanctions_screening"]["matches"]
                    and result["recommendation"] == "review_for_closure"
                ):
                    raise problem(
                        502,
                        "inconsistent_agent_result",
                        "An agent cannot recommend closure while potential sanctions matches need investigation.",
                    )
            self.step(
                store,
                job["id"],
                "verify_evidence",
                {
                    "passed": True,
                    "checks": [
                        "source_freshness"
                        if kind not in ("policy_analyst", "policy_change")
                        else "policy_snapshot",
                        "citation_ids",
                        "verbatim_quotations",
                        "allowed_output_schema",
                        "human_approval_boundary",
                    ],
                    "scope": "Verifies evidence references and constraints, not every inference in the narrative.",
                },
            )
            self.finish(store, job["id"], "completed", verified)
        except HTTPException as exc:
            detail = (
                exc.detail
                if isinstance(exc.detail, dict)
                else {"code": "agent_failed", "message": str(exc.detail)}
            )
            self.finish(store, job["id"], "failed", error=detail)
        except Exception:
            import logging

            logging.getLogger("policylens.agents").exception(
                "Agent run failed: %s", job["id"]
            )
            self.finish(
                store,
                job["id"],
                "failed",
                error={
                    "code": "agent_failed",
                    "message": "The workflow failed. Its completed steps remain available; no substitute analysis was produced.",
                },
            )

    async def maintenance(self, store, provider, ops, job_id=None):
        statuses = []
        for source in provider.selected_sources():
            if job_id and not self.is_running(store, job_id):
                return None
            statuses.append(await provider.sync(source))
        customers = ops.list("customer", 2001)
        if len(customers) > 2000:
            raise problem(
                422,
                "monitoring_capacity",
                "This single-instance monitoring run supports at most 2,000 customers.",
            )
        matches = 0
        for customer in customers:
            if job_id and not self.is_running(store, job_id):
                return None
            screening = await run_in_threadpool(
                provider.screen_names, {"customer": customer["name"]}
            )
            ops.save(
                "screening",
                {"customer_id": customer["id"], "screening": screening},
                "scheduled-monitor",
            )
            if screening["matches"]:
                from product_models import CaseInput

                case = ops.new_case(
                    CaseInput(
                        customer_id=customer["id"],
                        title="Potential sanctions match: " + customer["name"],
                        priority="high",
                        description="Scheduled screening found a potential name match. Verify identifiers and source evidence before deciding.",
                    ),
                    "scheduled-monitor",
                )
                ops.save(
                    "case_evidence",
                    {"case_id": case["id"], "screening": screening},
                    "scheduled-monitor",
                )
                matches += 1
            await asyncio.sleep(0)
        return {
            "sources": statuses,
            "screened": len(customers),
            "customers_with_matches": matches,
            "ai_calls": 0,
        }

    async def loop(self):
        recovered = set()
        while not self.stopping:
            organizations = self.hub.organizations()
            for org in organizations:
                store = self.hub.store(org["id"])
                if org["id"] not in recovered:
                    self.recover(store)
                    recovered.add(org["id"])
                ops = Operations(store)
                preferences = ops.preferences()
                if (
                    preferences.get("monitoring_enabled")
                    and preferences.get("next_monitor_at", "") <= now()
                ):
                    try:
                        self.enqueue(store, "maintenance", "workspace", "scheduler")
                        preferences["next_monitor_at"] = (
                            datetime.now(timezone.utc)
                            + timedelta(hours=preferences["monitoring_interval_hours"])
                        ).isoformat()
                        ops.save(
                            "preferences",
                            preferences,
                            "scheduler",
                            preferences.get("id"),
                        )
                    except HTTPException:
                        pass
                job = self.claim(store)
                if job:
                    await self.execute(org["id"], job)
            await run_in_threadpool(self.checkpoints.tick)
            await asyncio.sleep(1)

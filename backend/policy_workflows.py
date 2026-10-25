"""Workspace-scoped policy review and reversible removal from active use."""

import json
import uuid
from fastapi import HTTPException
from fastapi import APIRouter, Request
from operations import audit, canonical
from providers import problem
from store import now

router = APIRouter(prefix="/api")


@router.get("/policy-archive")
def archived_policies(request: Request):
    with request.state.store.connect() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,title,topic,version,updated_at FROM policies WHERE EXISTS (SELECT 1 FROM records WHERE kind='policy_archive' AND records.id=policies.id) ORDER BY updated_at DESC"
            )
        ]


def schedule_reviews(db, policy_id=None):
    """Coalesce activity changes into one durable refresh per active policy."""
    stamp = now()
    for row in db.execute(
        "SELECT id FROM policies WHERE (? IS NULL OR id=?) AND NOT EXISTS (SELECT 1 FROM records WHERE kind='policy_archive' AND records.id=policies.id)",
        (policy_id, policy_id),
    ).fetchall():
        payload = canonical({"policy_id": row[0], "revision": str(uuid.uuid4())})
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at",
            (
                "policy_review_pending",
                "policy-review-pending:" + row[0],
                stamp,
                stamp,
                payload,
            ),
        )


def refresh_pending(store, ops):
    with store.connect() as db:
        row = db.execute(
            "SELECT id,payload FROM records WHERE kind='policy_review_pending' ORDER BY updated_at LIMIT 1"
        ).fetchone()
    if not row:
        return
    try:
        review_policy(
            store, ops, json.loads(row[1])["policy_id"], "automatic-policy-review"
        )
    except HTTPException as exc:
        ops.save(
            "policy_review_failure",
            {"policy_id": json.loads(row[1])["policy_id"], "error": exc.detail},
            "automatic-policy-review",
            record_id="policy-review-failure:" + json.loads(row[1])["policy_id"],
        )
    with store.connect() as db:
        # A concurrent transaction must leave its newer revision queued.
        db.execute("DELETE FROM records WHERE id=? AND payload=?", (row[0], row[1]))


def review_policy(store, ops, policy_id, actor):
    policy = store.policy(policy_id)
    if not policy:
        raise problem(404, "not_found", "Policy not found.")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM records WHERE kind='policy_archive' AND id=?", (policy_id,)
        ).fetchone():
            raise problem(
                409, "policy_archived", "Restore this policy before reviewing activity."
            )
        current = db.execute(
            "SELECT version FROM policies WHERE id=?", (policy_id,)
        ).fetchone()
        if not current or current[0] != policy["version"]:
            raise problem(
                409,
                "policy_changed",
                "The policy changed before this review started. Retry the current version.",
            )
        controls = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM records WHERE kind='rule' AND json_extract(payload,'$.policy_id')=? AND json_extract(payload,'$.policy_version')=? AND json_extract(payload,'$.status')='active'",
                (policy_id, policy["version"]),
            )
        ]
        rows = db.execute(
            "SELECT payload FROM transactions ORDER BY occurred_at,id LIMIT 10001"
        ).fetchall()
        if len(rows) > 10000:
            raise problem(
                422,
                "review_capacity",
                "This deployment reviews up to 10,000 transactions per policy. No partial review was saved.",
            )
        customers = {
            r[0]: json.loads(r[1])
            for r in db.execute("SELECT id,payload FROM records WHERE kind='customer'")
        }
        results = []
        for row in rows:
            transaction = json.loads(row[0])
            customer = customers.get(transaction["customer_id"])
            hits = []
            applicable = [
                c
                for c in controls
                if c["kind"] not in ("amount", "aggregate")
                or c["currency"] == transaction["currency"]
            ]
            if customer:
                for control in applicable:
                    matched, facts = ops._matches(db, control, transaction, customer)
                    if matched:
                        alert, _ = ops.record_control_hit(
                            db,
                            control,
                            transaction,
                            customer,
                            facts,
                            actor,
                            historical_policy_review=True,
                        )
                        hits.append(
                            {
                                "control_id": control["id"],
                                "control_title": control["title"],
                                "control_version": control["version"],
                                "facts": facts,
                                "alert_id": alert["id"],
                                "case_id": alert["case_id"],
                            }
                        )
            results.append(
                {
                    "transaction_id": transaction["id"],
                    "external_id": transaction["external_id"],
                    "customer_id": transaction["customer_id"],
                    "status": "not_covered"
                    if not applicable or not customer
                    else "flagged"
                    if hits
                    else "no_control_hit",
                    "hits": hits,
                }
            )
    result = {
        "policy_id": policy_id,
        "policy_title": policy["title"],
        "policy_version": policy["version"],
        "reviewed_at": now(),
        "total": len(results),
        "active_controls": len(controls),
        "flagged": sum(r["status"] == "flagged" for r in results),
        "not_covered": sum(r["status"] == "not_covered" for r in results),
        "no_control_hit": sum(r["status"] == "no_control_hit" for r in results),
        "controls": [
            {"id": c["id"], "version": c["version"], "title": c["title"]}
            for c in controls
        ],
        "transactions": results,
        "scope": "All recorded transactions, evaluated against approved controls for this exact policy version. Uses currently recorded customer due-diligence status. No hit is not policy compliance; requirements without executable controls still need review. This review does not close cases or execute payments.",
    }
    saved = ops.save(
        "policy_review",
        result,
        actor,
        record_id="policy-review:" + policy_id,
        action="policy_transactions_reviewed",
    )
    with store.connect() as db:
        db.execute(
            "DELETE FROM records WHERE kind='policy_review_failure' AND id=?",
            ("policy-review-failure:" + policy_id,),
        )
    return saved


@router.get("/policies/{policy_id}/workflow")
def workflow(policy_id: str, request: Request):
    store, ops = request.state.store, request.state.ops
    if not store.policy(policy_id):
        raise problem(404, "not_found", "Policy not found.")
    with store.connect() as db:
        row = db.execute(
            "SELECT payload FROM records WHERE kind='policy_review' AND id=?",
            ("policy-review:" + policy_id,),
        ).fetchone()
        archived = bool(
            db.execute(
                "SELECT 1 FROM records WHERE kind='policy_archive' AND id=?",
                (policy_id,),
            ).fetchone()
        )
        automatic = db.execute(
            "SELECT payload FROM records WHERE kind='policy_automation' AND id=?",
            ("policy-automation:" + policy_id,),
        ).fetchone()
        pending = bool(
            db.execute(
                "SELECT 1 FROM records WHERE id=? AND kind='policy_review_pending'",
                ("policy-review-pending:" + policy_id,),
            ).fetchone()
        )
        failure = db.execute(
            "SELECT payload FROM records WHERE id=? AND kind='policy_review_failure'",
            ("policy-review-failure:" + policy_id,),
        ).fetchone()
    from agents import AgentEngine

    jobs = AgentEngine.list(store, policy_id)
    return {
        "policy": store.policy(policy_id),
        "archived": archived,
        "review": json.loads(row[0]) if row else None,
        "preparations": jobs[:10],
        "current_transactions": len(ops.customer_transactions(limit=10001)),
        "automation_enabled": request.app.state.settings.automatic_policy_analysis,
        "automation": json.loads(automatic[0]) if automatic else None,
        "refresh_pending": pending,
        "refresh_error": json.loads(failure[0])["error"] if failure else None,
    }


@router.post("/policies/{policy_id}/review")
def review(policy_id: str, request: Request):
    if request.state.user["role"] == "auditor":
        raise problem(403, "read_only_role", "Auditors cannot start reviews.")
    return review_policy(
        request.state.store, request.state.ops, policy_id, request.state.user["id"]
    )


@router.delete("/policies/{policy_id}")
def archive(policy_id: str, request: Request):
    if request.state.user["role"] != "admin":
        raise problem(
            403,
            "role_required",
            "Only workspace administrators can remove a policy from active use.",
        )
    store = request.state.store
    if not store.policy(policy_id):
        raise problem(404, "not_found", "Policy not found.")
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute(
            "SELECT 1 FROM records WHERE kind='policy_archive' AND id=?", (policy_id,)
        ).fetchone():
            return {"archived": True, "policy_id": policy_id}
        value = {
            "policy_id": policy_id,
            "archived_by": request.state.user["id"],
            "archived_at": now(),
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            ("policy_archive", policy_id, now(), now(), canonical(value)),
        )
        disabled = 0
        cancelled = []
        for job in db.execute(
            "SELECT id FROM jobs WHERE kind='policy_analyst' AND target_id=? AND state IN ('queued','running','paused')",
            (policy_id,),
        ).fetchall():
            db.execute(
                "UPDATE jobs SET state='cancelled',updated_at=? WHERE id=?",
                (now(), job[0]),
            )
            cancelled.append(job[0])
            audit(
                db,
                request.state.user["id"],
                "agent_cancel",
                {"id": job[0], "reason": "policy_archived"},
            )
        for row in db.execute(
            "SELECT id,payload FROM records WHERE kind='rule' AND json_extract(payload,'$.policy_id')=?",
            (policy_id,),
        ).fetchall():
            rule = json.loads(row[1])
            if rule["status"] == "active":
                rule["status"] = "disabled"
                rule["updated_at"] = now()
                db.execute(
                    "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                    (canonical(rule), now(), row[0]),
                )
                disabled += 1
        audit(
            db,
            request.state.user["id"],
            "policy_archived",
            {
                **value,
                "disabled_controls": disabled,
                "cancelled_preparations": cancelled,
            },
        )
    return {
        "archived": True,
        "policy_id": policy_id,
        "disabled_controls": disabled,
        "message": "Removed from active use. Archived versions and case evidence are preserved.",
    }


@router.post("/policies/{policy_id}/restore")
def restore(policy_id: str, request: Request):
    if request.state.user["role"] != "admin":
        raise problem(403, "role_required", "Only administrators can restore policies.")
    with request.state.store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT 1 FROM records WHERE kind='policy_archive' AND id=?", (policy_id,)
        ).fetchone()
        if not row:
            raise problem(404, "not_found", "Archived policy not found.")
        db.execute(
            "DELETE FROM records WHERE kind='policy_archive' AND id=?", (policy_id,)
        )
        schedule_reviews(db, policy_id)
        audit(
            db,
            request.state.user["id"],
            "policy_restored",
            {"policy_id": policy_id, "controls_reactivated": False},
        )
    return {"restored": True, "policy_id": policy_id, "controls_reactivated": False}

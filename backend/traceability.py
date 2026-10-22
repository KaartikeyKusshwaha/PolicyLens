"""Explicit human mappings from cited model-suggested obligations to controls."""

import hashlib
import json
from collections import defaultdict

from operations import audit, canonical
from providers import problem
from store import now

MAX_ROWS = 10000


def rows(db, query, parameters=()):
    values = []
    for row in db.execute(query, parameters):
        if len(values) >= MAX_ROWS:
            raise problem(
                413,
                "traceability_limit",
                "Traceability exceeds the 10,000-row pilot bound; no sampled matrix was returned.",
            )
        values.append(dict(row))
    return values


def matrix(db):
    policies = rows(db, "SELECT id,title,version FROM policies ORDER BY id")
    records = {}
    for kind in ("rule", "backtest", "traceability_link", "case_evidence"):
        records[kind] = [
            json.loads(r["payload"])
            for r in rows(
                db,
                "SELECT payload FROM records WHERE kind=? ORDER BY updated_at DESC,id",
                (kind,),
            )
        ]
    alerts = [
        json.loads(r["payload"])
        for r in rows(db, "SELECT payload FROM alerts ORDER BY id")
    ]
    controls = {r["id"]: r for r in records["rule"]}
    policy_by_id = {p["id"]: p for p in policies}
    links_by_obligation = defaultdict(list)
    for link in records["traceability_link"]:
        if link["linked"]:
            links_by_obligation[link["obligation_id"]].append(link)
    alerts_by_control = defaultdict(list)
    for alert in alerts:
        alerts_by_control[alert.get("rule_id")].append(alert)
    evidence_by_case = defaultdict(list)
    for item in records["case_evidence"]:
        evidence_by_case[item.get("case_id")].append(item)
    latest_simulations = {}
    for simulation in records["backtest"]:
        latest_simulations.setdefault(
            (simulation.get("rule_id"), simulation.get("version")), simulation
        )
    jobs = rows(
        db,
        "SELECT * FROM jobs WHERE kind='policy_analyst' AND state='completed' ORDER BY updated_at DESC,id DESC",
    )
    seen, obligations = set(), []
    for job in jobs:
        job_groups = set()
        payload = json.loads(job["payload"])
        result = payload.get("result", {})
        # Only the latest completed analysis for each policy version is current in
        # this matrix. Prior job data and mapping records remain in the audit/pack.
        for index, obligation in enumerate(result.get("obligations", [])):
            citation = obligation["citation"]
            version = citation.get("version")
            policy_id = citation.get("policy_id")
            if policy_id != job["target_id"]:
                continue
            group = (policy_id, version)
            if group in seen:
                continue
            job_groups.add(group)
            identifier = hashlib.sha256(
                canonical(
                    {"job_id": job["id"], "index": index, "obligation": obligation}
                ).encode()
            ).hexdigest()
            links = links_by_obligation[identifier]
            linked = []
            for link in links:
                control = controls.get(link["control_id"])
                if not control:
                    continue
                related = alerts_by_control[control["id"]]
                case_ids = {a["case_id"] for a in related}
                simulation = latest_simulations.get((control["id"], control["version"]))
                linked.append(
                    {
                        "control": control,
                        "mapping": link,
                        "latest_simulation": simulation,
                        "alert_count": len(related),
                        "evidence": [
                            e
                            for case_id in sorted(case_ids)
                            for e in evidence_by_case[case_id]
                        ],
                    }
                )
            policy = policy_by_id.get(policy_id)
            current = policy is not None and policy["version"] == version
            active = [
                r
                for r in linked
                if r["control"]["status"] == "active"
                and r["control"]["policy_id"] == policy_id
                and r["control"]["policy_version"] == version
            ]
            gaps = []
            if not current:
                gaps.append("historical_policy_version")
            if result.get("coverage", {}).get("complete") is False:
                gaps.append("partial_policy_analysis")
            if not linked:
                gaps.append("no_linked_control")
            if not active:
                gaps.append("no_active_control")
            if active and any(r["latest_simulation"] is None for r in active):
                gaps.append("active_control_without_recorded_simulation")
            obligations.append(
                {
                    "id": identifier,
                    "policy_id": policy_id,
                    "policy_version": version,
                    "policy_title": citation.get("title", ""),
                    "current_policy_version": current,
                    "analysis_job_id": job["id"],
                    "analysis_at": job["updated_at"],
                    "obligation": obligation["obligation"],
                    "citation": citation,
                    "suggested_control_kind": obligation.get("control_kind"),
                    "analysis_scope": result.get(
                        "output_scope",
                        "Suggested obligations; not an exhaustive inventory.",
                    ),
                    "analysis_coverage": result.get("coverage", {}),
                    "controls": linked,
                    "gaps": gaps,
                    "status": "linked_active_control"
                    if current and active
                    else "needs_review",
                }
            )
        seen.update(job_groups)
    missing = [
        p
        for p in policies
        if not any(
            o["policy_id"] == p["id"] and o["current_policy_version"]
            for o in obligations
        )
    ]
    return {
        "available_controls": list(controls.values()),
        "obligations": obligations,
        "policies_without_current_analysis": missing,
        "counts": {
            "obligations": len(obligations),
            "with_gaps": sum(bool(o["gaps"]) for o in obligations),
            "policies_without_current_analysis": len(missing),
        },
        "scope": "Latest completed policy-analyst suggestions per retained policy version. Human mappings are assertions of applicability, not proof of full policy coverage or effective detection. Simulations use historical transactions with current customer state; alert counts are observed volume, not accuracy.",
    }


def read_matrix(store):
    with store.connect() as db:
        db.execute("BEGIN")
        return matrix(db)


def map_control(store, obligation_id, data, actor):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        current = matrix(db)
        obligation = next(
            (o for o in current["obligations"] if o["id"] == obligation_id), None
        )
        if not obligation:
            raise problem(
                404,
                "obligation_not_found",
                "This obligation is missing or has been replaced by a newer analysis. Refresh the matrix.",
            )
        control = db.execute(
            "SELECT payload FROM records WHERE kind='rule' AND id=?", (data.control_id,)
        ).fetchone()
        if not control:
            raise problem(
                404, "control_not_found", "Control not found in this workspace."
            )
        control = json.loads(control[0])
        if data.linked and (
            not obligation["current_policy_version"]
            or control["policy_id"] != obligation["policy_id"]
            or control["policy_version"] != obligation["policy_version"]
        ):
            raise problem(
                409,
                "policy_version_mismatch",
                "Map a control from the same current policy version. Historical mappings can be removed but cannot be added.",
            )
        stamp = now()
        identifier = hashlib.sha256(
            (obligation_id + ":" + data.control_id).encode()
        ).hexdigest()
        prior = db.execute(
            "SELECT created_at FROM records WHERE kind='traceability_link' AND id=?",
            (identifier,),
        ).fetchone()
        value = {
            "id": identifier,
            "obligation_id": obligation_id,
            **data.model_dump(),
            "mapped_by": actor,
            "created_at": prior[0] if prior else stamp,
            "updated_at": stamp,
        }
        db.execute(
            "INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)",
            (
                "traceability_link",
                identifier,
                value["created_at"],
                stamp,
                canonical(value),
            ),
        )
        audit(
            db,
            actor,
            "obligation_control_linked"
            if data.linked
            else "obligation_control_unlinked",
            {
                "id": identifier,
                "obligation_id": obligation_id,
                "control_id": data.control_id,
                "notes": data.notes,
            },
        )
    return value

"""Automatic factual case preparation. No model calls or disposition writes."""

from decimal import Decimal

from intelligence import source_freshness


def prepare_review(pack, ops, settings, counts):
    totals = {}
    for transaction in pack["transactions"]:
        currency = transaction["currency"]
        totals[currency] = totals.get(currency, Decimal(0)) + Decimal(
            str(transaction["amount"])
        )
    total_transactions, total_alerts = counts
    missing = []
    if not pack.get("assignee_id") and pack["status"] != "resolved":
        missing.append("Assign an investigator before requesting a final review.")
    if pack["customer"].get("kyc_status") != "verified":
        missing.append("Customer due diligence is not recorded as verified.")
    sources = [
        source
        for evidence in pack["screening_evidence"]
        for source in evidence.get("screening", {}).get("sources", [])
    ]
    if not sources:
        missing.append("No sanctions source snapshots are attached to this case.")
    elif any(
        source_freshness(source, settings.sanctions_max_age_hours) != "ready"
        for source in sources
    ):
        missing.append(
            "Attached sanctions evidence includes expired or undated snapshots."
        )
    policies = {}
    signals = []
    for alert in pack["alerts"]:
        rule = alert.get("rule_snapshot") or {}
        policy_id, version = rule.get("policy_id"), rule.get("policy_version")
        key = (policy_id, version)
        if policy_id and key not in policies:
            archived = next(
                (p for p in ops.policy_versions(policy_id) if p["version"] == version),
                None,
            )
            policies[key] = {
                "id": policy_id,
                "version": version,
                "title": rule.get("policy_title", "Linked policy"),
                "available": archived is not None,
                "excerpt": archived["content"][:1200] if archived else None,
            }
            if not archived:
                missing.append("A control's archived policy version is unavailable.")
        signals.append(
            {
                "id": alert["id"],
                "title": alert["rule_title"],
                "transaction_id": alert.get("transaction_id"),
                "facts": alert.get("facts", {}),
                "policy_id": policy_id,
                "policy_version": version,
                "origin": alert.get("origin", "internal_control"),
            }
        )
    open_tasks = [task for task in pack["tasks"] if task["status"] == "open"]
    if not policies:
        missing.append("No policy-linked control evidence is attached to this case.")
    limitations = [
        "Totals describe the displayed customer history, not just flagged payments or a control's time window.",
        "Policy excerpts provide context; they do not establish that a breach occurred.",
        "This factual preparation does not validate an AI draft or make a final decision.",
        "Case notes and tasks are limited to 5,000 records each; attached screening history to 2,000 records.",
    ]
    if total_transactions > len(pack["transactions"]):
        limitations.append("Transaction history is limited to the latest 200 records.")
    if total_alerts > len(signals):
        limitations.append("Only the latest 500 case alerts are displayed.")
    if pack["status"] == "resolved":
        next_action = "Decision recorded. Download the evidence report or reopen if new evidence arrives."
    elif open_tasks or missing:
        next_action = "Review the outstanding evidence and tasks, then record your decision or escalate."
    else:
        next_action = (
            "Evidence is assembled. An independent reviewer can record a decision."
        )
    return {
        "mode": "automatic_factual_preparation",
        "prepared_at": pack["exported_at"],
        "transaction_count": len(pack["transactions"]),
        "total_customer_transactions": total_transactions,
        "totals_by_currency": {k: format(v, ".2f") for k, v in sorted(totals.items())},
        "alert_count": total_alerts,
        "signals": signals,
        "policies": list(policies.values()),
        "missing_evidence": list(dict.fromkeys(missing)),
        "open_tasks": open_tasks,
        "next_action": next_action,
        "limitations": limitations,
    }

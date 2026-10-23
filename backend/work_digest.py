"""Read-only, zero-model work summaries from a single workspace snapshot."""

import json
from datetime import datetime, timedelta, timezone

from intelligence import SOURCES, source_freshness

MAX_RECORDS = 10000
MAX_BYTES = 8 * 1024 * 1024
PREVIEW = 20


def timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def build_digest(store, settings):
    generated = datetime.now(timezone.utc)
    queues = {
        name: []
        for name in ("open_cases", "overdue_cases", "control_drafts", "policy_changes")
    }
    invalid_due_dates = 0
    with store.connect() as db:
        db.execute("BEGIN")
        size = 0
        for index, row in enumerate(
            db.execute(
                "SELECT id,kind,payload FROM records WHERE kind IN ('case','rule','policy_change') ORDER BY id"
            )
        ):
            size += len(row["payload"].encode())
            if index >= MAX_RECORDS or size > MAX_BYTES:
                raise ValueError("Complete digest exceeds pilot capacity")
            value = json.loads(row["payload"])
            if not isinstance(value, dict):
                raise ValueError("Invalid workspace record")
            item = {"id": row["id"], "title": str(value.get("title", row["id"]))[:240]}
            if row["kind"] == "case" and value.get("status") != "resolved":
                due = timestamp(value.get("due_at"))
                if value.get("due_at") and due is None:
                    invalid_due_dates += 1
                item["due_at"] = due.isoformat() if due else None
                queues["open_cases"].append(item)
                if due and due < generated:
                    queues["overdue_cases"].append(item)
            elif row["kind"] == "rule" and value.get("status") == "draft":
                queues["control_drafts"].append(item)
            elif (
                row["kind"] == "policy_change"
                and value.get("status") == "pending_review"
            ):
                queues["policy_changes"].append(item)
        row = db.execute(
            "SELECT payload FROM records WHERE kind='preferences' ORDER BY updated_at DESC,id LIMIT 1"
        ).fetchone()
        selected = json.loads(row[0])["enabled_sources"] if row else list(SOURCES)
        if (
            not isinstance(selected, list)
            or not selected
            or any(s not in SOURCES for s in selected)
        ):
            raise ValueError("Invalid enabled sources")
        sources = []
        for source in SOURCES:
            if source not in selected:
                continue
            row = db.execute(
                "SELECT json_remove(payload,'$.entries') FROM sources WHERE id=?",
                (source,),
            ).fetchone()
            data = json.loads(row[0]) if row else None
            if data is not None and not isinstance(data, dict):
                raise ValueError("Invalid source metadata")
            sources.append(
                {
                    "id": source,
                    "name": SOURCES[source]["name"],
                    "status": source_freshness(
                        data, settings.sanctions_max_age_hours, generated
                    ),
                    "fetched_at": data.get("fetched_at") if data else None,
                }
            )
        since = (generated - timedelta(hours=24)).isoformat()
        recent_alerts = db.execute(
            "SELECT count(*) FROM alerts WHERE julianday(created_at)>=julianday(?) AND julianday(created_at)<=julianday(?)",
            (since, generated.isoformat()),
        ).fetchone()[0]
        failed_runs = db.execute(
            "SELECT count(*) FROM jobs WHERE state='failed' AND julianday(updated_at)>=julianday(?) AND julianday(updated_at)<=julianday(?)",
            (since, generated.isoformat()),
        ).fetchone()[0]
    for name in ("open_cases", "overdue_cases"):
        queues[name].sort(key=lambda item: (item["due_at"] or "9999", item["id"]))
    return {
        "generated_at": generated.isoformat(),
        "window_start": since,
        "queues": {
            name: {
                "count": len(items),
                "items": items[:PREVIEW],
                "has_more": len(items) > PREVIEW,
            }
            for name, items in queues.items()
        },
        "sources": sources,
        "source_warnings": sum(s["status"] != "ready" for s in sources),
        "recent_alerts": recent_alerts,
        "failed_runs": failed_runs,
        "invalid_due_dates": invalid_due_dates,
        "model_calls": 0,
        "scope": "Current workspace snapshot; up to 20 items per queue. Alert and failed-run counts cover the preceding 24 hours. Source age measures retrieval time, not completeness or clearance. Refresh to detect changes; no email or background notification is sent.",
    }

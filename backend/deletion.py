"""Bounded customer deletion inventory. Planning only; never deletes rows/files."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

from pydantic import Field

from models import Input
from operations import canonical
from providers import problem
from retention import active_policy, blocking_holds, get, records

MAX_ROWS = 5000
MAX_BYTES = 16_000_000
MAX_REFERENCE_WORK = 500_000_000
TABLES = (
    "records",
    "transactions",
    "alerts",
    "jobs",
    "job_steps",
    "decisions",
    "reviews",
    "webhook_events",
    "events",
    "policies",
    "policy_versions",
    "chunks",
)
SYSTEM_TABLES = {
    "sources",
    "audit_chain",
    "sqlite_sequence",
    "chunks_data",
    "chunks_idx",
    "chunks_content",
    "chunks_docsize",
    "chunks_config",
}
OWNED_KINDS = {
    "case",
    "case_note",
    "case_evidence",
    "task",
    "screening",
    "adapter_object",
}
GOVERNANCE_KINDS = {
    "retention_policy",
    "retention_hold",
    "deletion_request",
    "deletion_receipt",
    "retained_copy",
}
JSON_COLUMNS = {"payload", "result"}


class Preview(Input):
    customer_id: str = Field(min_length=1, max_length=100)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_inventory(db):
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if tables - set(TABLES) - SYSTEM_TABLES or set(TABLES) - tables:
        raise problem(
            422,
            "deletion_schema_unknown",
            "The workspace has storage the deletion planner does not recognize. No partial inventory was produced.",
        )
    inventory, total = {}, 0
    for table in TABLES:
        rows = []
        for row in db.execute(f"SELECT rowid AS _rowid,* FROM {table} ORDER BY rowid"):
            if len(rows) >= MAX_ROWS:
                raise problem(
                    422,
                    "deletion_capacity",
                    "Deletion inventory exceeds its row bound; no partial plan was produced.",
                )
            raw = dict(row)
            total += len(canonical(raw).encode())
            if total > MAX_BYTES:
                raise problem(
                    422,
                    "deletion_capacity",
                    "Deletion inventory exceeds its byte bound; no partial plan was produced.",
                )
            value = {}
            for key in JSON_COLUMNS & raw.keys():
                try:
                    decoded = json.loads(raw[key])
                except (ValueError, TypeError) as exc:
                    raise problem(
                        422,
                        "deletion_invalid_record",
                        "A stored record cannot be inventoried safely.",
                    ) from exc
                if not isinstance(decoded, dict):
                    raise problem(
                        422,
                        "deletion_invalid_record",
                        "A stored record is not an object.",
                    )
                value.update(decoded)
            rows.append({"raw": raw, "value": value, "sha256": digest(raw)})
        inventory[table] = rows
    return inventory


def references(raw, tokens):
    # Conservative discovery, never an ownership rule. Text mentions create
    # residual-review blockers rather than permission to delete unrelated rows.
    text = canonical(raw).casefold()
    return any(token.casefold() in text for token in tokens if token)


def timestamp(value):
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            raise ValueError("Naive date")
        return stamp.astimezone(timezone.utc)
    except (ValueError, TypeError) as exc:
        raise problem(
            422,
            "deletion_invalid_timestamp",
            "A retention timestamp is missing, naive or invalid; eligibility cannot be inferred.",
        ) from exc


def summary(table, item, category):
    raw = item["raw"]
    return {
        "table": table,
        "kind": raw.get("kind", table),
        "record_id": str(
            raw.get(
                "id",
                raw.get(
                    "job_id",
                    raw.get("policy_id", raw.get("integration_id", raw["_rowid"])),
                ),
            )
        ),
        "rowid": raw["_rowid"],
        "sha256": item["sha256"],
        "category": category,
    }


def plan(db, workspace_id, customer_id, *, current=None):
    """Caller owns the read/write transaction for snapshot-consistent planning."""
    current = current or datetime.now(timezone.utc)
    customer = get(db, "customer", customer_id)
    inventory = read_inventory(db)
    policy = active_policy(db)
    cases = {
        row["raw"]["id"]
        for row in inventory["records"]
        if row["raw"]["kind"] == "case"
        and row["value"].get("customer_id") == customer_id
    }
    transactions = {
        row["raw"]["id"]
        for row in inventory["transactions"]
        if row["raw"]["customer_id"] == customer_id
    }
    jobs = {
        row["raw"]["id"]
        for row in inventory["jobs"]
        if row["raw"]["target_id"] in {customer_id, *cases}
    }
    decisions = {
        row["raw"]["id"]
        for row in inventory["decisions"]
        if row["value"].get("customer_id") == customer_id
    }
    selected = []
    for table, rows in inventory.items():
        for item in rows:
            raw, value = item["raw"], item["value"]
            owned = False
            if table == "records":
                kind = raw["kind"]
                owned = (kind == "customer" and raw["id"] == customer_id) or (
                    kind in OWNED_KINDS
                    and (
                        value.get("customer_id") == customer_id
                        or value.get("case_id") in cases
                        or value.get("local_case_id") in cases
                    )
                )
            elif table == "transactions":
                owned = raw["id"] in transactions
            elif table == "alerts":
                owned = raw["case_id"] in cases
            elif table == "jobs":
                owned = raw["id"] in jobs
            elif table == "job_steps":
                owned = raw["job_id"] in jobs
            elif table == "decisions":
                owned = raw["id"] in decisions
            elif table == "reviews":
                owned = raw["decision_id"] in decisions
            if owned:
                selected.append((table, item))
    tokens = {
        customer_id,
        customer.get("name", ""),
        customer.get("external_id", ""),
        *cases,
        *transactions,
        *jobs,
        *decisions,
    }
    for table, item in selected:
        if item["raw"].get("id"):
            tokens.add(item["raw"]["id"])
        if table == "transactions":
            tokens.add(item["raw"]["external_id"])
    selected_keys = {(table, item["raw"]["_rowid"]) for table, item in selected}
    estimated_work = len(tokens) * sum(
        len(canonical(item["raw"])) for rows in inventory.values() for item in rows
    )
    if estimated_work > MAX_REFERENCE_WORK:
        raise problem(
            422,
            "deletion_capacity",
            "Reference discovery exceeds the pilot work bound; no partial inventory was produced.",
        )
    residual = []
    retained_governance = []
    for table, rows in inventory.items():
        for item in rows:
            if (table, item["raw"]["_rowid"]) in selected_keys:
                continue
            if table == "records" and item["raw"]["kind"] in (
                "deletion_request",
                "deletion_receipt",
            ):
                # Workflow metadata cannot invalidate its own business inventory.
                # Requests are retained/audited separately, never deletion targets.
                continue
            if references(item["raw"], tokens):
                governance = (
                    table == "records" and item["raw"]["kind"] in GOVERNANCE_KINDS
                )
                (retained_governance if governance else residual).append(
                    summary(
                        table,
                        item,
                        "retained_governance" if governance else "unresolved_reference",
                    )
                )
    blockers = []

    def block(code, record_id=None):
        blockers.append(
            {"code": code, **({"record_id": record_id} if record_id else {})}
        )

    if not policy:
        block("approved_retention_policy_required")
    holds = blocking_holds(db, customer_id, cases)
    for hold in holds:
        block("legal_hold", hold["id"])
    for table, item in selected:
        raw, value = item["raw"], item["value"]
        record_id = raw.get("id", raw.get("job_id"))
        if value.get("customer_id") and value["customer_id"] != customer_id:
            block("inconsistent_customer_reference", record_id)
        if value.get("case_id") and value["case_id"] not in cases:
            block("inconsistent_case_reference", record_id)
        if (
            table == "records"
            and raw["kind"] == "case"
            and value.get("status") != "resolved"
        ):
            block("open_case", record_id)
        if (
            table == "records"
            and raw["kind"] == "case"
            and value.get("status") == "resolved"
            and not value.get("resolved_at")
        ):
            block("resolved_case_timestamp_missing", record_id)
        if (
            table == "records"
            and raw["kind"] == "task"
            and value.get("status") != "completed"
        ):
            block("open_task", record_id)
        if table == "jobs" and raw["state"] not in ("completed", "cancelled"):
            block("nonterminal_agent_run", record_id)
    # Every selected record gets a baseline age check, including notes, screening,
    # steps and imported objects. Recent changes reset its own retention clock.
    eligible_at = None
    if policy:
        for table, item in selected:
            raw, value = item["raw"], item["value"]
            dates = [
                raw[key]
                for key in ("created_at", "updated_at", "received_at", "occurred_at")
                if raw.get(key)
            ]
            dates += [
                value[key]
                for key in (
                    "created_at",
                    "updated_at",
                    "resolved_at",
                    "completed_at",
                    "imported_at",
                )
                if value.get(key)
            ]
            if not dates:
                block("retention_timestamp_missing", str(raw["_rowid"]))
                continue
            days = (
                policy["terminal_job_days"]
                if table in ("jobs", "job_steps")
                else policy["resolved_case_days"]
                if table == "records"
                and raw["kind"] in ("case", "case_note", "case_evidence", "task")
                else policy["customer_days"]
            )
            try:
                cutoff = max(timestamp(date) for date in dates) + timedelta(days=days)
            except OverflowError as exc:
                raise problem(
                    422,
                    "deletion_invalid_timestamp",
                    "A retention deadline exceeds the supported date range.",
                ) from exc
            eligible_at = max(eligible_at, cutoff) if eligible_at else cutoff
        if eligible_at and eligible_at > current:
            block("retention_period_not_elapsed")
    if residual:
        block("unresolved_shared_or_text_references")
    # External copies and physical compaction are deliberately not represented as
    # completed by a logical row inventory. The offline executor requires a
    # separate approved request and acknowledged discovery evidence.
    block("external_copy_reconciliation_required")
    external_copies = [
        copy
        for copy in records(db, "retained_copy")
        if copy["scope"] == "workspace"
        or copy.get("customer_id") == customer_id
        or (copy["scope"] == "case" and copy["target_id"] in cases)
    ]
    for copy in external_copies:
        if copy["status"] != "removal_confirmed":
            block("registered_copy_outstanding", copy["id"])
    audit_info = db.execute(
        "SELECT count(*),coalesce(max(seq),0) FROM audit_chain"
    ).fetchone()
    candidates = [
        summary(table, item, "operational_candidate") for table, item in selected
    ]
    binding = {
        "schema": "policylens.deletion-plan.v1",
        "workspace_id": workspace_id,
        "customer_id": customer_id,
        "policy_id": policy["id"] if policy else None,
        "policy_sha256": policy["configuration_sha256"] if policy else None,
        "candidates": candidates,
        "unresolved_references": residual,
        "retained_governance": retained_governance,
        "blocking_holds": holds,
        "external_copies": [
            {
                "id": copy["id"],
                "scope": copy["scope"],
                "category": copy["category"],
                "status": copy["status"],
                "sha256": digest(copy),
            }
            for copy in external_copies
        ],
        "eligible_at": eligible_at.isoformat() if eligible_at else None,
    }
    return {
        **binding,
        "inventory_sha256": digest(binding),
        "generated_at": current.isoformat(),
        "blockers": blockers,
        "execution_available": False,
        "retained_audit": {
            "events": audit_info[0],
            "head_sequence": audit_info[1],
            "scope": "Full immutable audit chain remains retained and may contain customer names or supplied text. Logical deletion cannot claim erasure of this history.",
        },
        "excluded_scope": [
            "Identity/account databases",
            "Public source feed snapshots",
            "External checkpoints",
            "Database free pages and WAL",
            "Backups, exports, plaintext originals and downstream copies",
        ],
        "limits": "Structured ownership determines candidates. Text/ID mentions only flag unresolved retained references; they never authorize deleting shared records. External copies and physical erasure are not verified. No data was deleted.",
    }


def preview(store, workspace_id, customer_id):
    with store.connect() as db:
        db.execute("BEGIN")
        return plan(db, workspace_id, customer_id)

import csv
import difflib
import hashlib
import hmac
import io
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from contextlib import closing

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from agents import AgentEngine, CATALOG
from auth import digest
from operations import Operations, audit, canonical, uid
from product_models import (
    AgentControl,
    AgentStart,
    CaseAction,
    CaseInput,
    CustomerInput,
    ImpactAction,
    IntegrationInput,
    MonitorTransaction,
    RuleAction,
    RuleInput,
    WorkspacePreferences,
)
from providers import problem
from store import now
from database import INTEGRITY_ERRORS, connect_database, descriptor
from retained_copies import (
    register_generated,
    reserve_generated,
    finish_generated,
    fail_generated,
)
from recovery import checksum, integrity as verify_database_integrity

router = APIRouter(prefix="/api")


def roles(request, *allowed):
    if request.state.user["role"] not in allowed:
        raise problem(403, "role_required", "Your role does not allow this action.")


@router.get("/preferences")
def preferences(request: Request):
    return request.state.ops.preferences()


@router.put("/preferences")
def update_preferences(data: WorkspacePreferences, request: Request):
    roles(request, "admin")
    prior = request.state.ops.preferences()
    value = {
        **data.model_dump(),
        "next_monitor_at": prior.get("next_monitor_at", now()),
    }
    return request.state.ops.save(
        "preferences", value, request.state.user["id"], prior.get("id")
    )


@router.get("/customers")
def customers(request: Request):
    return request.state.ops.list("customer", 2000)


@router.post("/customers", status_code=201)
def add_customer(data: CustomerInput, request: Request):
    try:
        return request.state.ops.save_customer(data, request.state.user["id"])
    except INTEGRITY_ERRORS as exc:
        raise problem(
            409, "duplicate_customer", "That customer reference already exists."
        ) from exc


@router.get("/customers/{customer_id}")
def customer(customer_id: str, request: Request):
    ops = request.state.ops
    value = ops.get("customer", customer_id)
    return {
        **value,
        "transactions": ops.customer_transactions(customer_id),
        "cases": [c for c in ops.list("case", 2000) if c["customer_id"] == customer_id],
        "screenings": [
            s for s in ops.list("screening", 2000) if s["customer_id"] == customer_id
        ][:10],
        "company_intelligence": [
            s
            for s in ops.list("company_intelligence", 2000)
            if s["customer_id"] == customer_id
        ][:1],
    }


@router.put("/customers/{customer_id}")
def update_customer(customer_id: str, data: CustomerInput, request: Request):
    try:
        return request.state.ops.save_customer(
            data, request.state.user["id"], customer_id
        )
    except INTEGRITY_ERRORS as exc:
        raise problem(
            409, "duplicate_customer", "That customer reference already exists."
        ) from exc


@router.post("/customers/{customer_id}/screen")
async def screen_customer(customer_id: str, request: Request):
    customer = request.state.ops.get("customer", customer_id)
    result = await run_in_threadpool(
        request.state.providers.screen_names, {"customer": customer["name"]}
    )
    saved = request.state.ops.save(
        "screening",
        {"customer_id": customer_id, "screening": result},
        request.state.user["id"],
    )
    if result["matches"]:
        case = request.state.ops.new_case(
            CaseInput(
                customer_id=customer_id,
                title="Potential sanctions match: " + customer["name"],
                priority="high",
                description="Potential name match found during screening. Verify identifiers before deciding.",
            ),
            request.state.user["id"],
        )
        request.state.ops.save(
            "case_evidence",
            {"case_id": case["id"], "screening": result},
            request.state.user["id"],
        )
    return saved


@router.post("/customers/{customer_id}/company-intelligence")
async def company_intelligence(customer_id: str, request: Request):
    customer = request.state.ops.get("customer", customer_id)
    if not customer["lei"]:
        raise problem(
            409,
            "lei_required",
            "Add the company LEI before looking up its public GLEIF record.",
        )
    result = await request.state.providers.gleif(customer["lei"])
    return request.state.ops.save(
        "company_intelligence",
        {"customer_id": customer_id, "data": result},
        request.state.user["id"],
    )


@router.get("/customers/{customer_id}/graph")
def relationship_graph(customer_id: str, request: Request):
    customer = request.state.ops.get("customer", customer_id)
    txns = request.state.ops.customer_transactions(customer_id, 100)
    nodes = [
        {
            "id": customer_id,
            "name": customer["name"],
            "kind": "customer",
            "country": customer["country"],
        }
    ]
    seen = {customer_id}
    links = []
    for txn in txns:
        other = (
            "party:"
            + digest(
                txn["counterparty"].casefold() + ":" + txn["counterparty_country"]
            )[:16]
        )
        if other not in seen:
            nodes.append(
                {
                    "id": other,
                    "name": txn["counterparty"],
                    "country": txn["counterparty_country"],
                    "kind": "counterparty",
                }
            )
            seen.add(other)
        links.append(
            {
                "source": customer_id,
                "target": other,
                "transaction_id": txn["id"],
                "label": txn["currency"] + " " + txn["amount"],
                "kind": "transaction",
            }
        )
        if txn["account_reference"]:
            account = "account:" + digest(txn["account_reference"])[:16]
            if account not in seen:
                nodes.append(
                    {
                        "id": account,
                        "name": txn["account_reference"],
                        "kind": "account_reference",
                    }
                )
                seen.add(account)
            links.append(
                {
                    "source": other,
                    "target": account,
                    "transaction_id": txn["id"],
                    "label": "Supplied reference",
                    "kind": "account",
                }
            )
    return {
        "nodes": nodes,
        "links": links,
        "transactions_sampled": len(txns),
        "scope": "Latest 100 customer transactions. Names and supplied account references are observed links, not verified identities or evidence of wrongdoing.",
    }


@router.get("/monitor/transactions")
def monitor_transactions(request: Request, limit: int = Query(200, ge=1, le=1000)):
    return request.state.ops.customer_transactions(limit=limit)


@router.post("/monitor/transactions", status_code=201)
def ingest(data: MonitorTransaction, request: Request):
    return request.state.ops.ingest(data, request.state.user["id"])


@router.get("/monitor/template")
def csv_template():
    fields = [
        "external_id",
        "customer_id",
        "amount",
        "currency",
        "counterparty",
        "counterparty_country",
        "account_reference",
        "description",
        "occurred_at",
    ]
    return Response(
        ",".join(fields) + "\n",
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="policylens-transactions.csv"'
        },
    )


@router.post("/monitor/import")
async def import_csv(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read(1_000_001)
        if len(content) > 1_000_000:
            raise problem(413, "import_too_large", "CSV imports are limited to 1 MB.")
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
        if not rows or len(rows) > 500:
            raise problem(422, "invalid_csv", "Import between 1 and 500 rows per file.")
        validated = []
        errors = []
        for i, row in enumerate(rows, 2):
            try:
                cleaned = {k: v for k, v in row.items() if v != ""}
                txn = MonitorTransaction.model_validate(cleaned)
                request.state.ops.get("customer", txn.customer_id)
                validated.append(txn)
            except (ValidationError, HTTPException):
                errors.append(
                    {
                        "row": i,
                        "message": "Invalid transaction fields or customer ID. Use the CSV template and ISO country codes.",
                    }
                )
        if errors:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": {
                        "code": "invalid_csv_rows",
                        "message": "No rows were imported. Fix the listed rows and retry.",
                        "rows": errors[:50],
                    }
                },
            )
        results = []
        for i, txn in enumerate(validated, 2):
            try:
                results.append(
                    {
                        "row": i,
                        **request.state.ops.ingest(txn, request.state.user["id"]),
                    }
                )
            except HTTPException as exc:
                # Explicit partial results; imports can be safely replayed using external IDs.
                errors.append({"row": i, "message": exc.detail["message"]})
        return {
            "imported": sum(not r["duplicate"] for r in results),
            "duplicates": sum(r["duplicate"] for r in results),
            "errors": errors,
            "results": results,
            "partial": bool(errors),
        }
    except UnicodeDecodeError as exc:
        raise problem(422, "invalid_csv_encoding", "Use a UTF-8 CSV file.") from exc
    finally:
        await file.close()


@router.get("/cases")
def cases(request: Request):
    ops = request.state.ops
    records = ops.list("case", 2000)
    alerts = ops.case_alerts()
    return [
        {**c, "alert_count": sum(a["case_id"] == c["id"] for a in alerts)}
        for c in records
    ]


@router.post("/cases", status_code=201)
def create_case(data: CaseInput, request: Request):
    return request.state.ops.new_case(data, request.state.user["id"])


def case_pack(case_id, request):
    ops = request.state.ops
    case = ops.get("case", case_id)
    return {
        **case,
        "customer": ops.get("customer", case["customer_id"]),
        "alerts": ops.case_alerts(case_id),
        "transactions": ops.customer_transactions(case["customer_id"], 200),
        "notes": [n for n in ops.list("case_note", 5000) if n["case_id"] == case_id],
        "tasks": [n for n in ops.list("task", 5000) if n.get("case_id") == case_id],
        "screening_evidence": [
            n for n in ops.list("case_evidence", 2000) if n["case_id"] == case_id
        ],
        "agent_runs": AgentEngine.list(request.state.store, case_id),
        "exported_at": now(),
        "audit_checkpoint": ops.verify_audit(),
    }


@router.get("/cases/{case_id}")
def case_detail(case_id: str, request: Request):
    return case_pack(case_id, request)


@router.post("/cases/{case_id}/actions")
def case_action(case_id: str, data: CaseAction, request: Request):
    team = request.app.state.hub.team(request.state.user["org_id"])
    ids = {u["id"] for u in team if u["role"] in ("admin", "analyst", "reviewer")}
    return request.state.ops.case_action(case_id, data, request.state.user, ids)


@router.get("/cases/{case_id}/export")
def case_export(case_id: str, request: Request):
    report = case_pack(case_id, request)
    response = JSONResponse(
        report,
        headers={
            "Content-Disposition": f'attachment; filename="policylens-case-{report["id"]}.json"'
        },
    )
    custody = register_generated(
        request.state.store,
        request.state.user,
        response.body,
        category="evidence_export",
        scope="customer",
        target_id=report["customer_id"],
        location_reference="case-pack-download:" + case_id,
    )
    response.headers["X-PolicyLens-Custody-ID"] = custody["id"]
    return response


@router.get("/tasks")
def tasks(request: Request):
    return request.state.ops.list("task", 2000)


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, request: Request):
    task = request.state.ops.get("task", task_id)
    if task["status"] != "open":
        raise problem(409, "task_complete", "Task is already complete.")
    return request.state.ops.save(
        "task",
        {
            **task,
            "status": "completed",
            "completed_by": request.state.user["id"],
            "completed_at": now(),
        },
        request.state.user["id"],
        task_id,
    )


@router.get("/rules")
def rules(request: Request):
    return request.state.ops.list("rule", 1000)


@router.post("/rules", status_code=201)
def create_rule(data: RuleInput, request: Request):
    roles(request, "admin", "analyst")
    return request.state.ops.save_rule(data, request.state.user)


@router.get("/rules/{rule_id}")
def rule_detail(rule_id: str, request: Request):
    return request.state.ops.get("rule", rule_id)


@router.put("/rules/{rule_id}", status_code=201)
def update_rule(rule_id: str, data: RuleInput, request: Request):
    roles(request, "admin", "analyst")
    return request.state.ops.save_rule(data, request.state.user, rule_id)


@router.post("/rules/{rule_id}/actions")
def rule_action(rule_id: str, data: RuleAction, request: Request):
    roles(request, "admin", "reviewer")
    return request.state.ops.rule_action(rule_id, data, request.state.user)


@router.post("/rules/{rule_id}/backtest")
def backtest(rule_id: str, request: Request):
    result = request.state.ops.backtest(rule_id)
    request.state.ops.save("backtest", result, request.state.user["id"])
    return result


@router.get("/policy-changes")
def policy_changes(request: Request):
    return request.state.ops.list("policy_change", 1000)


@router.get("/policy-changes/{change_id}")
def change_detail(change_id: str, request: Request):
    ops = request.state.ops
    change = ops.get("policy_change", change_id)
    versions = ops.policy_versions(change["policy_id"])
    old = next((v for v in versions if v["version"] == change["old_version"]), None)
    new = next((v for v in versions if v["version"] == change["new_version"]), None)
    if not old or not new:
        raise problem(
            409, "version_missing", "A required archived policy version is missing."
        )
    linked = [
        r for r in ops.list("rule", 1000) if r["policy_id"] == change["policy_id"]
    ]
    return {
        **change,
        "diff": "\n".join(
            difflib.unified_diff(
                old["content"].splitlines(),
                new["content"].splitlines(),
                fromfile=old["version"],
                tofile=new["version"],
            )
        ),
        "linked_rules": linked,
        "candidate_customers": ops.list("customer", 2000),
        "scope": "Workspace customers are candidates for impact review; affected status must be determined by a human.",
    }


@router.post("/policy-changes/{change_id}/actions")
def change_action(change_id: str, data: ImpactAction, request: Request):
    roles(request, "admin", "reviewer")
    with request.state.store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT payload FROM records WHERE kind='policy_change' AND id=?",
            (change_id,),
        ).fetchone()
        if not row:
            raise problem(404, "not_found", "Policy change not found.")
        change = json.loads(row[0])
        if change["status"] != "pending_review":
            raise problem(
                409, "already_reviewed", "This policy change has already been reviewed."
            )
        change.update(
            status="approved" if data.action == "approve" else "dismissed",
            reviewed_by=request.state.user["id"],
            reviewed_at=now(),
            review_notes=data.notes,
        )
        task_count = 0
        if data.action == "approve":
            candidates = db.execute(
                "SELECT payload FROM records WHERE kind='customer' LIMIT 2001"
            ).fetchall()
            if len(candidates) > 2000:
                raise problem(
                    422,
                    "impact_capacity",
                    "Review populations above 2,000 customers in smaller groups.",
                )
            for candidate in candidates:
                customer = json.loads(candidate[0])
                task = {
                    "id": uid(),
                    "customer_id": customer["id"],
                    "policy_change_id": change_id,
                    "title": "Assess applicability of "
                    + change["title"]
                    + " "
                    + change["new_version"]
                    + " to "
                    + customer["name"],
                    "status": "open",
                    "created_at": now(),
                    "created_by": request.state.user["id"],
                    "due_at": (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    ).isoformat(),
                }
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?)",
                    ("task", task["id"], now(), now(), canonical(task)),
                )
                task_count += 1
        change["review_tasks_created"] = task_count
        change["updated_at"] = now()
        db.execute(
            "UPDATE records SET payload=?,updated_at=? WHERE id=?",
            (canonical(change), now(), change_id),
        )
        audit(
            db,
            request.state.user["id"],
            "policy_change_" + data.action,
            {"id": change_id, "review_tasks_created": task_count, "notes": data.notes},
        )
    return change


@router.get("/agents/catalog")
def agent_catalog(request: Request):
    return {
        "agents": CATALOG,
        "daily_run_budget": request.app.state.settings.agent_daily_runs,
        "approval_policy": "Agents prepare evidence and drafts. Humans approve control activation and final case decisions.",
    }


@router.get("/agents/jobs")
def agent_jobs(request: Request):
    return AgentEngine.list(request.state.store)


@router.post("/agents/jobs", status_code=202)
def start_agent(data: AgentStart, request: Request):
    roles(request, "admin", "analyst", "reviewer")
    return request.app.state.engine.enqueue(
        request.state.store, data.kind, data.target_id, request.state.user["id"]
    )


@router.get("/agents/jobs/{job_id}")
def agent_job(job_id: str, request: Request):
    return AgentEngine.get(request.state.store, job_id)


@router.post("/agents/jobs/{job_id}/control")
def control_agent(job_id: str, data: AgentControl, request: Request):
    roles(request, "admin", "analyst", "reviewer")
    return request.app.state.engine.control(
        request.state.store, job_id, data.action, request.state.user["id"]
    )


@router.get("/analytics")
def analytics(request: Request):
    return request.state.ops.analytics()


@router.get("/audit")
def audit_log(request: Request):
    return {
        "verification": request.state.ops.verify_audit(),
        "events": request.state.ops.audit_events(300),
    }


@router.get("/audit/export")
def audit_export(request: Request):
    response = JSONResponse(
        audit_log(request),
        headers={
            "Content-Disposition": 'attachment; filename="policylens-audit-checkpoint.json"'
        },
    )
    custody = register_generated(
        request.state.store,
        request.state.user,
        response.body,
        category="audit_checkpoint",
        location_reference="legacy-audit-download",
    )
    response.headers["X-PolicyLens-Custody-ID"] = custody["id"]
    return response


@router.post("/backups", status_code=201)
def backup(request: Request):
    roles(request, "admin")
    directory = request.state.store.path.parent / "backups"
    directory.mkdir(exist_ok=True)
    backup_id = uid()
    path = directory / (backup_id + ".db")
    custody = reserve_generated(
        request.state.store,
        request.state.user,
        category="backup",
        location_reference="workspace-backup:" + backup_id,
        storage_root=str(request.state.store.path.parent.resolve()),
    )
    try:
        with (
            closing(
                connect_database(
                    request.state.store.path, request.app.state.settings, readonly=True
                )
            ) as source,
            closing(connect_database(path, request.app.state.settings)) as target,
        ):
            source.backup(target)
        verify_database_integrity(path, request.app.state.settings)
        integrity = "ok"
        custody = finish_generated(
            request.state.store,
            custody["id"],
            request.state.user,
            checksum(path),
            path.stat().st_size,
        )
    except Exception:
        fail_generated(request.state.store, custody["id"], request.state.user)
        raise
    saved = request.state.ops.save(
        "backup",
        {
            "id": backup_id,
            "file": path.name,
            "created_by": request.state.user["id"],
            "integrity": integrity,
            "database_encryption": descriptor(request.app.state.settings),
            "custody_id": custody["id"],
        },
        request.state.user["id"],
        backup_id,
    )
    return {**saved, "download_url": "/api/backups/" + backup_id}


@router.get("/backups/{backup_id}")
def download_backup(backup_id: str, request: Request):
    roles(request, "admin")
    backup = request.state.ops.get("backup", backup_id)
    path = request.state.store.path.parent / "backups" / backup["file"]
    custody = reserve_generated(
        request.state.store,
        request.state.user,
        category="backup",
        location_reference="workspace-backup-download:" + backup_id,
        storage_root=str(request.state.store.path.parent.resolve()),
    )
    # File artifacts are hashed as a stream, avoiding an additional database-sized
    # in-memory copy. This fresh custody entry represents the requested download.
    try:
        content_hash = checksum(path)
        if backup.get("custody_id"):
            original = request.state.ops.get("retained_copy", backup["custody_id"])
            if (
                original.get("generation_status")
                not in ("complete", "reconciled_present")
                or original["content_sha256"] != content_hash
            ):
                raise problem(
                    409,
                    "backup_changed",
                    "The backup no longer matches its generated custody record.",
                )
        custody = finish_generated(
            request.state.store,
            custody["id"],
            request.state.user,
            content_hash,
            path.stat().st_size,
        )
    except Exception:
        fail_generated(request.state.store, custody["id"], request.state.user)
        raise
    return FileResponse(
        path,
        media_type="application/vnd.sqlite3",
        filename="policylens-workspace-" + backup_id + ".db",
        headers={"X-PolicyLens-Custody-ID": custody["id"]},
    )


@router.get("/integrations")
def integrations(request: Request):
    roles(request, "admin")
    return [
        {k: v for k, v in r.items() if k != "secret"}
        for r in request.state.ops.list("integration")
    ]


@router.post("/integrations", status_code=201)
def create_integration(data: IntegrationInput, request: Request):
    roles(request, "admin")
    secret = secrets.token_hex(32)
    saved = request.state.ops.save(
        "integration",
        {"name": data.name, "secret": secret, "active": True},
        request.state.user["id"],
    )
    return {k: v for k, v in saved.items() if k != "secret"} | {
        "secret": secret,
        "webhook_path": f"/api/webhooks/{request.state.user['org_id']}/{saved['id']}",
    }


@router.post("/integrations/{integration_id}/revoke")
def revoke_integration(integration_id: str, request: Request):
    roles(request, "admin")
    data = request.state.ops.get("integration", integration_id)
    data["active"] = False
    saved = request.state.ops.save(
        "integration", data, request.state.user["id"], integration_id
    )
    return {k: v for k, v in saved.items() if k != "secret"}


@router.post("/webhooks/{org_id}/{integration_id}", status_code=202)
async def signed_ingestion(org_id: str, integration_id: str, request: Request):
    try:
        store = request.app.state.hub.store(org_id)
        ops = Operations(store)
        integration = ops.get("integration", integration_id)
    except HTTPException as exc:
        raise problem(
            403, "signature_invalid", "Invalid webhook authentication."
        ) from exc
    timestamp = request.headers.get("x-policylens-timestamp", "")
    signature = request.headers.get("x-policylens-signature", "")
    event_id = request.headers.get("x-policylens-event-id", "")
    if (
        not timestamp.isdigit()
        or abs(time.time() - int(timestamp)) > 300
        or not integration["active"]
    ):
        raise problem(
            403, "signature_invalid", "Invalid or expired webhook authentication."
        )
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 100_000:
            raise problem(
                413, "webhook_too_large", "Webhook bodies are limited to 100 KB."
            )
    body = bytes(content)
    expected = (
        "sha256="
        + hmac.new(
            integration["secret"].encode(),
            timestamp.encode() + b"." + body,
            hashlib.sha256,
        ).hexdigest()
    )
    if (
        not hmac.compare_digest(signature.encode(), expected.encode())
        or not 1 <= len(event_id) <= 100
    ):
        raise problem(
            403, "signature_invalid", "Invalid webhook signature or event identifier."
        )
    try:
        data = MonitorTransaction.model_validate_json(body)
    except ValidationError as exc:
        raise problem(
            422,
            "invalid_transaction",
            "Invalid transaction payload. Use the monitoring transaction schema.",
        ) from exc
    return ops.ingest(
        data,
        "integration:" + integration_id,
        integration_id=integration_id,
        event_id=event_id,
        payload_hash=hashlib.sha256(body).hexdigest(),
    )

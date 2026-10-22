"""Governed tools expose evidence and drafts, never final decisions."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from agent_keys import KeyCreate
from agents import AgentEngine
from operations import audit, uid
from privacy import pseudonymize
from product_api import case_pack
from providers import problem, verify_citations
from security import SecretBox
from store import now
from tool_contracts import TOOLS, catalog

router = APIRouter(prefix="/api")


def admin(request):
    if request.state.user["role"] != "admin":
        raise problem(
            403, "admin_required", "Only an administrator can manage agent keys."
        )


@router.get("/agent-tools")
def registry(request: Request):
    return {
        "tools": catalog(),
        "decision_boundary": "No approval, activation, closure or filing tools exist.",
    }


@router.get("/agent-keys")
def keys(request: Request):
    admin(request)
    return request.app.state.hub.agent_keys.list(request.state.user["org_id"])


@router.post("/agent-keys", status_code=201)
def create_key(data: KeyCreate, request: Request):
    admin(request)
    return request.app.state.hub.agent_keys.create(request.state.user, data)


@router.post("/agent-keys/{key_id}/revoke")
def revoke_key(key_id: str, request: Request):
    admin(request)
    return request.app.state.hub.agent_keys.revoke(request.state.user, key_id)


def principal(request):
    user = request.state.user
    if not user or not user.get("agent_key"):
        raise problem(
            401, "agent_key_required", "Use a scoped agent key for toolkit calls."
        )
    return user


def event(request, name, outcome, code=None):
    user = request.state.user
    with request.state.store.connect() as db:
        audit(
            db,
            user["id"],
            "tool_" + outcome,
            {
                "tool": name[:100],
                "key_id": user["agent_key"],
                "error_code": code,
                "model": user["policy"]["model"],
                "model_revision": user["policy"]["model_revision"],
            },
        )


@router.get("/toolkit/tools")
def tools(request: Request):
    user = principal(request)
    event(request, "list_tools", "completed")
    return {"tools": catalog(user["policy"]["scopes"])}


@router.post("/toolkit/call/{name}")
def invoke(name: str, arguments: dict, request: Request):
    user = principal(request)
    try:
        if name not in TOOLS or name not in user["policy"]["scopes"]:
            raise problem(
                403,
                "tool_scope_denied",
                "This tool is unavailable or outside this agent's scope.",
            )
        schema = TOOLS[name][1]
        try:
            data = schema.model_validate(arguments)
        except ValidationError as exc:
            # Pydantic input echoes may contain private evidence; expose only paths and messages.
            errors = [
                {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
                for error in exc.errors()
            ]
            raise problem(422, "invalid_tool_arguments", json.dumps(errors)) from exc
        event(request, name, "started")
        result = execute(name, data, request, user)
        if user["policy"]["pseudonymize"]:
            result = pseudonymize(
                result,
                SecretBox(request.app.state.settings).key(create=True),
                user["id"],
            )
        event(request, name, "completed")
        return result
    except HTTPException as exc:
        event(
            request,
            name,
            "denied" if exc.status_code in (401, 403, 429) else "failed",
            exc.detail.get("code") if isinstance(exc.detail, dict) else None,
        )
        raise
    except Exception:
        event(request, name, "failed", "internal_error")
        raise


def execute(name, data, request, user):
    ops, store = request.state.ops, request.state.store
    engine = request.app.state.engine
    if name == "search_policy":
        return {"excerpts": store.search(data.query, data.topic)}
    if name == "get_control":
        control = ops.get("rule", data.control_id)
        with store.connect() as db:
            history = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM audit_chain WHERE json_extract(data,'$.id')=? ORDER BY seq",
                    (data.control_id,),
                )
            ]
        return {"control": control, "approval_history": history}
    if name == "simulate_control":
        result = ops.backtest(data.control_id)
        saved = ops.save("backtest", result, user["id"])
        return {"simulation": saved, "activated": False, "live_alerts_created": False}
    if name == "list_alerts":
        with store.connect() as db:
            rows = db.execute(
                "SELECT payload FROM alerts WHERE (? IS NULL OR case_id=?) ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
                (data.case_id, data.case_id, data.limit + 1, data.offset),
            ).fetchall()
        return {
            "alerts": [json.loads(row[0]) for row in rows[: data.limit]],
            "has_more": len(rows) > data.limit,
            "offset": data.offset,
        }
    if name in ("get_case_context", "export_case_pack"):
        return case_pack(data.case_id, request)
    if name in ("draft_investigation_brief", "run_playbook"):
        kind = "investigation" if name == "draft_investigation_brief" else data.kind
        target = data.case_id if name == "draft_investigation_brief" else data.target_id
        return engine.enqueue(
            store,
            kind,
            target,
            user["id"],
            agent_policy={**user["policy"], "key_id": user["agent_key"]},
        )
    if name in ("get_agent_run", "control_agent_run", "verify_evidence"):
        job = AgentEngine.get(store, data.run_id)
        if name == "get_agent_run":
            return job
        if name == "control_agent_run":
            if job["actor"] != user["id"]:
                raise problem(
                    403, "run_owner_required", "Agents can control only their own runs."
                )
            return engine.control(store, data.run_id, data.action, user["id"])
        context = next(
            (
                step["output"]
                for step in job["steps"]
                if step["step"] == "collect_evidence"
            ),
            None,
        )
        if not context:
            raise problem(
                409,
                "evidence_not_collected",
                "This run has no collected policy evidence yet.",
            )
        if user["policy"]["pseudonymize"]:
            context = pseudonymize(
                context,
                SecretBox(request.app.state.settings).key(create=True),
                user["id"],
            )
        citations = verify_citations(
            {"citations": [citation.model_dump() for citation in data.citations]},
            context["policies"],
        )
        return {
            "valid": True,
            "citations": citations,
            "scope": "Quotation grounding only; this does not certify conclusions.",
        }
    if name == "create_review_task":
        ops.get("case", data.case_id)
        task = {
            "id": uid(),
            "case_id": data.case_id,
            "title": data.instructions,
            "status": "open",
            "requires_approval": True,
            "created_by": user["id"],
            "created_at": now(),
            "due_at": None,
        }
        return ops.save(
            "task",
            task,
            user["id"],
            record_id=task["id"],
            action="agent_review_requested",
        )
    # Registry and dispatcher must evolve together; do not accept arbitrary methods.
    raise problem(403, "tool_scope_denied", "This tool is not executable.")

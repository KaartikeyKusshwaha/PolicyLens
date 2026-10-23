from database import DB_ERRORS

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from providers import problem
from checkpoints import AuditBundleLimit
from retained_copies import register_generated

router = APIRouter(prefix="/api/audit/checkpoints")


@router.get("")
def checkpoint_status(request: Request):
    return request.app.state.checkpoints.status(request.state.user["org_id"])


@router.get("/export")
def checkpoint_export(request: Request):
    manager = request.app.state.checkpoints
    org_id = request.state.user["org_id"]
    try:
        result = manager.capture(org_id, include_events=True)
    except AuditBundleLimit as exc:
        raise problem(
            413,
            "audit_bundle_too_large",
            "The complete audit bundle exceeds the export bound. Automatic checkpoint retention remains separate from this download limit.",
        ) from exc
    except (ValueError, RuntimeError, OSError, *DB_ERRORS) as exc:
        manager.errors[org_id] = "checkpoint_capture_failed"
        raise problem(
            409,
            "checkpoint_unavailable",
            "A signed audit bundle could not be retained and verified. Check checkpoint configuration, key availability and database history; no unsigned substitute was generated.",
        ) from exc
    response = JSONResponse(
        result,
        headers={
            "Content-Disposition": 'attachment; filename="policylens-signed-audit.json"'
        },
    )
    custody = register_generated(
        request.state.store,
        request.state.user,
        response.body,
        category="audit_checkpoint",
        location_reference="signed-audit-download",
    )
    response.headers["X-PolicyLens-Custody-ID"] = custody["id"]
    return response

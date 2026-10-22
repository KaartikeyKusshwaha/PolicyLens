from database import DB_ERRORS

from fastapi import APIRouter, Request
from fastapi.responses import Response

from checkpoints import AuditBundleLimit
from evidence import EvidenceLimit, export_pack
from providers import problem
from operations import audit
from retained_copies import register_generated

router = APIRouter(prefix="/api/evidence")


@router.get("/sponsor-pack")
def sponsor_pack(request: Request):
    with request.state.store.connect() as db:
        audit(db, request.state.user["id"], "sponsor_evidence_requested", {})
    try:
        result = export_pack(
            request.app.state.checkpoints, request.state.user["org_id"]
        )
    except (AuditBundleLimit, EvidenceLimit) as exc:
        raise problem(
            413,
            "evidence_pack_too_large",
            "The complete workspace evidence exceeds the pilot export bound. No partial pack was generated.",
        ) from exc
    except (ValueError, RuntimeError, OSError, *DB_ERRORS) as exc:
        raise problem(
            409,
            "evidence_pack_unavailable",
            "A signed evidence pack could not be generated. Check external checkpoint storage, signing key and audit integrity. No unsigned substitute was generated.",
        ) from exc
    custody = register_generated(
        request.state.store,
        request.state.user,
        result,
        category="evidence_export",
        location_reference="sponsor-pack-download",
    )
    return Response(
        result,
        media_type="application/zip",
        headers={
            "X-PolicyLens-Custody-ID": custody["id"],
            "Content-Disposition": 'attachment; filename="policylens-sponsor-evidence.zip"',
        },
    )

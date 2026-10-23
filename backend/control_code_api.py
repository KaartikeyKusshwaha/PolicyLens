from fastapi import APIRouter, Request, Query
from fastapi.responses import Response

from control_code import (
    CodeRequest,
    ImportRequest,
    export_controls,
    preview,
    import_controls,
)
from providers import problem

router = APIRouter(prefix="/api/control-code")


def author(request):
    if request.state.user["role"] not in ("admin", "analyst"):
        raise problem(
            403,
            "role_required",
            "Only control authors can import configuration drafts.",
        )


@router.get("/export")
def export_yaml(
    request: Request, control_id: str | None = Query(default=None, max_length=100)
):
    text = export_controls(
        request.state.store, request.state.user["org_id"], control_id
    )
    return Response(
        text,
        media_type="application/yaml",
        headers={
            "Content-Disposition": 'attachment; filename="policylens-controls.yaml"'
        },
    )


@router.post("/preview")
def preview_yaml(data: CodeRequest, request: Request):
    author(request)
    return preview(request.state.store, request.state.user["org_id"], data)


@router.post("/import", status_code=201)
def import_yaml(data: ImportRequest, request: Request):
    author(request)
    return import_controls(
        request.state.store, request.state.user["org_id"], data, request.state.user
    )

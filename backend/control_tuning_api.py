from fastapi import APIRouter, Request

from control_tuning import DraftInput, TuningInput, detail, draft, preview
from providers import problem

router = APIRouter(prefix="/api/control-tuning")


def author(request):
    if request.state.user["role"] not in ("admin", "analyst"):
        raise problem(
            403, "role_required", "Only control authors can prepare tuning proposals."
        )


@router.post("/preview")
def simulate(data: TuningInput, request: Request):
    author(request)
    return preview(request.state.store, data)


@router.post("/draft", status_code=201)
def propose(data: DraftInput, request: Request):
    author(request)
    return draft(request.state.store, data, request.state.user)


@router.get("/{receipt_id}")
def inspect(receipt_id: str, request: Request):
    return detail(request.state.store, receipt_id)

from fastapi import APIRouter, Request
from pydantic import Field

from models import Input
from providers import problem
from traceability import read_matrix, map_control

router = APIRouter(prefix="/api/traceability")


class MappingInput(Input):
    control_id: str = Field(min_length=1, max_length=100)
    linked: bool = True
    notes: str = Field(min_length=10, max_length=2000)


@router.get("")
def traceability(request: Request):
    return read_matrix(request.state.store)


@router.put("/obligations/{obligation_id}/links")
def update_link(obligation_id: str, data: MappingInput, request: Request):
    if request.state.user["role"] not in ("admin", "analyst", "reviewer"):
        raise problem(
            403, "role_required", "Your role cannot change obligation mappings."
        )
    return map_control(
        request.state.store, obligation_id, data, request.state.user["id"]
    )

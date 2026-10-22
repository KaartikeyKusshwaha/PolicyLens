from fastapi import APIRouter, Request

import retention
from providers import problem

router = APIRouter(prefix="/api/retention")


def require(request, *roles):
    if request.state.user["role"] not in roles:
        raise problem(
            403, "role_required", "Your role cannot perform this retention action."
        )


@router.get("")
def overview(request: Request):
    require(request, "admin", "reviewer", "auditor")
    return retention.state(request.state.store)


@router.post("/policies", status_code=201)
def policy(data: retention.RetentionPolicy, request: Request):
    require(request, "admin")
    return retention.draft_policy(request.state.store, data, request.state.user)


@router.post("/policies/{record_id}/approve")
def approve_policy(record_id: str, data: retention.Review, request: Request):
    require(request, "admin", "reviewer")
    return retention.approve_policy(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/holds", status_code=201)
def hold(data: retention.HoldInput, request: Request):
    require(request, "admin", "reviewer")
    return retention.place_hold(request.state.store, data, request.state.user)


@router.post("/holds/{record_id}/request-release")
def request_release(record_id: str, data: retention.Review, request: Request):
    require(request, "admin", "reviewer")
    return retention.request_release(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/holds/{record_id}/approve-release")
def release(record_id: str, data: retention.Review, request: Request):
    require(request, "admin", "reviewer")
    return retention.approve_release(
        request.state.store, record_id, data, request.state.user
    )

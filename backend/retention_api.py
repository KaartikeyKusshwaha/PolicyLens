from fastapi import APIRouter, Query, Request

import retention
import deletion
import retained_copies
from providers import problem

router = APIRouter(prefix="/api/retention")


@router.post("/copies", status_code=201)
def register_copy(data: retained_copies.CopyInput, request: Request):
    require(request, "admin", "reviewer")
    return retained_copies.register(request.state.store, data, request.state.user)


@router.post("/copies/{record_id}/request-removal")
def request_copy_removal(
    record_id: str, data: retained_copies.CopyReview, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.request_removal(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/copies/{record_id}/approve-removal")
def approve_copy_removal(
    record_id: str, data: retained_copies.CopyReview, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.approve_removal(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/copies/{record_id}/report-removal")
def report_copy_removal(
    record_id: str, data: retained_copies.RemovalReport, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.report_removal(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/copies/{record_id}/confirm-removal")
def confirm_copy_removal(
    record_id: str, data: retained_copies.CopyReview, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.confirm_removal(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/copies/{record_id}/cancel-removal")
def cancel_copy_removal(
    record_id: str, data: retained_copies.CopyReview, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.cancel_removal(
        request.state.store, record_id, data, request.state.user
    )


@router.post("/copies/{record_id}/review-reported-removal")
def review_reported_copy_removal(
    record_id: str, data: retained_copies.CopyReview, request: Request
):
    require(request, "admin", "reviewer")
    return retained_copies.review_reported_removal(
        request.state.store, record_id, data, request.state.user
    )


def require(request, *roles):
    if request.state.user["role"] not in roles:
        raise problem(
            403, "role_required", "Your role cannot perform this retention action."
        )


@router.get("")
def overview(request: Request):
    require(request, "admin", "reviewer", "auditor")
    return retention.state(request.state.store)


@router.post("/deletion-preview")
def deletion_preview(data: deletion.Preview, request: Request):
    require(request, "admin", "reviewer")
    return deletion.preview(
        request.state.store, request.state.user["org_id"], data.customer_id
    )


@router.get("/deletion-preview")
def read_deletion_preview(
    request: Request, customer_id: str = Query(min_length=1, max_length=100)
):
    require(request, "admin", "reviewer", "auditor")
    return deletion.preview(
        request.state.store, request.state.user["org_id"], customer_id
    )


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

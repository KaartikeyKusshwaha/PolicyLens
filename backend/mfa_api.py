"""MFA endpoints require an authenticated cookie, CSRF and password reauthentication."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import Field

from models import Input
from operations import audit

router = APIRouter(prefix="/api/auth/mfa")


class Proof(Input):
    # Password whitespace is meaningful, just as in the sign-in schema.
    model_config = {"str_strip_whitespace": False, "extra": "forbid"}
    password: str = Field(min_length=12, max_length=128)
    code: str = Field(default="", max_length=64)


@router.get("")
def status(request: Request):
    return request.app.state.hub.mfa.status(request.state.user["id"])


@router.post("/enroll")
def enroll(data: Proof, request: Request):
    return request.app.state.hub.mfa.begin(request.state.user["id"], data.password)


def complete(request, data, action):
    user = request.state.user
    hub = request.app.state.hub
    if action == "enable":
        result = hub.mfa.finish(user["id"], data.password, data.code)
    else:
        result = hub.mfa.change(user["id"], data.password, data.code, action)
    with request.state.store.connect() as db:
        audit(db, user["id"], "account_mfa_" + action, {"sessions_revoked": True})
    response = JSONResponse({})
    result["user"] = request.app.state.set_session(response, user["id"], user["org_id"])
    response.body = JSONResponse(result).body
    response.headers["content-length"] = str(len(response.body))
    return response


@router.post("/confirm")
def confirm(data: Proof, request: Request):
    return complete(request, data, "enable")


@router.post("/recovery-codes")
def recovery(data: Proof, request: Request):
    return complete(request, data, "recovery_codes_rotated")


@router.post("/disable")
def disable(data: Proof, request: Request):
    return complete(request, data, "disable")

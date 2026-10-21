from fastapi import APIRouter, Request
from pydantic import ConfigDict, Field

from auth import digest, password_hash, password_matches
from models import Input
from operations import audit
from providers import problem

router = APIRouter(prefix="/api")


class MemberAccess(Input):
    role: str = Field(pattern=r"^(admin|analyst|reviewer|auditor|revoked)$")


class PasswordChange(Input):
    model_config = ConfigDict(str_strip_whitespace=False, extra="forbid")
    current_password: str = Field(min_length=12, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


@router.post("/team/{user_id}/access")
def access(user_id: str, data: MemberAccess, request: Request):
    user = request.state.user
    if user["role"] != "admin":
        raise problem(
            403, "admin_required", "Only an administrator can change team access."
        )
    hub = request.app.state.hub
    with hub.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT role FROM memberships WHERE user_id=? AND org_id=?",
            (user_id, user["org_id"]),
        ).fetchone()
        if not prior:
            raise problem(404, "member_not_found", "Workspace member not found.")
        if prior["role"] == "admin" and data.role != "admin":
            count = db.execute(
                "SELECT count(*) FROM memberships WHERE org_id=? AND role='admin'",
                (user["org_id"],),
            ).fetchone()[0]
            if count <= 1:
                raise problem(
                    409,
                    "last_admin",
                    "A workspace must retain at least one administrator.",
                )
        if data.role == "revoked":
            db.execute(
                "DELETE FROM memberships WHERE user_id=? AND org_id=?",
                (user_id, user["org_id"]),
            )
            db.execute(
                "DELETE FROM sessions WHERE user_id=? AND org_id=?",
                (user_id, user["org_id"]),
            )
        else:
            db.execute(
                "UPDATE memberships SET role=? WHERE user_id=? AND org_id=?",
                (data.role, user_id, user["org_id"]),
            )
    with request.state.store.connect() as db:
        audit(
            db,
            user["id"],
            "member_access_changed",
            {"member_id": user_id, "role": data.role},
        )
    return {"user_id": user_id, "role": data.role}


@router.post("/auth/password")
def change_password(data: PasswordChange, request: Request):
    hub = request.app.state.hub
    hub.throttle("password:" + request.state.user["id"])
    with hub.connect() as db:
        row = db.execute(
            "SELECT password FROM users WHERE id=?", (request.state.user["id"],)
        ).fetchone()
    if not row or not password_matches(data.current_password, row["password"]):
        raise problem(401, "invalid_credentials", "Current password is incorrect.")
    encoded = password_hash(data.new_password)
    with hub.connect() as db:
        db.execute(
            "UPDATE users SET password=? WHERE id=?",
            (encoded, request.state.user["id"]),
        )
        db.execute(
            "DELETE FROM sessions WHERE user_id=? AND id!=?",
            (request.state.user["id"], digest(request.cookies["policylens_session"])),
        )
        db.execute(
            "DELETE FROM password_resets WHERE user_id=?", (request.state.user["id"],)
        )
    with request.state.store.connect() as db:
        audit(
            db,
            request.state.user["id"],
            "password_changed",
            {"other_sessions_revoked": True},
        )
    return {"changed": True, "other_sessions_revoked": True}

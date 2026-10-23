"""Scoped agent identities are separate from human sessions and never become reviewers."""

import json
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import Field, field_validator

from auth import digest
from models import Input
from operations import audit
from providers import PROMPT_VERSION, problem
from security import SecretBox
from store import now
from tool_contracts import TOOLS


class KeyCreate(Input):
    model_config = {"str_strip_whitespace": False, "extra": "forbid"}
    name: str = Field(min_length=3, max_length=80)
    scopes: list[str] = Field(min_length=1, max_length=len(TOOLS))
    expires_days: int = Field(default=30, ge=1, le=90)
    requests_per_minute: int = Field(default=30, ge=1, le=120)
    daily_runs: int = Field(default=5, ge=0, le=100)
    pseudonymize: bool = True
    password: str = Field(min_length=12, max_length=128)
    second_factor: str = Field(default="", max_length=64)

    @field_validator("scopes")
    @classmethod
    def known_tools(cls, values):
        if len(values) != len(set(values)) or any(
            value not in TOOLS for value in values
        ):
            raise ValueError("Select unique tools from the governed registry.")
        return values

    @field_validator("name")
    @classmethod
    def useful_name(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Use a descriptive agent name.")
        return value.strip()


class AgentKeys:
    def __init__(self, hub):
        self.hub = hub
        with hub.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agent_keys(
                    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_by TEXT NOT NULL,
                    name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, payload TEXT NOT NULL,
                    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS agent_requests(key_id TEXT NOT NULL, stamp REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS agent_request_window ON agent_requests(key_id,stamp);
                CREATE TABLE IF NOT EXISTS agent_access_events(
                    id INTEGER PRIMARY KEY, key_id TEXT, action TEXT NOT NULL, at TEXT NOT NULL);
            """)

    def create(self, user, data):
        self.hub.throttle("agent-key-create:" + user["id"])
        key_id = str(uuid.uuid4())
        token = "pl_agent_" + key_id + "_" + secrets.token_urlsafe(32)
        settings = self.hub.settings
        payload = {
            "scopes": data.scopes,
            "requests_per_minute": data.requests_per_minute,
            "daily_runs": data.daily_runs,
            "pseudonymize": data.pseudonymize,
            "model": settings.groq_model,
            "model_revision": settings.groq_model_revision,
            "prompt_version": PROMPT_VERSION,
        }
        expiry = (
            datetime.now(timezone.utc) + timedelta(days=data.expires_days)
        ).isoformat()
        with self.hub.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.hub.mfa.password(db, user["id"], data.password)
            self.hub.mfa.consume(db, user["id"], data.second_factor)
            if data.pseudonymize:
                SecretBox(settings).key(create=True)
            db.execute(
                "INSERT INTO agent_keys VALUES (?,?,?,?,?,?,?,?,0)",
                (
                    key_id,
                    user["org_id"],
                    user["id"],
                    data.name.strip(),
                    digest(token),
                    json.dumps(payload),
                    now(),
                    expiry,
                ),
            )
        with self.hub.store(user["org_id"]).connect() as db:
            audit(
                db,
                user["id"],
                "agent_key_created",
                {
                    "key_id": key_id,
                    "name": data.name.strip(),
                    **payload,
                    "expires_at": expiry,
                },
            )
        return {"id": key_id, "token": token, "expires_at": expiry, **payload}

    def list(self, org_id):
        with self.hub.connect() as db:
            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "created_by": row["created_by"],
                    "created_at": row["created_at"],
                    "expires_at": row["expires_at"],
                    "revoked": bool(row["revoked"]),
                    **json.loads(row["payload"]),
                }
                for row in db.execute(
                    "SELECT * FROM agent_keys WHERE org_id=? ORDER BY created_at DESC",
                    (org_id,),
                )
            ]

    def active(self, key_id):
        with self.hub.connect() as db:
            row = db.execute(
                """SELECT k.* FROM agent_keys k JOIN memberships m
                ON m.user_id=k.created_by AND m.org_id=k.org_id
                WHERE k.id=? AND k.revoked=0 AND k.expires_at>? AND m.role='admin'""",
                (key_id, now()),
            ).fetchone()
        return dict(row) if row else None

    def authenticate(self, token):
        if not token or len(token) > 160:
            with self.hub.connect() as db:
                db.execute(
                    "INSERT INTO agent_access_events(key_id,action,at) VALUES (NULL,'authentication_denied',?)",
                    (now(),),
                )
            raise problem(
                401, "agent_key_required", "A valid scoped agent key is required."
            )
        with self.hub.connect() as db:
            row = db.execute(
                "SELECT id FROM agent_keys WHERE token_hash=?", (digest(token),)
            ).fetchone()
        record = self.active(row["id"]) if row else None
        if not record:
            with self.hub.connect() as db:
                db.execute(
                    "INSERT INTO agent_access_events(key_id,action,at) VALUES (NULL,'authentication_denied',?)",
                    (now(),),
                )
            raise problem(
                401, "agent_key_required", "A valid scoped agent key is required."
            )
        policy = json.loads(record["payload"])
        stamp = time.time()
        with self.hub.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM agent_requests WHERE stamp<?", (stamp - 120,))
            count = db.execute(
                "SELECT count(*) FROM agent_requests WHERE key_id=? AND stamp>?",
                (record["id"], stamp - 60),
            ).fetchone()[0]
            limited = count >= policy["requests_per_minute"]
            if not limited:
                db.execute(
                    "INSERT INTO agent_requests VALUES (?,?)", (record["id"], stamp)
                )
            db.execute(
                "INSERT INTO agent_access_events(key_id,action,at) VALUES (?,?,?)",
                (record["id"], "rate_limited" if limited else "authenticated", now()),
            )
        if limited:
            raise problem(
                429,
                "agent_rate_limit",
                "This agent's request budget is exhausted; wait for the next minute.",
            )
        return {
            "id": "agent:" + record["id"],
            "key_issuer_id": record["created_by"],
            "org_id": record["org_id"],
            "role": "agent",
            "agent_key": record["id"],
            "name": record["name"],
            "policy": policy,
            "csrf": "",
        }

    def revoke(self, user, key_id):
        with self.hub.connect() as db:
            result = db.execute(
                "UPDATE agent_keys SET revoked=1 WHERE id=? AND org_id=?",
                (key_id, user["org_id"]),
            )
            if not result.rowcount:
                raise problem(404, "not_found", "Agent key not found.")
        store = self.hub.store(user["org_id"])
        with store.connect() as db:
            db.execute(
                "UPDATE jobs SET state='cancelled',updated_at=? WHERE actor=? AND state IN ('queued','running','paused')",
                (now(), "agent:" + key_id),
            )
            audit(db, user["id"], "agent_key_revoked", {"key_id": key_id})
        return {"revoked": True, "queued_runs_cancelled": True}

"""Account MFA lifecycle. All factor consumption happens under BEGIN IMMEDIATE."""

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from auth import digest, password_matches
from providers import problem
from security import SecretBox, matching_counter
from store import now


class AccountMFA:
    def __init__(self, hub):
        self.hub = hub
        self.box = SecretBox(hub.settings)
        with hub.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS account_mfa(
                    user_id TEXT PRIMARY KEY REFERENCES users(id), secret TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, expires_at TEXT,
                    last_counter INTEGER NOT NULL DEFAULT -1, recovery TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS security_events(
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    @staticmethod
    def record(db, user_id, action):
        db.execute(
            "INSERT INTO security_events(user_id,action,created_at) VALUES (?,?,?)",
            (user_id, action, now()),
        )

    @staticmethod
    def recovery_hash(user_id, code):
        return digest(user_id + ":" + code.replace("-", "").upper())

    def status(self, user_id):
        with self.hub.connect() as db:
            row = db.execute(
                "SELECT enabled,recovery FROM account_mfa WHERE user_id=?", (user_id,)
            ).fetchone()
        return {
            "enabled": bool(row and row["enabled"]),
            "recovery_codes_remaining": len(json.loads(row["recovery"]))
            if row and row["enabled"]
            else 0,
        }

    def password(self, db, user_id, password):
        user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or not password_matches(password, user["password"]):
            raise problem(
                401, "reauthentication_required", "Current password is incorrect."
            )
        return user

    def consume(self, db, user_id, code):
        row = db.execute(
            "SELECT * FROM account_mfa WHERE user_id=? AND enabled=1", (user_id,)
        ).fetchone()
        if not row:
            return
        secret = self.box.decrypt(row["secret"], "mfa:" + user_id)
        counter = matching_counter(secret, code, row["last_counter"])
        if counter is not None:
            db.execute(
                "UPDATE account_mfa SET last_counter=? WHERE user_id=?",
                (counter, user_id),
            )
            self.record(db, user_id, "mfa_totp_verified")
            return
        codes = json.loads(row["recovery"])
        hashed = self.recovery_hash(user_id, code)
        if hashed in codes:
            codes.remove(hashed)
            db.execute(
                "UPDATE account_mfa SET recovery=? WHERE user_id=?",
                (json.dumps(codes), user_id),
            )
            self.record(db, user_id, "mfa_recovery_used")
            return
        raise problem(
            401,
            "second_factor_required",
            "Enter a fresh authenticator code or an unused recovery code.",
        )

    def begin(self, user_id, password):
        self.hub.throttle("mfa-manage:" + user_id)
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        with self.hub.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            user = self.password(db, user_id, password)
            if db.execute(
                "SELECT 1 FROM account_mfa WHERE user_id=? AND enabled=1", (user_id,)
            ).fetchone():
                raise problem(409, "mfa_enabled", "MFA is already enabled.")
            encrypted = self.box.encrypt(secret, "mfa:" + user_id)
            expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
            db.execute(
                "INSERT OR REPLACE INTO account_mfa(user_id,secret,expires_at) VALUES (?,?,?)",
                (user_id, encrypted, expires),
            )
            self.record(db, user_id, "mfa_enrollment_started")
        uri = "otpauth://totp/" + quote("PolicyLens:" + user["email"], safe="")
        uri += "?" + urlencode(
            {
                "secret": secret,
                "issuer": "PolicyLens",
                "algorithm": "SHA1",
                "digits": 6,
                "period": 30,
            }
        )
        return {"secret": secret, "provisioning_uri": uri, "expires_at": expires}

    def finish(self, user_id, password, code):
        self.hub.throttle("mfa-manage:" + user_id)
        codes = [secrets.token_hex(5) + "-" + secrets.token_hex(5) for _ in range(10)]
        with self.hub.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.password(db, user_id, password)
            row = db.execute(
                "SELECT * FROM account_mfa WHERE user_id=?", (user_id,)
            ).fetchone()
            if not row or row["enabled"] or row["expires_at"] <= now():
                raise problem(409, "enrollment_expired", "Start a new MFA enrollment.")
            secret = self.box.decrypt(row["secret"], "mfa:" + user_id)
            counter = matching_counter(secret, code)
            if counter is None:
                raise problem(
                    401,
                    "invalid_authenticator_code",
                    "Enter the current six-digit authenticator code.",
                )
            db.execute(
                "UPDATE account_mfa SET enabled=1,expires_at=NULL,last_counter=?,recovery=? WHERE user_id=?",
                (
                    counter,
                    json.dumps([self.recovery_hash(user_id, c) for c in codes]),
                    user_id,
                ),
            )
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            self.record(db, user_id, "mfa_enabled")
        return {"enabled": True, "recovery_codes": codes}

    def change(self, user_id, password, code, action):
        self.hub.throttle("mfa-manage:" + user_id)
        with self.hub.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.password(db, user_id, password)
            if not db.execute(
                "SELECT 1 FROM account_mfa WHERE user_id=? AND enabled=1", (user_id,)
            ).fetchone():
                raise problem(409, "mfa_not_enabled", "MFA is not enabled.")
            self.consume(db, user_id, code)
            if action == "disable":
                db.execute("DELETE FROM account_mfa WHERE user_id=?", (user_id,))
                result = {"enabled": False}
            else:
                codes = [
                    secrets.token_hex(5) + "-" + secrets.token_hex(5) for _ in range(10)
                ]
                db.execute(
                    "UPDATE account_mfa SET recovery=? WHERE user_id=?",
                    (
                        json.dumps([self.recovery_hash(user_id, c) for c in codes]),
                        user_id,
                    ),
                )
                result = {"enabled": True, "recovery_codes": codes}
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
            self.record(db, user_id, "mfa_" + action)
        return result

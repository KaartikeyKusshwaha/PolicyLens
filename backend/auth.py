"""Cookie sessions and workspace membership. Every workspace has its own SQLite file."""

import hashlib
import hmac
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ConfigDict, Field, field_validator

from models import Input
from providers import problem
from store import Store, now

ROLES = {"admin", "analyst", "reviewer", "auditor"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=32768,
        r=8,
        p=1,
        maxmem=128 * 1024 * 1024,
    )
    return salt + ":" + hashed.hex()


def password_matches(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(":")[0]), encoded)


class Credentials(Input):
    model_config = ConfigDict(str_strip_whitespace=False, extra="forbid")
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class Setup(Credentials):
    name: str = Field(min_length=2, max_length=100)
    workspace: str = Field(min_length=3, max_length=100)
    bootstrap_token: str = Field(min_length=20, max_length=100)


class Invite(Input):
    email: str = Field(min_length=5, max_length=254)
    role: str = Field(pattern=r"^(admin|analyst|reviewer|auditor)$")


class Join(Credentials):
    name: str = Field(min_length=2, max_length=100)
    token: str = Field(min_length=20, max_length=100)


class Hub:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.database_path.parent / "identity.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stores = {}
        self.dummy_password = password_hash("dummy-password-for-timing")
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS organizations(id TEXT PRIMARY KEY,name TEXT,db_path TEXT UNIQUE,created_at TEXT);
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,name TEXT,password TEXT,created_at TEXT);
                CREATE TABLE IF NOT EXISTS memberships(user_id TEXT REFERENCES users(id),org_id TEXT REFERENCES organizations(id),role TEXT,PRIMARY KEY(user_id,org_id));
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),org_id TEXT,csrf TEXT,expires_at TEXT);
                CREATE TABLE IF NOT EXISTS invites(id TEXT PRIMARY KEY,org_id TEXT,email TEXT,role TEXT,expires_at TEXT,used INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS login_attempts(key TEXT,stamp REAL);
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
            """)
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                token_file = self.path.parent / ".bootstrap-token"
                existing = db.execute(
                    "SELECT value FROM metadata WHERE key='bootstrap'"
                ).fetchone()
                if not existing:
                    token = secrets.token_urlsafe(32)
                    token_file.write_text(token, encoding="utf-8")
                    try:
                        token_file.chmod(0o600)
                    except OSError:
                        pass
                    db.execute(
                        "INSERT INTO metadata VALUES ('bootstrap',?)", (digest(token),)
                    )
                self.bootstrap_file = token_file

    def connect(self):
        # Store.connect provides commit/rollback and always closes the connection.
        return Store.connect(self)

    def needs_setup(self):
        with self.connect() as db:
            return not bool(db.execute("SELECT 1 FROM users LIMIT 1").fetchone())

    def setup(self, data):
        hashed = password_hash(data.password)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            expected = db.execute(
                "SELECT value FROM metadata WHERE key='bootstrap'"
            ).fetchone()
            if (
                db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
                or not expected
                or not hmac.compare_digest(expected[0], digest(data.bootstrap_token))
            ):
                raise problem(
                    403,
                    "setup_denied",
                    "Setup is complete or the local bootstrap key is incorrect.",
                )
            org_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
            db.execute(
                "INSERT INTO organizations VALUES (?,?,?,?)",
                (
                    org_id,
                    data.workspace,
                    str(self.settings.database_path.resolve()),
                    now(),
                ),
            )
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?,?)",
                (user_id, data.email, data.name, hashed, now()),
            )
            db.execute(
                "INSERT INTO memberships VALUES (?,?,?)", (user_id, org_id, "admin")
            )
            db.execute("DELETE FROM metadata WHERE key='bootstrap'")
        self.bootstrap_file.unlink(missing_ok=True)
        return user_id, org_id

    def throttle(self, key):
        key = digest(key)
        stamp = time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM login_attempts WHERE stamp<?", (stamp - 900,))
            count = db.execute(
                "SELECT count(*) FROM login_attempts WHERE key=?", (key,)
            ).fetchone()[0]
            if count >= 12:
                raise problem(
                    429,
                    "auth_rate_limit",
                    "Too many authentication attempts. Try again in 15 minutes.",
                )
            db.execute("INSERT INTO login_attempts VALUES (?,?)", (key, stamp))

    def login(self, data):
        with self.connect() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email=?", (data.email,)
            ).fetchone()
            # Equal work on unknown emails limits account enumeration by response timing.
            encoded = user["password"] if user else self.dummy_password
            valid = password_matches(data.password, encoded)
            if not user or not valid:
                raise problem(
                    401, "invalid_credentials", "Email or password is incorrect."
                )
            membership = db.execute(
                "SELECT org_id FROM memberships WHERE user_id=? ORDER BY org_id LIMIT 1",
                (user["id"],),
            ).fetchone()
            if not membership:
                raise problem(
                    403, "membership_required", "No active workspace membership."
                )
            return user["id"], membership[0]

    def session(self, user_id, org_id):
        token, csrf = secrets.token_urlsafe(40), secrets.token_urlsafe(32)
        expiry = (
            datetime.now(timezone.utc) + timedelta(hours=self.settings.session_hours)
        ).isoformat()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<?", (now(),))
            db.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (digest(token), user_id, org_id, csrf, expiry),
            )
        return token, self.authenticate(token)

    def authenticate(self, token):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute(
                """SELECT u.id,u.email,u.name,s.org_id,s.csrf,m.role,o.name AS workspace
                FROM sessions s JOIN users u ON u.id=s.user_id
                JOIN memberships m ON m.user_id=u.id AND m.org_id=s.org_id
                JOIN organizations o ON o.id=s.org_id WHERE s.id=? AND s.expires_at>?""",
                (digest(token), now()),
            ).fetchone()
        return dict(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (digest(token or ""),))

    def organizations(self, user_id=None):
        with self.connect() as db:
            if user_id:
                return [
                    dict(r)
                    for r in db.execute(
                        "SELECT o.id,o.name,m.role FROM organizations o JOIN memberships m ON m.org_id=o.id WHERE m.user_id=?",
                        (user_id,),
                    )
                ]
            return [dict(r) for r in db.execute("SELECT id,name FROM organizations")]

    def store(self, org_id):
        if org_id in self.stores and not self.stores[org_id].path.is_file():
            raise problem(
                503,
                "workspace_storage_missing",
                "Workspace storage is missing. Restore its database; no replacement database was created.",
            )
        if org_id not in self.stores:
            with self.connect() as db:
                row = db.execute(
                    "SELECT db_path FROM organizations WHERE id=?", (org_id,)
                ).fetchone()
            if not row:
                raise problem(404, "workspace_not_found", "Workspace not found.")
            from operations import Operations

            path = Path(row[0])
            if not path.is_file():
                raise problem(
                    503,
                    "workspace_storage_missing",
                    "Workspace storage is missing. Restore its database before restarting; no replacement database was created.",
                )
            store = Store(path)
            Operations(store)
            self.stores[org_id] = store
        return self.stores[org_id]

    def team(self, org_id):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT u.id,u.name,u.email,m.role FROM users u JOIN memberships m ON m.user_id=u.id WHERE m.org_id=? ORDER BY u.name",
                    (org_id,),
                )
            ]

    def invite(self, org_id, data):
        email = Credentials.validate_email(data.email)
        token = secrets.token_urlsafe(32)
        expiry = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
        with self.connect() as db:
            db.execute(
                "INSERT INTO invites(id,org_id,email,role,expires_at) VALUES (?,?,?,?,?)",
                (digest(token), org_id, email, data.role, expiry),
            )
        return {"token": token, "email": email, "role": data.role, "expires_at": expiry}

    def join(self, data):
        hashed = password_hash(data.password)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            invite = db.execute(
                "SELECT * FROM invites WHERE id=? AND used=0 AND expires_at>?",
                (digest(data.token), now()),
            ).fetchone()
            if not invite or invite["email"] != data.email:
                raise problem(
                    403,
                    "invalid_invite",
                    "Invitation is invalid, expired, or belongs to another email.",
                )
            user = db.execute(
                "SELECT * FROM users WHERE email=?", (data.email,)
            ).fetchone()
            if user:
                if not password_matches(data.password, user["password"]):
                    raise problem(
                        401,
                        "invalid_credentials",
                        "Use your existing account password to accept this invitation.",
                    )
                user_id = user["id"]
            else:
                user_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?)",
                    (user_id, data.email, data.name, hashed, now()),
                )
            db.execute(
                "INSERT OR IGNORE INTO memberships VALUES (?,?,?)",
                (user_id, invite["org_id"], invite["role"]),
            )
            db.execute("UPDATE invites SET used=1 WHERE id=?", (digest(data.token),))
        return user_id, invite["org_id"]

    def create_workspace(self, user_id, name):
        org_id = str(uuid.uuid4())
        path = self.path.parent / "workspaces" / (org_id + ".db")
        from operations import Operations

        Operations(Store(path))
        with self.connect() as db:
            db.execute(
                "INSERT INTO organizations VALUES (?,?,?,?)",
                (org_id, name, str(path.resolve()), now()),
            )
            db.execute(
                "INSERT INTO memberships VALUES (?,?,?)", (user_id, org_id, "admin")
            )
        return org_id

    def switch(self, token, user_id, org_id):
        with self.connect() as db:
            if not db.execute(
                "SELECT 1 FROM memberships WHERE user_id=? AND org_id=?",
                (user_id, org_id),
            ).fetchone():
                raise problem(
                    403, "workspace_forbidden", "You do not belong to this workspace."
                )
            db.execute(
                "UPDATE sessions SET org_id=? WHERE id=?", (org_id, digest(token))
            )

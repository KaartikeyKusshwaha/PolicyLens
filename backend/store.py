"""Durable local storage. FTS5/BM25 is the sole policy retrieval engine."""

import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from database import connect_database, driver


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path, settings=None):
        self.path = path
        self.settings = settings
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS policies (
                    id TEXT PRIMARY KEY, title TEXT, content TEXT, topic TEXT,
                    version TEXT, source_url TEXT, created_at TEXT, updated_at TEXT);
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                    chunk_id UNINDEXED, policy_id UNINDEXED, title, text,
                    tokenize='unicode61 remove_diacritics 2');
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY, transaction_id TEXT UNIQUE, created_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, decision_id TEXT REFERENCES decisions(id), created_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, fetched_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, created_at TEXT, kind TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS policy_versions(policy_id TEXT,version TEXT,created_at TEXT,payload TEXT,PRIMARY KEY(policy_id,version));
                CREATE TABLE IF NOT EXISTS records(kind TEXT,id TEXT PRIMARY KEY,created_at TEXT,updated_at TEXT,payload TEXT);
            """)

    @contextmanager
    def connect(self):
        settings = getattr(self, "settings", None)
        db = connect_database(self.path, settings)
        db.row_factory = driver(settings).Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def event(self, kind, payload):
        with self.connect() as db:
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?)",
                (str(uuid.uuid4()), now(), kind, json.dumps(payload)),
            )

    def save_policy(self, policy, policy_id=None):
        data = policy.model_dump()
        stamp = now()
        policy_id = policy_id or str(uuid.uuid4())
        words = data["content"].split()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT * FROM policies WHERE id=?", (policy_id,)
            ).fetchone()
            if old and old["version"] == data["version"]:
                raise ValueError("Use a new version when updating a policy.")
            if db.execute(
                "SELECT 1 FROM policy_versions WHERE policy_id=? AND version=?",
                (policy_id, data["version"]),
            ).fetchone():
                raise ValueError("A historical version number cannot be reused.")
            if old:
                # Checks approved for a prior policy version must stop on update.
                for row in db.execute(
                    "SELECT id,payload FROM records WHERE kind='rule' AND json_extract(payload,'$.policy_id')=? AND json_extract(payload,'$.status')='active'",
                    (policy_id,),
                ).fetchall():
                    control = json.loads(row[1])
                    control.update(status="disabled", updated_at=stamp)
                    db.execute(
                        "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                        (json.dumps(control), stamp, row[0]),
                    )
                db.execute(
                    "INSERT OR IGNORE INTO policy_versions VALUES (?,?,?,?)",
                    (
                        policy_id,
                        old["version"],
                        old["updated_at"],
                        json.dumps(dict(old)),
                    ),
                )
                change = {
                    "id": str(uuid.uuid4()),
                    "policy_id": policy_id,
                    "title": data["title"],
                    "old_version": old["version"],
                    "new_version": data["version"],
                    "status": "pending_review",
                    "created_at": stamp,
                    "updated_at": stamp,
                }
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?)",
                    ("policy_change", change["id"], stamp, stamp, json.dumps(change)),
                )
            db.execute(
                "INSERT INTO policy_versions VALUES (?,?,?,?)",
                (
                    policy_id,
                    data["version"],
                    stamp,
                    json.dumps({"id": policy_id, **data}),
                ),
            )
            db.execute(
                "INSERT OR REPLACE INTO policies VALUES (?,?,?,?,?,?,?,?)",
                (
                    policy_id,
                    data["title"],
                    data["content"],
                    data["topic"],
                    data["version"],
                    data["source_url"],
                    old["created_at"] if old else stamp,
                    stamp,
                ),
            )
            db.execute("DELETE FROM chunks WHERE policy_id=?", (policy_id,))
            for i, start in enumerate(range(0, len(words), 240)):
                db.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?)",
                    (
                        f"{policy_id}:{data['version']}:{i}",
                        policy_id,
                        data["title"],
                        " ".join(words[start : start + 300]),
                    ),
                )
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    stamp,
                    "policy_updated" if old else "policy_added",
                    json.dumps(
                        {
                            "policy_id": policy_id,
                            "title": data["title"],
                            "version": data["version"],
                        }
                    ),
                ),
            )
        return self.policy(policy_id)

    def policy(self, policy_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM policies WHERE id=?", (policy_id,)
            ).fetchone()
        return dict(row) if row else None

    def policies(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,title,topic,version,source_url,created_at,updated_at FROM policies WHERE NOT EXISTS (SELECT 1 FROM records WHERE kind='policy_archive' AND records.id=policies.id) ORDER BY updated_at DESC"
                )
            ]

    def search(self, query, topic=None):
        stop = {
            "the",
            "and",
            "for",
            "what",
            "how",
            "does",
            "this",
            "with",
            "from",
            "that",
            "are",
            "our",
            "can",
            "should",
        }
        tokens = list(
            dict.fromkeys(
                t.lower()
                for t in re.findall(r"[^\W_]{3,}", query)
                if t.lower() not in stop
            )
        )[:32]
        if not tokens:
            return []
        expression = " OR ".join('"' + t + '"' for t in tokens)
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    """
                SELECT c.chunk_id,c.policy_id,c.title,c.text,p.version,p.source_url,p.topic,
                       bm25(chunks,0,0,3,1) AS rank
                FROM chunks c JOIN policies p ON p.id=c.policy_id
                WHERE chunks MATCH ? AND (? IS NULL OR p.topic=?)
                  AND NOT EXISTS (SELECT 1 FROM records WHERE kind='policy_archive' AND records.id=p.id)
                ORDER BY rank LIMIT 8
            """,
                    (expression, topic, topic),
                )
            ]

    def source(self, source_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM sources WHERE id=?", (source_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_source(self, source_id, payload):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO sources VALUES (?,?,?)",
                (source_id, payload["fetched_at"], json.dumps(payload)),
            )

    def source_metadata(self, source_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT json_remove(payload,'$.entries') FROM sources WHERE id=?",
                (source_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def decision(self, decision_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM decisions WHERE id=?", (decision_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def has_transaction(self, transaction_id):
        with self.connect() as db:
            return (
                db.execute(
                    "SELECT 1 FROM decisions WHERE transaction_id=?", (transaction_id,)
                ).fetchone()
                is not None
            )

    def save_decision(self, payload):
        with self.connect() as db:
            db.execute(
                "INSERT INTO decisions VALUES (?,?,?,?)",
                (
                    payload["id"],
                    payload["transaction"]["transaction_id"],
                    payload["created_at"],
                    json.dumps(payload),
                ),
            )
            db.execute(
                "INSERT INTO events VALUES (?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    payload["created_at"],
                    "transaction_assessed",
                    json.dumps(
                        {
                            "transaction_id": payload["transaction"]["transaction_id"],
                            "verdict": payload["assessment"]["verdict"],
                        }
                    ),
                ),
            )

    def decisions(self, limit=50, offset=0):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM decisions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            ]

    def review(self, decision_id, data):
        payload = dict(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            created_at=now(),
            **data.model_dump(),
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO reviews VALUES (?,?,?,?)",
                (
                    payload["id"],
                    decision_id,
                    payload["created_at"],
                    json.dumps(payload),
                ),
            )
        return payload

    def reviews(self, decision_id=None):
        with self.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM reviews WHERE (? IS NULL OR decision_id=?) ORDER BY created_at DESC",
                    (decision_id, decision_id),
                )
            ]

    def dashboard(self):
        with self.connect() as db:
            total = db.execute("SELECT count(*) FROM decisions").fetchone()[0]
            flagged = db.execute(
                "SELECT count(*) FROM decisions WHERE json_extract(payload,'$.assessment.verdict')='flag'"
            ).fetchone()[0]
            pending = db.execute(
                "SELECT count(*) FROM decisions d WHERE NOT EXISTS (SELECT 1 FROM reviews r WHERE r.decision_id=d.id)"
            ).fetchone()[0]
            average = db.execute(
                "SELECT avg(json_extract(payload,'$.processing_time_ms')) FROM decisions"
            ).fetchone()[0]
            events = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM events ORDER BY created_at DESC LIMIT 8"
                )
            ]
            for event in events:
                event["payload"] = json.loads(event["payload"])
        return {
            "total": total,
            "flagged": flagged,
            "pending": pending,
            "average_ms": average,
            "events": events,
        }

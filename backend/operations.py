"""Typed product records, transactional monitoring, and a verifiable audit chain."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from providers import problem
from store import now


def uid():
    return str(uuid.uuid4())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def audit(db, actor, action, data):
    last = db.execute(
        "SELECT hash FROM audit_chain ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    previous = last[0] if last else "0" * 64
    stamp = now()
    payload = canonical(
        {
            "at": stamp,
            "actor": actor,
            "action": action,
            "data": data,
            "previous": previous,
        }
    )
    hashed = hashlib.sha256(payload.encode()).hexdigest()
    db.execute(
        "INSERT INTO audit_chain(at,actor,action,data,previous,hash) VALUES (?,?,?,?,?,?)",
        (stamp, actor, action, canonical(data), previous, hashed),
    )


class Operations:
    def __init__(self, store):
        self.store = store
        if getattr(store, "_operations_initialized", False):
            return
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS records(kind TEXT,id TEXT PRIMARY KEY,created_at TEXT,updated_at TEXT,payload TEXT);
                CREATE INDEX IF NOT EXISTS records_kind ON records(kind,updated_at);
                CREATE UNIQUE INDEX IF NOT EXISTS customer_external_id ON records(json_extract(payload,'$.external_id')) WHERE kind='customer';
                CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,external_id TEXT UNIQUE,customer_id TEXT,amount_minor INTEGER,currency TEXT,occurred_at TEXT,received_at TEXT,payload TEXT);
                CREATE INDEX IF NOT EXISTS transaction_window ON transactions(customer_id,currency,occurred_at);
                CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY,dedupe TEXT UNIQUE,case_id TEXT,created_at TEXT,payload TEXT);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT,target_id TEXT,state TEXT,created_at TEXT,updated_at TEXT,actor TEXT,payload TEXT);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(state,created_at);
                CREATE TABLE IF NOT EXISTS job_steps(job_id TEXT,step TEXT,created_at TEXT,payload TEXT,PRIMARY KEY(job_id,step));
                CREATE TABLE IF NOT EXISTS webhook_events(integration_id TEXT,event_id TEXT,payload_hash TEXT,result TEXT,PRIMARY KEY(integration_id,event_id));
                CREATE TABLE IF NOT EXISTS audit_chain(seq INTEGER PRIMARY KEY AUTOINCREMENT,at TEXT,actor TEXT,action TEXT,data TEXT,previous TEXT,hash TEXT);
                CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_chain BEGIN SELECT RAISE(ABORT,'Audit entries are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_chain BEGIN SELECT RAISE(ABORT,'Audit entries are immutable'); END;
                CREATE TABLE IF NOT EXISTS policy_versions(policy_id TEXT,version TEXT,created_at TEXT,payload TEXT,PRIMARY KEY(policy_id,version));
            """)
            db.execute(
                "INSERT OR IGNORE INTO policy_versions SELECT id,version,updated_at,json_object('id',id,'title',title,'content',content,'topic',topic,'version',version,'source_url',source_url) FROM policies"
            )

        store._operations_initialized = True

    def get(self, kind, record_id):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM records WHERE kind=? AND id=?", (kind, record_id)
            ).fetchone()
        if not row:
            raise problem(
                404, "not_found", f"{kind.replace('_', ' ').capitalize()} not found."
            )
        return json.loads(row[0])

    def list(self, kind, limit=200):
        with self.store.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM records WHERE kind=? ORDER BY updated_at DESC LIMIT ?",
                    (kind, limit),
                )
            ]

    def save(self, kind, data, actor, record_id=None, action=None):
        stamp = now()
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = (
                db.execute(
                    "SELECT created_at FROM records WHERE id=? AND kind=?",
                    (record_id, kind),
                ).fetchone()
                if record_id
                else None
            )
            record = {
                **data,
                "id": record_id or uid(),
                "created_at": old[0] if old else stamp,
                "updated_at": stamp,
            }
            db.execute(
                "INSERT OR REPLACE INTO records VALUES (?,?,?,?,?)",
                (kind, record["id"], record["created_at"], stamp, canonical(record)),
            )
            audit(
                db,
                actor,
                action or f"{kind}_saved",
                {
                    "id": record["id"],
                    "title": record.get("title", record.get("name", "")),
                },
            )
        return record

    def preferences(self):
        values = self.list("preferences", 1)
        return (
            values[0]
            if values
            else {
                "enabled_sources": ["ofac", "un", "uk"],
                "monitoring_enabled": False,
                "monitoring_interval_hours": 6,
            }
        )

    def save_customer(self, data, actor, customer_id=None):
        if customer_id:
            self.get("customer", customer_id)
        with self.store.connect() as db:
            duplicate = db.execute(
                "SELECT id FROM records WHERE kind='customer' AND json_extract(payload,'$.external_id')=? AND id!=?",
                (data.external_id, customer_id or ""),
            ).fetchone()
        if duplicate:
            raise problem(
                409, "duplicate_customer", "That customer reference already exists."
            )
        return self.save("customer", data.model_dump(), actor, customer_id)

    def customer_transactions(self, customer_id=None, limit=200):
        with self.store.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM transactions WHERE (? IS NULL OR customer_id=?) ORDER BY occurred_at DESC,id LIMIT ?",
                    (customer_id, customer_id, limit),
                )
            ]

    def transaction(self, transaction_id):
        with self.store.connect() as db:
            row = db.execute(
                "SELECT payload FROM transactions WHERE id=?", (transaction_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def _matches(self, db, rule, txn, customer):
        kind = rule["kind"]
        value = None
        if kind == "amount":
            value = (
                Decimal(txn["amount"]) if txn["currency"] == rule["currency"] else None
            )
            hit = value is not None and value >= Decimal(rule["threshold"])
        elif kind in ("velocity", "aggregate"):
            end = datetime.fromisoformat(txn["occurred_at"])
            start = (end - timedelta(hours=rule["window_hours"])).isoformat()
            rows = db.execute(
                "SELECT amount_minor FROM transactions WHERE customer_id=? AND occurred_at>=? AND occurred_at<=? AND (? OR currency=?)",
                (
                    txn["customer_id"],
                    start,
                    end.isoformat(),
                    kind == "velocity",
                    rule["currency"],
                ),
            ).fetchall()
            value = (
                Decimal(len(rows))
                if kind == "velocity"
                else sum((Decimal(r[0]) / 100 for r in rows), Decimal(0))
            )
            hit = value >= Decimal(rule["threshold"]) and (
                kind == "velocity" or txn["currency"] == rule["currency"]
            )
        elif kind == "corridor":
            value = txn["counterparty_country"]
            hit = value in rule["countries"] and value != customer["country"]
        else:
            value = customer["kyc_status"]
            hit = value != "verified"
        return bool(hit), {
            "kind": kind,
            "observed": str(value),
            "threshold": rule["threshold"],
            "currency": rule["currency"],
            "window_hours": rule["window_hours"],
            "destinations": rule["countries"],
        }

    def _open_case(self, db, customer, title, priority, description, actor):
        row = db.execute(
            "SELECT payload FROM records WHERE kind='case' AND json_extract(payload,'$.customer_id')=? AND json_extract(payload,'$.status')!='resolved' ORDER BY created_at LIMIT 1",
            (customer["id"],),
        ).fetchone()
        if row:
            existing = json.loads(row[0])
            order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            if order[priority] > order[existing["priority"]]:
                existing["priority"] = priority
                existing["updated_at"] = now()
                db.execute(
                    "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                    (canonical(existing), now(), existing["id"]),
                )
                audit(
                    db,
                    actor,
                    "case_priority_raised",
                    {"case_id": existing["id"], "priority": priority},
                )
            return existing
        stamp = now()
        case = {
            "id": uid(),
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "title": title,
            "priority": priority,
            "description": description,
            "status": "open",
            "assignee_id": "",
            "disposition": "",
            "created_by": actor,
            "created_at": stamp,
            "updated_at": stamp,
            "due_at": (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            ("case", case["id"], stamp, stamp, canonical(case)),
        )
        audit(
            db, actor, "case_opened", {"id": case["id"], "customer_id": customer["id"]}
        )
        return case

    def ingest(
        self, txn, actor, *, integration_id=None, event_id=None, payload_hash=None
    ):
        customer = self.get("customer", txn.customer_id)
        data = txn.model_dump(mode="json")
        data["occurred_at"] = txn.occurred_at.isoformat()
        data["amount"] = str(Decimal(data["amount"]).quantize(Decimal("0.01")))
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if integration_id:
                seen = db.execute(
                    "SELECT payload_hash,result FROM webhook_events WHERE integration_id=? AND event_id=?",
                    (integration_id, event_id),
                ).fetchone()
                if seen:
                    if seen[0] != payload_hash:
                        raise problem(
                            409,
                            "event_conflict",
                            "An event ID cannot be reused with another payload.",
                        )
                    return {**json.loads(seen[1]), "duplicate": True}
            existing = db.execute(
                "SELECT id,payload FROM transactions WHERE external_id=?",
                (data["external_id"],),
            ).fetchone()
            if existing:
                old = json.loads(existing[1])
                if any(
                    old.get(k) != v
                    for k, v in data.items()
                    if k != "occurred_at" or "occurred_at" in txn.model_fields_set
                ):
                    raise problem(
                        409,
                        "transaction_conflict",
                        "This transaction reference already exists with different details.",
                    )
                result = {"id": existing[0], "duplicate": True, "alerts": []}
                if integration_id:
                    db.execute(
                        "INSERT INTO webhook_events VALUES (?,?,?,?)",
                        (integration_id, event_id, payload_hash, canonical(result)),
                    )
                return result
            record = {**data, "id": uid(), "received_at": now()}
            db.execute(
                "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
                (
                    record["id"],
                    data["external_id"],
                    data["customer_id"],
                    int(Decimal(data["amount"]) * 100),
                    data["currency"],
                    data["occurred_at"],
                    record["received_at"],
                    canonical(record),
                ),
            )
            rules = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM records WHERE kind='rule' AND json_extract(payload,'$.status')='active'"
                )
            ]
            hits = []
            for rule in rules:
                candidates = [record]
                if rule["kind"] in ("velocity", "aggregate"):
                    end = (
                        txn.occurred_at + timedelta(hours=rule["window_hours"])
                    ).isoformat()
                    rows = db.execute(
                        "SELECT payload FROM transactions WHERE customer_id=? AND occurred_at>=? AND occurred_at<=? ORDER BY occurred_at LIMIT 1001",
                        (customer["id"], record["occurred_at"], end),
                    ).fetchall()
                    if len(rows) > 1000:
                        raise problem(
                            422,
                            "late_event_capacity",
                            "This event would require more than 1,000 subsequent transaction rechecks. Import a smaller chronological batch.",
                        )
                    candidates = [json.loads(row[0]) for row in rows]
                for candidate in candidates:
                    hit, facts = self._matches(db, rule, candidate, customer)
                    dedupe = (
                        rule["id"] + ":" + str(rule["version"]) + ":" + candidate["id"]
                    )
                    if (
                        not hit
                        or db.execute(
                            "SELECT 1 FROM alerts WHERE dedupe=?", (dedupe,)
                        ).fetchone()
                    ):
                        continue
                    case = self._open_case(
                        db,
                        customer,
                        f"Review activity for {customer['name']}",
                        rule["priority"],
                        "A configured internal control triggered. Review the evidence before deciding.",
                        actor,
                    )
                    alert = {
                        "id": uid(),
                        "case_id": case["id"],
                        "transaction_id": candidate["id"],
                        "rule_id": rule["id"],
                        "rule_title": rule["title"],
                        "rule_version": rule["version"],
                        "rule_snapshot": rule,
                        "facts": facts,
                        "created_at": now(),
                        "priority": rule["priority"],
                        "rechecked_after_late_event": candidate["id"] != record["id"],
                    }
                    db.execute(
                        "INSERT INTO alerts VALUES (?,?,?,?,?)",
                        (
                            alert["id"],
                            dedupe,
                            case["id"],
                            alert["created_at"],
                            canonical(alert),
                        ),
                    )
                    hits.append(alert)
                    audit(
                        db,
                        actor,
                        "control_triggered",
                        {
                            "alert_id": alert["id"],
                            "case_id": case["id"],
                            "rule_id": rule["id"],
                            "transaction_id": candidate["id"],
                        },
                    )
            audit(
                db,
                actor,
                "transaction_ingested",
                {
                    "id": record["id"],
                    "customer_id": customer["id"],
                    "alert_count": len(hits),
                },
            )
            result = {"id": record["id"], "duplicate": False, "alerts": hits}
            if integration_id:
                db.execute(
                    "INSERT INTO webhook_events VALUES (?,?,?,?)",
                    (integration_id, event_id, payload_hash, canonical(result)),
                )
            return result

    def case_alerts(self, case_id=None):
        with self.store.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM alerts WHERE (? IS NULL OR case_id=?) ORDER BY created_at DESC LIMIT 500",
                    (case_id, case_id),
                )
            ]

    def new_case(self, data, actor):
        customer = self.get("customer", data.customer_id)
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            return self._open_case(
                db, customer, data.title, data.priority, data.description, actor
            )

    def case_action(self, case_id, data, user, team_ids):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM records WHERE kind='case' AND id=?", (case_id,)
            ).fetchone()
            if not row:
                raise problem(404, "not_found", "Case not found.")
            case = json.loads(row[0])
            action = data.action
            if action == "assign":
                if data.assignee_id not in team_ids:
                    raise problem(
                        422,
                        "invalid_assignee",
                        "Choose an analyst or reviewer from this workspace.",
                    )
                case["assignee_id"] = data.assignee_id
            elif action == "resolve":
                if not case["assignee_id"]:
                    raise problem(
                        409,
                        "investigator_required",
                        "Assign an investigator before final review.",
                    )
                if (
                    user["role"] not in ("admin", "reviewer")
                    or user["id"] == case["assignee_id"]
                ):
                    raise problem(
                        403,
                        "independent_review_required",
                        "A reviewer other than the assigned investigator must resolve the case.",
                    )
                if data.disposition not in (
                    "confirmed",
                    "false_positive",
                    "insufficient_evidence",
                ):
                    raise problem(
                        422, "disposition_required", "Choose a documented disposition."
                    )
                case.update(
                    status="resolved",
                    disposition=data.disposition,
                    resolved_by=user["id"],
                    resolved_at=now(),
                )
            elif action in ("start", "escalate", "reopen"):
                if case["status"] == "resolved" and action != "reopen":
                    raise problem(
                        409,
                        "case_closed",
                        "Reopen the case before changing its workflow.",
                    )
                case["status"] = {
                    "start": "investigating",
                    "escalate": "escalated",
                    "reopen": "open",
                }[action]
                if action == "reopen":
                    case["disposition"] = ""
            elif action == "task":
                task = {
                    "id": uid(),
                    "case_id": case_id,
                    "title": data.notes,
                    "status": "open",
                    "created_by": user["id"],
                    "created_at": now(),
                    "due_at": data.due_at.isoformat() if data.due_at else None,
                }
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?)",
                    ("task", task["id"], now(), now(), canonical(task)),
                )
            note = {
                "id": uid(),
                "case_id": case_id,
                "action": action,
                "notes": data.notes,
                "author": user["name"],
                "author_id": user["id"],
                "created_at": now(),
            }
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?)",
                ("case_note", note["id"], now(), now(), canonical(note)),
            )
            case["updated_at"] = now()
            db.execute(
                "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                (canonical(case), case["updated_at"], case_id),
            )
            audit(
                db,
                user["id"],
                "case_" + action,
                {
                    "case_id": case_id,
                    "note_id": note["id"],
                    "disposition": data.disposition,
                },
            )
        return case

    def save_rule(self, data, user, rule_id=None):
        policy = self.store.policy(data.policy_id)
        if not policy:
            raise problem(
                422, "policy_required", "Choose a policy from this workspace."
            )
        old = self.get("rule", rule_id) if rule_id else None
        record = {
            **data.model_dump(mode="json"),
            "version": old["version"] + 1 if old else 1,
            "status": "draft",
            "created_by": user["id"],
            "policy_version": policy["version"],
            "policy_title": policy["title"],
            "replaces_id": old["id"] if old else None,
        }
        return self.save("rule", record, user["id"])

    def rule_action(self, rule_id, data, user):
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT payload FROM records WHERE kind='rule' AND id=?", (rule_id,)
            ).fetchone()
            if not row:
                raise problem(404, "not_found", "Control not found.")
            rule = json.loads(row[0])
            if data.action == "approve":
                if rule["created_by"] == user["id"]:
                    raise problem(
                        403,
                        "independent_approval",
                        "A second authorized person must approve this control.",
                    )
                current = db.execute(
                    "SELECT version FROM policies WHERE id=?", (rule["policy_id"],)
                ).fetchone()
                if not current or current[0] != rule["policy_version"]:
                    raise problem(
                        409,
                        "policy_changed",
                        "The linked policy changed. Save a new control draft before approval.",
                    )
                if rule["status"] != "draft":
                    raise problem(
                        409, "not_draft", "Only draft controls can be approved."
                    )
                rule.update(status="active", approved_by=user["id"], approved_at=now())
                if rule.get("replaces_id"):
                    prior = db.execute(
                        "SELECT payload FROM records WHERE kind='rule' AND id=?",
                        (rule["replaces_id"],),
                    ).fetchone()
                    if prior:
                        retired = json.loads(prior[0])
                        if retired["status"] == "superseded":
                            raise problem(
                                409,
                                "control_superseded",
                                "Another draft already replaced this control. Rebase your proposal on the active version.",
                            )
                        retired["status"] = "superseded"
                        retired["updated_at"] = now()
                        db.execute(
                            "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                            (canonical(retired), now(), retired["id"]),
                        )
            else:
                rule["status"] = "disabled"
            rule["updated_at"] = now()
            rule["approval_notes"] = data.notes
            db.execute(
                "UPDATE records SET payload=?,updated_at=? WHERE id=?",
                (canonical(rule), now(), rule_id),
            )
            audit(
                db,
                user["id"],
                "rule_" + data.action,
                {"id": rule_id, "version": rule["version"], "notes": data.notes},
            )
        return rule

    def backtest(self, rule_id):
        rule = self.get("rule", rule_id)
        results = []
        with self.store.connect() as db:
            rows = db.execute(
                "SELECT payload FROM transactions ORDER BY occurred_at LIMIT 10001"
            ).fetchall()
            if len(rows) > 10000:
                raise problem(
                    422,
                    "backtest_limit",
                    "This single-instance backtest is limited to 10,000 transactions.",
                )
            for row in rows:
                txn = json.loads(row[0])
                customer = self.get("customer", txn["customer_id"])
                matched, facts = self._matches(db, rule, txn, customer)
                if matched:
                    results.append(
                        {
                            "transaction_id": txn["id"],
                            "external_id": txn["external_id"],
                            "facts": facts,
                        }
                    )
        return {
            "rule_id": rule_id,
            "version": rule["version"],
            "tested": len(rows),
            "matches": results,
            "match_count": len(results),
            "mode": "historical_simulation",
            "limitation": "Uses current customer KYC state; outcomes are not labelled ground truth and do not measure detection accuracy.",
        }

    def policy_versions(self, policy_id):
        with self.store.connect() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM policy_versions WHERE policy_id=? ORDER BY created_at DESC",
                    (policy_id,),
                )
            ]

    def verify_audit(self):
        previous = "0" * 64
        count = 0
        with self.store.connect() as db:
            for row in db.execute("SELECT * FROM audit_chain ORDER BY seq"):
                data = dict(row)
                payload = canonical(
                    {
                        "at": data["at"],
                        "actor": data["actor"],
                        "action": data["action"],
                        "data": json.loads(data["data"]),
                        "previous": previous,
                    }
                )
                expected = hashlib.sha256(payload.encode()).hexdigest()
                if data["previous"] != previous or data["hash"] != expected:
                    return {
                        "valid": False,
                        "entries_checked": count,
                        "failed_seq": data["seq"],
                    }
                previous = expected
                count += 1
        return {
            "valid": True,
            "entries_checked": count,
            "head_hash": previous,
            "limitation": "A local hash chain detects modification relative to a trusted checkpoint. It does not prevent a database administrator from rewriting or truncating history.",
        }

    def audit_events(self, limit=200):
        with self.store.connect() as db:
            return [
                {**dict(r), "data": json.loads(r["data"])}
                for r in db.execute(
                    "SELECT * FROM audit_chain ORDER BY seq DESC LIMIT ?", (limit,)
                )
            ]

    def analytics(self):
        with self.store.connect() as db:
            transactions = db.execute("SELECT count(*) FROM transactions").fetchone()[0]
            job_states = {
                r[0]: r[1]
                for r in db.execute("SELECT state,count(*) FROM jobs GROUP BY state")
            }
            corridors = [
                dict(r)
                for r in db.execute(
                    "SELECT json_extract(payload,'$.counterparty_country') AS country,count(*) AS transactions FROM transactions GROUP BY country ORDER BY transactions DESC LIMIT 10"
                )
            ]
        cases = self.list("case", 10000)
        return {
            "customers": len(self.list("customer", 10000)),
            "transactions": transactions,
            "cases": len(cases),
            "open_cases": sum(c["status"] != "resolved" for c in cases),
            "escalated": sum(c["status"] == "escalated" for c in cases),
            "resolved": sum(c["status"] == "resolved" for c in cases),
            "active_rules": sum(r["status"] == "active" for r in self.list("rule")),
            "jobs": job_states,
            "corridors": corridors,
            "overdue": sum(
                c["status"] != "resolved" and c["due_at"] < now() for c in cases
            ),
            "dispositions": {
                v: sum(c["disposition"] == v for c in cases)
                for v in ("confirmed", "false_positive", "insufficient_evidence")
            },
        }

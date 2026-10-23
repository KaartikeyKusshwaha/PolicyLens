"""Deterministic threshold search. Historical workload is not detection accuracy."""

import hashlib
import json
from collections import Counter
from decimal import Decimal

from pydantic import Field, model_validator

from models import Input
from operations import Operations, audit, canonical, uid
from product_models import RuleInput
from providers import problem
from store import now

MAX_TRANSACTIONS = 10_000
MAX_INPUT_BYTES = 16_000_000
MAX_ROLLING_WORK = 20_000_000
MAX_RECEIPTS = 1000


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class TuningInput(Input):
    control_id: str = Field(min_length=1, max_length=100)
    candidate_thresholds: list[Decimal] = Field(min_length=1, max_length=8)
    target_match_count: int = Field(ge=0, le=MAX_TRANSACTIONS, strict=True)
    rationale: str = Field(min_length=20, max_length=2000)

    @model_validator(mode="after")
    def thresholds(self):
        for threshold in self.candidate_thresholds:
            if (
                not threshold.is_finite()
                or threshold < 1
                or threshold >= Decimal("100000000000000")
                or threshold.as_tuple().exponent < -2
            ):
                raise ValueError(
                    "Supply finite thresholds from 1 to 99999999999999.99, with at most two decimals."
                )
        if len(set(self.candidate_thresholds)) != len(self.candidate_thresholds):
            raise ValueError("Candidate thresholds must be distinct.")
        return self


class DraftInput(TuningInput):
    preview_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def request_value(data):
    return TuningInput.model_validate(
        {key: getattr(data, key) for key in TuningInput.model_fields}
    ).model_dump(mode="json")


def record(db, kind, record_id):
    row = db.execute(
        "SELECT payload FROM records WHERE kind=? AND id=?", (kind, record_id)
    ).fetchone()
    if not row:
        raise problem(404, "not_found", "Record not found in this workspace.")
    return json.loads(row[0])


def configuration(rule):
    return RuleInput.model_validate({key: rule[key] for key in RuleInput.model_fields})


def simulate(db, store, data):
    parent = record(db, "rule", data.control_id)
    if parent["status"] != "active":
        raise problem(
            409,
            "tuning_parent_inactive",
            "Start from an active control. Tuning never activates or edits it.",
        )
    if parent["kind"] not in ("amount", "velocity", "aggregate"):
        raise problem(
            422,
            "tuning_kind",
            "Only amount, velocity and aggregate controls have tunable numeric thresholds.",
        )
    policy_row = db.execute(
        "SELECT * FROM policies WHERE id=?", (parent["policy_id"],)
    ).fetchone()
    if not policy_row or policy_row["version"] != parent["policy_version"]:
        raise problem(
            409,
            "policy_changed",
            "The control's policy version changed. Review a new control version first.",
        )
    rows = db.execute(
        "SELECT * FROM transactions ORDER BY occurred_at,id LIMIT ?",
        (MAX_TRANSACTIONS + 1,),
    ).fetchall()
    if not rows or len(rows) > MAX_TRANSACTIONS:
        raise problem(
            422,
            "tuning_capacity",
            "Tuning requires 1–10,000 historical transactions; no sample was substituted.",
        )
    raw = [dict(row) for row in rows]
    size = sum(len(row["payload"].encode()) for row in raw)
    if size > MAX_INPUT_BYTES:
        raise problem(
            422,
            "tuning_capacity",
            "The complete transaction inventory exceeds the 16 MB tuning bound.",
        )
    if parent["kind"] in ("velocity", "aggregate"):
        sizes = Counter(row["customer_id"] for row in raw)
        if sum(count * count for count in sizes.values()) > MAX_ROLLING_WORK:
            raise problem(
                422,
                "tuning_capacity",
                "The rolling-window replay exceeds the pilot work bound. No partial simulation was used.",
            )
    customers = {}
    for customer_id in sorted({row["customer_id"] for row in raw}):
        customer = record(db, "customer", customer_id)
        size += len(canonical(customer).encode())
        if size > MAX_INPUT_BYTES:
            raise problem(
                422,
                "tuning_capacity",
                "The complete tuning context exceeds its 16 MB bound.",
            )
        customers[customer_id] = customer
    ops = Operations(store)
    observations, before = [], []
    for raw_row in raw:
        try:
            txn = json.loads(raw_row["payload"])
            matching_columns = all(
                txn[key] == raw_row[key]
                for key in (
                    "id",
                    "external_id",
                    "customer_id",
                    "currency",
                    "occurred_at",
                )
            )
            amount = Decimal(txn["amount"])
            if (
                not matching_columns
                or not amount.is_finite()
                or amount <= 0
                or amount * 100 != raw_row["amount_minor"]
            ):
                raise ValueError("Transaction columns and retained evidence disagree")
        except (KeyError, TypeError, ValueError, ArithmeticError):
            raise problem(
                422,
                "tuning_evidence_invalid",
                "Transaction evidence is malformed or disagrees with its indexed values. No comparison or draft was accepted.",
            ) from None
        matched, facts = ops._matches(
            db, parent, txn, customers[raw_row["customer_id"]]
        )
        observations.append(
            (
                txn["id"],
                txn["currency"],
                Decimal(facts["observed"]) if facts["observed"] != "None" else None,
            )
        )
        if matched:
            before.append(txn["id"])
    candidates = []
    for threshold in data.candidate_thresholds:
        if parent["kind"] == "velocity" and threshold != threshold.to_integral_value():
            raise problem(
                422, "tuning_threshold", "Velocity thresholds must be integer counts."
            )
        if threshold == Decimal(parent["threshold"]):
            raise problem(
                422, "tuning_threshold", "Candidates must change the current threshold."
            )
        matches = [
            txn_id
            for txn_id, currency, observed in observations
            if observed is not None
            and observed >= threshold
            and (parent["kind"] == "velocity" or currency == parent["currency"])
        ]
        candidates.append(
            {
                "threshold": format(threshold, "f"),
                "match_count": len(matches),
                "match_transaction_ids": matches,
                "distance_from_target": abs(len(matches) - data.target_match_count),
            }
        )
    selected = min(candidates, key=lambda candidate: candidate["distance_from_target"])
    value = {
        "schema": "policylens.control-tuning.v1",
        "request": request_value(data),
        "parent_sha256": digest(parent),
        "policy_sha256": digest(dict(policy_row)),
        "input_sha256": digest({"transactions": raw, "customers": customers}),
        "tested": len(raw),
        "current_threshold": parent["threshold"],
        "before": {"match_count": len(before), "match_transaction_ids": before},
        "candidates": candidates,
        "selected": selected,
        "added_match_ids": sorted(set(selected["match_transaction_ids"]) - set(before)),
        "removed_match_ids": sorted(
            set(before) - set(selected["match_transaction_ids"])
        ),
        "selection": "Smallest absolute difference from the caller's target match count; ties use caller candidate order.",
        "limitations": [
            "Historical match volume is workload, not detection accuracy, false-positive rate, legal compliance or a calibrated risk measure.",
            "Uses current recorded customer context and the complete bounded transaction inventory, including inclusive rolling windows and same-timestamp peers.",
            "Only the threshold changes; policy, currency, window, destinations and priority remain pinned. The target and candidate thresholds are supplied judgments, not regulatory requirements.",
            "No live alerts, cases, payments or sanctions outcomes are changed. Independent human approval remains required, and changed evidence requires a fresh proposal.",
        ],
        "activated": False,
        "live_alerts_created": False,
    }
    value["preview_sha256"] = digest(value)
    return value


def preview(store, data):
    Operations(store)
    with store.connect() as db:
        db.execute("BEGIN")
        return simulate(db, store, data)


def draft(store, data, user):
    Operations(store)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            "SELECT payload FROM records WHERE kind='control_tuning' ORDER BY id LIMIT ?",
            (MAX_RECEIPTS + 1,),
        ).fetchall()
        if len(rows) > MAX_RECEIPTS:
            raise problem(
                422, "tuning_capacity", "Tuning history exceeds the pilot bound."
            )
        for row in rows:
            receipt = json.loads(row[0])
            if receipt["preview"]["preview_sha256"] == data.preview_sha256:
                if receipt["created_by"] != user["id"] or receipt[
                    "request_sha256"
                ] != digest(request_value(data)):
                    raise problem(
                        409,
                        "tuning_replay_conflict",
                        "This preview already belongs to another submission.",
                    )
                return {
                    "replayed": True,
                    "receipt": receipt,
                    "control": record(db, "rule", receipt["draft_id"]),
                }
        if len(rows) >= MAX_RECEIPTS:
            raise problem(
                422, "tuning_capacity", "Tuning history reached the pilot bound."
            )
        result = simulate(db, store, data)
        if result["preview_sha256"] != data.preview_sha256:
            raise problem(
                409,
                "tuning_preview_changed",
                "Control, policy or transaction/customer evidence changed. Inspect a fresh simulation.",
            )
        parent = record(db, "rule", data.control_id)
        config = configuration(parent).model_copy(
            update={"threshold": Decimal(result["selected"]["threshold"])}
        )
        control = Operations(store).draft_rule(db, config, user, parent["id"])
        receipt_id = uid()
        control.update(
            tuning_receipt_id=receipt_id,
            tuning_maker_id=user.get("key_issuer_id", user["id"]),
        )
        db.execute(
            "UPDATE records SET payload=? WHERE id=?",
            (canonical(control), control["id"]),
        )
        receipt = {
            "id": receipt_id,
            "created_at": now(),
            "created_by": user["id"],
            "maker_id": control["tuning_maker_id"],
            "draft_id": control["id"],
            "draft_sha256": digest(control),
            "request_sha256": digest(request_value(data)),
            "preview": result,
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            (
                "control_tuning",
                receipt_id,
                receipt["created_at"],
                receipt["created_at"],
                canonical(receipt),
            ),
        )
        audit(
            db,
            user["id"],
            "control_tuning_drafted",
            {
                "id": receipt_id,
                "control_id": control["id"],
                "receipt_sha256": digest(receipt),
                "maker_id": control["tuning_maker_id"],
            },
        )
        return {"replayed": False, "receipt": receipt, "control": control}


def validate_approval(db, store, control, user):
    receipt = record(db, "control_tuning", control["tuning_receipt_id"])
    if user["id"] in (receipt["created_by"], receipt["maker_id"]):
        raise problem(
            403,
            "independent_approval",
            "A different reviewer from the tuning author and agent-key issuer must approve this proposal.",
        )
    if (
        receipt["draft_id"] != control["id"]
        or digest(control) != receipt["draft_sha256"]
    ):
        raise problem(
            409,
            "tuning_draft_changed",
            "The retained tuning draft changed. Prepare a fresh proposal.",
        )
    current = simulate(
        db, store, TuningInput.model_validate(receipt["preview"]["request"])
    )
    if current["preview_sha256"] != receipt["preview"]["preview_sha256"]:
        raise problem(
            409,
            "tuning_evidence_changed",
            "The simulation evidence changed. Review a fresh tuning proposal before activation.",
        )


def detail(store, receipt_id):
    with store.connect() as db:
        db.execute("BEGIN")
        receipt = record(db, "control_tuning", receipt_id)
        control = record(db, "rule", receipt["draft_id"])
        return {"receipt": receipt, "control_status": control["status"]}

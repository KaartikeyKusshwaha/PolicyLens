"""Cross-check database snapshots against independently verified history copies."""

import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

from checkpoints import verify_chain
from deletion_guard import TABLE_KEYS, sha256
from deploy.checkpoint_backup import verify as verify_checkpoints
from deploy.deletion_state_backup import verify_bundle as verify_deletions
from deploy.pull_backup import verify_archive, verification_database


def verify(
    database_content,
    *,
    database_key_file=None,
    checkpoint_content=None,
    fingerprint=None,
    deletion_content=None,
    max_age_hours=30,
):
    manifest = verify_archive(
        database_content, max_age_hours, database_key_file=database_key_file
    )
    settings = (
        SimpleNamespace(
            database_encryption="sqlcipher4",
            security_key_path=Path(database_key_file),
            deployment_mode="public",
        )
        if database_key_file
        else None
    )
    checkpoints, deletions = None, None
    expected_workspaces = set(manifest["organization_paths"])
    if checkpoint_content is not None:
        verify_checkpoints(checkpoint_content, fingerprint, max_age_hours=max_age_hours)
        checkpoints = json.loads(checkpoint_content)["payload"]["workspaces"]
        if set(checkpoints) != expected_workspaces:
            raise ValueError(
                "Checkpoint history workspace roster differs from the database snapshot"
            )
    if deletion_content is not None:
        if settings is None:
            raise ValueError(
                "Deletion recovery-set validation requires original installation recovery key"
            )
        verify_deletions(deletion_content, settings, max_age_hours=max_age_hours)
        import base64

        deletions = []
        for encoded in json.loads(deletion_content)["payload"]["files"].values():
            guard = json.loads(base64.b64decode(encoded, validate=True))["payload"]
            # Historical guards predate newly added workspaces; they may name a
            # subset, but may not refer to tenants omitted from this snapshot.
            if not set(guard["workspaces"]).issubset(expected_workspaces):
                raise ValueError(
                    "Deletion history workspace roster differs from the snapshot"
                )
            deletions.extend(guard["receipts"])
    checked, receipts = 0, 0
    with tarfile.open(fileobj=io.BytesIO(database_content), mode="r:gz") as archive:
        for workspace_id, relative in manifest["organization_paths"].items():
            with verification_database(
                archive.extractfile(relative).read(), settings
            ) as db:
                if checkpoints is not None:
                    anchor = checkpoints[workspace_id][-1]["payload"]
                    cursor = db.execute("SELECT * FROM audit_chain ORDER BY seq")
                    names = [column[0] for column in cursor.description]
                    result = verify_chain(
                        (dict(zip(names, row)) for row in cursor), anchor
                    )
                    if (
                        result["sequence"] != anchor["sequence"]
                        or result["head_hash"] != anchor["head_hash"]
                    ):
                        raise ValueError(
                            "Database audit head differs from independently signed history"
                        )
                if deletions is not None:
                    # Committed guards cumulatively include prior receipts;
                    # aborted guards additionally include one uncommitted target.
                    expected = {}
                    for item in deletions:
                        if item["workspace_id"] == workspace_id:
                            if (
                                item["receipt_id"] in expected
                                and expected[item["receipt_id"]] != item
                            ):
                                raise ValueError(
                                    "External deletion history contains conflicting receipt identities"
                                )
                            expected[item["receipt_id"]] = item
                    actual = {}
                    for record_id, raw in db.execute(
                        "SELECT id,payload FROM records WHERE kind='deletion_receipt'"
                    ):
                        if record_id not in expected or expected[record_id][
                            "receipt_sha256"
                        ] != sha256(json.loads(raw)):
                            raise ValueError(
                                "Snapshot deletion receipt lacks matching external history"
                            )
                        actual[record_id] = expected[record_id]
                        receipts += 1
                    for record_id, item in expected.items():
                        if record_id not in actual:
                            request = db.execute(
                                "SELECT payload FROM records WHERE kind='deletion_request' AND id=?",
                                (item["request_id"],),
                            ).fetchone()
                            value = json.loads(request[0]) if request else {}
                            if (
                                value.get("status") != "cancelled"
                                or value.get("customer_id") != item["customer_id"]
                                or value.get("aborted_execution_receipt_id")
                                != record_id
                            ):
                                raise ValueError(
                                    "External deletion receipt is absent from snapshot without a matching proved abort"
                                )
                            continue
                        for target in item["candidates"]:
                            table, column = target["table"], TABLE_KEYS[target["table"]]
                            query, params = (
                                f"SELECT 1 FROM {table} WHERE {column}=?",
                                (target["record_id"],),
                            )
                            if table == "records":
                                query += " AND kind=?"
                                params += (target["kind"],)
                            if db.execute(query + " LIMIT 1", params).fetchone():
                                raise ValueError(
                                    "Database snapshot resurrects an externally recorded deleted target"
                                )
                checked += 1
    return {
        "verified": True,
        "workspaces": checked,
        "checkpoint_heads_checked": checkpoints is not None,
        "deletion_receipts_checked": receipts if deletions is not None else None,
        "scope": "Cross-artifact consistency of the selected snapshot and authenticated history, not current live state, off-machine custody, physical erasure or deployed recovery proof.",
    }

"""Standalone offline verifier. Use a trusted copy of this script, never execute untrusted pack code."""

import argparse
import base64
import hashlib
import hmac
import io
import json
import re
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

MAX_BYTES = 32_000_000
CONTENTS = {"evidence.json", "report.pdf", "audit.json", "verify.py", "README.txt"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def signed(document, fingerprint):
    if set(document) != {"payload", "public_key", "signature", "algorithm"}:
        raise ValueError("Unexpected signature fields.")
    if document["algorithm"] != "Ed25519":
        raise ValueError("Unsupported signature algorithm.")
    public = base64.b64decode(document["public_key"], validate=True)
    if not hmac.compare_digest(hashlib.sha256(public).hexdigest(), fingerprint):
        raise ValueError("Signing identity does not match the trusted fingerprint.")
    Ed25519PublicKey.from_public_bytes(public).verify(
        base64.b64decode(document["signature"], validate=True),
        canonical(document["payload"]).encode(),
    )
    return document["payload"]


def verify_pack(content, fingerprint):
    """No extraction, network calls, embedded script execution or signing secret required."""
    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", fingerprint
    ):
        raise ValueError(
            "An independently trusted SHA-256 key fingerprint is required."
        )
    if len(content) > MAX_BYTES:
        raise ValueError("Archive exceeds the verification size bound.")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        files = archive.infolist()
        if len(files) != 6 or {f.filename for f in files} != CONTENTS | {
            "manifest.json"
        }:
            raise ValueError("Missing, duplicate or unexpected archive entries.")
        if sum(f.file_size for f in files) > MAX_BYTES:
            raise ValueError("Uncompressed archive exceeds the verification bound.")
        data = {f.filename: archive.read(f) for f in files}
    manifest = signed(json.loads(data["manifest.json"]), fingerprint)
    if set(manifest) != {
        "schema",
        "workspace_id",
        "sequence",
        "head_hash",
        "created_at",
        "files",
    }:
        raise ValueError("Unexpected manifest fields.")
    if (
        manifest["schema"] != "policylens.evidence-manifest.v1"
        or set(manifest["files"]) != CONTENTS
    ):
        raise ValueError("Unsupported evidence manifest.")
    for name, digest in manifest["files"].items():
        if hashlib.sha256(data[name]).hexdigest() != digest:
            raise ValueError("Evidence file digest does not match: " + name)
    bundle = json.loads(data["audit.json"])
    if (
        set(bundle) != {"format", "checkpoint", "events"}
        or bundle["format"] != "policylens.audit-bundle.v1"
    ):
        raise ValueError("Unsupported audit bundle.")
    anchor = signed(bundle["checkpoint"], fingerprint)
    if (
        set(anchor)
        != {
            "schema",
            "workspace_id",
            "sequence",
            "head_hash",
            "created_at",
            "previous_checkpoint_sha256",
        }
        or anchor["schema"] != "policylens.audit-checkpoint.v1"
    ):
        raise ValueError("Unsupported audit anchor.")
    if not isinstance(bundle["events"], list) or len(bundle["events"]) > 100000:
        raise ValueError("Invalid audit event list.")
    previous = "0" * 64
    for sequence, event in enumerate(bundle["events"], 1):
        if set(event) != {"seq", "at", "actor", "action", "data", "previous", "hash"}:
            raise ValueError("Unexpected audit event fields.")
        if (
            type(event["seq"]) is not int
            or event["seq"] != sequence
            or event["previous"] != previous
        ):
            raise ValueError("Audit sequence or hash link is invalid.")
        if not isinstance(event["data"], dict) or any(
            not isinstance(event[k], str)
            for k in ("at", "actor", "action", "previous", "hash")
        ):
            raise ValueError("Invalid audit event types.")
        hashed = hashlib.sha256(
            canonical(
                {k: event[k] for k in ("at", "actor", "action", "data", "previous")}
            ).encode()
        ).hexdigest()
        if hashed != event["hash"]:
            raise ValueError("Audit event hash is invalid.")
        previous = hashed
    evidence = json.loads(data["evidence.json"])
    if evidence["format"] != "policylens.sponsor-evidence.v1":
        raise ValueError("Unsupported evidence document.")
    for key, actual in (
        ("sequence", len(bundle["events"])),
        ("head_hash", previous),
        ("workspace_id", evidence["workspace_id"]),
    ):
        if (
            anchor[key] != actual
            or manifest[key] != actual
            or evidence["audit_snapshot"][key] != actual
        ):
            raise ValueError("Evidence, manifest and signed audit snapshot disagree.")
    return {
        "valid": True,
        "workspace_id": manifest["workspace_id"],
        "sequence": manifest["sequence"],
        "head_hash": previous,
        "files_checked": len(CONTENTS),
        "fingerprint": fingerprint,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive")
    parser.add_argument("--fingerprint", required=True)
    args = parser.parse_args()
    try:
        with open(args.archive, "rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        result = verify_pack(content, args.fingerprint)
    except Exception as exc:
        # No private data or attacker-controlled exception messages in terminal output.
        print(json.dumps({"valid": False, "error": type(exc).__name__}))
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()

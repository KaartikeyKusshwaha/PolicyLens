"""Opt-in operational status messages; never send case data, paths or credentials."""

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import httpx

SCHEMA = "policylens.telegram-alert-state.v1"


def read_json(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError("Private configuration/state unavailable")
    with path.open("rb") as stream:
        content = stream.read(4097)
    if len(content) > 4096:
        raise ValueError("Configuration/state oversized")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Invalid configuration/state")
    return value


def configuration(path):
    value = read_json(path)
    if os.name != "nt" and Path(path).stat().st_mode & 0o077:
        raise ValueError("Telegram configuration must be private")
    if set(value) != {"bot_token", "chat_id"}:
        raise ValueError("Unexpected Telegram configuration fields")
    if not isinstance(value["bot_token"], str) or not re.fullmatch(
        r"[1-9][0-9]{4,20}:[A-Za-z0-9_-]{20,100}", value["bot_token"]
    ):
        raise ValueError("Invalid Telegram bot token")
    if not isinstance(value["chat_id"], str) or not re.fullmatch(
        r"-?[1-9][0-9]{0,20}", value["chat_id"]
    ):
        raise ValueError("Use an explicit numeric destination chat")
    return value


def write_state(path, value):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("Unsafe Telegram state file")
    descriptor, temporary = tempfile.mkstemp(prefix=".telegram-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write((json.dumps(value, sort_keys=True) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def notify(config_path, report_directory, result, *, transport=None, test=False):
    """Notify on changed failures/recovery; retain state only after API acceptance."""
    try:
        config = configuration(config_path)
        root = Path(report_directory).absolute()
        if root.resolve() != root or not root.is_dir():
            raise ValueError("Existing private report directory required")
        target = root / "telegram-state.json"
        destination = hashlib.sha256(
            (config["bot_token"] + "\n" + config["chat_id"]).encode()
        ).hexdigest()
        previous = read_json(target) if target.exists() or target.is_symlink() else None
        if previous is not None and (
            set(previous) != {"schema", "destination", "incident"}
            or previous["schema"] != SCHEMA
            or not isinstance(previous["incident"], str)
            or not re.fullmatch(r"healthy|[a-f0-9]{64}", previous["incident"])
        ):
            raise ValueError("Invalid Telegram state")
        if previous and previous["destination"] != destination:
            previous = None
        failures = sorted(
            (item["name"], item["code"])
            for item in result["checks"]
            if item["healthy"] is not True
        )
        if any(
            not re.fullmatch(r"[a-z_]{1,64}", name)
            or not re.fullmatch(r"[a-z_]{1,64}", code)
            for name, code in failures
        ) or bool(failures) == bool(result["healthy"]):
            raise ValueError("Invalid operational result")
        incident = (
            hashlib.sha256(json.dumps(failures).encode()).hexdigest()
            if failures
            else "healthy"
        )
        state = {"schema": SCHEMA, "destination": destination, "incident": incident}
        if not test and previous and previous["incident"] == incident:
            return {"ok": True, "status": "unchanged", "delivered": False}
        if not test and previous is None and not failures:
            write_state(target, state)
            return {"ok": True, "status": "healthy_baseline", "delivered": False}
        if test:
            text = "PolicyLens operational alert test. Telegram configuration is reachable. This message does not establish service health or recovery."
        elif failures:
            text = "PolicyLens operational FAILURE\n" + "\n".join(
                name + ": " + code for name, code in failures
            )
        else:
            text = "PolicyLens operational RECOVERED\nAll configured checks passed."
        # Fixed official host; no proxy inheritance, redirects or automatic retry.
        with httpx.Client(
            timeout=10, trust_env=False, follow_redirects=False, transport=transport
        ) as client:
            with client.stream(
                "POST",
                "https://api.telegram.org/bot" + config["bot_token"] + "/sendMessage",
                json={"chat_id": config["chat_id"], "text": text},
            ) as response:
                content = bytearray()
                for block in response.iter_bytes(chunk_size=1024):
                    content.extend(block)
                    if len(content) > 16384:
                        raise ValueError("Telegram response oversized")
                accepted = json.loads(content)
                if (
                    response.status_code != 200
                    or not isinstance(accepted, dict)
                    or accepted.get("ok") is not True
                ):
                    raise ValueError("Telegram did not accept notification")
        if not test:
            write_state(target, state)
        return {
            "ok": True,
            "status": "test_sent"
            if test
            else "failure_sent"
            if failures
            else "recovery_sent",
            "delivered": True,
        }
    except (OSError, ValueError, TypeError, KeyError, httpx.HTTPError):
        # Telegram embeds credentials in URLs; never expose response/errors here.
        return {
            "ok": False,
            "status": "telegram_configuration_delivery_or_state_failed",
            "delivered": False,
        }

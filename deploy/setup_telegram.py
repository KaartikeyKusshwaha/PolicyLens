"""Pair a dedicated Telegram bot privately; run in an interactive local terminal."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sys

import httpx

if __package__:
    from .telegram_alerts import notify, read_json
else:
    from telegram_alerts import notify, read_json


def paired_chat(token, code, *, transport=None):
    """Select only the private chat that sent this session's exact pairing code."""
    with httpx.Client(
        timeout=10, trust_env=False, follow_redirects=False, transport=transport
    ) as client:
        with client.stream(
            "POST",
            "https://api.telegram.org/bot" + token + "/getUpdates",
            json={"allowed_updates": ["message"], "limit": 100, "timeout": 0},
        ) as response:
            content = bytearray()
            for block in response.iter_bytes(chunk_size=4096):
                content.extend(block)
                if len(content) > 131072:
                    raise ValueError("Pairing response oversized")
            value = json.loads(content)
            if (
                response.status_code != 200
                or not isinstance(value, dict)
                or value.get("ok") is not True
                or not isinstance(value.get("result"), list)
            ):
                raise ValueError(
                    "Pairing unavailable; use a dedicated bot without a webhook"
                )
    matches = set()
    for update in value["result"]:
        message = update.get("message", {}) if isinstance(update, dict) else {}
        if not isinstance(message, dict):
            continue
        chat = message.get("chat", {})
        if (
            isinstance(chat, dict)
            and chat.get("type") == "private"
            and message.get("text") == code
        ):
            identifier = str(chat.get("id", ""))
            if re.fullmatch(r"[1-9][0-9]{0,20}", identifier):
                matches.add(identifier)
    if len(matches) != 1:
        raise ValueError("Exactly one private chat must send the current pairing code")
    return matches.pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Existing private blank bot_token/chat_id JSON",
    )
    parser.add_argument("--report-directory", required=True, type=Path)
    args = parser.parse_args()
    try:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ValueError(
                "Use an interactive local terminal; token input must not echo"
            )
        if read_json(args.config) != {"bot_token": "", "chat_id": ""}:
            raise ValueError("Refusing to replace an existing Telegram configuration")
        token = getpass.getpass("Paste your dedicated bot token (hidden): ").strip()
        if not re.fullmatch(r"[1-9][0-9]{4,20}:[A-Za-z0-9_-]{20,100}", token):
            raise ValueError("Invalid bot token")
        code = "policylens-pair-" + secrets.token_hex(12)
        print("Open a private chat with your bot and send exactly:\n" + code)
        input("After sending it, press Enter here: ")
        chat_id = paired_chat(token, code)
        # Preserve the operator-provisioned Windows ACL of the existing blank file.
        with args.config.open("r+", encoding="utf-8") as stream:
            if json.load(stream) != {"bot_token": "", "chat_id": ""}:
                raise ValueError("Configuration changed during pairing")
            stream.seek(0)
            json.dump({"bot_token": token, "chat_id": chat_id}, stream)
            stream.write("\n")
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
        result = notify(
            args.config,
            args.report_directory,
            {"healthy": True, "checks": []},
            test=True,
        )
        if not result["ok"]:
            raise ValueError("Configuration saved but test delivery failed")
        print(
            "Telegram accepted the pairing test. Configuration saved privately; scheduled monitor activation is still required."
        )
        return 0
    except (OSError, ValueError, TypeError, KeyError, EOFError, httpx.HTTPError):
        print(
            "Telegram setup did not complete. Check the private local configuration and dedicated bot; no token or response content was logged."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""TOTP primitives and purpose-bound encryption for installation secrets."""

import base64
import hashlib
import hmac
import os
import re
import secrets
import struct
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def totp(secret, counter, digits=6):
    key = base64.b32decode(secret, casefold=True)
    value = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = value[-1] & 15
    number = struct.unpack(">I", value[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % (10**digits)).zfill(digits)


def matching_counter(secret, code, last=-1, stamp=None):
    if not re.fullmatch(r"[0-9]{6}", code):
        return None
    current = int((time.time() if stamp is None else stamp) // 30)
    # Check the entire bounded window, then consume the matching counter atomically.
    matches = [
        counter
        for counter in (current - 1, current, current + 1)
        if counter >= 0 and hmac.compare_digest(totp(secret, counter), code)
    ]
    return max(matches) if matches and max(matches) > last else None


class SecretBox:
    """Keys are kept outside DB snapshots; missing keys never get replaced on decrypt."""

    def __init__(self, settings):
        self.path = Path(
            settings.security_key_path
            or settings.database_path.parent / ".security-key"
        )
        self.public = settings.deployment_mode == "public"

    def key(self, create=False):
        if create and not self.path.exists() and not self.public:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(
                    self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "wb") as file:
                    file.write(secrets.token_bytes(32))
        if not self.path.is_file():
            raise RuntimeError(
                "Installation encryption key is unavailable. Configure SECURITY_KEY_PATH; preserve the original key when restoring."
            )
        key = self.path.read_bytes()
        if len(key) != 32:
            raise RuntimeError(
                "Installation encryption key must contain 32 random bytes."
            )
        if os.name != "nt" and self.path.stat().st_mode & 0o077:
            raise RuntimeError("Installation encryption key permissions must be 0600.")
        return key

    def encrypt(self, value, purpose):
        nonce = secrets.token_bytes(12)
        encrypted = AESGCM(self.key(create=True)).encrypt(
            nonce, value.encode(), purpose.encode()
        )
        return base64.urlsafe_b64encode(nonce + encrypted).decode()

    def decrypt(self, value, purpose):
        try:
            raw = base64.urlsafe_b64decode(value)
            return (
                AESGCM(self.key())
                .decrypt(raw[:12], raw[12:], purpose.encode())
                .decode()
            )
        except (InvalidTag, ValueError, UnicodeError) as exc:
            raise RuntimeError("Encrypted secret could not be verified.") from exc

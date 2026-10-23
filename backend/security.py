"""Purpose-bound encryption for installation secrets."""

import base64
import os
import secrets
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


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

import base64

import pytest

from security import SecretBox


def test_secret_encryption_rejects_tampering_and_purpose_rebinding(workspace):
    _, _, _, settings = workspace
    box = SecretBox(settings)
    encrypted = box.encrypt("fictional private value", "test:user-1")
    assert box.decrypt(encrypted, "test:user-1") == "fictional private value"
    with pytest.raises(RuntimeError, match="could not be verified"):
        box.decrypt(encrypted, "test:user-2")
    with pytest.raises(RuntimeError, match="could not be verified"):
        box.decrypt(base64.urlsafe_b64encode(b"invalid encrypted secret").decode(), "test:user-1")


def test_public_installation_key_must_be_provisioned_explicitly(workspace, tmp_path):
    _, _, _, settings = workspace
    target = tmp_path / "unprovisioned-key"
    public = settings.model_copy(update={"deployment_mode": "public", "security_key_path": target})
    with pytest.raises(RuntimeError, match="encryption key is unavailable"):
        SecretBox(public).encrypt("fictional value", "test:purpose")
    assert not target.exists()

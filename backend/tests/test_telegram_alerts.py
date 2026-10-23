import json
from pathlib import Path

import httpx
import pytest

from deploy.telegram_alerts import notify
from deploy.setup_telegram import paired_chat
from deploy import watchdog, telegram_alerts


@pytest.fixture
def configured(tmp_path):
    config = tmp_path / "telegram.json"
    config.write_text(
        json.dumps({"bot_token": "123456789:" + "A" * 35, "chat_id": "123456789"})
    )
    config.chmod(0o600)
    reports = tmp_path / "reports"
    reports.mkdir()
    return config, reports


def status(healthy, code="disk_below_floor"):
    return {
        "healthy": healthy,
        "checks": [
            {
                "name": "disk_space",
                "healthy": healthy,
                "code": "disk_floor_met" if healthy else code,
            }
        ],
        "private_customer": "Never transmit this",
        "private_path": "Never transmit this either",
    }


def test_failure_changes_and_recovery_are_deduplicated(configured):
    config, reports = configured
    messages = []

    def respond(request):
        assert request.url.host == "api.telegram.org"
        assert request.method == "POST"
        message = json.loads(request.content)
        assert set(message) == {"chat_id", "text"}
        assert "Never transmit" not in message["text"]
        messages.append(message["text"])
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(respond)
    assert (
        notify(config, reports, status(True), transport=transport)["status"]
        == "healthy_baseline"
    )
    assert not messages
    assert (
        notify(config, reports, status(False), transport=transport)["status"]
        == "failure_sent"
    )
    assert (
        notify(config, reports, status(False), transport=transport)["status"]
        == "unchanged"
    )
    assert (
        notify(
            config, reports, status(False, "disk_path_unavailable"), transport=transport
        )["status"]
        == "failure_sent"
    )
    assert (
        notify(config, reports, status(True), transport=transport)["status"]
        == "recovery_sent"
    )
    assert (
        notify(config, reports, status(True), transport=transport)["status"]
        == "unchanged"
    )
    assert len(messages) == 3 and "RECOVERED" in messages[-1]


@pytest.mark.parametrize(
    "failure", ["http", "network", "redirect", "oversized", "wrong_json_type"]
)
def test_delivery_failure_does_not_advance_state_or_leak_token(configured, failure):
    config, reports = configured

    def respond(request):
        if failure == "network":
            raise httpx.ConnectError(
                "Sensitive URL: " + str(request.url), request=request
            )
        if failure == "oversized":
            return httpx.Response(200, content=b"x" * 17000)
        if failure == "wrong_json_type":
            return httpx.Response(200, json=[])
        return httpx.Response(
            302 if failure == "redirect" else 403,
            json={"ok": False},
            headers={"Location": "https://example.invalid"},
        )

    result = notify(
        config, reports, status(False), transport=httpx.MockTransport(respond)
    )
    assert result["ok"] is False and result["delivered"] is False
    assert json.loads(config.read_text())["bot_token"] not in json.dumps(result)
    assert not (reports / "telegram-state.json").exists()
    result = notify(
        config,
        reports,
        status(False),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"ok": True})
        ),
    )
    assert result["status"] == "failure_sent"


def test_explicit_test_does_not_suppress_actual_incident(configured):
    config, reports = configured
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True})
    )
    assert (
        notify(config, reports, status(False), transport=transport, test=True)["status"]
        == "test_sent"
    )
    assert not (reports / "telegram-state.json").exists()
    assert (
        notify(config, reports, status(False), transport=transport)["status"]
        == "failure_sent"
    )


def test_corrupt_state_does_not_send_misleading_recovery(configured):
    config, reports = configured
    (reports / "telegram-state.json").write_text('{"schema":"unexpected"}')

    def unexpected(request):
        pytest.fail("Corrupt state must not send a notification")

    assert (
        notify(
            config, reports, status(True), transport=httpx.MockTransport(unexpected)
        )["ok"]
        is False
    )


def test_changed_destination_receives_current_failure(configured):
    config, reports = configured
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True})
    )
    assert notify(config, reports, status(False), transport=transport)["delivered"]
    value = json.loads(config.read_text())
    value["chat_id"] = "987654321"
    config.write_text(json.dumps(value))
    assert notify(config, reports, status(False), transport=transport)["delivered"]


def test_invalid_destination_and_broad_posix_permissions_are_refused(configured):
    config, reports = configured
    value = json.loads(config.read_text())
    value["chat_id"] = "https://example.invalid"
    config.write_text(json.dumps(value))
    assert not notify(config, reports, status(False))["ok"]
    if __import__("os").name != "nt":
        value["chat_id"] = "123456789"
        config.write_text(json.dumps(value))
        config.chmod(0o644)
        assert not notify(config, reports, status(False))["ok"]


def test_unsafe_state_path_is_not_overwritten(configured):
    config, reports = configured
    Path(reports / "telegram-state.json").mkdir()
    assert not notify(config, reports, status(False))["ok"]


def test_pairing_uses_only_exact_code_in_one_private_chat():
    updates = [
        {"message": {"text": "wrong", "chat": {"type": "private", "id": 111}}},
        {"message": {"text": "current-code", "chat": {"type": "group", "id": -222}}},
        {"message": {"text": "current-code", "chat": {"type": "private", "id": 333}}},
    ]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True, "result": updates})
    )
    assert paired_chat("test-token", "current-code", transport=transport) == "333"
    updates.append(
        {"message": {"text": "current-code", "chat": {"type": "private", "id": 444}}}
    )
    with pytest.raises(ValueError):
        paired_chat("test-token", "current-code", transport=transport)


def test_pairing_does_not_choose_an_unmatched_recipient():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "ok": True,
                "result": [
                    {
                        "message": {
                            "text": "old-code",
                            "chat": {"type": "private", "id": 111},
                        }
                    }
                ],
            },
        )
    )
    with pytest.raises(ValueError):
        paired_chat("test-token", "current-code", transport=transport)


def test_healthy_checks_with_failed_telegram_delivery_exit_nonzero(
    configured, monkeypatch
):
    config, reports = configured
    monkeypatch.setattr(watchdog, "check", lambda *args, **kwargs: status(True))
    monkeypatch.setattr(
        telegram_alerts,
        "notify",
        lambda *args, **kwargs: {
            "ok": False,
            "delivered": False,
            "status": "delivery_failed",
        },
    )
    assert (
        watchdog.main(
            [
                "--origin",
                "https://example.invalid",
                "--offsite-directory",
                str(reports),
                "--disk-path",
                str(reports),
                "--report-directory",
                str(reports),
                "--telegram-config",
                str(config),
            ]
        )
        == 2
    )
    saved = json.loads((reports / "latest.json").read_text())
    assert saved["healthy"] is True and saved["telegram"]["ok"] is False

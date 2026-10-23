"""Prepare an isolated, persistent synthetic workspace before browser acceptance."""

import argparse
import hashlib
import json
import secrets
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import Settings  # noqa: E402
from main import create_app  # noqa: E402

SCHEMA = "policylens.synthetic-browser-fixture.v1"
PACK = ROOT / "examples" / "fintech-pilot"


def settings_for(directory):
    return Settings(
        _env_file=None,
        database_path=directory / "data" / "workspace.db",
        security_key_path=directory / "private" / "installation.key",
        checkpoint_directory=directory / "checkpoints",
        database_encryption="sqlcipher4",
        groq_api_key="",
        deployment_mode="local",
        cookie_secure=False,
        allowed_hosts="127.0.0.1,testserver",
    )


def no_outbound(request):
    raise RuntimeError("External providers disabled for isolated browser fixture")


def marble_bundle(customer_id, timestamp):
    def identifier(name):
        return str(
            uuid5(NAMESPACE_URL, f"https://example.invalid/policylens-fixture/{name}")
        )

    case_id = identifier("case")
    return {
        "schema_version": "policylens.marble-import.v1",
        "source_instance": "fictional-browser-fixture",
        "cases": {
            "data": [
                {
                    "id": case_id,
                    "inbox": {"id": identifier("inbox")},
                    "name": "FICTIONAL upstream closed case; local review still required",
                    "status": "closed",
                    "outcome": "false_positive",
                    "contributors": [],
                    "tags": [],
                    "review_level": None,
                    "created_at": timestamp,
                }
            ]
        },
        "decisions": {
            "data": [
                {
                    "id": identifier("decision"),
                    "case": {"id": case_id},
                    "outcome": "review",
                    "review_status": None,
                    "score": 70,
                    "scenario": {
                        "id": identifier("scenario"),
                        "iteration_id": identifier("iteration"),
                        "version": "1",
                    },
                    "trigger_object": {
                        "object_id": "FICTIONAL-TRIGGER-001",
                        "updated_at": timestamp,
                    },
                    "created_at": timestamp,
                }
            ]
        },
        "customer_mappings": [
            {"object_type": "case", "source_id": case_id, "customer_id": customer_id}
        ],
    }


def prepare(directory):
    directory = Path(directory).absolute()
    if directory.resolve() != directory:
        raise ValueError("Use an unredirected new directory")
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    private = directory / "private"
    private.mkdir(mode=0o700)
    settings = settings_for(directory)
    manifest = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Fictional local acceptance fixture; not a browser or deployment result",
        "provider_network": "disabled",
        "agent_worker": "disabled",
        "input_sha256": {
            name: hashlib.sha256((PACK / name).read_bytes()).hexdigest()
            for name in ("policy.txt", "customers.json", "transactions.json")
        },
    }
    credentials = []
    with TestClient(
        create_app(settings, httpx.MockTransport(no_outbound), start_worker=False)
    ) as owner:

        def request(client, method, path, status=200, **kwargs):
            result = client.request(method, path, **kwargs)
            if result.status_code != status:
                raise RuntimeError(
                    f"Synthetic fixture request failed: {method} {path} ({result.status_code})"
                )
            return result.json()

        password = secrets.token_urlsafe(24)
        account = request(
            owner,
            "POST",
            "/api/auth/setup",
            201,
            json={
                "email": "acceptance-owner@example.invalid",
                "name": "Fictional Acceptance Owner",
                "password": password,
                "workspace": "Fictional Browser Acceptance",
                "bootstrap_token": (
                    directory / "data" / ".bootstrap-token"
                ).read_text(),
            },
        )
        owner.headers["X-CSRF-Token"] = account["csrf"]
        credentials.append(
            {"role": "admin", "email": account["email"], "password": password}
        )
        # Share the running app without entering its installation lifespan twice.
        with closing(TestClient(owner.app)) as reviewer:
            for role in ("reviewer", "analyst"):
                email = f"acceptance-{role}@example.invalid"
                password = secrets.token_urlsafe(24)
                invite = request(
                    owner,
                    "POST",
                    "/api/team/invites",
                    201,
                    json={"email": email, "role": role},
                )
                request(
                    reviewer,
                    "POST",
                    "/api/auth/join",
                    201,
                    json={
                        "email": email,
                        "password": password,
                        "name": f"Fictional {role.title()}",
                        "token": invite["token"],
                    },
                )
                credentials.append({"role": role, "email": email, "password": password})
            reviewer.cookies.clear()
            identity = credentials[1]
            logged_in = request(
                reviewer,
                "POST",
                "/api/auth/login",
                json={
                    "email": identity["email"],
                    "password": identity["password"],
                },
            )
            reviewer.headers["X-CSRF-Token"] = logged_in["csrf"]
            policy = request(
                owner,
                "POST",
                "/api/policies",
                201,
                json={
                    "title": "FICTIONAL acceptance policy — not regulatory guidance",
                    "topic": "aml",
                    "version": "1.0",
                    "content": (PACK / "policy.txt").read_text(encoding="utf-8"),
                },
            )
            controls = []
            for kind, threshold, hours in (
                ("amount", "5000", 24),
                ("velocity", "3", 1),
                ("aggregate", "8000", 24),
                ("kyc", "100", 24),
            ):
                control = request(
                    owner,
                    "POST",
                    "/api/rules",
                    201,
                    json={
                        "title": f"Fictional {kind} control",
                        "kind": kind,
                        "policy_id": policy["id"],
                        "currency": "USD",
                        "threshold": threshold,
                        "window_hours": hours,
                        "countries": [],
                        "priority": "high",
                        "description": "Invented software acceptance setting.",
                    },
                )
                action = {
                    "action": "approve",
                    "notes": "Independent synthetic acceptance review.",
                }
                request(
                    owner,
                    "POST",
                    f"/api/rules/{control['id']}/actions",
                    403,
                    json=action,
                )
                request(
                    reviewer, "POST", f"/api/rules/{control['id']}/actions", json=action
                )
                controls.append(control["id"])
            draft = request(
                owner,
                "POST",
                "/api/rules",
                201,
                json={
                    "title": "Fictional pending maker-checker browser action",
                    "kind": "amount",
                    "policy_id": policy["id"],
                    "currency": "USD",
                    "threshold": "9000",
                    "window_hours": 24,
                    "countries": [],
                    "priority": "medium",
                    "description": "Leave as draft for browser approval checks.",
                },
            )
            customers = {}
            for data in json.loads((PACK / "customers.json").read_text()):
                customers[data["external_id"]] = request(
                    owner, "POST", "/api/customers", 201, json=data
                )["id"]
            timestamp = datetime.now(timezone.utc)
            alerts = []
            for scenario in json.loads((PACK / "transactions.json").read_text()):
                customer = customers[scenario.pop("customer_reference")]
                minutes = scenario.pop("minutes_ago")
                payload = {
                    **scenario,
                    "customer_id": customer,
                    "occurred_at": (timestamp - timedelta(minutes=minutes)).isoformat(),
                }
                result = request(
                    owner, "POST", "/api/monitor/transactions", 201, json=payload
                )
                alerts.extend(row["id"] for row in result["alerts"])
            replay = request(
                owner, "POST", "/api/monitor/transactions", 201, json=payload
            )
            cases = request(owner, "GET", "/api/cases")
            if len(alerts) != 6 or len(cases) != 3 or replay["duplicate"] is not True:
                raise RuntimeError("Synthetic fixture invariants failed")
            native_case = cases[0]
            path = f"/api/cases/{native_case['id']}/actions"
            request(
                owner,
                "POST",
                path,
                json={
                    "action": "assign",
                    "assignee_id": account["id"],
                    "notes": "Assign the fictional investigator.",
                },
            )
            request(
                owner,
                "POST",
                path,
                json={
                    "action": "start",
                    "notes": "Review fictional acceptance evidence.",
                },
            )
            disposition = {
                "action": "resolve",
                "disposition": "insufficient_evidence",
                "notes": "Fictional acceptance review; no real payment decision.",
            }
            request(owner, "POST", path, 403, json=disposition)
            request(reviewer, "POST", path, json=disposition)
            simulation = request(owner, "POST", f"/api/rules/{controls[2]}/backtest")
            if simulation["match_count"] != 1:
                raise RuntimeError("Synthetic aggregate backtest mismatch")
            bundle = marble_bundle(
                next(iter(customers.values())), timestamp.isoformat()
            )
            preview = request(
                owner, "POST", "/api/adapters/marble/preview", json={"bundle": bundle}
            )
            imported = request(
                owner,
                "POST",
                "/api/adapters/marble/import",
                201,
                json={"bundle": bundle, "preview_sha256": preview["preview_sha256"]},
            )
            if imported["replayed"]:
                raise RuntimeError("Fresh synthetic import unexpectedly replayed")
            cases = request(owner, "GET", "/api/cases")
            matrix = request(owner, "GET", "/api/traceability")
            if len(cases) != 4 or not any(
                row["id"] == policy["id"]
                for row in matrix["policies_without_current_analysis"]
            ):
                raise RuntimeError("Synthetic import or analysis-gap invariant failed")
            manifest.update(
                {
                    "policy_id": policy["id"],
                    "approved_control_ids": controls,
                    "draft_control_id": draft["id"],
                    "customer_ids": customers,
                    "alert_ids": alerts,
                    "case_ids": [row["id"] for row in cases],
                    "resolved_case_id": native_case["id"],
                    "marble_bundle_sha256": hashlib.sha256(
                        json.dumps(bundle, sort_keys=True).encode()
                    ).hexdigest(),
                    "expected": {
                        "transactions": 6,
                        "native_alerts": 6,
                        "open_cases": 3,
                        "resolved_cases": 1,
                        "imported_alerts": 1,
                        "aggregate_backtest_hits": 1,
                        "investigator_self_resolution_refused": True,
                        "policy_without_current_analysis": True,
                        "maker_self_approval_refused": True,
                        "replay_duplicate": True,
                    },
                }
            )
    # A failed preparation never publishes the completion marker used by serve.
    credential_file = private / "accounts.json"
    with credential_file.open("x", encoding="utf-8") as output:
        credential_file.chmod(0o600)
        json.dump(credentials, output, indent=2)
    (directory / "fixture.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def serve(directory, port):
    import uvicorn

    directory = Path(directory).absolute()
    if directory.resolve() != directory:
        raise ValueError("Use an unredirected fixture directory")
    marker = directory / "fixture.json"
    if marker.is_symlink() or json.loads(marker.read_text())["schema"] != SCHEMA:
        raise ValueError("Completed synthetic fixture required")
    uvicorn.run(
        create_app(
            settings_for(directory),
            httpx.MockTransport(no_outbound),
            start_worker=False,
        ),
        host="127.0.0.1",
        port=port,
        workers=1,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "serve"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument(
        "--port", type=int, default=8765, choices=range(1024, 65536), metavar="PORT"
    )
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare(args.directory)
            print(
                json.dumps(
                    {"prepared": True, "schema": SCHEMA, "expected": result["expected"]}
                )
            )
        else:
            serve(args.directory, args.port)
    except (ValueError, RuntimeError, OSError, KeyError):
        print(json.dumps({"ok": False, "error": "synthetic_fixture_failed"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

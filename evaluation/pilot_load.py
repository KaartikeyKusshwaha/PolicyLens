"""Isolated synthetic single-worker HTTP load/recovery evidence. No live target option."""

import argparse
import hashlib
import json
import math
import os
import platform
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config import Settings  # noqa: E402
from main import create_app  # noqa: E402
from verify_evidence_pack import verify_pack  # noqa: E402

SCHEMA = "policylens.synthetic-http-load.v1"


def settings_for(directory):
    return Settings(
        _env_file=None,
        database_path=directory / "data" / "workspace.db",
        security_key_path=directory / "private" / "installation.key",
        database_encryption="sqlcipher4",
        checkpoint_directory=directory / "checkpoints",
        deletion_state_directory=None,
        groq_api_key="",
        deployment_mode="local",
        cookie_secure=False,
        allowed_hosts="127.0.0.1",
    )


def serve(directory, port):
    import uvicorn

    marker = directory / "synthetic-run.json"
    if (
        marker.is_symlink()
        or not marker.is_file()
        or json.loads(marker.read_text())["schema"] != SCHEMA
    ):
        raise ValueError("Only a newly prepared isolated synthetic run may be served")

    def no_outbound(request):
        raise RuntimeError("Outbound providers disabled for synthetic load run")

    uvicorn.run(
        create_app(
            settings_for(directory),
            httpx.MockTransport(no_outbound),
            start_worker=False,
        ),
        host="127.0.0.1",
        port=port,
        workers=1,
        access_log=False,
    )


def percentile(values, fraction):
    if not values:
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def latency_summary(samples):
    groups = defaultdict(list)
    for name, milliseconds, status in samples:
        groups[name].append((milliseconds, status))
    return {
        name: {
            "requests": len(rows),
            "p50_ms": round(percentile([v for v, _ in rows], 0.5), 3),
            "p95_ms": round(percentile([v for v, _ in rows], 0.95), 3),
            "max_ms": round(max(v for v, _ in rows), 3),
            "http_statuses": dict(
                sorted(Counter(str(status) for _, status in rows).items())
            ),
        }
        for name, rows in sorted(groups.items())
    }


def gate(report, p95_ms):
    checks = {
        "all_correctness_invariants": bool(report["invariants"])
        and all(value is True for value in report["invariants"].values()),
        "no_request_failures": report["request_failures"] == 0,
        "chosen_http_p95_met": bool(report["latencies"])
        and all(row["p95_ms"] <= p95_ms for row in report["latencies"].values()),
        "signed_pack_within_minute": report.get("evidence_pack_seconds", float("inf"))
        <= 60
        and report.get("evidence_pack_verified") is True,
        "server_stopped": report.get("server_stopped") is True,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "scope": "Chosen synthetic envelope only; not a partner SLA, Oracle VM capacity proof or security review.",
    }


def run(
    directory,
    *,
    customers=100,
    transactions=1000,
    concurrency=4,
    read_rounds=10,
    p95_ms=2000,
):
    directory = Path(directory).absolute()
    if not (
        1 <= customers <= 2000
        and 1 <= transactions <= 10000
        and 1 <= concurrency <= 16
        and 1 <= read_rounds <= 100
        and 1 <= p95_ms <= 60000
    ):
        raise ValueError("Synthetic profile exceeds bounded pilot envelope")
    if directory.resolve() != directory:
        raise ValueError("Run directory cannot use redirected parents")
    directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    config = {
        "schema": SCHEMA,
        "customers": customers,
        "unique_transactions": transactions,
        "each_transaction_submitted": 2,
        "concurrency": concurrency,
        "read_rounds": read_rounds,
        "chosen_p95_ms": p95_ms,
        "workers": 1,
        "database_encryption": "sqlcipher4",
        "model_calls": 0,
        "provider_network": "disabled",
        "agent_worker": "disabled",
    }
    (directory / "synthetic-run.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    samples, invariant, clients = [], {}, []
    lock, local = threading.Lock(), threading.local()
    report = {
        "schema": SCHEMA,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "configuration": config,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "oracle_vm_proven": False,
        },
        "invariants": invariant,
        "request_failures": 0,
    }
    process = None
    phase = "startup"
    started = time.perf_counter()
    try:
        with (directory / "server.log").open("wb") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--serve",
                    "--directory",
                    str(directory),
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        with httpx.Client(base_url=base, timeout=60, trust_env=False) as owner:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError("server_start_failed")
                try:
                    if owner.get("/api/ready", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("server_start_timeout")
                time.sleep(0.1)

            def expect(client, method, path, status=200, **kwargs):
                response = client.request(method, path, **kwargs)
                if response.status_code != status:
                    report["failure_http_status"] = response.status_code
                    try:
                        code = response.json().get("detail", {}).get("code")
                        if (
                            isinstance(code, str)
                            and code.isascii()
                            and code.replace("_", "").isalnum()
                            and len(code) <= 80
                        ):
                            report["failure_code"] = code
                    except (ValueError, AttributeError):
                        pass
                    raise RuntimeError("fixture_or_correctness_request_failed")
                return response

            phase = "synthetic_setup"
            password = secrets.token_urlsafe(24)
            user = expect(
                owner,
                "POST",
                "/api/auth/setup",
                201,
                json={
                    "email": "load-owner@example.invalid",
                    "name": "Synthetic Load Owner",
                    "password": password,
                    "workspace": "Isolated Synthetic Load",
                    "bootstrap_token": (
                        directory / "data" / ".bootstrap-token"
                    ).read_text(),
                },
            ).json()
            owner.headers["X-CSRF-Token"] = user["csrf"]
            policy = expect(
                owner,
                "POST",
                "/api/policies",
                201,
                json={
                    "title": "Synthetic load policy, not regulatory guidance",
                    "content": "This synthetic test policy requires human review of test transactions exceeding an internal workload threshold. It does not specify a regulatory requirement or authorize payment decisions.",
                    "topic": "aml",
                    "version": "1.0",
                },
            ).json()
            control = expect(
                owner,
                "POST",
                "/api/rules",
                201,
                json={
                    "title": "Synthetic internal amount control",
                    "kind": "amount",
                    "policy_id": policy["id"],
                    "currency": "USD",
                    "threshold": "100",
                    "window_hours": 24,
                    "countries": [],
                    "priority": "high",
                    "description": "Illustrative load-test threshold; no regulatory inference.",
                },
            ).json()
            invariant["maker_self_approval_refused"] = (
                owner.post(
                    f"/api/rules/{control['id']}/actions",
                    json={
                        "action": "approve",
                        "notes": "Synthetic maker cannot approve its own control.",
                    },
                ).status_code
                == 403
            )
            invite = expect(
                owner,
                "POST",
                "/api/team/invites",
                201,
                json={"email": "load-reviewer@example.invalid", "role": "reviewer"},
            ).json()
            with httpx.Client(base_url=base, timeout=60, trust_env=False) as reviewer:
                second = expect(
                    reviewer,
                    "POST",
                    "/api/auth/join",
                    201,
                    json={
                        "email": "load-reviewer@example.invalid",
                        "name": "Synthetic Load Reviewer",
                        "password": password,
                        "token": invite["token"],
                    },
                ).json()
                reviewer.headers["X-CSRF-Token"] = second["csrf"]
                expect(
                    reviewer,
                    "POST",
                    f"/api/rules/{control['id']}/actions",
                    json={
                        "action": "approve",
                        "notes": "Independently reviewed synthetic control and policy.",
                    },
                )
            customer_ids = [
                expect(
                    owner,
                    "POST",
                    "/api/customers",
                    201,
                    json={
                        "external_id": f"SYNTH-{index:05}",
                        "name": f"Synthetic Load Customer {index:05}",
                        "country": "IN",
                    },
                ).json()["id"]
                for index in range(customers)
            ]
            cookies, csrf = dict(owner.cookies), owner.headers["X-CSRF-Token"]

            def client_for_thread():
                if not hasattr(local, "client"):
                    local.client = httpx.Client(
                        base_url=base,
                        timeout=60,
                        trust_env=False,
                        cookies=cookies,
                        headers={"X-CSRF-Token": csrf},
                    )
                    with lock:
                        clients.append(local.client)
                return local.client

            def measured(method, path, *, json_body=None):
                beginning = time.perf_counter()
                try:
                    response = client_for_thread().request(method, path, json=json_body)
                    status = response.status_code
                except httpx.HTTPError:
                    response, status = None, 0
                with lock:
                    samples.append(
                        (
                            method + " " + path.split("?")[0],
                            (time.perf_counter() - beginning) * 1000,
                            status,
                        )
                    )
                    if status != (201 if method == "POST" else 200):
                        report["request_failures"] += 1
                return (
                    response.json()
                    if response is not None and status in (200, 201)
                    else None
                )

            phase = "concurrent_ingestion"
            stamp = datetime.now(timezone.utc).isoformat()

            def ingest(index):
                return measured(
                    "POST",
                    "/api/monitor/transactions",
                    json_body={
                        "external_id": f"SYNTH-TXN-{index:06}",
                        "customer_id": customer_ids[index % customers],
                        "amount": "150.00" if index % 2 else "50.00",
                        "currency": "USD",
                        "counterparty": "Synthetic Test Counterparty",
                        "counterparty_country": "GB",
                        "description": "Synthetic load transaction, not a live payment.",
                        "occurred_at": stamp,
                    },
                )

            ingest_started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                results = list(
                    pool.map(
                        ingest,
                        [index for index in range(transactions) for _ in range(2)],
                    )
                )
                report["ingestion_seconds"] = round(
                    time.perf_counter() - ingest_started, 3
                )
                report["ingestion_requests_per_second"] = round(
                    2 * transactions / max(time.perf_counter() - ingest_started, 0.001),
                    3,
                )
                invariant["exactly_one_original_per_reference"] = (
                    sum(
                        item is not None and item.get("duplicate") is False
                        for item in results
                    )
                    == transactions
                )
                invariant["exactly_one_duplicate_per_reference"] = (
                    sum(
                        item is not None and item.get("duplicate") is True
                        for item in results
                    )
                    == transactions
                )
                phase = "populated_reads"
                paths = [
                    "/api/cases",
                    "/api/alerts?limit=200&offset=0",
                    "/api/evidence/digest",
                    "/api/traceability",
                    "/api/analytics",
                    "/api/monitor/transactions?limit=1000",
                ]
                list(pool.map(lambda path: measured("GET", path), paths * read_rounds))
            for client in clients:
                client.close()
            phase = "correctness_verification"
            analytics = expect(owner, "GET", "/api/analytics").json()
            cases = expect(owner, "GET", "/api/cases").json()
            expected_cases = len(
                {index % customers for index in range(transactions) if index % 2}
            )
            invariant["unique_transaction_count"] = (
                analytics["transactions"] == transactions
            )
            invariant["one_case_per_flagged_customer"] = (
                len(cases) == expected_cases
                and len({item["customer_id"] for item in cases}) == expected_cases
            )
            alerts = []
            for offset in range(0, 10001, 200):
                page = expect(
                    owner, "GET", f"/api/alerts?limit=200&offset={offset}"
                ).json()
                alerts.extend(page["alerts"])
                if not page["has_more"]:
                    break
            invariant["exact_alert_count"] = len(alerts) == transactions // 2
            invariant["distinct_alert_ids"] = len(
                {item["id"] for item in alerts}
            ) == len(alerts)
            digest = expect(owner, "GET", "/api/evidence/digest").json()
            invariant["digest_counts_match"] = digest["queues"]["open_cases"][
                "count"
            ] == expected_cases and digest["recent_alerts"] == len(alerts)
            invariant["audit_chain_valid"] = (
                expect(owner, "GET", "/api/audit").json()["verification"]["valid"]
                is True
            )
            invariant["no_model_jobs"] = analytics["jobs"] == {}
            invariant["encrypted_database_headers"] = all(
                path.read_bytes()[:16] != b"SQLite format 3\x00"
                for path in (directory / "data").rglob("*.db")
            )
            phase = "signed_evidence"
            pack_started = time.perf_counter()
            pack = expect(owner, "GET", "/api/evidence/sponsor-pack").content
            report["evidence_pack_seconds"] = round(
                time.perf_counter() - pack_started, 3
            )
            fingerprint = expect(owner, "GET", "/api/audit/checkpoints").json()[
                "fingerprint"
            ]
            report["evidence_pack_verified"] = verify_pack(pack, fingerprint)["valid"]
            report["evidence_pack_bytes"] = len(pack)
            (directory / "synthetic-evidence.zip").write_bytes(pack)
            phase = "tenant_isolation"
            other = expect(
                owner,
                "POST",
                "/api/auth/workspaces",
                201,
                json={"name": "Empty Synthetic Isolation Tenant"},
            ).json()["id"]
            expect(owner, "POST", f"/api/auth/workspaces/{other}/switch")
            isolated = expect(owner, "GET", "/api/analytics").json()
            invariant["second_tenant_empty"] = (
                isolated["transactions"] == 0
                and isolated["cases"] == 0
                and expect(owner, "GET", "/api/customers").json() == []
            )
            invariant["cross_tenant_customer_refused"] = (
                owner.get("/api/customers/" + customer_ids[0]).status_code == 404
            )
            phase = "complete"
    except Exception:
        report["failure_phase"] = phase
        report["request_failures"] += 1
    finally:
        for client in clients:
            client.close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=15)
                report["server_stopped"] = True
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                report["server_stopped"] = False
        else:
            report["server_stopped"] = False
    report["latencies"] = latency_summary(samples)
    report["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    report["gate"] = gate(report, p95_ms)
    report["limits"] = (
        "Isolated synthetic HTTP run on the recorded machine. No browser, real customer data, full sanctions feeds, model/network providers, agent-worker throughput, 1-GB Oracle VM or partner workload acceptance was tested. Setup/correctness/evidence export are outside concurrent-read/ingestion latency samples. Test credentials, keys and databases remain private inside the run directory; do not publish that directory."
    )
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (directory / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--customers", type=int, default=100)
    parser.add_argument("--transactions", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--read-rounds", type=int, default=10)
    parser.add_argument("--p95-ms", type=int, default=2000)
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve:
        serve(args.directory, args.port)
        return 0
    report = run(
        args.directory,
        customers=args.customers,
        transactions=args.transactions,
        concurrency=args.concurrency,
        read_rounds=args.read_rounds,
        p95_ms=args.p95_ms,
    )
    print(
        json.dumps(
            {
                "gate": report["gate"],
                "elapsed_seconds": report["elapsed_seconds"],
                "failure_phase": report.get("failure_phase"),
                "report_sha256": report["report_sha256"],
            }
        )
    )
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""Isolated synthetic replay using the production investigation runner and budgets."""

import asyncio
import json
import os
import secrets
from pathlib import Path

import httpx

from agents import AgentEngine
from auth import Hub, Setup
from models import PolicyInput
from operations import Operations
from product_models import CaseInput, CustomerInput, MonitorTransaction
from providers import PROMPT_VERSION
from runtime import InstallationLock
from scorecards import Dataset, MAX_DATASET_BYTES, scorecard, sha
from store import Store, now


def write_private(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


def load_dataset(path):
    path = Path(path)
    if path.stat().st_size > MAX_DATASET_BYTES:
        raise ValueError("Dataset exceeds the 4 MB input bound.")
    return Dataset.model_validate_json(path.read_bytes())


async def replay(dataset, settings, destination, *, transport=None, interval_seconds=3):
    if not 0 <= interval_seconds <= 60:
        raise ValueError("Replay interval must be between zero and 60 seconds.")
    if dataset.origin != "synthetic":
        raise ValueError(
            "This isolated seeder only supports synthetic data and synthetic screening. Historical evaluation requires real archived source evidence."
        )
    if len(dataset.cases) > settings.agent_daily_runs:
        raise ValueError(
            "The dataset exceeds the configured daily run budget; explicitly configure a sufficient evaluation budget before replay."
        )
    # Preflight before creating any artifact or making a model request.
    key = settings.groq_api_key.get_secret_value().strip()
    if not key or key.startswith(("your", "gsk_your", "replace")):
        raise ValueError(
            "Configure GROQ_API_KEY before replay; no substitute answers are generated."
        )
    destination = Path(destination).resolve()
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    isolated = settings.model_copy(
        update={
            "database_path": destination / "data" / "evaluation.db",
            "security_key_path": destination / "private-installation-key",
            "checkpoint_directory": destination / "checkpoints",
            "deployment_mode": "local",
            "cookie_secure": False,
        }
    )
    write_private(destination / "dataset.json", dataset.model_dump(mode="json"))
    write_private(
        destination / "replay-manifest.json",
        {
            "dataset_sha256": sha(dataset.model_dump(mode="json")),
            "model": isolated.groq_model,
            "model_revision": isolated.groq_model_revision,
            "prompt_version": PROMPT_VERSION,
            "run_budget": isolated.agent_daily_runs,
            "execution_mode": "test_transport" if transport else "live_provider",
            "screening": "Synthetic locally supplied feed. No official sanctions status is measured.",
            "started_at": now(),
        },
    )
    with InstallationLock(isolated.database_path.parent):
        hub = Hub(isolated)
        actor, workspace = hub.setup(
            Setup(
                email="evaluation@example.invalid",
                password=secrets.token_urlsafe(40),
                name="Synthetic evaluation runner",
                workspace="Isolated synthetic evaluation",
                bootstrap_token=hub.bootstrap_file.read_text().strip(),
            )
        )
        # Only this fresh, exclusively created installation may initialize storage.
        # Hub.store deliberately refuses replacing missing registered databases.
        Store(isolated.database_path, isolated)
        store = hub.store(workspace)
        ops = Operations(store)
        ops.save(
            "preferences",
            {"enabled_sources": ["ofac"], "monitoring_enabled": False},
            actor,
        )
        store.save_policy(PolicyInput(**dataset.policy.model_dump()))
        feed = {
            "entries": [],
            "count": 0,
            "published_at": now(),
            "fetched_at": now(),
            "url": "urn:policylens:synthetic-evaluation-feed",
        }
        feed["sha256"] = sha(feed)
        store.save_source("ofac", feed)
        jobs = {}
        async with httpx.AsyncClient(
            transport=transport, follow_redirects=False
        ) as client:
            engine = AgentEngine(hub, isolated, client)
            for index, label in enumerate(dataset.cases):
                if index and interval_seconds and transport is None:
                    await asyncio.sleep(interval_seconds)
                # Only whitelisted evidence fields cross into the workspace. Label,
                # label rationale/reference and category never enter agent context.
                customer = ops.save_customer(
                    CustomerInput(**label.customer.model_dump()), actor
                )
                case = ops.new_case(
                    CaseInput(
                        customer_id=customer["id"],
                        title=label.title,
                        description=label.description,
                    ),
                    actor,
                )
                for transaction in label.transactions:
                    ops.ingest(
                        MonitorTransaction(
                            **{
                                **transaction.model_dump(),
                                "customer_id": customer["id"],
                            }
                        ),
                        actor,
                    )
                queued = engine.enqueue(store, "investigation", case["id"], actor)
                claimed = engine.claim(store)
                if not claimed or claimed["id"] != queued["id"]:
                    raise RuntimeError(
                        "The isolated replay queue changed unexpectedly."
                    )
                await engine.execute(workspace, claimed)
                job = engine.get(store, queued["id"])
                if job["state"] not in ("completed", "failed"):
                    raise RuntimeError(
                        "Replay ended without a terminal run; no scorecard was published."
                    )
                jobs[label.id] = job
                write_private(destination / ("run-" + label.id + ".json"), job)
                if job["payload"].get("error", {}).get("code") in (
                    "ai_request_rejected",
                    "groq_access_denied",
                    "groq_rate_limited",
                ):
                    write_private(
                        destination / "replay-stopped.json",
                        {
                            "stopped_at": now(),
                            "retained_runs": len(jobs),
                            "labeled_cases": len(dataset.cases),
                            "error_code": job["payload"]["error"]["code"],
                            "scorecard_published": False,
                        },
                    )
                    raise RuntimeError(
                        "Provider configuration or capacity stopped replay. The failed run was retained; no partial scorecard was published."
                    )
            report = scorecard(
                dataset,
                jobs,
                execution_mode="test_transport" if transport else "live_provider",
            )
            write_private(destination / "scorecard.json", report)
            return report

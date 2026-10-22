"""Replay labeled synthetic cases in a NEW isolated workspace; never change pilot data."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from config import Settings  # noqa: E402
from evaluation_replay import load_dataset, replay  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--daily-run-budget", type=int)
    parser.add_argument("--model")
    parser.add_argument("--model-revision")
    parser.add_argument("--interval-seconds", type=float, default=3)
    args = parser.parse_args()
    updates = {}
    for argument, setting in (
        ("daily_run_budget", "agent_daily_runs"),
        ("model", "groq_model"),
        ("model_revision", "groq_model_revision"),
    ):
        if getattr(args, argument) is not None:
            updates[setting] = getattr(args, argument)
    try:
        settings = Settings(**updates)
        dataset = load_dataset(args.dataset)
        report = asyncio.run(
            replay(
                dataset, settings, args.output, interval_seconds=args.interval_seconds
            )
        )
    except Exception as exc:
        # Provider/client exceptions can contain private inputs. Keep terminal output
        # limited to known validation messages and exception type; artifacts preserve runs.
        print(
            json.dumps({"completed": False, "error_type": type(exc).__name__}),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "completed": True,
                "output": str(args.output.resolve()),
                "metrics": report["metrics"],
                "gate": report["gate"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Recompute a retained evaluation against an independently trusted report digest."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from evaluation_artifacts import verify_directory  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--scorecard-sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify_directory(args.directory, trusted_digest=args.scorecard_sha256)
    except Exception as error:
        print(json.dumps({"valid": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result["verification"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

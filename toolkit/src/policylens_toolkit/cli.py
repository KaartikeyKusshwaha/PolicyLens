import argparse
import json
import sys
from pathlib import Path

from .client import PolicyLens, PolicyLensError


def main():
    parser = argparse.ArgumentParser(
        description="Governed PolicyLens tools. Credentials come from a private file or environment."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list-tools")
    call = commands.add_parser("call")
    call.add_argument("tool")
    call.add_argument(
        "--arguments",
        type=Path,
        help="JSON object file; otherwise read JSON from stdin.",
    )
    args = parser.parse_args()
    try:
        with PolicyLens.from_environment() as client:
            if args.command == "list-tools":
                result = client.list_tools()
            else:
                with (
                    args.arguments.open(encoding="utf-8")
                    if args.arguments
                    else _stdin() as stream
                ):
                    arguments = json.load(stream)
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object.")
                result = client.call(args.tool, **arguments)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PolicyLensError, ValueError, OSError) as exc:
        print(
            json.dumps(
                {
                    "error": getattr(exc, "code", "configuration_or_input_error"),
                    "message": str(exc),
                }
            ),
            file=sys.stderr,
        )
        return 1


class _stdin:
    def __enter__(self):
        return sys.stdin

    def __exit__(self, *_):
        return False


if __name__ == "__main__":
    sys.exit(main())

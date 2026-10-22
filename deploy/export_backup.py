"""Read-only exporter for the newest verified snapshot. Run through verified SSH."""

import io
import re
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from recovery import verify_snapshot  # noqa: E402
from config import Settings  # noqa: E402

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024


def export_snapshot(root=Path("/var/backups/policylens"), settings=None):
    snapshots = sorted(
        (
            path
            for path in root.iterdir()
            if re.fullmatch(r"snapshot-\d{8}T\d{6}Z", path.name)
            and path.is_dir()
            and not path.is_symlink()
        ),
        reverse=True,
    )
    if not snapshots:
        raise ValueError("No daily snapshot is available.")
    # Never silently fall back to an older snapshot when the newest is corrupt.
    snapshot = snapshots[0]
    manifest = verify_snapshot(snapshot, settings)
    files = ["manifest.json", *[item["path"] for item in manifest["files"]]]
    if (
        sum((snapshot / relative).stat().st_size for relative in files)
        > MAX_ARCHIVE_BYTES
    ):
        raise ValueError("Snapshot exceeds the off-machine transfer bound.")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for relative in files:
            path = snapshot / relative
            if path.is_symlink() or not path.resolve().is_relative_to(
                snapshot.resolve()
            ):
                raise ValueError("Snapshot files must be regular local files.")
            archive.add(path, arcname=relative, recursive=False)
    payload = stream.getvalue()
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Compressed snapshot exceeds the off-machine transfer bound.")
    return payload


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(export_snapshot(settings=Settings()))
    except Exception:
        # No database contents, secret paths or raw exception details in remote logs.
        print(
            "PolicyLens snapshot export failed; inspect the backup service.",
            file=sys.stderr,
        )
        sys.exit(1)

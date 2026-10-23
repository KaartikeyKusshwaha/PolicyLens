"""Read-only, explicit-root copy discovery. Hashes do not establish ownership/erasure."""

import hashlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from operations import canonical

SCHEMA = "policylens.copy-discovery.v1"
MAX_FILES = 10000
MAX_DIRECTORIES = 2000
MAX_DEPTH = 100
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
MAX_REPORT_BYTES = 8 * 1024 * 1024


def unchanged(value):
    identity = (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_nlink,
    )
    # Windows lstat and CRT fstat expose different ctime semantics on some
    # filesystems. Modification time and stable handle identity remain checked;
    # Unix ctime additionally detects metadata/content changes there.
    return identity + ((value.st_ctime_ns,) if os.name != "nt" else ())


def safe_stat(path, root):
    value = path.lstat()
    if (
        stat.S_ISLNK(value.st_mode)
        or getattr(value, "st_file_attributes", 0) & 0x400
        or path.resolve(strict=True) != path
        or not path.is_relative_to(root)
    ):
        raise ValueError(
            "Copy inventory refuses symlinks, junctions or redirected paths"
        )
    return value


def scan(roots):
    if not 1 <= len(roots) <= 32:
        raise ValueError("Select 1–32 explicit discovery directories")
    selected = [Path(root).absolute() for root in roots]
    for index, root in enumerate(selected):
        if not stat.S_ISDIR(safe_stat(root, root).st_mode):
            raise ValueError("Discovery roots must be regular directories")
        if any(
            root.is_relative_to(other) or other.is_relative_to(root)
            for other in selected[:index]
        ):
            raise ValueError("Discovery roots must not duplicate or overlap")
    started = datetime.now(timezone.utc).isoformat()
    files, observed, total, directory_count = [], [], 0, 0
    for root_index, root in enumerate(selected):
        stack = [(root, 0)]
        while stack:
            directory, depth = stack.pop()
            directory_count += 1
            if directory_count > MAX_DIRECTORIES or depth > MAX_DEPTH:
                raise ValueError("Complete discovery exceeds its directory/depth bound")
            before = safe_stat(directory, root)
            observed.append((directory, root, unchanged(before)))
            entries = []
            with os.scandir(directory) as iterator:
                for entry in iterator:
                    if len(entries) >= MAX_FILES + MAX_DIRECTORIES:
                        raise ValueError("Discovery directory exceeds its entry bound")
                    entries.append(entry.name)
            for name in sorted(entries):
                path = directory / name
                value = safe_stat(path, root)
                if stat.S_ISDIR(value.st_mode):
                    stack.append((path, depth + 1))
                    continue
                if not stat.S_ISREG(value.st_mode):
                    raise ValueError("Copy inventory refuses nonregular files")
                if (
                    len(files) >= MAX_FILES
                    or value.st_size > MAX_FILE_BYTES
                    or total + value.st_size > MAX_TOTAL_BYTES
                ):
                    raise ValueError("Complete discovery exceeds its file/byte bound")
                descriptor = os.open(
                    path,
                    os.O_RDONLY
                    | getattr(os, "O_BINARY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                )
                with os.fdopen(descriptor, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not stat.S_ISREG(opened.st_mode) or unchanged(
                        opened
                    ) != unchanged(value):
                        raise ValueError("Discovery file changed before reading")
                    digest, size = hashlib.sha256(), 0
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        size += len(block)
                        if (
                            size > value.st_size
                            or size > MAX_FILE_BYTES
                            or total + size > MAX_TOTAL_BYTES
                        ):
                            raise ValueError(
                                "Discovery file grew or exceeded byte capacity"
                            )
                        digest.update(block)
                    if size != value.st_size or unchanged(
                        os.fstat(stream.fileno())
                    ) != unchanged(value):
                        raise ValueError("Discovery file changed while reading")
                observed.append((path, root, unchanged(value)))
                total += size
                files.append(
                    {
                        "root_index": root_index,
                        "relative_path": path.relative_to(root).as_posix(),
                        "bytes": size,
                        "sha256": digest.hexdigest(),
                        "modified_at": datetime.fromtimestamp(
                            value.st_mtime, timezone.utc
                        ).isoformat(),
                        "link_count": value.st_nlink,
                        "shared_link_review_required": value.st_nlink > 1,
                    }
                )
    # Detect directory additions/removals and file changes occurring after their
    # individual scan. This is an observed filesystem inventory, not an OS snapshot.
    for path, root, previous in observed:
        if unchanged(safe_stat(path, root)) != previous:
            raise ValueError(
                "Discovery input changed before the complete inventory finished"
            )
    files.sort(key=lambda item: (item["root_index"], item["relative_path"]))
    value = {
        "schema": SCHEMA,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "complete_for_selected_roots": True,
        "roots": [str(root) for root in selected],
        "files": files,
        "directories": directory_count,
        "total_bytes": total,
        "limits": "Metadata and byte hashes for the explicitly selected accessible roots only. No customer-content inspection, ownership/category inference, legal retention decision, deletion, removal verification or complete-system discovery. Unselected/remote/downstream/media copies remain unknown. Matching hashes do not prove shared custody or permission to delete. Paths and metadata are private. This is not an atomic filesystem snapshot or protection against a hostile host.",
    }
    value["inventory_sha256"] = hashlib.sha256(canonical(value).encode()).hexdigest()
    if len(canonical(value).encode()) > MAX_REPORT_BYTES:
        raise ValueError("Complete discovery report exceeds its byte bound")
    return value


def export(roots, output):
    output = Path(output).absolute()
    if (
        output.exists()
        or output.is_symlink()
        or output.parent.resolve(strict=True) != output.parent
    ):
        raise ValueError(
            "Discovery output requires a new file with a nonredirected existing parent"
        )
    selected = [Path(root).absolute() for root in roots]
    if any(output.is_relative_to(root) for root in selected):
        raise ValueError("Keep the discovery report outside inventoried roots")
    value = scan(roots)
    content = (canonical(value) + "\n").encode()
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "files": len(value["files"]),
        "directories": value["directories"],
        "total_bytes": value["total_bytes"],
        "inventory_sha256": value["inventory_sha256"],
        "report_sha256": hashlib.sha256(content).hexdigest(),
        "no_files_removed": True,
        "complete_system_discovery_proven": False,
    }

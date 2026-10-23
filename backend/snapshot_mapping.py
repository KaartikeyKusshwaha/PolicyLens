"""Match archive tenant files to the captured identity database, across OSes."""

from pathlib import PurePosixPath, PureWindowsPath


def verify_workspace_mapping(manifest, organizations):
    mappings = manifest.get("organization_paths")
    if not isinstance(mappings, dict) or not mappings:
        raise ValueError("Snapshot workspace mappings are missing")
    organizations = dict(organizations)
    if set(mappings) != set(organizations):
        raise ValueError(
            "Snapshot workspace mappings do not match the identity database"
        )
    if any(not isinstance(value, str) for value in mappings.values()):
        raise ValueError("Invalid snapshot workspace path")
    if (
        len(set(mappings.values())) != len(mappings)
        or "identity.db" in mappings.values()
    ):
        raise ValueError(
            "Snapshot workspace files must be distinct from each other and identity"
        )
    names = [item["path"] for item in manifest["files"]]
    if len(set(names)) != len(names) or set(names) != {
        "identity.db",
        *mappings.values(),
    }:
        raise ValueError(
            "Snapshot files do not exactly cover identity and workspace mappings"
        )
    roots = set()
    for workspace_id, relative in mappings.items():
        archive_path = PurePosixPath(relative)
        if (
            archive_path.is_absolute()
            or ".." in archive_path.parts
            or "\\" in relative
            or archive_path.as_posix() != relative
            or not archive_path.parts
        ):
            raise ValueError("Snapshot workspace path is not a normalized archive path")
        saved = organizations[workspace_id]
        if not isinstance(saved, str):
            raise ValueError("Invalid identity workspace path")
        windows = bool(PureWindowsPath(saved).drive)
        source = PureWindowsPath(saved) if windows else PurePosixPath(saved)
        if not source.is_absolute():
            raise ValueError("Identity workspace paths must be absolute")
        parts = (
            tuple(part.casefold() for part in source.parts) if windows else source.parts
        )
        suffix = (
            tuple(part.casefold() for part in archive_path.parts)
            if windows
            else archive_path.parts
        )
        if len(parts) <= len(suffix) or parts[-len(suffix) :] != suffix:
            raise ValueError(
                "Snapshot workspace mapping points to a different identity database file"
            )
        roots.add((windows, parts[: -len(suffix)]))
    if len(roots) != 1:
        raise ValueError(
            "Snapshot workspace mappings do not share the captured installation root"
        )

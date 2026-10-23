import uuid

from deletion_guard import export_guard


def guard_arguments(settings, directory):
    path = directory / ("restore-guard-" + uuid.uuid4().hex + ".json")
    result = export_guard(settings, path)
    return {"deletion_guard_path": path, "trusted_guard_sha256": result["sha256"]}

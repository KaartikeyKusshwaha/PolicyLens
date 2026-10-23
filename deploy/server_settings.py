"""Load the fixed private environment for root-run SSH export commands."""

import os
import stat
from pathlib import Path

from config import Settings


def load_server_settings(path=Path("/etc/policylens.env")):
    path = Path(path)
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or path.resolve() != path.absolute()
        or (os.name != "nt" and (info.st_uid != 0 or info.st_mode & 0o077))
    ):
        raise ValueError("Private server environment unavailable")
    # Explicit file selection: SSH does not inherit systemd EnvironmentFile.
    # Keep dotenv values inside Settings; never print or export secret contents.
    return Settings(_env_file=path)

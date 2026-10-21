"""Install, build, and serve PolicyLens locally: python run.py."""

import hashlib
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(command, cwd=ROOT):
    subprocess.run(command, cwd=cwd, check=True)


def digest(paths):
    return hashlib.sha256(b"".join(path.read_bytes() for path in paths)).hexdigest()


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError("Python 3.11 or newer is required.")
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    node = shutil.which("node")
    if not npm or not node:
        raise RuntimeError(
            "Install Node.js 22.12+ (including npm), then run this command again."
        )
    version = (
        subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
    )
    if tuple(map(int, version.split(".")[:2])) < (22, 12):
        raise RuntimeError("Node.js 22.12 or newer is required.")
    virtual = ROOT / ".venv"
    python = virtual / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    if not python.exists():
        print("Creating the Python environment...", flush=True)
        venv.create(virtual, with_pip=True)
    requirements = ROOT / "backend/requirements.txt"
    stamp = virtual / ".policylens-dependencies"
    current = digest([requirements])
    if not stamp.exists() or stamp.read_text() != current:
        run([str(python), "-m", "pip", "install", "-r", str(requirements)])
        stamp.write_text(current)
    environment = ROOT / "backend/.env"
    if not environment.exists():
        shutil.copyfile(ROOT / "backend/.env.example", environment)
        print(
            "Created backend/.env. Add your free Groq key there to enable AI analysis.",
            flush=True,
        )
    frontend = ROOT / "frontend"
    node_stamp = frontend / "node_modules/.policylens-dependencies"
    node_current = digest([frontend / "package.json", frontend / "package-lock.json"])
    if not node_stamp.exists() or node_stamp.read_text() != node_current:
        run([npm, "ci"], cwd=frontend)
        node_stamp.write_text(node_current)
    run([npm, "run", "build"], cwd=frontend)
    print("\nPolicyLens: http://127.0.0.1:8000\nPress Ctrl+C to stop.\n", flush=True)
    run(
        [
            str(python),
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=ROOT / "backend",
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"PolicyLens could not start: {exc}", file=sys.stderr)
        sys.exit(1)

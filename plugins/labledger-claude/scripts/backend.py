"""Private plugin launcher. Reads one JSON request from stdin; no user commands."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def environment_path():
    requirements = (PLUGIN_ROOT / "runtime/requirements.txt").read_bytes()
    identity = requirements + str((sys.version_info[:2], sys.base_prefix)).encode()
    key = hashlib.sha256(identity).hexdigest()[:24]
    configured = os.environ.get("XDG_CACHE_HOME")
    base = (
        Path(configured)
        if configured and Path(configured).is_absolute()
        else Path.home() / ".cache"
    )
    return base / "labledger" / "runtimes" / key


def ready(environment):
    return (environment / "ready").is_file() and (environment / "bin/python").is_file()


def ensure_environment(install=True):
    environment = environment_path()
    if ready(environment):
        return environment
    if not install:
        return None
    environment.parent.mkdir(parents=True, exist_ok=True)
    with (environment.parent / f"{environment.name}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not ready(environment):
            # This is exclusively our incomplete, content-addressed runtime directory.
            if environment.exists():
                shutil.rmtree(environment)
            venv.EnvBuilder(with_pip=True, symlinks=True).create(environment)
            completed = subprocess.run(
                [
                    str(environment / "bin/python"),
                    "-I",
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-input",
                    "--requirement",
                    str(PLUGIN_ROOT / "runtime/requirements.txt"),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
            )
            if completed.returncode:
                raise RuntimeError(
                    "Could not prepare plugin dependencies. Check package-index/network access "
                    "in this session, then retry the skill. No project files were changed."
                )
            (environment / "ready").write_text("ready\n")
    return environment


def main():
    if sys.version_info < (3, 11):
        raise RuntimeError("Use Python 3.11 or newer for the plugin helper in this session")
    environment = ensure_environment()
    if Path(sys.prefix).resolve() != environment.resolve():
        # Replace the process so cancellation and runner identity remain accurate.
        os.execv(
            str(environment / "bin/python"),
            [
                str(environment / "bin/python"),
                "-I",
                "-B",
                str(Path(__file__).resolve()),
            ],
        )
    sys.path.insert(0, str(PLUGIN_ROOT / "runtime"))
    from labledger.backend import main as dispatch

    return dispatch()


if __name__ == "__main__":
    try:
        code = main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "code": 5, "error": str(error)}))
        code = 5
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "code": 130, "error": "Interrupted during runtime setup"}))
        code = 130
    raise SystemExit(code)

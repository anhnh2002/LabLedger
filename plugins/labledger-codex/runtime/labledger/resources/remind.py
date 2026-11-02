"""Optional host reminder. Never install dependencies or block session startup."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def main():
    try:
        helper = Path(__file__).with_name("backend.py")
        spec = importlib.util.spec_from_file_location("labledger_launcher", helper)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        environment = launcher.ensure_environment(install=False)
        if environment is None:
            return 0
        payload = json.loads(sys.stdin.read(65536) or "{}")
        if not isinstance(payload, dict) or not isinstance(payload.get("cwd"), str):
            return 0
        result = subprocess.run(
            [str(environment / "bin/python"), "-I", "-B", str(helper)],
            input=json.dumps(
                {
                    "operation": "_hook",
                    "root": str(Path(payload["cwd"]).resolve()),
                    "arguments": {"event": sys.argv[1]},
                    "payload": payload,
                }
            ),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode == 0:
            response = json.loads(result.stdout)
            if response["ok"]:
                print(json.dumps(response["result"]))
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired, IndexError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import difflib
import json
import subprocess
from importlib.resources import files

from .errors import Conflict, LedgerError, Prerequisite
from .schema import validate
from .storage import Store, digest, encoded


def resource(name):
    return files("labledger").joinpath("resources", name).read_text()


def git_metadata(root):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
        return result.stdout.decode(errors="replace").strip() if result.returncode == 0 else None

    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return {
        "commit": commit,
        "branch": git("branch", "--show-current"),
        "dirty": bool(status) if status is not None else None,
        "available": commit is not None,
    }


def managed(existing, body, name, baseline):
    start, end = (
        (f"# labledger:{name}:start", f"# labledger:{name}:end")
        if name == ".gitignore"
        else (f"<!-- labledger:{name}:start -->", f"<!-- labledger:{name}:end -->")
    )
    block = f"{start}\n{body.rstrip()}\n{end}"
    if start not in existing and end not in existing:
        return existing.rstrip() + ("\n\n" if existing.strip() else "") + block + "\n", block
    if existing.count(start) != 1 or existing.count(end) != 1:
        raise Conflict(f"Malformed managed block in {name}")
    left, right = existing.index(start), existing.index(end) + len(end)
    if right < left:
        raise Conflict(f"Malformed managed block in {name}")
    current = existing[left:right]
    if current != block and (baseline is None or digest(current.encode()) != baseline):
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(True),
                block.splitlines(True),
                fromfile="current",
                tofile="proposed",
            )
        )
        raise Conflict(f"User-edited managed block in {name}; reconcile manually:\n{diff}")
    return existing[:left] + block + existing[right:], block


def initialize(root, payload=None, dry_run=False):
    store = Store(root)
    payload = payload or {}
    validate(payload, "init_input")
    unknown = set(payload) - {"name", "charter", "research_dir", "artifacts_dir"}
    if unknown:
        raise LedgerError(f"Unknown init inputs: {sorted(unknown)}")
    if not store.config and (not payload.get("name") or not payload.get("charter")):
        raise Prerequisite(
            "Initial setup requires a payload with name and the agreed charter Markdown"
        )
    if store.config:
        for key in ("name", "research_dir", "artifacts_dir"):
            if key in payload and payload[key] != store.config["project"][key]:
                raise Conflict(
                    f"Existing {key} differs; init does not migrate project configuration"
                )
        config = store.config
        config_bytes = (store.meta / "config.toml").read_bytes()
    else:
        import tomllib

        config_text = resource("config.toml").replace('"PROJECT_NAME"', json.dumps(payload["name"]))
        for name, default in (("research_dir", "research"), ("artifacts_dir", "artifacts/runs")):
            config_text = config_text.replace(
                f'{name} = "{default}"', f"{name} = {json.dumps(payload.get(name, default))}"
            )
        config = tomllib.loads(config_text)
        validate(config, "config")
        config_bytes = config_text.encode()
        store.research = store.path(config["project"]["research_dir"])
        store.artifacts = store.path(config["project"]["artifacts_dir"])
        paths = (store.research, store.artifacts, store.meta)
        if (
            len(set(paths)) != 3
            or store.root in paths
            or any(a != b and a.is_relative_to(b) for a in paths for b in paths)
        ):
            raise LedgerError(
                "Research, artifact and metadata paths must be distinct, non-overlapping subdirectories"
            )

    def proposed():
        changes = {store.meta / "config.toml": config_bytes}
        charter = store.research / "CHARTER.md"
        if charter.exists():
            if "charter" in payload and charter.read_text().strip() != payload["charter"].strip():
                raise Conflict("Existing charter differs; init will not overwrite research policy")
        else:
            changes[charter] = payload["charter"].rstrip() + "\n"
        status = store.research / "STATUS.md"
        if not status.exists():
            changes[status] = (
                "# Research status\n\nAsk LabLedger in this session to inspect tasks and outstanding analysis.\n"
            )
        baseline_path = store.meta / "managed.json"
        baselines = json.loads(baseline_path.read_text()) if baseline_path.exists() else {}
        updated = dict(baselines)
        instructions = resource("conventions.md").replace(
            "RESEARCH_DIR", store.relative(store.research)
        )
        for name, content in (
            ("AGENTS.md", instructions),
            ("CLAUDE.md", instructions),
            (
                ".gitignore",
                f"/{store.relative(store.artifacts)}/\n/.labledger/cache/\n/.labledger/transactions/\n",
            ),
        ):
            path = store.root / name
            text, block = managed(
                path.read_text() if path.exists() else "", content, name, baselines.get(name)
            )
            changes[path] = text
            updated[name] = digest(block.encode())
        changes[baseline_path] = encoded(updated)
        changes[store.meta / "schemas/v1.json"] = resource("schema.json")
        if not (store.meta / "policy/current.json").exists():
            from .policy import initial_policy

            charter_text = (
                charter.read_text() if charter.exists() else payload["charter"].rstrip() + "\n"
            )
            policy = initial_policy(config, charter_text)
            changes[store.meta / "policy/current.json"] = encoded(policy)
            history = store.meta / "policy/history/1.json"
            if history.exists():
                raise Conflict(
                    "Policy history exists without its current pointer; inspect before initializing"
                )
            changes[history] = encoded(policy)
        return {
            path: data
            for path, data in changes.items()
            if not path.exists()
            or path.read_bytes() != (data.encode() if isinstance(data, str) else data)
        }

    # No lock or journal creation at all for dry-run.
    if dry_run:
        changes = proposed()
    else:
        with store.locked():
            changes = proposed()
            store.commit(changes)
    return {
        "dry_run": dry_run,
        "files": [
            {
                "path": store.relative(path),
                "action": "update" if path.exists() and dry_run else "write",
                "content": data.decode() if isinstance(data, bytes) else data,
            }
            for path, data in changes.items()
        ],
    }

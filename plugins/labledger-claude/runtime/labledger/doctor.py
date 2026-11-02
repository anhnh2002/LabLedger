import json
import platform
import shutil
import subprocess

from . import __version__
from .errors import LedgerError
from .memory import dependent_warnings
from .runner import file_digest, inspect_execution
from .schema import validate
from .storage import KINDS
from .workflows import check_handoff, check_plan


def capabilities():
    result = {
        "backend_version": __version__,
        "platform": platform.system(),
        "runner": "supported" if platform.system() in ("Darwin", "Linux") else "unsupported",
        "budget_enforcement": {
            "run_count": True,
            "wall_time": True,
            "tokens": False,
            "cost": False,
        },
        "approval_authentication": False,
        "restricted_storage_isolation": False,
        "hooks": "optional_reminders",
    }
    for host in ("codex", "claude"):
        binary = shutil.which(host)
        version = None
        if binary:
            try:
                completed = subprocess.run(
                    [binary, "--version"], capture_output=True, text=True, timeout=5
                )
                version = completed.stdout.strip() if completed.returncode == 0 else None
            except (OSError, subprocess.TimeoutExpired):
                pass
        result[host] = {
            "installed": binary is not None,
            "version": version,
            "workflow_validation": "manual_required",
            "hooks": "partial: manually installed desktop plugins only"
            if host == "codex"
            else "optional: verify installed host capabilities",
        }
    return result


def doctor(store, restricted=False):
    errors, warnings, records = [], [], []
    with store.locked(repair=True):
        pending = store.pending()
        if pending:
            errors.append(
                {
                    "code": "incomplete_transaction",
                    "message": "Use the doctor skill to inspect and explicitly repair this operation",
                    "count": len(pending),
                }
            )
        if not pending:
            for kind, (folder, _) in KINDS.items():
                for path in sorted((store.research / folder).glob("*/record.json")):
                    try:
                        record = store.read(kind, path.parent.name)
                        if record["visibility"] == "restricted_evaluation" and not restricted:
                            # Validate internally, but do not expose restricted identity or wording.
                            label = "restricted record"
                        else:
                            label = record["id"]
                        validate(record, kind)
                        store.verify(record)
                        history = store.read(kind, record["id"], record["revision"])
                        if record != history:
                            raise LedgerError("Current record differs from immutable history")
                        for revision in range(1, record["revision"] + 1):
                            store.read(kind, record["id"], revision)
                        records.append(record)
                        if record["visibility"] == "restricted_evaluation" and not restricted:
                            continue
                        if kind == "task":
                            if record.get("handoff"):
                                warnings.extend(
                                    {"id": label, "code": "stale_handoff", "message": issue}
                                    for issue in check_handoff(store, record)
                                )
                            if record.get("plan"):
                                warnings.extend(
                                    {"id": label, "code": "stale_plan", "message": issue}
                                    for issue in check_plan(store, record)
                                )
                        if kind == "run":
                            observed = inspect_execution(record)
                            if observed["state"] not in ("terminal", "live"):
                                warnings.append(
                                    {
                                        "id": label,
                                        "code": "reconcile_required",
                                        "execution": observed,
                                    }
                                )
                            if record["analysis_status"] == "pending":
                                warnings.append({"id": label, "code": "analysis_pending"})
                            for snapshot in record.get("inputs", {}).get("snapshots", []):
                                if snapshot.get("availability") == "unavailable":
                                    continue
                                captured = store.path(snapshot["snapshot"])
                                if (
                                    not captured.is_file()
                                    or file_digest(captured) != snapshot["checksum"]
                                ):
                                    errors.append(
                                        {
                                            "id": label,
                                            "code": "input_snapshot_missing_or_changed",
                                            "path": snapshot["snapshot"],
                                        }
                                    )
                        retired = {
                            event["path"]
                            for event in record.get("annotations", [])
                            if event.get("kind") == "artifact_tombstone" and "path" in event
                        }
                        for ref in store.references(record):
                            if (
                                ref.get("checksum")
                                and ref.get("path")
                                and ref.get("availability", "available") == "available"
                                and ref["path"] not in retired
                            ):
                                artifact = store.path(ref["path"])
                                if artifact.is_file() and file_digest(artifact) != ref["checksum"]:
                                    errors.append(
                                        {
                                            "id": label,
                                            "code": "checksum_mismatch",
                                            "path": ref["path"],
                                        }
                                    )
                    except (LedgerError, ValueError, OSError) as error:
                        try:
                            raw = json.loads(path.read_text())
                            is_restricted = (
                                not isinstance(raw, dict)
                                or raw.get("visibility") == "restricted_evaluation"
                            )
                        except (ValueError, OSError):
                            is_restricted = True
                        errors.append(
                            {
                                "code": "invalid_record",
                                "path": "restricted record"
                                if is_restricted and not restricted
                                else store.relative(path),
                                "message": "Restricted record failed validation"
                                if is_restricted and not restricted
                                else str(error),
                            }
                        )
            warnings.extend(dependent_warnings(store, records, restricted))
        charter = store.research / "CHARTER.md"
        if not charter.is_file():
            errors.append({"code": "missing_charter"})
        policy_path = store.meta / "policy/current.json"
        if policy_path.exists() and not pending:
            try:
                policy = json.loads(policy_path.read_text())
                validate(policy, "policy_snapshot")
                if policy["config"] != store.config or policy["charter"] != charter.read_text():
                    warnings.append(
                        {
                            "code": "unrecorded_policy_change",
                            "message": "Use policy update with actual approval evidence to preserve charter/config history",
                        }
                    )
                for revision in range(1, policy["revision"] + 1):
                    entry = json.loads(
                        (store.meta / "policy/history" / f"{revision}.json").read_text()
                    )
                    validate(entry, "policy_snapshot")
                    if entry["revision"] != revision or (
                        revision == policy["revision"] and entry != policy
                    ):
                        raise LedgerError("Policy history mismatch")
            except (LedgerError, OSError, ValueError) as error:
                errors.append({"code": "invalid_policy_history", "message": str(error)})
        elif not policy_path.exists():
            warnings.append(
                {
                    "code": "missing_policy_baseline",
                    "message": "Run init to record the current charter/config baseline",
                }
            )
        for name in ("AGENTS.md", "CLAUDE.md"):
            path = store.root / name
            if not path.exists() or f"<!-- labledger:{name}:start -->" not in path.read_text():
                warnings.append({"code": "missing_instructions", "path": name})
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "capabilities": capabilities(),
    }

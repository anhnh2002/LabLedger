import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

from .errors import Conflict, LedgerError, Prerequisite
from .project import git_metadata
from .storage import digest, encoded, now
from .workflows import check_plan, dependency_issues

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def file_digest(path):
    import hashlib

    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def identity(pid=None):
    try:
        process = psutil.Process(pid)
        return {
            "pid": process.pid,
            "created_at": process.create_time(),
            "hostname": platform.node(),
            "boot_time": psutil.boot_time(),
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def process_state(value):
    if not value or value.get("hostname") != platform.node() or "created_at" not in value:
        return "unknown"
    if value.get("boot_time") != psutil.boot_time():
        return "stopped"
    try:
        process = psutil.Process(value["pid"])
        if process.create_time() != value["created_at"]:
            return "stopped"
        return (
            "stopped" if process.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD) else "live"
        )
    except psutil.NoSuchProcess:
        return "stopped"
    except (psutil.AccessDenied, KeyError):
        return "unknown"


def manifest_changes(store, record):
    artifact = store.path(store.relative(store.artifacts / record["id"]))
    return {
        artifact / "manifest.json": encoded(
            {
                "generated_from": store.relative(store.location("run", record["id"])),
                "record": record,
            }
        )
    }


def update_run(store, record, patch):
    return store.update(
        "run",
        record["id"],
        patch,
        record["revision"],
        extra=lambda value: manifest_changes(store, value),
        internal=True,
    )


def validate_protocol(store, experiment):
    if experiment["status"] not in ("approved", "running"):
        raise Prerequisite("Run requires an approved experiment protocol")
    store.verify(experiment)
    issues = dependency_issues(store, experiment["decision_refs"])
    if issues:
        raise Conflict("; ".join(issues))
    if experiment.get("task_id"):
        task = store.read("task", experiment["task_id"])
        if task["status"] not in ("implementing", "evaluating"):
            raise Prerequisite(
                "Task must be implementing or evaluating before experiment execution"
            )
        issues = check_plan(store, task)
        if issues:
            raise Conflict("; ".join(issues))
    held_out = any(item["role"] == "held_out_test" for item in experiment["dataset_refs"])
    if held_out:
        store.require(experiment, "freeze")
        store.require(
            experiment["freeze"], "code", "config", "evaluator", "metric", "selection_rule"
        )
        if experiment["visibility"] != "restricted_evaluation":
            raise Prerequisite("Held-out experiments must use restricted_evaluation visibility")
        exposed = {
            (item["dataset_id"], item["dataset_version"])
            for item in store.all("exposure")
            if item["used_for_development"]
        }
        if any(
            (item["id"], item["version"]) in exposed
            for item in experiment["dataset_refs"]
            if item["role"] == "held_out_test"
        ):
            raise Prerequisite(
                "Known development exposure prevents treating this dataset version as a fresh holdout"
            )
    return held_out


def safe_capture(store, relative):
    path = store.path(relative)
    if not path.is_file():
        raise LedgerError(f"Capture input is not a file: {relative}")
    if path.is_relative_to(store.artifacts) or path.is_relative_to(store.meta / "transactions"):
        raise LedgerError("Run outputs and transaction journals cannot be captured as inputs")
    sensitive = (".env", "credentials", "id_rsa", "id_ed25519", ".pem", ".key")
    if any(
        part.lower().startswith(sensitive) or part.lower().endswith((".pem", ".key"))
        for part in path.parts
    ):
        raise Prerequisite(f"Refusing sensitive capture path: {relative}; supply a redacted input")
    return path


def group_active(process):
    if process.poll() is None:
        return True
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # A zombie-only group can produce EPERM on macOS.
    for member in psutil.process_iter(["pid", "status"]):
        try:
            if os.getpgid(member.pid) == process.pid and member.info["status"] not in (
                psutil.STATUS_ZOMBIE,
                psutil.STATUS_DEAD,
            ):
                return True
        except (ProcessLookupError, PermissionError, psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def terminate_group(process, grace=2.0):
    if not group_active(process):
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace
    # Workers may outlive the group leader. Kill the group after the grace period.
    while time.monotonic() < deadline:
        if not group_active(process):
            return
        time.sleep(0.05)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def start(
    store, experiment_id, argv, captures=(), parent=None, retry_reason=None, cwd=None, metadata=None
):
    if platform.system() not in ("Darwin", "Linux"):
        raise Prerequisite("Experiment execution supports macOS and Linux only")
    if not argv:
        raise LedgerError("Provide a nonempty argv array for the experiment")
    metadata = metadata or {}
    if set(metadata) - {"model", "environment", "inputs"}:
        raise LedgerError("Run metadata supports model, environment and inputs only")
    if any(not isinstance(value, dict) for value in metadata.values()):
        raise LedgerError("Model, environment and inputs metadata must be JSON objects")
    workdir = store.root if cwd in (None, ".") else store.path(cwd)
    if not workdir.is_dir():
        raise LedgerError("Working directory does not exist")
    capture_paths = [safe_capture(store, value) for value in captures]
    settings = store.config["experiments"]
    if capture_paths and not settings.get("capture_config_snapshot", True):
        raise Prerequisite("Input snapshots are disabled by project policy")
    with store.locked():
        experiment = store.read("experiment", experiment_id)
        held_out = validate_protocol(store, experiment)
        previous = [r for r in store.all("run") if r.get("experiment_id") == experiment_id]
        limit = experiment["budget"].get("max_runs")
        if limit is not None and len(previous) >= limit:
            raise Prerequisite(
                "Experiment run-count budget exhausted (including failures and retries)"
            )
        if bool(parent) != bool(retry_reason):
            raise LedgerError("Retry requires both parent and retry_reason")
        if parent:
            ancestor = store.read("run", parent)
            if (
                ancestor.get("experiment_id") != experiment_id
                or ancestor["execution_status"] not in TERMINAL
            ):
                raise Prerequisite("Retry parent must be a terminal run of the same experiment")
        execution = {"runner": identity(), "child": None, "launch_started": False}
        payload = {
            "experiment_id": experiment_id,
            "experiment_revision": experiment["revision"],
            "task_id": experiment.get("task_id"),
            "visibility": experiment["visibility"],
            "parent_run_id": parent,
            "execution_status": "queued",
            "research_outcome": "not_assessed",
            "analysis_status": "pending",
            "argv": list(argv),
            "cwd": store.relative(workdir) if workdir != store.root else ".",
            "started_at": None,
            "ended_at": None,
            "exit_code": None,
            "cancellation_reason": None,
            "execution": execution,
            "code": git_metadata(store.root)
            if settings.get("capture_git_metadata", True)
            else {
                "available": False,
                "commit": None,
                "branch": None,
                "dirty": None,
                "reason": "Capture disabled by policy",
            },
            "inputs": metadata.get("inputs", {}),
            "environment": {
                **metadata.get("environment", {}),
                "python": sys.version,
                "platform": platform.platform(),
            },
            "model": metadata.get("model", {}),
            "outputs": {},
            "accounting": {
                "duration_seconds": None,
                "tokens": None,
                "cost": None,
                "missing_reason": "No provider telemetry supplied",
            },
            "reproducibility_status": "partial",
            "missing_metadata": ["Input snapshots pending"],
            "budget_enforcement": {
                "max_runs": "enforced" if limit else "not_configured",
                "wall_time_seconds": "enforced"
                if experiment["budget"].get("wall_time_seconds")
                else "not_configured",
                "tokens": "unavailable" if "tokens" in experiment["budget"] else "not_configured",
                "cost": "unavailable" if "cost" in experiment["budget"] else "not_configured",
            },
        }
        if parent:
            payload["retry_reason"] = retry_reason
        record = store.create("run", payload, extra=lambda r: manifest_changes(store, r))
        if held_out:
            for dataset in experiment["dataset_refs"]:
                if dataset["role"] == "held_out_test":
                    store.create(
                        "exposure",
                        {
                            "task_id": experiment.get("task_id"),
                            "visibility": "restricted_evaluation",
                            "dataset_id": dataset["id"],
                            "dataset_version": dataset["version"],
                            "role": dataset["role"],
                            "purpose": "Confirmatory execution",
                            "details": f"Registered attempt {record['id']}; actual reads outside wrapper are unknown.",
                            "exposed_at": now(),
                            "experiment_refs": [store.ref(experiment)],
                            "used_for_development": False,
                        },
                    )

    artifact_dir = store.path(store.relative(store.artifacts / record["id"]))
    started = time.monotonic()
    process = None
    reason = None
    interruption = {"signal": None}
    handlers = {}

    def cancel(signum, _frame):
        interruption["signal"] = signum

    for signum in (signal.SIGINT, signal.SIGTERM):
        handlers[signum] = signal.signal(signum, cancel)
    try:
        snapshots = []
        for index, path in enumerate(capture_paths):
            destination = artifact_dir / "inputs" / f"{index}-{path.name}"
            # Stream copies: input size does not become runner RAM usage.
            import shutil

            destination.parent.mkdir(parents=True, exist_ok=True)
            with path.open("rb") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            snapshots.append(
                {
                    "path": store.relative(path),
                    "snapshot": store.relative(destination),
                    "checksum": file_digest(destination),
                    "size": destination.stat().st_size,
                }
            )
        missing = []
        if not record["code"]["available"]:
            missing.append("Git commit unavailable")
        if record["code"]["dirty"]:
            missing.append("Dirty repository: only explicitly captured files are preserved")
        if not snapshots:
            missing.append("No explicit config/input snapshots")
        if not any(
            Path(item["path"]).name
            in ("uv.lock", "poetry.lock", "requirements.txt", "environment.yml", "Dockerfile")
            for item in snapshots
        ):
            missing.append("Dependency lock or container snapshot unavailable")
        if not metadata.get("model"):
            missing.append("Model metadata not supplied; applicability unknown")
        for stream_name in ("stdout", "stderr"):
            if not settings.get(f"capture_{stream_name}", True):
                missing.append(f"{stream_name} capture disabled by project policy")
        inputs = {
            **record["inputs"],
            "snapshots": snapshots,
            "dataset_refs": experiment["dataset_refs"],
            "primary_metric": experiment["primary_metric"],
            "freeze": experiment.get("freeze"),
        }
        record = update_run(
            store,
            record,
            {
                "inputs": inputs,
                "missing_metadata": missing,
                "reproducibility_status": "partial" if missing else "complete",
            },
        )
        settings = store.config["experiments"]
        with (
            (artifact_dir / "stdout.log").open("wb") as stdout,
            (artifact_dir / "stderr.log").open("wb") as stderr,
        ):
            record = update_run(
                store,
                record,
                {"started_at": now()},
            )
            if interruption["signal"]:
                reason = "User interruption before process launch"
            elif (
                experiment["budget"].get("wall_time_seconds")
                and time.monotonic() - started >= experiment["budget"]["wall_time_seconds"]
            ):
                reason = "Wall-time budget exhausted during preparation; child not launched"
            else:
                record = update_run(
                    store, record, {"execution": {**execution, "launch_started": True}}
                )
                process = subprocess.Popen(
                    argv,
                    cwd=workdir,
                    stdin=subprocess.DEVNULL,
                    stdout=stdout if settings.get("capture_stdout", True) else subprocess.DEVNULL,
                    stderr=stderr if settings.get("capture_stderr", True) else subprocess.DEVNULL,
                    start_new_session=True,
                )
                execution = {
                    **execution,
                    "launch_started": True,
                    "child": identity(process.pid),
                    "process_group": process.pid,
                }
                record = update_run(
                    store, record, {"execution_status": "running", "execution": execution}
                )
                deadline = experiment["budget"].get("wall_time_seconds")
                while group_active(process):
                    if interruption["signal"]:
                        reason = f"User interruption: signal {interruption['signal']}"
                        terminate_group(process)
                        break
                    if deadline and time.monotonic() - started >= deadline:
                        reason = "Wall-time budget exhausted"
                        terminate_group(process)
                        break
                    time.sleep(0.05)
                process.wait()
            stdout.flush()
            stderr.flush()
            os.fsync(stdout.fileno())
            os.fsync(stderr.fileno())
        status = "cancelled" if reason else "completed" if process.returncode == 0 else "failed"
        exit_code = process.returncode if process else None
    except (OSError, LedgerError) as error:
        if process and process.poll() is None:
            terminate_group(process)
        status, exit_code = "failed", process.returncode if process else None
        reason = f"Runner failure: {error}"
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
    outputs = {
        "logs": [],
        "metrics": None,
        "capture_policy": {
            "stdout": store.config["experiments"].get("capture_stdout", True),
            "stderr": store.config["experiments"].get("capture_stderr", True),
        },
    }
    for name in ("stdout.log", "stderr.log"):
        path = artifact_dir / name
        if path.exists():
            outputs["logs"].append(
                {
                    "type": "artifact",
                    "path": store.relative(path),
                    "checksum": file_digest(path),
                    "size": path.stat().st_size,
                }
            )
    # Concurrent annotations can change the revision while the process runs.
    with store.locked():
        record = store.read("run", record["id"])
        record = update_run(
            store,
            record,
            {
                "execution_status": status,
                "exit_code": exit_code,
                "ended_at": now(),
                "cancellation_reason": reason,
                "outputs": outputs,
                "accounting": {
                    **record["accounting"],
                    "duration_seconds": time.monotonic() - started,
                },
            },
        )
    return record, 130 if interruption["signal"] else 0 if status == "completed" else 1


def inspect_execution(record):
    if record["execution_status"] in TERMINAL:
        return {
            "state": "terminal",
            "next_action": "Analyze pending results or inspect recorded evidence.",
        }
    execution = record.get("execution", {})
    runner = process_state(execution.get("runner"))
    child = process_state(execution.get("child"))
    group = "unknown"
    child_identity = execution.get("child") or {}
    if (
        child == "stopped"
        and child_identity.get("hostname") == platform.node()
        and child_identity.get("boot_time") == psutil.boot_time()
        and execution.get("process_group")
    ):
        group = "stopped"
        for member in psutil.process_iter(["pid", "status"]):
            try:
                if os.getpgid(member.pid) == execution["process_group"] and member.info[
                    "status"
                ] not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                    group = "live_members_unverified"
                    break
            except (ProcessLookupError, PermissionError, psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    if runner == "live":
        state = "live"
    elif child == "live":
        state = "orphan_live"
    elif group == "live_members_unverified":
        state = "unknown"  # Group ID alone cannot establish workers' identities after a crash.
    elif runner == "stopped" and (child == "stopped" or not execution.get("launch_started")):
        state = "stopped"
    else:
        state = "unknown"
    return {
        "state": state,
        "runner": runner,
        "child": child,
        "process_group": group,
        "next_action": "Inspect then use run reconcile; never automatically rerun."
        if state != "live"
        else "Observe the active runner.",
    }


def reconcile(store, identifier, expected, reason, confirm_stopped=False):
    with store.locked():
        record = store.read("run", identifier)
        if record["revision"] != expected:
            raise Conflict("Run changed before reconciliation")
        observed = inspect_execution(record)
        if observed["state"] in ("live", "orphan_live", "terminal"):
            raise Conflict(f"Cannot mark execution interrupted: {observed['state']}")
        if observed["state"] == "unknown" and not confirm_stopped:
            raise Prerequisite(
                "Execution identity is uncertain; inspect and provide confirm_stopped with evidence"
            )
        if not reason:
            raise LedgerError("Reconciliation requires an evidence/reason summary")
        annotations = record.get("annotations", []) + [
            {
                "kind": "reconciliation",
                "at": now(),
                "reason": reason,
                "observed": observed,
                "operator_confirmed_stopped": confirm_stopped,
            }
        ]
        return update_run(
            store,
            record,
            {
                "execution_status": "interrupted",
                "ended_at": now(),
                "cancellation_reason": reason,
                "annotations": annotations,
            },
        )


def annotate(store, identifier, patch, expected):
    from .schema import validate

    validate(patch, "analysis_input")
    with store.locked():
        record = store.read("run", identifier)
        if record["revision"] != expected:
            raise Conflict("Run changed before annotation")
        if set(patch) - {"analysis_status", "research_outcome", "analysis", "annotation"}:
            raise LedgerError(
                "Annotations may update interpretation only; raw execution metadata is immutable"
            )
        if record["execution_status"] not in TERMINAL and set(patch) - {"annotation"}:
            raise Prerequisite("Analyze only after execution is terminal")
        if patch.get("analysis_status") in ("analyzed", "deferred"):
            store.require(patch, "analysis")
            store.require(patch["analysis"], "summary")
        outcome = patch.get("research_outcome", record["research_outcome"])
        analysis_state = patch.get("analysis_status", record["analysis_status"])
        if outcome != "not_assessed":
            if analysis_state != "analyzed":
                raise Prerequisite("Assessed research outcomes require analyzed status")
            analysis = patch.get("analysis", record.get("analysis", {}))
            store.require(analysis, "summary", "evidence_refs")
            if "limitations" not in analysis or not isinstance(analysis["limitations"], list):
                raise LedgerError(
                    "Assessed analysis requires a limitations array (which may be empty)"
                )
            store.check_references(
                {"visibility": record["visibility"], "evidence_refs": analysis["evidence_refs"]}
            )
        change = {key: value for key, value in patch.items() if key != "annotation"}
        change["annotations"] = record.get("annotations", []) + [{"at": now(), "content": patch}]
        return update_run(store, record, change)


def import_run(store, manifest, source_path):
    original = manifest.get("record", manifest)
    properties = __import__("labledger.schema", fromlist=["schema"]).schema()["$defs"]["run"][
        "properties"
    ]
    reserved = {"schema_version", "entity_type", "id", "revision", "created_at", "updated_at"}
    unknown = set(original) - set(properties)
    if unknown:
        raise LedgerError(f"Unknown external run fields: {sorted(unknown)}")
    payload = {key: value for key, value in original.items() if key not in reserved}
    missing = list(payload.get("missing_metadata", []))
    for key in (
        "experiment_id",
        "experiment_revision",
        "argv",
        "cwd",
        "started_at",
        "ended_at",
        "exit_code",
        "code",
        "inputs",
        "environment",
        "model",
        "outputs",
        "accounting",
    ):
        if key not in payload or payload[key] is None:
            missing.append(f"External manifest missing {key}")
    if "execution_status" not in payload:
        raise LedgerError(
            "External manifest must explicitly declare execution_status; it cannot be inferred"
        )
    payload.update(
        {
            "imported": True,
            "missing_metadata": missing,
            "reproducibility_status": "partial"
            if missing
            else payload.get("reproducibility_status", "unavailable"),
            "research_outcome": payload.get("research_outcome", "not_assessed"),
            "analysis_status": payload.get("analysis_status", "pending"),
            "import_source": {
                "path": str(source_path),
                "original_id": original.get("id"),
                "checksum": digest(encoded(manifest)),
            },
        }
    )
    if payload.get("experiment_id"):
        store.read("experiment", payload["experiment_id"], payload.get("experiment_revision"))

    def extra(record):
        return {
            **manifest_changes(store, record),
            store.location("run", record["id"]).parent / "imported-manifest.json": encoded(
                manifest
            ),
        }

    return store.create("run", payload, extra=extra)

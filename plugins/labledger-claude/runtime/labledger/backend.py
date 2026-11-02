"""Private JSON request handler used by the bundled coding-agent helper."""

import json
import sys
from pathlib import Path

from . import __version__
from .doctor import capabilities, doctor
from .errors import Conflict, LedgerError, Prerequisite
from .memory import rebuild_cache, recall, report, resume, status
from .project import initialize
from .runner import annotate, import_run, reconcile, start
from .schema import schema
from .storage import Store
from .workflows import attach_plan, check_handoff, check_plan, handoff, task_status

# operation: (required arguments, optional arguments with defaults, payload mode)
OPERATIONS = {
    "version": ([], {}, "none"),
    "schema": ([], {"kind": None}, "none"),
    "init": ([], {"dry_run": False}, "optional"),
    "handoff": (["task"], {"check": False, "expected_revision": None}, "optional"),
    "run.get": (["id"], {"revision": None, "include_restricted": False}, "none"),
    "run.start": (
        ["experiment", "argv"],
        {"capture": [], "parent": None, "retry_reason": None, "cwd": None, "metadata": None},
        "none",
    ),
    "run.import": ([], {"source_name": "session-import.json"}, "required"),
    "run.annotate": (["id", "expected_revision"], {}, "required"),
    "run.reconcile": (["id", "expected_revision", "reason"], {"confirm_stopped": False}, "none"),
    "recall": (["query"], {"task": None, "limit": 10, "include_restricted": False}, "none"),
    "cache.rebuild": ([], {}, "none"),
    "status": ([], {"task": None, "include_restricted": False}, "none"),
    "resume": (["task"], {"include_restricted": False}, "none"),
    "report": (["task"], {"include_restricted": False, "output": None}, "none"),
    "doctor": ([], {"repair": False, "include_restricted": False, "capabilities": False}, "none"),
    "policy.get": ([], {}, "none"),
    "policy.update": (["expected_revision"], {}, "required"),
    "_hook": (["event"], {}, "required"),
}
for _kind in ("task", "decision", "experiment", "finding", "claim", "probe", "exposure", "review"):
    _action = "add" if _kind in ("finding", "claim", "probe", "exposure", "review") else "new"
    OPERATIONS[f"{_kind}.{_action}"] = ([], {}, "required")
    OPERATIONS[f"{_kind}.update"] = (["id", "expected_revision"], {}, "required")
    OPERATIONS[f"{_kind}.get"] = (
        ["id"],
        {"revision": None, "include_restricted": False},
        "none",
    )
OPERATIONS["task.attach-plan"] = (["id", "expected_revision"], {"execution": False}, "required")
for _action in ("add", "tombstone", "redact"):
    _required = ["run", "expected_revision"]
    if _action in ("tombstone", "redact"):
        _required.append("path")
    if _action == "tombstone":
        _required.append("reason")
    if _action == "redact":
        _required.append("output")
    OPERATIONS[f"artifact.{_action}"] = (
        _required,
        {},
        "none" if _action == "tombstone" else "required",
    )

ARGUMENT_TYPES = {
    **dict.fromkeys(
        (
            "dry_run",
            "check",
            "include_restricted",
            "confirm_stopped",
            "repair",
            "capabilities",
            "execution",
        ),
        bool,
    ),
    **dict.fromkeys(("expected_revision", "revision", "limit"), int),
    **dict.fromkeys(("argv", "capture"), list),
    "metadata": dict,
}


def parse_request(request):
    if not isinstance(request, dict):
        raise LedgerError("Request must be a JSON object")
    unknown = set(request) - {"operation", "root", "arguments", "payload"}
    if unknown:
        raise LedgerError(f"Unknown request fields: {sorted(unknown)}")
    operation = request.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise LedgerError(f"Unknown operation: {operation!r}")
    root = request.get("root")
    if not isinstance(root, str) or not Path(root).is_absolute():
        raise LedgerError("root must be an absolute project path")
    arguments = request.get("arguments", {})
    if not isinstance(arguments, dict):
        raise LedgerError("arguments must be an object")
    required, defaults, mode = OPERATIONS[operation]
    unknown = set(arguments) - set(required) - set(defaults)
    if unknown or set(required) - set(arguments):
        raise LedgerError(
            f"Invalid arguments for {operation}; required: {required}, optional: {sorted(defaults)}"
        )
    for key, value in arguments.items():
        if value is None and key in defaults and defaults[key] is None:
            continue
        expected = ARGUMENT_TYPES.get(key, str)
        if type(value) is not expected:
            raise LedgerError(f"{key} must be {expected.__name__}")
        if expected is str and not value.strip():
            raise LedgerError(f"{key} must not be empty")
        if expected is int and value < 1:
            raise LedgerError(f"{key} must be positive")
        if expected is list and any(not isinstance(item, str) for item in value):
            raise LedgerError(f"{key} must contain strings")
    if mode == "none" and "payload" in request:
        raise LedgerError(f"{operation} does not accept a payload")
    if (mode == "required" or "payload" in request) and not isinstance(
        request.get("payload"), dict
    ):
        raise LedgerError(f"{operation} requires an object payload")
    return operation, Path(root).resolve(), {**defaults, **arguments}, request.get("payload", {})


def dispatch(operation, root, args, payload):
    if operation == "version":
        return {"version": __version__}, 0
    if operation == "schema":
        document = schema()
        if args["kind"]:
            if args["kind"] not in document["$defs"]:
                raise LedgerError(f"Unknown schema kind: {args['kind']}")
            document = {
                "$schema": document["$schema"],
                "$ref": f"#/$defs/{args['kind']}",
                "$defs": document["$defs"],
            }
        return document, 0
    if operation == "_hook":
        from .hooks import reminder

        if args["event"] not in ("SessionStart", "Stop"):
            raise LedgerError("Unknown hook event")
        return reminder(args["event"], payload), 0
    if operation == "init":
        result = initialize(root, payload, args["dry_run"])
        if not args["dry_run"]:
            result["doctor"] = doctor(Store(root))
        return result, 0
    if operation == "doctor" and args["capabilities"]:
        return capabilities(), 0
    store = Store(root)
    if not store.config:
        raise Prerequisite(
            "Project is not initialized; use the LabLedger init skill in this session"
        )

    def task_files(task):
        return {store.location("task", task["id"]).parent / "STATUS.md": task_status(store, task)}

    if operation == "doctor":
        repairs = store.repair() if args["repair"] else []
        result = doctor(store, args["include_restricted"])
        result["repaired_transactions"] = repairs
        return result, 0 if result["ok"] else 3
    if operation == "policy.get":
        return json.loads((store.meta / "policy/current.json").read_text()), 0
    if operation == "policy.update":
        from .policy import update_policy

        return update_policy(store, payload, args["expected_revision"]), 0
    kind, _, action = operation.partition(".")
    if action == "get":
        result = store.read(kind, args["id"], args["revision"])
        if result["visibility"] != "development" and not args["include_restricted"]:
            raise LedgerError("Record unavailable in development view")
        return result, 0
    if kind in (
        "task",
        "decision",
        "experiment",
        "finding",
        "claim",
        "probe",
        "exposure",
        "review",
    ):
        if action == "attach-plan":
            return attach_plan(
                store, args["id"], payload, args["expected_revision"], args["execution"]
            ), 0
        extra = task_files if kind == "task" else None
        if action in ("new", "add"):
            return store.create(kind, payload, extra=extra), 0
        if kind == "task" and payload.get("status") in ("implementing", "evaluating", "completed"):
            issues = check_plan(store, store.read("task", args["id"]))
            if issues:
                raise Conflict("; ".join(issues))
        return store.update(kind, args["id"], payload, args["expected_revision"], extra=extra), 0
    if operation == "handoff":
        if args["check"]:
            issues = check_handoff(store, store.read("task", args["task"]))
            return {"ok": not issues, "issues": issues}, 3 if issues else 0
        if not payload or args["expected_revision"] is None:
            raise LedgerError("Handoff generation requires payload and expected_revision")
        return handoff(store, args["task"], payload, args["expected_revision"]), 0
    if operation == "run.start":
        record, code = start(
            store,
            args["experiment"],
            args["argv"],
            args["capture"],
            args["parent"],
            args["retry_reason"],
            args["cwd"],
            args["metadata"],
        )
        return {"run": record, "next_action": "Analyze the run or explicitly defer analysis."}, code
    if operation == "run.import":
        return import_run(store, payload, Path(args["source_name"]).name), 0
    if operation == "run.annotate":
        return annotate(store, args["id"], payload, args["expected_revision"]), 0
    if operation == "run.reconcile":
        return reconcile(
            store, args["id"], args["expected_revision"], args["reason"], args["confirm_stopped"]
        ), 0
    if operation == "recall":
        return {
            "findings": recall(
                store, args["query"], args["task"], args["include_restricted"], args["limit"]
            )
        }, 0
    if kind == "artifact":
        from . import artifacts

        if action == "add":
            return artifacts.add(store, args["run"], payload, args["expected_revision"]), 0
        if action == "tombstone":
            return artifacts.tombstone(
                store, args["run"], args["path"], args["reason"], args["expected_revision"]
            ), 0
        return artifacts.redact(
            store, args["run"], args["path"], args["output"], payload, args["expected_revision"]
        ), 0
    if operation == "cache.rebuild":
        return rebuild_cache(store), 0
    if operation == "status":
        return status(store, args["task"], args["include_restricted"]), 0
    if operation == "resume":
        return resume(store, args["task"], args["include_restricted"]), 0
    if operation == "report":
        output = store.path(args["output"]) if args["output"] else None
        text = report(store, args["task"], args["include_restricted"], output)
        if output:
            with store.locked():
                if output.exists():
                    raise Conflict(
                        "Report export path already exists; choose a new revision filename"
                    )
                store.commit({output: text})
            return {"path": store.relative(output), "content": text}, 0
        return {"content": text}, 0
    raise LedgerError(f"Unsupported operation: {operation}")


def handle(request):
    """Return an envelope without leaking tracebacks or losing unsuccessful run records."""
    try:
        result, code = dispatch(*parse_request(request))
        return {"ok": code == 0, "code": code, "result": result}
    except LedgerError as error:
        return {"ok": False, "code": error.code, "error": str(error)}
    except (OSError, ValueError) as error:
        return {"ok": False, "code": 5, "error": str(error)}


def read_request(raw):
    def reject(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    try:
        return json.loads(raw, parse_constant=reject)
    except ValueError as error:
        raise LedgerError(f"Invalid request JSON: {error}") from error


def main():
    """One stdin JSON request per process; only the plugin helper calls this function."""
    try:
        response = handle(read_request(sys.stdin.read()))
    except LedgerError as error:
        response = {"ok": False, "code": error.code, "error": str(error)}
    except KeyboardInterrupt:
        response = {"ok": False, "code": 130, "error": "Interrupted"}
    print(json.dumps(response, ensure_ascii=False, allow_nan=False))
    return response["code"]

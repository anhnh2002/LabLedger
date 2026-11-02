"""Canonical records, optimistic revisions, and recoverable filesystem transactions."""

import base64
import contextlib
import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except ImportError:  # Allows capability diagnostics on unsupported Windows installations.
    fcntl = None

from .errors import Conflict, LedgerError, Prerequisite, StorageError
from .schema import validate

KINDS = {
    "task": ("tasks", "TASK"),
    "decision": ("decisions", "DEC"),
    "experiment": ("experiments", "EXP"),
    "run": ("runs", "RUN"),
    "finding": ("findings", "FND"),
    "claim": ("claims", "CLM"),
    "probe": ("probes", "PRB"),
    "exposure": ("exposures", "XPS"),
    "review": ("reviews", "REV"),
}
ID_PATTERN = re.compile(r"^([A-Z]+)-[a-f0-9]{32}$")
TASK_TRANSITIONS = {
    "brainstorming": {"ready_for_planning", "blocked", "paused", "cancelled"},
    "ready_for_planning": {"planning", "brainstorming", "blocked", "paused", "cancelled"},
    "planning": {"plan_approved", "brainstorming", "blocked", "paused", "cancelled"},
    "plan_approved": {"implementing", "planning", "blocked", "paused", "cancelled"},
    "implementing": {"evaluating", "completed", "blocked", "paused", "cancelled"},
    "evaluating": {"implementing", "completed", "blocked", "paused", "cancelled"},
    "blocked": {
        "brainstorming",
        "ready_for_planning",
        "planning",
        "implementing",
        "evaluating",
        "paused",
        "cancelled",
    },
    "paused": {
        "brainstorming",
        "ready_for_planning",
        "planning",
        "implementing",
        "evaluating",
        "blocked",
        "cancelled",
    },
    "completed": set(),
    "cancelled": set(),
}
DECISION_TRANSITIONS = {
    "proposed": {"discussed", "approved", "rejected", "deferred"},
    "discussed": {"approved", "rejected", "deferred"},
    "deferred": {"discussed", "approved", "rejected"},
    "approved": {"superseded"},
    "rejected": {"discussed", "superseded"},
    "superseded": set(),
}
EXPERIMENT_TRANSITIONS = {
    "draft": {"approved", "superseded"},
    "approved": {"running", "closed", "superseded", "draft"},
    "running": {"approved", "closed", "superseded"},
    "closed": {"superseded"},
    "superseded": set(),
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".labledger-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def find_root(start=None):
    start = Path(start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".labledger/config.toml").is_file():
            return candidate
    raise Prerequisite("No LabLedger project found; use the init skill in this session")


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.meta = self.path(".labledger")
        self.config = None
        self._local = threading.local()
        config_path = self.meta / "config.toml"
        if config_path.exists():
            try:
                self.config = tomllib.loads(config_path.read_text())
            except (ValueError, OSError) as error:
                raise LedgerError(f"Invalid config: {error}") from error
            validate(self.config, "config")
            self.research = self.path(self.config["project"]["research_dir"])
            self.artifacts = self.path(self.config["project"]["artifacts_dir"])
            paths = (self.research, self.artifacts, self.meta)
            for left in paths:
                for right in paths:
                    if left != right and left.is_relative_to(right):
                        raise LedgerError(
                            "Research, artifact and metadata directories must not overlap"
                        )
            if len(set(paths)) != 3 or self.root in paths:
                raise LedgerError("Project data directories must be distinct subdirectories")
        else:
            self.research = self.root / "research"
            self.artifacts = self.root / "artifacts/runs"

    @property
    def _lock_depth(self):
        return getattr(self._local, "depth", 0)

    @_lock_depth.setter
    def _lock_depth(self, depth):
        self._local.depth = depth

    def path(self, relative):
        candidate = self.root / relative
        result = candidate.resolve()
        if not result.is_relative_to(self.root) or result == self.root:
            raise LedgerError(f"Path must stay inside project: {relative}")
        return result

    def relative(self, path):
        return Path(path).relative_to(self.root).as_posix()

    @contextlib.contextmanager
    def locked(self, repair=False):
        if fcntl is None:
            raise Prerequisite(
                "Storage operations require macOS or Linux; ask the doctor skill about capabilities"
            )
        if self._lock_depth:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return
        # Outside the repository: read commands never create repository files.
        lock_dir = Path(tempfile.gettempdir()) / f"labledger-locks-{os.getuid()}"
        lock_dir.mkdir(mode=0o700, exist_ok=True)
        lock_path = lock_dir / digest(str(self.root).encode())
        with lock_path.open("a+b") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            self._lock_depth = 1
            try:
                if not repair and self.pending():
                    raise Conflict(
                        "Incomplete transaction; use the doctor skill to inspect and repair it"
                    )
                yield
            finally:
                self._lock_depth = 0
                fcntl.flock(stream, fcntl.LOCK_UN)

    def pending(self):
        return sorted((self.meta / "transactions").glob("*.json"))

    def commit(self, changes):
        """Roll-forward journal; callers hold the project lock."""
        if not self._lock_depth:
            raise StorageError("Transaction requires project lock")
        entries = []
        for path, data in changes.items():
            path = self.path(self.relative(path))
            data = data.encode() if isinstance(data, str) else data
            before = path.read_bytes() if path.exists() else None
            if before == data:
                continue
            entries.append(
                {
                    "path": self.relative(path),
                    "before": digest(before) if before is not None else None,
                    "after": digest(data),
                    "data": base64.b64encode(data).decode(),
                }
            )
        if not entries:
            return
        journal = self.meta / "transactions" / f"{uuid.uuid4().hex}.json"
        atomic_write(journal, encoded({"schema_version": 1, "entries": entries}))
        self._apply(journal)

    def _apply(self, journal):
        transaction = json.loads(journal.read_text())
        if transaction.get("schema_version") != 1:
            raise Conflict(f"Unsupported transaction: {journal.name}")
        # Preflight every destination before changing anything during recovery.
        for item in transaction["entries"]:
            path = self.path(item["path"])
            present = digest(path.read_bytes()) if path.exists() else None
            data = base64.b64decode(item["data"], validate=True)
            if digest(data) != item["after"] or present not in (item["before"], item["after"]):
                raise Conflict(f"Transaction conflicts with external edit: {item['path']}")
        for item in transaction["entries"]:
            path = self.path(item["path"])
            data = base64.b64decode(item["data"])
            if not path.exists() or digest(path.read_bytes()) != item["after"]:
                atomic_write(path, data)
        journal.unlink()

    def repair(self):
        with self.locked(repair=True):
            repaired = []
            for journal in self.pending():
                self._apply(journal)
                repaired.append(journal.name)
            return repaired

    def location(self, kind, identifier, revision=None):
        if kind not in KINDS or not ID_PATTERN.fullmatch(identifier):
            raise LedgerError(f"Invalid entity reference: {kind}/{identifier}")
        folder, prefix = KINDS[kind]
        if not identifier.startswith(prefix + "-"):
            raise LedgerError(f"ID does not match entity type {kind}: {identifier}")
        base = self.path(self.relative(self.research / folder / identifier))
        if revision is not None:
            if type(revision) is not int or revision < 1:
                raise LedgerError("Revision must be a positive integer")
            return base / "history" / f"{revision}.json"
        return base / "record.json"

    def read(self, kind, identifier, revision=None):
        with self.locked():
            path = self.location(kind, identifier, revision)
            if not path.is_file():
                raise LedgerError(f"Missing {kind} record: {identifier}@{revision or 'current'}")
            try:
                record = json.loads(path.read_text())
            except ValueError as error:
                raise LedgerError(f"Invalid JSON at {self.relative(path)}: {error}") from error
            try:
                validate(record, kind)
            except LedgerError as error:
                if isinstance(record, dict) and record.get("visibility") == "restricted_evaluation":
                    raise LedgerError(
                        "Restricted record failed validation; inspect in an evaluation context"
                    ) from error
                raise
            if record["id"] != identifier or (revision and record["revision"] != revision):
                raise Conflict(f"Record identity mismatch at {self.relative(path)}")
            return record

    def all(self, kind=None):
        with self.locked():
            records = []
            for entity in [kind] if kind else KINDS:
                for path in sorted((self.research / KINDS[entity][0]).glob("*/record.json")):
                    records.append(self.read(entity, path.parent.name))
            return records

    def ref(self, record):
        return {"type": record["entity_type"], "id": record["id"], "revision": record["revision"]}

    def references(self, record):
        def walk(value):
            if isinstance(value, dict):
                if (value.get("type") in KINDS and "id" in value) or (
                    value.get("type") in ("artifact", "source", "document")
                    and ("path" in value or "uri" in value)
                ):
                    yield value
                else:
                    for nested in value.values():
                        yield from walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    yield from walk(nested)

        return list(walk(record))

    def check_references(self, record):
        retired = {
            event["path"]
            for event in record.get("annotations", [])
            if event.get("kind") == "artifact_tombstone" and "path" in event
        }
        for ref in self.references(record):
            validate(ref, "reference")
            if (
                ref.get("visibility") == "restricted_evaluation"
                and record["visibility"] == "development"
            ):
                raise Prerequisite("Restricted evidence requires restricted record visibility")
            if ref["type"] in KINDS:
                target = self.read(ref["type"], ref["id"], ref["revision"])
                if (
                    target["visibility"] == "restricted_evaluation"
                    and record["visibility"] != target["visibility"]
                ):
                    raise Prerequisite("Development records cannot include restricted evidence")
            elif "path" in ref and ref.get("availability", "available") == "available":
                if ref["path"] not in retired and not self.path(ref["path"]).exists():
                    raise LedgerError(f"Missing evidence path: {ref['path']}")
            elif "uri" in ref and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", ref["uri"]):
                raise LedgerError("Source URI must include a scheme")
        if record.get("task_id"):
            task = self.read("task", record["task_id"])
            if (
                task["visibility"] == "restricted_evaluation"
                and record["visibility"] == "development"
            ):
                raise Prerequisite("Records for restricted tasks must also be restricted")

    def create(self, kind, payload, extra=None):
        with self.locked():
            if any(
                key in payload
                for key in (
                    "id",
                    "revision",
                    "created_at",
                    "updated_at",
                    "entity_type",
                    "schema_version",
                )
            ):
                raise LedgerError("Identity, timestamps and revisions are assigned by LabLedger")
            record = {
                "schema_version": 1,
                "entity_type": kind,
                "id": f"{KINDS[kind][1]}-{uuid.uuid4().hex}",
                "revision": 1,
                "created_at": now(),
                "updated_at": now(),
                "visibility": "development",
                **copy.deepcopy(payload),
            }
            if kind == "task":
                record = {
                    "status": "brainstorming",
                    "brief_revision": 0,
                    "plan_revision": 0,
                    "decision_refs": [],
                    "acceptance_criteria": [],
                    **record,
                }
            elif kind == "decision":
                record = {"status": "proposed", "evidence_refs": [], **record}
            elif kind == "experiment":
                record = {"status": "draft", "decision_refs": [], **record}
            elif kind == "claim":
                record = {
                    "status": "proposed",
                    "evidence_refs": [],
                    "counterevidence_refs": [],
                    "limitations": [],
                    "report_refs": [],
                    **record,
                }
            self.verify(record)
            self.normalize_times(record)
            changes = self.record_changes(record)
            if extra:
                changes.update(extra(record))
            self.commit(changes)
            return record

    def update(self, kind, identifier, patch, expected, extra=None, internal=False):
        with self.locked():
            old = self.read(kind, identifier)
            if expected != old["revision"]:
                raise Conflict(
                    f"Expected revision {expected}; current revision is {old['revision']}"
                )
            protected = {
                "id",
                "revision",
                "schema_version",
                "entity_type",
                "created_at",
                "updated_at",
            }
            if protected.intersection(patch):
                raise LedgerError("Identity and revision fields cannot be patched")
            if (
                kind == "task"
                and not internal
                and {"handoff", "plan", "brief_revision", "plan_revision"}.intersection(patch)
            ):
                raise Prerequisite(
                    "Use handoff or execution-time plan attachment for task documents"
                )
            if kind == "run" and not internal:
                raise Prerequisite("Use run annotate or reconcile to update a run")
            if all(old.get(key) == value for key, value in patch.items()):
                return old
            record = {
                **old,
                **copy.deepcopy(patch),
                "revision": old["revision"] + 1,
                "updated_at": now(),
            }
            self.verify(record, old)
            self.normalize_times(record)
            changes = self.record_changes(record)
            if extra:
                changes.update(extra(record))
            self.commit(changes)
            return record

    def record_changes(self, record):
        kind, identifier, revision = record["entity_type"], record["id"], record["revision"]
        history = self.location(kind, identifier, revision)
        if history.exists():
            raise Conflict(f"Immutable revision already exists: {identifier}@{revision}")
        return {history: encoded(record), self.location(kind, identifier): encoded(record)}

    def verify(self, record, old=None):
        kind = record["entity_type"]
        validate(record, kind)
        self.check_references(record)
        if old and kind in ("task", "decision", "experiment"):
            transitions = {
                "task": TASK_TRANSITIONS,
                "decision": DECISION_TRANSITIONS,
                "experiment": EXPERIMENT_TRANSITIONS,
            }[kind]
            before, after = old["status"], record["status"]
            if before != after and after not in transitions[before]:
                raise Conflict(f"Illegal {kind} transition: {before} -> {after}")
        if (
            old
            and old["visibility"] == "restricted_evaluation"
            and record["visibility"] == "development"
        ):
            raise Prerequisite("Restricted history cannot be declassified by an update")
        if kind == "task":
            if record["status"] == "planning" and not record.get("planning_evidence"):
                raise Prerequisite("Planning requires actual session observation evidence")
            if record["status"] == "ready_for_planning" and not record.get("handoff"):
                raise Prerequisite("Generate a valid handoff before ready_for_planning")
            if record["status"] in (
                "plan_approved",
                "implementing",
                "evaluating",
                "completed",
            ) and not record.get("plan"):
                raise Prerequisite("An approved persisted plan is required")
            if record["status"] == "completed" and not record.get("completion_evidence"):
                raise Prerequisite("Completion requires acceptance evidence")
            if record["status"] == "blocked" and not record.get("blocker_reason"):
                raise Prerequisite("Blocked tasks require a reason")
        if kind == "decision" and record["status"] == "approved":
            choices = [option["id"] for option in record["options"]]
            if len(set(choices)) != len(choices) or record.get("selected_option") not in choices:
                raise LedgerError("Selected option must identify one unique option")
            self.require(record, "approved_scope", "approval_evidence")
            if old and old["status"] == "approved":
                material = ("question", "options", "selected_option", "approved_scope")
                if any(old.get(k) != record.get(k) for k in material) and old.get(
                    "approval_evidence"
                ) == record.get("approval_evidence"):
                    raise Prerequisite("Changed decision scope requires new approval evidence")
        if kind == "experiment" and record["status"] in ("approved", "running"):
            self.require(
                record,
                "baseline",
                "intervention",
                "dataset_refs",
                "primary_metric",
                "evaluation_unit",
                "repetitions",
                "budget",
                "success_criteria",
                "stop_conditions",
                "failure_handling",
                "analysis_plan",
                "approval_evidence",
                "approved_scope",
                "decision_refs",
            )
            for ref in record["decision_refs"]:
                if ref["type"] != "decision":
                    raise LedgerError("Experiment decision_refs must reference decisions")
                decision = self.read("decision", ref["id"], ref["revision"])
                if ref["type"] != "decision" or decision["status"] != "approved":
                    raise Prerequisite("Experiment must reference approved decision revisions")
            if old:
                previous = old
                if previous["status"] not in ("approved", "running"):
                    for revision in range(old["revision"] - 1, 0, -1):
                        candidate = self.read("experiment", old["id"], revision)
                        if candidate["status"] in ("approved", "running"):
                            previous = candidate
                            break
                material = set(record) - {
                    "revision",
                    "updated_at",
                    "status",
                    "approval_evidence",
                    "observed_results",
                    "revision_reason",
                    "tags",
                }
                changed = any(previous.get(k) != record.get(k) for k in material)
                if previous["status"] in ("approved", "running") and changed:
                    if previous.get("approval_evidence") == record.get("approval_evidence"):
                        raise Prerequisite("Protocol changes require renewed approval evidence")
                    self.require(record, "revision_reason")
                    observed = [
                        r for r in self.all("run") if r.get("experiment_id") == record["id"]
                    ]
                    declared = {ref.get("id") for ref in record.get("observed_results", [])}
                    if not {run["id"] for run in observed}.issubset(declared):
                        raise Prerequisite(
                            "Protocol revision must disclose existing runs in observed_results"
                        )
        if kind in ("finding", "claim"):
            if record.get("kind") != "hypothesis" and not record.get("evidence_refs"):
                raise Prerequisite("Findings and claims require evidence references")
            if record.get("kind") == "correction" and not record.get("supersedes"):
                raise Prerequisite("Correction must reference the finding it supersedes")
            if record.get("kind") == "correction" and record["supersedes"]["type"] != "finding":
                raise LedgerError("Correction must supersede a finding")
            if record.get("kind") == "correction" and record["supersedes"]["id"] == record["id"]:
                raise LedgerError("Create a new correction finding instead of superseding itself")
        if (
            kind == "exposure"
            and record["role"] == "held_out_test"
            and record["visibility"] != "restricted_evaluation"
        ):
            raise Prerequisite("Held-out exposure details require restricted_evaluation visibility")
        if kind == "run":
            if bool(record.get("experiment_id")) != bool(record.get("experiment_revision")):
                raise LedgerError("Experiment ID and revision must be recorded together")
            if record.get("experiment_id"):
                self.read("experiment", record["experiment_id"], record["experiment_revision"])
            if record["research_outcome"] != "not_assessed":
                if record["analysis_status"] != "analyzed":
                    raise Prerequisite("Assessed research outcomes require analyzed status")
                self.require(record, "analysis")
                self.require(record["analysis"], "summary", "evidence_refs")
                if not isinstance(record["analysis"].get("limitations"), list):
                    raise LedgerError("Assessed analysis requires limitations")
            if record["analysis_status"] in ("analyzed", "deferred"):
                self.require(record, "analysis")
                self.require(record["analysis"], "summary")

    @staticmethod
    def normalize_times(record):
        for key in ("exposed_at", "started_at", "ended_at"):
            if record.get(key):
                record[key] = (
                    datetime.fromisoformat(record[key].replace("Z", "+00:00"))
                    .astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )

    @staticmethod
    def require(record, *keys):
        missing = [key for key in keys if not record.get(key)]
        if missing:
            raise Prerequisite("Missing prerequisites: " + ", ".join(missing))

"""Explicit artifact registration, derivative redaction, and retention metadata."""

import copy
import os
import re
import tempfile

from .errors import Conflict, LedgerError, Prerequisite
from .runner import TERMINAL, file_digest, update_run
from .schema import validate
from .storage import now


def terminal_run(store, identifier, expected):
    record = store.read("run", identifier)
    if record["revision"] != expected:
        raise Conflict("Run changed before artifact annotation")
    if record["execution_status"] not in TERMINAL:
        raise Prerequisite("Wait for terminal execution before modifying artifact metadata")
    return record


def add(store, identifier, payload, expected):
    with store.locked():
        record = terminal_run(store, identifier, expected)
        reference = {"type": "artifact", **payload}
        if "path" in reference:
            path = store.path(reference["path"])
            if any(
                event.get("kind") == "artifact_tombstone"
                and event.get("path") == store.relative(path)
                for event in record.get("annotations", [])
            ):
                raise Conflict("Retired artifact paths cannot be reused; choose a new path")
            if not path.is_file():
                raise LedgerError("Artifact path must be an existing file")
            reference.update({"checksum": file_digest(path), "size": path.stat().st_size})
            reference["path"] = store.relative(path)
        else:
            store.require(reference, "uri", "checksum", "access_requirements")
            if reference.get("size") is None:
                raise LedgerError("External artifact size is required")
            if any(
                token in reference["uri"].casefold()
                for token in ("x-amz-signature=", "x-goog-signature=", "sig=")
            ):
                raise LedgerError("Use a durable storage URI instead of a signed download URL")
            reference["availability"] = "external"
        validate(reference, "reference")
        outputs = copy.deepcopy(record.get("outputs", {}))
        outputs["artifacts"] = outputs.get("artifacts", []) + [reference]
        return update_run(
            store,
            record,
            {
                "outputs": outputs,
                "annotations": record.get("annotations", [])
                + [{"at": now(), "kind": "artifact_registered", "reference": reference}],
            },
        )


def tombstone(store, identifier, relative, reason, expected):
    """Mark an explicitly retired artifact; never delete the file."""
    if not reason.strip():
        raise LedgerError("Artifact retirement requires a reason")
    with store.locked():
        record = terminal_run(store, identifier, expected)
        path = store.path(relative)
        relative = store.relative(path)
        if not path.is_relative_to(store.artifacts / identifier):
            raise LedgerError("Retire only artifacts belonging to this run")
        outputs = copy.deepcopy(record.get("outputs", {}))
        inputs = copy.deepcopy(record.get("inputs", {}))
        matched = []
        for ref in store.references(outputs):
            if ref.get("path") == relative:
                matched.append({key: value for key, value in ref.items() if key != "type"})
                ref["availability"] = "unavailable"
                ref["access_requirements"] = f"Retired: {reason}"
        for snapshot in inputs.get("snapshots", []):
            if snapshot["snapshot"] == relative:
                matched.append(copy.deepcopy(snapshot))
                snapshot["availability"] = "unavailable"
        if not matched:
            raise LedgerError("Artifact is not registered in this run")
        return update_run(
            store,
            record,
            {
                "outputs": outputs,
                "inputs": inputs,
                "annotations": record.get("annotations", [])
                + [
                    {
                        "at": now(),
                        "kind": "artifact_tombstone",
                        "path": relative,
                        "reason": reason,
                        "previous_metadata": matched,
                        "file_deleted_by_labledger": False,
                    }
                ],
            },
        )


def redact(store, identifier, relative, output, payload, expected):
    """Create a streamed derivative; never rewrite or erase the original."""
    store.require(payload, "reason", "replacements")
    if set(payload) != {"reason", "replacements"}:
        raise LedgerError("Redaction inputs are reason and replacements only")
    replacements = {}
    for entry in payload["replacements"]:
        if not isinstance(entry, dict) or set(entry) != {"text", "replacement"}:
            raise LedgerError("Each replacement requires text and replacement")
        source, target = entry["text"], entry["replacement"]
        if not isinstance(source, str) or not source or not isinstance(target, str):
            raise LedgerError("Redaction requires nonempty literal text and a replacement string")
        replacements[source.encode()] = target.encode()
    with store.locked():
        record = terminal_run(store, identifier, expected)
        source, target = store.path(relative), store.path(output)
        relative, output = store.relative(source), store.relative(target)
        run_dir = store.artifacts / identifier
        if not source.is_relative_to(run_dir) or not target.is_relative_to(run_dir):
            raise LedgerError("Redacted derivatives must stay in this run's artifact directory")
        if target.exists() or not source.is_file():
            raise Conflict("Source must exist and derivative destination must be new")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=target.parent, prefix=".redaction-")
        count = 0
        pattern = re.compile(
            b"|".join(re.escape(value) for value in sorted(replacements, key=len, reverse=True))
        )
        longest = max(map(len, replacements))
        try:
            with source.open("rb") as original, os.fdopen(fd, "wb") as destination:
                buffer = b""
                while True:
                    chunk = original.read(1024 * 1024)
                    buffer += chunk
                    cutoff = max(0, len(buffer) - longest + 1) if chunk else len(buffer)
                    consumed = 0
                    for match in pattern.finditer(buffer):
                        if match.start() >= cutoff:
                            break
                        destination.write(buffer[consumed : match.start()])
                        destination.write(replacements[match.group()])
                        consumed = match.end()
                        count += 1
                    end = max(consumed, cutoff)
                    destination.write(buffer[consumed:end])
                    buffer = buffer[end:]
                    if not chunk:
                        break
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        reference = {
            "type": "artifact",
            "path": output,
            "checksum": file_digest(target),
            "size": target.stat().st_size,
        }
        outputs = copy.deepcopy(record.get("outputs", {}))
        outputs["artifacts"] = outputs.get("artifacts", []) + [reference]
        # The secret matching strings are deliberately absent from the ledger.
        return update_run(
            store,
            record,
            {
                "outputs": outputs,
                "annotations": record.get("annotations", [])
                + [
                    {
                        "at": now(),
                        "kind": "redacted_derivative",
                        "source_path": relative,
                        "source_checksum": file_digest(source),
                        "derivative_path": output,
                        "reason": payload["reason"],
                        "replacement_count": count,
                        "original_preserved": True,
                    }
                ],
            },
        )

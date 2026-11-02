import io
import json
import sys

import pytest

from labledger.backend import handle, main


def request(root, operation, arguments=None, **fields):
    return handle(
        {"root": str(root), "operation": operation, "arguments": arguments or {}, **fields}
    )


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_agent_authored_init_preview_apply_and_idempotence(tmp_path):
    payload = {
        "name": "Discussed project",
        "charter": '# Agreed charter\n\nQuotes " and tiếng Việt.',
    }
    before = snapshot(tmp_path)
    preview = request(tmp_path, "init", {"dry_run": True}, payload=payload)
    assert preview["ok"] and preview["result"]["dry_run"]
    assert snapshot(tmp_path) == before
    applied = request(tmp_path, "init", payload=payload)
    assert applied["ok"] and applied["result"]["doctor"]["ok"]
    assert (tmp_path / "research/CHARTER.md").read_text().strip() == payload["charter"].strip()
    before = snapshot(tmp_path)
    assert request(tmp_path, "init")["result"]["files"] == []
    assert snapshot(tmp_path) == before


def test_schema_errors_missing_project_and_revision_conflicts(tmp_path, store):
    assert request(tmp_path / "missing", "status")["code"] == 4
    schema = request(tmp_path, "schema", {"kind": "init_input"})
    assert schema["ok"] and schema["result"]["$ref"] == "#/$defs/init_input"
    assert request(tmp_path, "schema", {"kind": "unknown"})["code"] == 2
    assert (
        request(store.root, "task.new", payload={"title": "Fixture", "unknown": True})["code"] == 2
    )
    task = request(store.root, "task.new", payload={"title": "Fixture"})["result"]
    args = {"id": task["id"], "expected_revision": 1}
    assert request(store.root, "task.update", args, payload={"title": "Revised"})["ok"]
    before = snapshot(store.root)
    assert request(store.root, "task.update", args, payload={"title": "Lost update"})["code"] == 3
    assert snapshot(store.root) == before


@pytest.mark.parametrize(
    "invalid",
    [
        [],
        {"operation": 1, "root": "/tmp"},
        {"operation": "unknown", "root": "/tmp"},
        {"operation": "status", "root": "relative"},
        {"operation": "status", "root": "/tmp", "extra": True},
        {"operation": "status", "root": "/tmp", "arguments": []},
        {"operation": "status", "root": "/tmp", "payload": {}},
        {"operation": "init", "root": "/tmp", "arguments": {"dry_run": "false"}},
        {"operation": "task.new", "root": "/tmp"},
        {
            "operation": "task.update",
            "root": "/tmp",
            "arguments": {"id": "T", "expected_revision": True},
            "payload": {},
        },
        {"operation": "recall", "root": "/tmp", "arguments": {"query": "x", "limit": 0}},
        {"operation": "run.start", "root": "/tmp", "arguments": {"experiment": "E", "argv": [1]}},
        {
            "operation": "run.start",
            "root": "/tmp",
            "arguments": {"experiment": "E", "argv": [], "typo": True},
        },
    ],
)
def test_bad_requests_are_structured_errors(invalid):
    response = handle(invalid)
    assert not response["ok"] and response["code"] == 2 and response["error"]


@pytest.mark.parametrize(
    "raw", ["{broken", "[]", '{"operation":"init","root":"/tmp","payload":{"value":NaN}}']
)
def test_transport_rejects_malformed_json_without_traceback(raw, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    assert main() == 2
    captured = capsys.readouterr()
    response = json.loads(captured.out)
    assert response["code"] == 2 and not response["ok"]
    assert captured.err == ""


def test_failed_run_returns_durable_record_and_readonly_requests_leave_repo_unchanged(
    store, experiment
):
    response = request(
        store.root,
        "run.start",
        {
            "experiment": experiment["id"],
            "argv": [sys.executable, "-c", "raise SystemExit(7)"],
        },
    )
    assert response["code"] == 1 and not response["ok"]
    run = response["result"]["run"]
    assert run["execution_status"] == "failed" and run["exit_code"] == 7
    before = snapshot(store.root)
    for operation, args in (("status", {}), ("run.get", {"id": run["id"]}), ("doctor", {})):
        assert request(store.root, operation, args)["ok"]
    assert snapshot(store.root) == before


def test_record_reads_filter_restricted_data(store):
    task = store.create(
        "task", {"title": "Restricted fixture", "visibility": "restricted_evaluation"}
    )
    assert request(store.root, "task.get", {"id": task["id"]})["code"] == 2
    assert (
        request(store.root, "task.get", {"id": task["id"], "include_restricted": True})["result"]
        == task
    )


def test_import_and_reconcile_keep_unknown_metadata(store):
    imported = request(store.root, "run.import", payload={"execution_status": "running"})["result"]
    assert imported["research_outcome"] == "not_assessed"
    args = {"id": imported["id"], "expected_revision": 1, "reason": "Synthetic observed cessation"}
    assert request(store.root, "run.reconcile", args)["code"] == 4
    response = request(store.root, "run.reconcile", {**args, "confirm_stopped": True})
    assert response["ok"] and response["result"]["execution_status"] == "interrupted"

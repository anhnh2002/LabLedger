import pytest

from labledger.backend import handle
from labledger.errors import Conflict, Prerequisite
from labledger.storage import Store
from labledger.workflows import attach_plan, check_handoff, check_plan, handoff


def test_fresh_session_and_execution_plan(store, decision, brief, approval):
    task = store.create("task", {"title": "Fixture", "decision_refs": [store.ref(decision)]})
    result = handoff(store, task["id"], brief, 1)
    task = result["task"]
    assert task["status"] == "ready_for_planning"
    assert len(result["steps"]) == 4 and "<task-id>" not in result["prompt"]
    fresh = Store(store.root)
    assert check_handoff(fresh, task) == []
    documents = fresh.location("task", task["id"]).parent
    assert (documents / "HANDOFF.md").is_file()
    payload = {
        "content": "## Goal\nSynthetic work only.\n## Verification\nInspect the synthetic output.",
        "brief_revision": 1,
        "decision_refs": task["decision_refs"],
        "approval_evidence": approval,
        "planning_evidence": {
            "summary": "Synthetic fresh planning session",
            "source": "pytest fixture",
        },
    }
    before = fresh.read("task", task["id"])
    with pytest.raises(Prerequisite):
        attach_plan(fresh, task["id"], payload, task["revision"])
    assert fresh.read("task", task["id"]) == before
    updated = attach_plan(fresh, task["id"], payload, task["revision"], execution=True)
    assert updated["status"] == "plan_approved"
    assert (documents / "PLAN.md").is_file()
    assert check_plan(fresh, updated) == []
    response = handle(
        {
            "operation": "task.update",
            "root": str(store.root),
            "arguments": {"id": task["id"], "expected_revision": updated["revision"]},
            "payload": {"status": "implementing"},
        }
    )
    assert response["ok"]
    assert fresh.read("task", task["id"])["status"] == "implementing"


def test_handoff_requires_real_approved_direction(store, brief):
    task = store.create("task", {"title": "Unchosen"})
    with pytest.raises(Prerequisite):
        handoff(store, task["id"], brief, 1)
    assert not (store.location("task", task["id"]).parent / "BRIEF.md").exists()


def test_stale_handoff_and_document_history(store, decision, brief, approval):
    task = store.create("task", {"title": "Fixture", "decision_refs": [store.ref(decision)]})
    task = handoff(store, task["id"], brief, 1)["task"]
    base = store.location("task", task["id"]).parent
    first = (base / "BRIEF.md").read_bytes()
    newer = handoff(
        store,
        task["id"],
        {**brief, "brief": {**brief["brief"], "scope": "Updated fixture scope"}},
        task["revision"],
    )["task"]
    assert newer["brief_revision"] == 2
    assert (base / "documents/brief-1/BRIEF.md").read_bytes() == first
    store.update("decision", decision["id"], {"revisit_when": ["New evidence"]}, 1)
    assert any("Stale reference" in issue for issue in check_handoff(store, newer))
    with pytest.raises(Conflict):
        attach_plan(store, task["id"], {}, newer["revision"], execution=True)


def test_editing_handoff_is_detected(store, decision, brief):
    task = store.create("task", {"title": "Fixture", "decision_refs": [store.ref(decision)]})
    task = handoff(store, task["id"], brief, 1)["task"]
    base = store.location("task", task["id"]).parent
    (base / "HANDOFF.md").write_text("External edit")
    assert any("edited" in issue for issue in check_handoff(store, task))


def test_custom_directories_and_external_references(tmp_path, decision, brief):
    from labledger.project import initialize

    root = tmp_path / "custom"
    root.mkdir()
    initialize(
        root,
        {
            "name": "Custom",
            "charter": "Fixture",
            "research_dir": "notes",
            "artifacts_dir": "outputs",
        },
    )
    custom = Store(root)
    # Independent decision record in the custom ledger.
    fields = {
        key: value
        for key, value in decision.items()
        if key
        not in ("id", "entity_type", "schema_version", "revision", "created_at", "updated_at")
    }
    chosen = custom.create("decision", fields)
    task = custom.create("task", {"title": "Custom", "decision_refs": [custom.ref(chosen)]})
    brief["references"] = [
        {"type": "document", "path": "remote-not-present.md", "availability": "unavailable"}
    ]
    result = handoff(custom, task["id"], brief, 1)
    assert "notes/tasks/" in result["prompt"]
    assert check_handoff(custom, result["task"]) == []

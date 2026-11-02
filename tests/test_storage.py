import json
from concurrent.futures import ThreadPoolExecutor

import pytest

import labledger.storage as storage
from labledger.doctor import doctor
from labledger.errors import Conflict, LedgerError, Prerequisite
from labledger.project import initialize
from labledger.schema import schema, validate
from labledger.storage import Store


def snapshot(root):
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


def test_init_idempotent_and_dry_run(tmp_path):
    payload = {"name": "Fixture", "charter": "# Synthetic charter"}
    before = snapshot(tmp_path)
    preview = initialize(tmp_path, payload, dry_run=True)
    assert preview["files"] and snapshot(tmp_path) == before
    initialize(tmp_path, payload)
    before = snapshot(tmp_path)
    assert initialize(tmp_path)["files"] == []
    assert initialize(tmp_path, dry_run=True)["files"] == []
    assert snapshot(tmp_path) == before


def test_init_preserves_instructions_and_detects_edits(tmp_path):
    path = tmp_path / "AGENTS.md"
    path.write_text("# Existing instructions\n\nKeep this content.\n")
    initialize(tmp_path, {"name": "Fixture", "charter": "Synthetic charter"})
    assert path.read_text().startswith("# Existing instructions")
    path.write_text(path.read_text().replace("Before a research decision", "Edited by researcher"))
    before = snapshot(tmp_path)
    with pytest.raises(Conflict, match="User-edited managed block"):
        initialize(tmp_path)
    assert snapshot(tmp_path) == before


def test_schema_authority_and_unknown_versions(store):
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(schema())
    task = store.create("task", {"title": "Fixture"})
    validate(task, "task")
    with pytest.raises(LedgerError):
        validate({**task, "schema_version": 999}, "task")
    with pytest.raises(LedgerError):
        validate({**task, "created_at": "not-a-timestamp"}, "task")
    config = store.meta / "config.toml"
    config.write_text(config.read_text().replace("schema_version = 1", "schema_version = 999"))
    before = config.read_bytes()
    with pytest.raises(LedgerError):
        Store(store.root)
    assert config.read_bytes() == before


def test_history_and_optimistic_revision(store):
    task = store.create("task", {"title": "Fixture"})
    original = store.location("task", task["id"], 1).read_bytes()
    updated = store.update("task", task["id"], {"title": "Updated"}, 1)
    assert updated["revision"] == 2
    assert store.location("task", task["id"], 1).read_bytes() == original
    with pytest.raises(Conflict):
        store.update("task", task["id"], {"title": "Lost update"}, 1)
    with pytest.raises(Conflict):
        store.update("task", task["id"], {"status": "planning"}, 2)
    with pytest.raises(Conflict):
        store.update("task", task["id"], {"status": "completed"}, 2)


def test_cross_process_style_lock_prevents_lost_updates(store):
    task = store.create("task", {"title": "Fixture"})

    def update(title):
        try:
            return Store(store.root).update("task", task["id"], {"title": title}, 1)
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["One", "Two"]))
    assert sum(result is not None for result in results) == 1
    assert store.read("task", task["id"])["revision"] == 2


def test_partial_transaction_is_detected_and_repaired(store, monkeypatch):
    first, second = store.research / "first.md", store.research / "second.md"
    real_write = storage.atomic_write

    def crash(path, data):
        if path == second:
            raise OSError("Synthetic disk fault")
        real_write(path, data)

    with monkeypatch.context() as context:
        context.setattr(storage, "atomic_write", crash)
        with pytest.raises(OSError):
            with store.locked():
                store.commit({first: "first", second: "second"})
    assert first.exists() and not second.exists()
    assert not doctor(store)["ok"]
    with pytest.raises(Conflict, match="Incomplete transaction"):
        store.all()
    assert len(store.repair()) == 1
    assert first.read_text() == "first" and second.read_text() == "second"
    assert doctor(store)["ok"]


def test_repair_refuses_external_conflict(store, monkeypatch):
    path = store.research / "conflict.md"
    real_write = storage.atomic_write

    def crash(destination, data):
        if destination == path:
            raise OSError("Synthetic disk fault")
        real_write(destination, data)

    with monkeypatch.context() as context:
        context.setattr(storage, "atomic_write", crash)
        with pytest.raises(OSError):
            with store.locked():
                store.commit({path: "journal version"})
    path.write_text("external edit")
    with pytest.raises(Conflict, match="external edit"):
        store.repair()
    assert path.read_text() == "external edit"


def test_paths_and_missing_references(store, tmp_path):
    with pytest.raises(LedgerError):
        store.path("../escape")
    (tmp_path / "outside-link").symlink_to(tmp_path.parent)
    with pytest.raises(LedgerError):
        store.path("outside-link/escape")
    with pytest.raises(LedgerError):
        store.create(
            "decision",
            {
                "question": "Fixture",
                "options": [{"id": "a", "description": "a"}],
                "evidence_refs": [{"type": "finding", "id": "FND-" + "a" * 32, "revision": 1}],
            },
        )


def test_doctor_detects_current_history_mismatch(store):
    task = store.create("task", {"title": "Fixture"})
    path = store.location("task", task["id"])
    path.write_text(json.dumps({**task, "title": "Unrecorded edit"}))
    result = doctor(store)
    assert not result["ok"]
    assert "differs from immutable history" in result["errors"][0]["message"]


def test_approval_defaults_and_material_revision(store, decision):
    draft = store.create(
        "decision", {"question": "Unchosen", "options": [{"id": "a", "description": "a"}]}
    )
    assert draft["status"] == "proposed"
    with pytest.raises(Prerequisite):
        store.update("decision", draft["id"], {"status": "approved", "selected_option": "a"}, 1)
    with pytest.raises(Prerequisite, match="new approval"):
        store.update("decision", decision["id"], {"approved_scope": "A broader scope"}, 1)


def test_external_timestamps_are_validated_and_normalized_to_utc(store):
    from labledger.runner import import_run

    record = import_run(
        store,
        {"execution_status": "failed", "started_at": "2026-11-02T08:00:00+07:00"},
        "synthetic.json",
    )
    assert record["started_at"] == "2026-11-02T01:00:00Z"
    with pytest.raises(LedgerError):
        import_run(
            store,
            {"execution_status": "failed", "started_at": "unknown human text"},
            "synthetic.json",
        )

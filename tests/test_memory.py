import json
import shutil
import sys

import pytest

from labledger.doctor import doctor
from labledger.errors import Prerequisite
from labledger.hooks import reminder
from labledger.memory import dependent_warnings, rebuild_cache, recall, report, resume, status
from labledger.runner import import_run, start


def finding(store, **overrides):
    payload = {
        "kind": "observation",
        "statement": "Synthetic retrieval budget reduced coverage",
        "scope": "Synthetic fixtures only",
        "evidence_refs": [{"type": "source", "uri": "https://example.invalid/synthetic-fixture"}],
        "limitations": ["Not research evidence"],
        "confidence": "tentative",
        "alternative_explanations": ["Synthetic generator choice"],
        "next_action": "Inspect fixture",
    }
    return store.create("finding", {**payload, **overrides})


def test_restricted_recall_and_cache_filter_before_matching(store):
    public = finding(store)
    hidden = finding(
        store, visibility="restricted_evaluation", statement="ULTRA_PRIVATE_HELDOUT_FAILURE"
    )
    assert recall(store, "ULTRA_PRIVATE_HELDOUT_FAILURE") == []
    assert recall(store, "ULTRA_PRIVATE_HELDOUT_FAILURE", restricted=True)[0]["id"] == hidden["id"]
    assert recall(store, "coverage")[0]["id"] == public["id"]
    rebuild_cache(store)
    assert "ULTRA_PRIVATE" not in (store.meta / "cache/findings.json").read_text()
    before = store.location("finding", public["id"]).read_bytes()
    shutil.rmtree(store.meta / "cache")
    rebuild_cache(store)
    assert store.location("finding", public["id"]).read_bytes() == before
    assert "ULTRA_PRIVATE" not in json.dumps(status(store))
    with pytest.raises(Prerequisite):
        finding(store, evidence_refs=[store.ref(hidden)])


def test_correction_keeps_history_and_warns_transitive_dependents(store, approval):
    original = finding(store)
    before = store.location("finding", original["id"]).read_bytes()
    claim = store.create(
        "claim",
        {
            "statement": "Synthetic fixture claim",
            "scope": "Fixtures only",
            "evidence_refs": [store.ref(original)],
        },
    )
    decision = store.create(
        "decision",
        {
            "question": "Synthetic dependent choice",
            "options": [{"id": "a", "description": "a"}],
            "evidence_refs": [store.ref(claim)],
        },
    )
    finding(
        store,
        kind="correction",
        statement="Synthetic coverage generator had an error",
        supersedes=store.ref(original),
    )
    assert store.location("finding", original["id"]).read_bytes() == before
    warnings = dependent_warnings(store)
    assert {warning["id"] for warning in warnings} == {claim["id"], decision["id"]}
    assert (
        next(item for item in recall(store, "coverage") if item["id"] == original["id"])["status"]
        == "superseded"
    )


def test_report_includes_failed_and_pending_runs(store, protocol):
    task = store.create("task", {"title": "Report fixture"})
    # External records let this test focus on inventory rather than execute task planning.
    good = import_run(
        store, {"task_id": task["id"], "execution_status": "completed"}, "external-good.json"
    )
    bad = import_run(
        store, {"task_id": task["id"], "execution_status": "failed"}, "external-bad.json"
    )
    hidden = finding(
        store,
        task_id=task["id"],
        visibility="restricted_evaluation",
        statement="PRIVATE_REPORT_DETAILS",
    )
    text = report(store, task["id"])
    assert good["id"] in text and bad["id"] in text
    assert "failed" in text and "pending" in text and "PRIVATE_REPORT_DETAILS" not in text
    assert hidden["id"] not in text
    before = store.all("run")
    assert resume(store, task["id"])["execution_policy"]
    assert store.all("run") == before


def test_held_out_requires_freeze_and_records_exposure(store, protocol):
    protocol["dataset_refs"][0]["role"] = "held_out_test"
    experiment = store.create("experiment", protocol)
    with pytest.raises(Prerequisite, match="freeze"):
        start(store, experiment["id"], [sys.executable, "-c", "pass"])
    updated = store.update(
        "experiment",
        experiment["id"],
        {
            "visibility": "restricted_evaluation",
            "freeze": {
                "code": "synthetic fixture checksum",
                "config": "fixture-v1",
                "evaluator": "fixture-v1",
                "metric": "exit",
                "selection_rule": "all attempts",
            },
            "approval_evidence": {
                "summary": "Synthetic holdout protocol",
                "source": "pytest fixture",
            },
            "revision_reason": "Fixture freeze",
        },
        1,
    )
    run, _ = start(store, updated["id"], [sys.executable, "-c", "pass"])
    assert run["visibility"] == "restricted_evaluation"
    assert len(store.all("exposure")) == 1
    assert status(store)["runs"] == []
    assert status(store, restricted=True)["runs"][0]["id"] == run["id"]


def test_read_commands_and_reminder_do_not_modify_repo(store):
    def snapshot():
        return {str(path): path.read_bytes() for path in store.root.rglob("*") if path.is_file()}

    before = snapshot()
    output = reminder("SessionStart", {"cwd": str(store.root)})
    assert output["hookSpecificOutput"]["additionalContext"]
    assert "decision" not in output
    status(store)
    doctor(store)
    assert snapshot() == before


def test_restricted_correction_warns_without_exposing_details(store):
    original = finding(store)
    claim = store.create(
        "claim",
        {
            "statement": "Public fixture claim",
            "scope": "Fixtures only",
            "evidence_refs": [store.ref(original)],
        },
    )
    correction = finding(
        store,
        kind="correction",
        supersedes=store.ref(original),
        visibility="restricted_evaluation",
        statement="PRIVATE_CORRECTION_DETAILS",
    )
    summary = status(store)
    assert claim["id"] in str(summary["review_warnings"])
    assert "PRIVATE_CORRECTION_DETAILS" not in str(summary)
    assert recall(store, "coverage")[0]["status"] == "superseded"
    path = store.location("finding", correction["id"])
    invalid = {**correction, "confidence": "PRIVATE_INVALID_VALUE"}
    path.write_text(json.dumps(invalid))
    from labledger.errors import LedgerError

    with pytest.raises(LedgerError) as captured:
        recall(store, "coverage")
    assert "PRIVATE_INVALID_VALUE" not in str(captured.value)


def test_known_holdout_feedback_cannot_be_relabelled_fresh(store, protocol):
    from labledger.storage import now

    store.create(
        "exposure",
        {
            "dataset_id": "synthetic",
            "dataset_version": "1",
            "role": "held_out_test",
            "purpose": "Synthetic debugging feedback",
            "details": "Synthetic failures used for development",
            "exposed_at": now(),
            "used_for_development": True,
            "visibility": "restricted_evaluation",
        },
    )
    protocol.update(
        {
            "visibility": "restricted_evaluation",
            "freeze": {
                "code": "fixture",
                "config": "fixture",
                "evaluator": "fixture",
                "metric": "exit",
                "selection_rule": "all",
            },
        }
    )
    protocol["dataset_refs"][0]["role"] = "held_out_test"
    experiment = store.create("experiment", protocol)
    with pytest.raises(Prerequisite, match="fresh holdout"):
        start(store, experiment["id"], [sys.executable, "-c", "pass"])


def test_exported_report_links_resolve_to_exact_revisions(store):
    import re
    from pathlib import Path

    task = store.create("task", {"title": "Link fixture"})
    run = import_run(store, {"task_id": task["id"], "execution_status": "failed"}, "synthetic.json")
    finding(store, task_id=task["id"], evidence_refs=[store.ref(run)])
    destination = store.research / "reports/report-1.md"
    text = report(store, task["id"], destination=destination)
    for target in re.findall(r"\]\(([^)]+)\)", text):
        assert (destination.parent / Path(target)).resolve().is_file()
    assert "history/1.json" in text

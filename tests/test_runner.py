import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from labledger.errors import Prerequisite
from labledger.runner import (
    annotate,
    identity,
    import_run,
    inspect_execution,
    process_state,
    reconcile,
    start,
)


def backend_process(store, operation, **arguments):
    process = subprocess.Popen(
        [sys.executable, "-c", "from labledger.backend import main; raise SystemExit(main())"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process.stdin.write(
        json.dumps({"operation": operation, "root": str(store.root), "arguments": arguments})
    )
    process.stdin.close()
    process.stdin = None
    return process


def until(predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError("Timed out waiting for synthetic child")


def test_manifest_precedes_child_and_logs_stream(store, experiment):
    source = store.root / "settings.json"
    source.write_text('{"synthetic": true}')
    script = "from pathlib import Path; import json,sys; m=list(Path('artifacts/runs').glob('*/manifest.json')); assert len(m)==1; assert json.loads(m[0].read_text())['record']['execution_status'] in ('queued','running'); sys.stdout.write('x'*2000000); sys.stderr.write('y'*1000000)"
    record, code = start(store, experiment["id"], [sys.executable, "-c", script], ["settings.json"])
    assert code == 0 and record["execution_status"] == "completed"
    assert record["research_outcome"] == "not_assessed" and record["analysis_status"] == "pending"
    assert {ref["size"] for ref in record["outputs"]["logs"]} == {2000000, 1000000}
    assert record["inputs"]["snapshots"][0]["checksum"]
    assert record["reproducibility_status"] == "partial"
    assert record["environment"].get("environ") is None


def test_completed_negative_is_distinct_from_failed_execution(store, experiment):
    record, _ = start(
        store, experiment["id"], [sys.executable, "-c", "print('synthetic metric: -1')"]
    )
    updated = annotate(
        store,
        record["id"],
        {
            "analysis_status": "analyzed",
            "research_outcome": "negative",
            "analysis": {
                "summary": "Synthetic metric is below the fixture baseline",
                "limitations": ["Synthetic data only"],
                "evidence_refs": [store.ref(record)],
            },
        },
        record["revision"],
    )
    assert updated["execution_status"] == "completed" and updated["research_outcome"] == "negative"
    failed, code = start(store, experiment["id"], [sys.executable, "-c", "raise SystemExit(7)"])
    assert code == 1 and failed["exit_code"] == 7
    assert failed["execution_status"] == "failed" and failed["research_outcome"] == "not_assessed"


def test_retry_is_new_run_and_preserves_parent(store, experiment):
    first, _ = start(store, experiment["id"], [sys.executable, "-c", "raise SystemExit(1)"])
    before = store.location("run", first["id"]).read_bytes()
    second, _ = start(
        store,
        experiment["id"],
        [sys.executable, "-c", "pass"],
        parent=first["id"],
        retry_reason="Synthetic retry fixture",
    )
    assert first["id"] != second["id"] and second["parent_run_id"] == first["id"]
    assert store.location("run", first["id"]).read_bytes() == before


def test_budget_timeout_and_spawn_failure_preserve_attempts(store, protocol):
    protocol["budget"]["wall_time_seconds"] = 0.15
    experiment = store.create("experiment", protocol)
    record, code = start(
        store, experiment["id"], [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    assert code == 1 and record["execution_status"] == "cancelled"
    assert "budget" in record["cancellation_reason"]
    failed, code = start(store, experiment["id"], ["/synthetic/missing-executable"])
    assert code == 1 and failed["execution_status"] == "failed"
    assert store.location("run", failed["id"]).exists()


def test_concurrent_run_budget_and_unique_ids(store, protocol):
    protocol["budget"]["max_runs"] = 1
    experiment = store.create("experiment", protocol)
    first = backend_process(
        store,
        "run.start",
        experiment=experiment["id"],
        argv=[sys.executable, "-c", "import time; time.sleep(.2)"],
    )
    second = backend_process(
        store,
        "run.start",
        experiment=experiment["id"],
        argv=[sys.executable, "-c", "import time; time.sleep(.2)"],
    )
    first.communicate(timeout=15)
    second.communicate(timeout=15)
    assert sorted([first.returncode, second.returncode]) == [0, 4]
    assert len(store.all("run")) == 1


def test_parallel_runs_have_separate_logs(store, experiment):
    processes = [
        backend_process(
            store,
            "run.start",
            experiment=experiment["id"],
            argv=[sys.executable, "-c", f"print('{word}')"],
        )
        for word in ("first", "second")
    ]
    for process in processes:
        process.communicate(timeout=15)
        assert process.returncode == 0
    runs = store.all("run")
    assert len({run["id"] for run in runs}) == 2
    outputs = [
        Path(
            store.root
            / next(
                (
                    ref["path"]
                    for ref in run["outputs"]["logs"]
                    if ref["path"].endswith("stdout.log")
                )
            )
        )
        .read_text()
        .strip()
        for run in runs
    ]
    assert sorted(outputs) == ["first", "second"]


@pytest.mark.skipif(os.name != "posix", reason="POSIX runner")
def test_user_cancellation_stops_descendants(store, experiment):
    worker = "import signal,time,os,json; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path('worker.json').write_text(json.dumps({'pid':os.getpid()})); time.sleep(30)"
    script = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{worker!r}]); time.sleep(30)"
    process = backend_process(
        store, "run.start", experiment=experiment["id"], argv=[sys.executable, "-c", script]
    )
    try:
        marker = store.root / "worker.json"
        until(marker.exists)
        worker_identity = identity(json.loads(marker.read_text())["pid"])
        process.send_signal(signal.SIGINT)
        process.communicate(timeout=15)
        assert process.returncode == 130
        until(lambda: process_state(worker_identity) == "stopped")
        record = store.all("run")[0]
        assert record["execution_status"] == "cancelled"
        assert record["analysis_status"] == "pending"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


@pytest.mark.skipif(os.name != "posix", reason="POSIX runner")
def test_killed_runner_reconciles_without_reporting_success(store, experiment):
    process = backend_process(
        store,
        "run.start",
        experiment=experiment["id"],
        argv=[sys.executable, "-c", "import time; time.sleep(.7)"],
    )
    try:

        def running():
            records = store.all("run")
            return records[0] if records and records[0]["execution_status"] == "running" else None

        record = until(running)
        process.kill()
        process.communicate(timeout=10)
        assert inspect_execution(record)["state"] == "orphan_live"
        with pytest.raises(Exception, match="orphan_live"):
            reconcile(store, record["id"], record["revision"], "Synthetic stopped observation")
        until(lambda: inspect_execution(record)["state"] == "stopped")
        updated = reconcile(
            store,
            record["id"],
            record["revision"],
            "Synthetic runner was killed and child has stopped",
        )
        assert updated["execution_status"] == "interrupted"
        assert updated["research_outcome"] == "not_assessed" and updated["exit_code"] is None
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()


def test_pid_reuse_and_uncertain_identity_are_not_success(store):
    current = identity()
    assert process_state(current) == "live"
    assert process_state({**current, "created_at": current["created_at"] - 10}) == "stopped"
    assert process_state({**current, "hostname": "another-host"}) == "unknown"
    record = import_run(store, {"execution_status": "running"}, "synthetic.json")
    with pytest.raises(Prerequisite):
        reconcile(store, record["id"], 1, "Inspected externally")
    updated = reconcile(
        store, record["id"], 1, "Operator independently verified cessation", confirm_stopped=True
    )
    assert updated["execution_status"] == "interrupted"


def test_external_import_does_not_infer_missing_metadata(store):
    record = import_run(store, {"execution_status": "failed"}, "synthetic.json")
    assert "exit_code" not in record
    assert record["research_outcome"] == "not_assessed"
    assert "External manifest missing started_at" in record["missing_metadata"]
    assert record["reproducibility_status"] == "partial"


def test_protocol_revision_preserves_old_run_links(store, experiment):
    run, _ = start(store, experiment["id"], [sys.executable, "-c", "pass"])
    with pytest.raises(Prerequisite, match="renewed approval"):
        store.update("experiment", experiment["id"], {"baseline": "changed"}, 1)
    revised = store.update(
        "experiment",
        experiment["id"],
        {
            "baseline": "changed",
            "approval_evidence": {
                "summary": "Synthetic changed baseline approved",
                "source": "pytest fixture",
            },
            "revision_reason": "Synthetic protocol change after result",
            "observed_results": [store.ref(run)],
        },
        1,
    )
    assert revised["revision"] == 2
    assert store.read("run", run["id"])["experiment_revision"] == 1


def test_secret_capture_is_rejected_before_launch(store, experiment):
    (store.root / ".env").write_text("SYNTHETIC_SECRET=not-real")
    with pytest.raises(Prerequisite, match="sensitive"):
        start(store, experiment["id"], [sys.executable, "-c", "pass"], [".env"])
    assert store.all("run") == []


def test_worker_continues_under_budget_after_leader_exits(store, protocol):
    protocol["budget"]["wall_time_seconds"] = 0.3
    experiment = store.create("experiment", protocol)
    worker = "import time; time.sleep(30)"
    script = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{worker!r}])"
    run, code = start(store, experiment["id"], [sys.executable, "-c", script])
    assert code == 1 and run["execution_status"] == "cancelled"
    assert run["exit_code"] == 0
    assert "budget" in run["cancellation_reason"]


def test_reapproval_cannot_bypass_protocol_history_via_draft(store, experiment):
    draft = store.update(
        "experiment", experiment["id"], {"status": "draft", "baseline": "changed while drafting"}, 1
    )
    with pytest.raises(Prerequisite, match="renewed approval"):
        store.update("experiment", experiment["id"], {"status": "approved"}, draft["revision"])


def test_dead_leader_with_live_group_is_not_reconciled_as_stopped(store, experiment):
    worker = "import time; time.sleep(.9)"
    script = f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{worker!r}])"
    process = backend_process(
        store, "run.start", experiment=experiment["id"], argv=[sys.executable, "-c", script]
    )
    try:

        def group_waiting():
            records = store.all("run")
            if not records or records[0]["execution_status"] != "running":
                return None
            return (
                records[0]
                if process_state(records[0]["execution"].get("child")) == "stopped"
                else None
            )

        record = until(group_waiting)
        process.kill()
        process.communicate(timeout=10)
        observed = inspect_execution(record)
        assert (
            observed["state"] == "unknown"
            and observed["process_group"] == "live_members_unverified"
        )
        with pytest.raises(Prerequisite):
            reconcile(store, record["id"], record["revision"], "Synthetic inspection")
        until(lambda: inspect_execution(record)["state"] == "stopped")
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

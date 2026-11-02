"""Developer check: exercise relocated plugin archives with synthetic data only."""

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import venv
import zipfile
from pathlib import Path


def smoke_archive(archive_path, workspace, python, environment):
    destination = workspace / archive_path.stem
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(destination)
    root = destination / "synthetic project"
    root.mkdir()
    helper = destination / "scripts/backend.py"
    reminder = destination / "scripts/remind.py"
    if reminder.exists():
        empty_cache = destination / "unprepared cache"
        cold = subprocess.run(
            [str(python), "-I", "-B", str(reminder), "SessionStart"],
            input=json.dumps({"cwd": str(root)}),
            capture_output=True,
            text=True,
            timeout=10,
            env={**environment, "XDG_CACHE_HOME": str(empty_cache)},
        )
        assert cold.returncode == 0 and cold.stdout == "" and not empty_cache.exists()

    def invoke(operation, payload=None, expected=0, **arguments):
        request = {"operation": operation, "root": str(root), "arguments": arguments}
        if payload is not None:
            request["payload"] = payload
        completed = subprocess.run(
            [str(python), "-I", "-B", str(helper)],
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=240,
            cwd=root,
            env=environment,
        )
        if completed.returncode != expected:
            raise AssertionError(
                f"{operation}: {completed.returncode}\n{completed.stdout}\n{completed.stderr}"
            )
        response = json.loads(completed.stdout)
        assert response["code"] == expected
        return response["result"]

    def ref(record):
        return {"type": record["entity_type"], "id": record["id"], "revision": record["revision"]}

    approval = {
        "summary": "Synthetic release fixture only",
        "source": "Automated smoke test; not real user approval",
    }
    preview = invoke(
        "init",
        payload={
            "name": "Synthetic release fixture",
            "charter": "# Synthetic charter\nTemporary process fixtures only; no research claims.",
        },
        dry_run=True,
    )
    assert preview["dry_run"] and (not (root / ".labledger").exists())
    # All later requests must work with index access disabled, including other adapters.
    environment["PIP_NO_INDEX"] = "1"
    invoke(
        "init",
        payload={
            "name": "Synthetic release fixture",
            "charter": "# Synthetic charter\nTemporary process fixtures only; no research claims.",
        },
    )
    assert invoke("init")["files"] == []
    task = invoke("task.new", payload={"title": "Synthetic bundled-plugin workflow"})
    decision = invoke(
        "decision.new",
        payload={
            "question": "Which fixture?",
            "options": [{"id": "fixture", "description": "Synthetic process fixture"}],
        },
    )
    assert decision["status"] == "proposed"
    decision = invoke(
        "decision.update",
        payload={
            "status": "approved",
            "selected_option": "fixture",
            "approved_scope": "Temporary synthetic subprocesses",
            "approval_evidence": approval,
        },
        id=decision["id"],
        expected_revision=1,
    )
    task = invoke(
        "task.update",
        payload={"decision_refs": [ref(decision)]},
        id=task["id"],
        expected_revision=1,
    )
    brief = {
        "brief": {
            key: f"Synthetic fixture {key}; bounded temporary files only."
            for key in [
                "problem",
                "scope",
                "evidence",
                "options",
                "direction",
                "constraints",
                "acceptance_criteria",
                "open_questions",
            ]
        }
    }
    task = invoke("handoff", payload=brief, task=task["id"], expected_revision=task["revision"])[
        "task"
    ]
    assert task["status"] == "ready_for_planning"
    assert invoke("handoff", task=task["id"], check=True)["ok"]
    task = invoke(
        "task.attach-plan",
        payload={
            "content": "## Synthetic plan\nRun one negative-result fixture and one failed process, preserve evidence, and report both.",
            "brief_revision": 1,
            "decision_refs": task["decision_refs"],
            "approval_evidence": approval,
            "planning_evidence": approval,
        },
        id=task["id"],
        execution=True,
        expected_revision=task["revision"],
    )
    task = invoke(
        "task.update",
        payload={"status": "implementing"},
        id=task["id"],
        expected_revision=task["revision"],
    )
    protocol = {
        "task_id": task["id"],
        "hypothesis": "Synthetic fixture metric exceeds zero",
        "status": "approved",
        "decision_refs": [ref(decision)],
        "baseline": "Zero fixture v1",
        "intervention": "Print negative fixture metric",
        "dataset_refs": [
            {
                "id": "synthetic",
                "version": "1",
                "role": "development",
                "provenance": "Generated smoke fixture",
            }
        ],
        "primary_metric": {
            "name": "fixture",
            "direction": "higher",
            "unit": "count",
            "denominator": "one synthetic process",
        },
        "secondary_metrics": [],
        "evaluation_unit": "synthetic process",
        "repetitions": {"seeds": [1]},
        "budget": {"max_runs": 3, "wall_time_seconds": 10},
        "success_criteria": "Fixture metric > 0",
        "stop_conditions": "Three attempts or ten seconds per attempt",
        "failure_handling": "Preserve failures",
        "analysis_plan": "Inspect synthetic output; no statistical claims",
        "approved_scope": "Three temporary synthetic processes, including cancellation",
        "approval_evidence": approval,
    }
    experiment = invoke("experiment.new", payload=protocol)
    good = invoke(
        "run.start",
        experiment=experiment["id"],
        argv=[sys.executable, "-c", "print('synthetic metric=-1')"],
    )["run"]
    bad = invoke(
        "run.start",
        expected=1,
        experiment=experiment["id"],
        argv=[sys.executable, "-c", "raise SystemExit(7)"],
    )["run"]
    assert good["execution_status"] == "completed" and bad["exit_code"] == 7
    cancelled_request = {
        "operation": "run.start",
        "root": str(root),
        "arguments": {
            "experiment": experiment["id"],
            "argv": [
                str(python),
                "-c",
                "from pathlib import Path; import time; Path('cancel-ready').touch(); time.sleep(30)",
            ],
        },
    }
    process = subprocess.Popen(
        [str(python), "-I", "-B", str(helper)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    try:
        process.stdin.write(json.dumps(cancelled_request))
        process.stdin.close()
        process.stdin = None
        deadline = time.monotonic() + 10
        while not (root / "cancel-ready").exists():
            if process.poll() is not None or time.monotonic() > deadline:
                raise AssertionError("Bundled runner did not start cancellation fixture")
            time.sleep(0.03)
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 130, (stdout, stderr)
        cancelled = json.loads(stdout)["result"]["run"]
        assert cancelled["execution_status"] == "cancelled"
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=15)
    good = invoke(
        "run.annotate",
        payload={
            "analysis_status": "analyzed",
            "research_outcome": "negative",
            "analysis": {
                "summary": "Synthetic metric -1 is below zero",
                "evidence_refs": [ref(good)],
                "limitations": ["Synthetic fixture only"],
            },
        },
        id=good["id"],
        expected_revision=good["revision"],
    )
    finding = invoke(
        "finding.add",
        payload={
            "task_id": task["id"],
            "kind": "observation",
            "statement": "Synthetic metric was below its fixture baseline",
            "scope": "One synthetic process",
            "evidence_refs": [ref(good)],
            "limitations": ["Not research evidence"],
            "confidence": "tentative",
            "alternative_explanations": ["The fixture prints a fixed value"],
            "next_action": "Inspect smoke report",
        },
    )
    assert invoke("recall", query="synthetic baseline")["findings"][0]["id"] == finding["id"]
    output = invoke("report", task=task["id"], output="research/reports/synthetic-1.md")
    assert bad["id"] in output["content"] and "negative" in output["content"]
    assert set(invoke("resume", task=task["id"])["outstanding_analysis"]) == {
        bad["id"],
        cancelled["id"],
    }
    assert invoke("doctor")["ok"]
    if reminder.exists():
        before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        warm = subprocess.run(
            [str(python), "-I", "-B", str(reminder), "SessionStart"],
            input=json.dumps({"cwd": str(root)}),
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        assert warm.returncode == 0 and "hookSpecificOutput" in json.loads(warm.stdout)
        assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    print(
        json.dumps(
            {
                "archive": archive_path.name,
                "synthetic_plugin_workflow": "passed",
                "relocated": True,
                "separate_core_installed": False,
                "real_host_sessions_tested": False,
            }
        ),
        flush=True,
    )
    return helper, root, task["id"]


def main():
    parser = argparse.ArgumentParser(
        description="Verify the bundled plugin backend, not host behavior"
    )
    parser.add_argument(
        "--plugins", type=Path, default=Path(__file__).resolve().parents[1] / "dist/plugins"
    )
    args = parser.parse_args()
    archives = sorted(args.plugins.glob("*.zip"))
    if not archives:
        raise SystemExit("Build plugin archives first")
    with tempfile.TemporaryDirectory(prefix="labledger plugin smoke ") as directory:
        workspace = Path(directory)
        clean = workspace / "host python"
        venv.EnvBuilder(symlinks=True).create(clean)
        python = clean / "bin/python"
        probe = subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import importlib.util; assert importlib.util.find_spec('labledger') is None",
            ],
            capture_output=True,
            text=True,
        )
        assert probe.returncode == 0, probe.stderr
        environment = {**os.environ, "XDG_CACHE_HOME": str(workspace / "cache")}
        contexts = [smoke_archive(archive, workspace, python, environment) for archive in archives]
        for index, (_, root, task_id) in enumerate(contexts):
            other_helper = contexts[(index + 1) % len(contexts)][0]
            before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            resumed = subprocess.run(
                [str(python), "-I", "-B", str(other_helper)],
                input=json.dumps(
                    {"operation": "resume", "root": str(root), "arguments": {"task": task_id}}
                ),
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
            )
            assert resumed.returncode == 0, resumed.stdout
            assert json.loads(resumed.stdout)["result"]["tasks"][0]["id"] == task_id
            assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        print(json.dumps({"cross_package_resume": "passed", "real_host_sessions_tested": False}))


if __name__ == "__main__":
    main()

import json

import pytest

from labledger.project import initialize
from labledger.storage import Store


@pytest.fixture
def store(tmp_path):
    initialize(
        tmp_path,
        {
            "name": "Synthetic test project",
            "charter": "# Charter\n\nSynthetic fixture; no research observations.\n",
        },
    )
    return Store(tmp_path)


@pytest.fixture
def approval():
    return {
        "summary": "Synthetic fixture approval for a bounded test",
        "source": "pytest fixture; not a real user approval",
    }


@pytest.fixture
def decision(store, approval):
    return store.create(
        "decision",
        {
            "question": "Which synthetic approach?",
            "options": [{"id": "a", "description": "Bounded synthetic approach"}],
            "status": "approved",
            "selected_option": "a",
            "approved_scope": "Execute synthetic processes in temporary test directories",
            "approval_evidence": approval,
        },
    )


@pytest.fixture
def protocol(approval, decision, store):
    return {
        "hypothesis": "A synthetic test child exits normally",
        "status": "approved",
        "decision_refs": [store.ref(decision)],
        "baseline": "Synthetic zero baseline v1",
        "intervention": "Synthetic child only",
        "dataset_refs": [
            {
                "id": "synthetic",
                "version": "1",
                "role": "development",
                "provenance": "Generated fixture",
            }
        ],
        "primary_metric": {
            "name": "exit",
            "direction": "lower",
            "unit": "code",
            "denominator": "one process",
        },
        "secondary_metrics": [],
        "evaluation_unit": "one temporary process",
        "repetitions": {"seeds": [1]},
        "budget": {"max_runs": 20, "wall_time_seconds": 10},
        "success_criteria": "Exit zero",
        "stop_conditions": "Stop after ten seconds",
        "failure_handling": "Keep every failure; retries create new run IDs",
        "analysis_plan": "Inspect each exit independently",
        "approval_evidence": approval,
        "approved_scope": "Synthetic temporary process fixtures",
    }


@pytest.fixture
def experiment(store, protocol):
    return store.create("experiment", protocol)


@pytest.fixture
def brief():
    return {
        "brief": {
            "problem": "Synthetic workflow fixture",
            "scope": "Temporary test files only; no research conclusions",
            "evidence": "Synthetic protocol",
            "options": "Bounded fixture",
            "direction": "Run the synthetic fixture",
            "constraints": "No external data, compute or API calls",
            "acceptance_criteria": "Fixture is preserved",
            "open_questions": "None for this fixture",
        },
        "references": [],
    }


@pytest.fixture
def write_json(tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value))
        return str(path)

    return write

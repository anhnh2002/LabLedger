import copy

import pytest

from labledger.doctor import doctor
from labledger.errors import Conflict
from labledger.policy import update_policy
from labledger.storage import Store


def test_policy_updates_preserve_history_and_detect_external_changes(store, approval):
    before = (store.meta / "policy/history/1.json").read_bytes()
    config = copy.deepcopy(store.config)
    config["adapters"]["hooks"] = "disabled"
    updated = update_policy(
        store,
        {"config": config, "charter": "# Revised synthetic charter", "approval_evidence": approval},
        1,
    )
    assert updated["revision"] == 2
    assert (store.meta / "policy/history/1.json").read_bytes() == before
    assert Store(store.root).config["adapters"]["hooks"] == "disabled"
    assert doctor(store)["ok"]
    with pytest.raises(Conflict):
        update_policy(
            store,
            {"config": config, "charter": "Another fixture", "approval_evidence": approval},
            1,
        )
    (store.research / "CHARTER.md").write_text("External charter edit")
    assert any(item.get("code") == "unrecorded_policy_change" for item in doctor(store)["warnings"])


def test_policy_does_not_move_storage(store, approval):
    config = copy.deepcopy(store.config)
    config["project"]["research_dir"] = "elsewhere"
    with pytest.raises(Conflict):
        update_policy(
            store, {"config": config, "charter": "Fixture", "approval_evidence": approval}, 1
        )

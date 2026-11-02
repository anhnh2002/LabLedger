import json

from .errors import Conflict, LedgerError
from .schema import validate
from .storage import encoded, now


def initial_policy(config, charter):
    return {
        "schema_version": 1,
        "revision": 1,
        "created_at": now(),
        "config": config,
        "charter": charter,
        "change_evidence": {
            "summary": "Initialized from the supplied charter and configuration",
            "source": "init input; the caller is responsible for obtaining actual approval",
        },
    }


def render_config(config):
    lines = [f"schema_version = {config['schema_version']}", ""]
    for section, values in config.items():
        if section == "schema_version":
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines)


def update_policy(store, payload, expected):
    if set(payload) != {"config", "charter", "approval_evidence"}:
        raise LedgerError("Policy inputs are config, charter and approval_evidence")
    validate(payload["config"], "config")
    validate(payload["approval_evidence"], "approval")
    if not isinstance(payload["charter"], str) or not payload["charter"].strip():
        raise LedgerError("Policy charter must be nonempty Markdown")
    for key in ("research_dir", "artifacts_dir"):
        if payload["config"]["project"][key] != store.config["project"][key]:
            raise Conflict("Policy updates cannot relocate research or artifact storage")
    with store.locked():
        path = store.meta / "policy/current.json"
        if not path.exists():
            raise Conflict("Policy baseline is missing; run init to record it")
        current = json.loads(path.read_text())
        validate(current, "policy_snapshot")
        if current["revision"] != expected:
            raise Conflict(f"Expected policy revision {expected}; current is {current['revision']}")
        updated = {
            "schema_version": 1,
            "revision": expected + 1,
            "created_at": now(),
            "config": payload["config"],
            "charter": payload["charter"].rstrip() + "\n",
            "change_evidence": payload["approval_evidence"],
        }
        history = store.meta / "policy/history" / f"{expected + 1}.json"
        if history.exists():
            raise Conflict("Policy revision already exists")
        store.commit(
            {
                path: encoded(updated),
                history: encoded(updated),
                store.meta / "config.toml": render_config(updated["config"]),
                store.research / "CHARTER.md": updated["charter"],
            }
        )
        store.config = updated["config"]
        return updated

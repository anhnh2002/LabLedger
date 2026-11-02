import json

from .errors import LedgerError
from .memory import status
from .storage import Store, find_root


def reminder(event, payload):
    """Read-only, bounded context. Never block, approve, or change ledger state."""
    try:
        store = Store(find_root(payload.get("cwd")))
        if store.config["adapters"]["hooks"] == "disabled":
            return {}
        summary = status(store)
        ready = sum(task["status"] == "ready_for_planning" for task in summary["tasks"])
        text = (
            f"LabLedger: {ready} tasks ready for a NEW native planning session; "
            f"{len(summary['outstanding_analysis'])} runs pending analysis. "
            "Use the LabLedger resume skill in this session for durable context. Record actual approvals only. "
            "Do not rerun experiments automatically."
        )
        if event == "SessionStart":
            return {
                "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}
            }
        return {"systemMessage": text}
    except (LedgerError, OSError, ValueError):
        return {}  # Missing ledger or an incomplete transaction must not block the host.


def main(event, raw):
    try:
        payload = json.loads(raw or "{}")
        return reminder(event, payload) if isinstance(payload, dict) else {}
    except (ValueError, TypeError):
        return {}

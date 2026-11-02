"""Deterministic document generation and execution-time plan persistence."""

import re

from .errors import Conflict, LedgerError, Prerequisite
from .project import git_metadata
from .storage import digest, now

BRIEF_SECTIONS = {
    "problem": "Problem and motivation",
    "scope": "Scope and non-goals",
    "evidence": "Evidence reviewed",
    "options": "Options considered",
    "direction": "Agreed direction",
    "constraints": "Constraints",
    "acceptance_criteria": "Acceptance criteria",
    "open_questions": "Open questions",
}
PLACEHOLDER = re.compile(r"<(?:task-id|revision|ids and revisions)>|\{\{[^}]+\}\}")


def task_status(store, task):
    runs = [
        record
        for record in store.all("run")
        if record.get("task_id") == task["id"] and record["visibility"] == task["visibility"]
    ]
    findings = [
        record
        for record in store.all("finding")
        if record.get("task_id") == task["id"] and record["visibility"] == task["visibility"]
    ]
    evidence = (
        ", ".join(map(reference_label, task.get("completion_evidence", [])))
        or "No completion evidence recorded."
    )
    pending = (
        ", ".join(record["id"] for record in runs if record["analysis_status"] == "pending")
        or "None recorded."
    )
    found = ", ".join(record["id"] for record in findings) or "None recorded."
    return (
        f"# Task status\n\n<!-- Generated from record.json; ask the LabLedger agent to update it. -->\n\n"
        f"Task: {task['id']}\nState: {task['status']}\nUpdated at: {task['updated_at']}\n"
        f"Active brief revision: {task['brief_revision']}\nActive plan revision: {task['plan_revision']}\n\n"
        f"## Next action\n\n{task.get('next_action', 'Ask LabLedger to inspect status and referenced records.')}\n\n"
        f"## Blockers\n\n{task.get('blocker_reason', 'None recorded.')}\n"
        f"\n## Completed\n\n{evidence}\n\n## In progress\n\nCurrent phase: {task['status']}.\n"
        f"\n## Findings and pending analysis\n\nFindings: {found}\nPending runs: {pending}\n"
    )


def reference_label(ref):
    if "id" in ref:
        return f"{ref['type']}:{ref['id']}@{ref['revision']}"
    return ref.get("path", ref.get("uri", "unknown"))


def dependency_issues(store, references):
    issues = []
    superseded = {record["supersedes"]["id"] for record in store.all() if record.get("supersedes")}
    for ref in references:
        if "id" in ref:
            try:
                current = store.read(ref["type"], ref["id"])
                if current["revision"] != ref["revision"]:
                    issues.append(
                        f"Stale reference {reference_label(ref)}; current revision {current['revision']}"
                    )
                if current.get("status") in ("superseded", "rejected", "withdrawn"):
                    issues.append(f"Inactive reference {reference_label(ref)}")
                if ref["id"] in superseded:
                    issues.append(f"Superseded evidence {reference_label(ref)} requires review")
            except LedgerError as error:
                issues.append(str(error))
        elif "path" in ref and ref.get("availability", "available") == "available":
            path = store.path(ref["path"])
            if not path.exists():
                issues.append(f"Missing document {ref['path']}")
            elif ref.get("checksum") and digest(path.read_bytes()) != ref["checksum"]:
                issues.append(f"Changed evidence {ref['path']}")
    return issues


def check_handoff(store, task):
    handoff = task.get("handoff")
    if not handoff:
        return ["Task has no handoff"]
    issues = dependency_issues(store, handoff["references"])
    if handoff["brief_revision"] != task["brief_revision"]:
        issues.append("Handoff refers to an older brief")
    if handoff["decision_refs"] != task["decision_refs"]:
        issues.append("Handoff decision references differ from task")
    for name, checksum in handoff["documents"].items():
        path = store.location("task", task["id"]).parent / name
        if not path.is_file() or digest(path.read_bytes()) != checksum:
            issues.append(f"Missing or edited handoff document: {name}")
    return issues


def check_plan(store, task):
    plan = task.get("plan")
    if not plan:
        return ["Task has no persisted approved plan"]
    issues = check_handoff(store, task)
    if (
        plan["brief_revision"] != task["brief_revision"]
        or plan["decision_refs"] != task["decision_refs"]
    ):
        issues.append("Approved plan is based on older brief/decision revisions")
    issues.extend(dependency_issues(store, plan["decision_refs"]))
    path = store.location("task", task["id"]).parent / "PLAN.md"
    if not path.exists() or digest(path.read_bytes()) != plan["checksum"]:
        issues.append("Persisted plan is missing or edited")
    return issues


def handoff(store, identifier, payload, expected):
    from .schema import validate

    validate(payload, "handoff_input")
    with store.locked():
        task = store.read("task", identifier)
        if task["revision"] != expected:
            raise Conflict("Task changed before handoff generation")
        if task["visibility"] != "development":
            raise Prerequisite("Restricted tasks cannot generate development handoffs")
        unknown = set(payload) - {"brief", "references"}
        if unknown:
            raise LedgerError(f"Unknown handoff inputs: {sorted(unknown)}")
        brief = payload.get("brief", {})
        missing = [
            key
            for key in BRIEF_SECTIONS
            if not isinstance(brief.get(key), str) or not brief[key].strip()
        ]
        if missing:
            raise LedgerError(f"Missing brief sections: {', '.join(missing)}")
        if not task["decision_refs"]:
            raise Prerequisite(
                "Handoff requires an approved research or bounded exploration decision"
            )
        policy_paths = [store.research / "CHARTER.md", store.meta / "config.toml"]
        policy_paths += [
            store.root / name for name in ("AGENTS.md", "CLAUDE.md") if (store.root / name).exists()
        ]
        policy_refs = [
            {
                "type": "document",
                "path": store.relative(path),
                "checksum": digest(path.read_bytes()),
            }
            for path in policy_paths
        ]
        refs = task["decision_refs"] + payload.get("references", []) + policy_refs
        for ref in refs:
            validate(ref, "reference")
        store.check_references({"visibility": "development", "evidence_refs": refs})
        issues = dependency_issues(store, refs)
        if issues:
            raise Conflict("; ".join(issues))
        for ref in task["decision_refs"]:
            if (
                ref["type"] != "decision"
                or store.read("decision", ref["id"], ref["revision"])["status"] != "approved"
            ):
                raise Prerequisite("Handoff decisions must be approved")
        base = store.location("task", identifier).parent
        revision = task["brief_revision"] + 1
        brief_text = (
            f"# Research brief\n\nTask: {identifier}\nRevision: {revision}\n"
            f"Decision references: {', '.join(map(reference_label, task['decision_refs']))}\n\n"
        )
        brief_text += "\n".join(
            f"## {title}\n\n{brief[key].strip()}\n" for key, title in BRIEF_SECTIONS.items()
        )
        brief_text += (
            "\n## Relevant files and records\n\n"
            + "\n".join(f"- {reference_label(ref)}" for ref in refs)
            + "\n"
        )
        root_rel = store.relative(store.research)
        task_rel = store.relative(base)
        state = git_metadata(store.root)
        handoff_text = (
            f"# Fresh session handoff\n\nStart a NEW Codex or Claude Code session in this repository.\n"
            f"Enable the host's native Plan Mode before starting. Do not implement in planning.\n"
            f"Do not rely on the previous conversation.\n\nTask: {identifier}\nBrief revision: {revision}\n"
            f"Repository state: {state}\n\n## Read first\n\n"
            f"1. Applicable AGENTS.md or CLAUDE.md instructions.\n2. {root_rel}/CHARTER.md\n"
            f"3. {task_rel}/BRIEF.md\n4. {task_rel}/STATUS.md and record.json\n"
            f"5. The decisions, findings, and sources referenced by the brief.\n\n"
            "## Planning task\n\nInspect the actual repository, branch, code entry points, and drift from this handoff.\n"
            "Recall permitted findings. Propose an implementation plan within the approved direction,\n"
            "with dependencies, verification, experiment protocol, scope, and acceptance criteria.\n"
            "Separate approved decisions, assumptions, and open questions. Discuss material changes\n"
            "to method, evaluation, scope, or acceptance criteria before adopting them.\n"
            "Present the plan for user review. Planning does not require repository writes.\n\n"
            "## Transition to execution\n\nAfter approval and transition out of Plan Mode, have the LabLedger agent persist the plan using backend `task.attach-plan` with `execution: true`\n"
            "to persist PLAN.md with its brief/decision revisions and real approval evidence, before\n"
            "changing research code. Record the observed planning session; never invent its identity.\n"
            "Then enter implementing, register experiments, preserve failed attempts, and maintain findings and status.\n"
        )
        prompt = (
            f"I am starting a NEW session in the same repository for {identifier}.\n"
            "Use native Plan Mode; I will enable it using the host's control.\n"
            f"Read {task_rel}/HANDOFF.md and the files it references. Treat these documents as\n"
            "durable context; do not assume access to the previous chat. Inspect the repository and\n"
            "propose a plan within the agreed research direction. Discuss material changes with me.\n"
            "Present the plan for review before implementation. After approval and switching to execution,\n"
            "persist PLAN.md, then implement and maintain experiment records, findings, and task status.\n"
        )
        documents = {"BRIEF.md": brief_text, "HANDOFF.md": handoff_text, "PROMPT.txt": prompt}
        if any(PLACEHOLDER.search(content) for content in documents.values()):
            raise LedgerError("Generated documents contain unfilled placeholders")
        metadata = {
            "brief_revision": revision,
            "decision_refs": task["decision_refs"],
            "references": refs,
            "repository": state,
            "created_at": now(),
            "documents": {name: digest(content.encode()) for name, content in documents.items()},
        }
        next_state = (
            "ready_for_planning"
            if task["status"] in ("brainstorming", "ready_for_planning")
            else task["status"]
        )
        patch = {
            "brief_revision": revision,
            "handoff": metadata,
            "status": next_state,
            "next_action": "Open a NEW session in this repository, enable native Plan Mode, and paste PROMPT.txt.",
        }

        def extra(updated):
            changes = {base / "STATUS.md": task_status(store, updated)}
            for name, content in documents.items():
                history = base / "documents" / f"brief-{revision}" / name
                if history.exists():
                    raise Conflict("Immutable document revision already exists")
                changes.update({base / name: content, history: content})
            return changes

        updated = store.update("task", identifier, patch, expected, extra=extra, internal=True)
        return {
            "task": updated,
            "prompt": prompt,
            "steps": [
                "Open a NEW Codex or Claude Code session in the same repository.",
                "Enable native Plan Mode using /plan or the host's corresponding control.",
                f"Paste the generated prompt from {task_rel}/PROMPT.txt.",
                "Review the plan; after approval, switch to execution to implement.",
            ],
        }


def attach_plan(store, identifier, payload, expected, execution=False):
    if not execution:
        raise Prerequisite("Persist the plan only after leaving Plan Mode; set execution to true")
    with store.locked():
        task = store.read("task", identifier)
        if expected != task["revision"]:
            raise Conflict("Task changed before plan attachment")
        issues = check_handoff(store, task)
        if issues:
            raise Conflict("; ".join(issues))
        from .schema import validate

        validate(payload, "plan_input")
        required = (
            "content",
            "approval_evidence",
            "brief_revision",
            "decision_refs",
            "planning_evidence",
        )
        store.require(payload, *required)
        if set(payload) - set(required):
            raise LedgerError("Unknown plan input field")
        validate(payload["approval_evidence"], "approval")
        validate(payload["planning_evidence"], "approval")
        if (
            payload["brief_revision"] != task["brief_revision"]
            or payload["decision_refs"] != task["decision_refs"]
        ):
            raise Conflict("Approved plan must identify the active brief and decision revisions")
        if not isinstance(payload["content"], str) or PLACEHOLDER.search(payload["content"]):
            raise LedgerError("Plan must be Markdown without unfilled placeholders")
        if task["status"] == "ready_for_planning":
            task = store.update(
                "task",
                identifier,
                {"status": "planning", "planning_evidence": payload["planning_evidence"]},
                task["revision"],
                internal=True,
            )
        if task["status"] not in ("planning", "plan_approved", "implementing", "evaluating"):
            raise Conflict(f"Cannot attach an execution plan while {task['status']}")
        revision = task["plan_revision"] + 1
        content = (
            f"# Approved implementation plan\n\nTask: {identifier}\nPlan revision: {revision}\n"
            f"Based on brief revision: {task['brief_revision']}\n"
            f"Decision references: {', '.join(map(reference_label, task['decision_refs']))}\n"
            f"Approval evidence: {payload['approval_evidence']}\n"
            f"Planning evidence: {payload['planning_evidence']}\n\n{payload['content'].strip()}\n"
        )
        plan = {
            "revision": revision,
            "brief_revision": task["brief_revision"],
            "decision_refs": task["decision_refs"],
            "approval_evidence": payload["approval_evidence"],
            "checksum": digest(content.encode()),
        }
        patch = {
            "plan_revision": revision,
            "plan": plan,
            "approval_evidence": payload["approval_evidence"],
            "next_action": "Enter implementing and execute the approved plan.",
        }
        if task["status"] == "planning":
            patch["status"] = "plan_approved"
        base = store.location("task", identifier).parent

        def extra(updated):
            history = base / "documents" / f"plan-{revision}" / "PLAN.md"
            if history.exists():
                raise Conflict("Immutable plan document already exists")
            return {
                base / "PLAN.md": content,
                history: content,
                base / "STATUS.md": task_status(store, updated),
            }

        return store.update("task", identifier, patch, task["revision"], extra=extra, internal=True)

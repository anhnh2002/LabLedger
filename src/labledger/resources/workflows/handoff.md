# Prepare a fresh-session handoff

Read the task, approved decision revisions, relevant findings, charter, and code entry
points. The task must identify an approved direction or bounded exploration. Distinguish
accepted decisions, assumptions, and open questions.

Use backend operations `schema` (kind `task`) and `task.get` to inspect metadata. Create
the handoff payload yourself with `brief` sections: problem, scope, evidence, options,
direction, constraints, acceptance_criteria, open_questions. Sections are Markdown
strings; write "None known" only when accurate. Add typed `references` to records and
actual project-relative paths or external sources. Mark unavailable/external references.
Include the budget, stop conditions, evaluation boundaries, and approved scope.

Invoke `handoff` with task ID, expected_revision, and the payload, then invoke `handoff`
with the task ID and `check: true`. Resolve stale decisions with the researcher; do not
silently choose newer revisions. Never include secrets or restricted held-out details in
development context. Regeneration retains older document versions.

Return all four steps and the actual generated prompt: open a NEW Codex or Claude Code
session in the same repository; enable native Plan Mode using /plan or the host control;
paste PROMPT.txt; review the plan and switch to execution after approval. Paths must be
filled. This is a handoff, not evidence that a session started.

In the new planning session, read HANDOFF.md and its references, inspect repository
drift, and propose a plan within approved direction. Discuss material departures. Do not
write to the repository merely to record planning. Once the user approves and the host
enters execution, use `task.attach-plan` with `execution: true`, matching brief/decision
revisions, the approved plan content, approval_evidence, and honest planning_evidence.
Then update the task to implementing before code changes.

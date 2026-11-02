# Resume from durable context

Use backend `resume` with the task ID, then read the charter, task status,
handoff/brief, approved plan if present, and relevant records. Inspect actual repository
drift. Separate agreed decisions, current evidence, open questions, and stale
references. Report one concrete next action plus blockers and pending/deferred analysis.

ready_for_planning means the user must open a NEW session in native Plan Mode; an
exported prompt does not prove planning occurred. While in Plan Mode, inspect and
propose a plan without requiring repository writes. Persist approval and actual planning
evidence only after entering execution. Discuss material direction changes.

Inspect live/uncertain runs with doctor. Do not use PID alone, mark success without
evidence, relaunch an expensive experiment, or overwrite a failed attempt. Explicit
`run.reconcile` records interruption after verified cessation; uncertainty needs
operator confirmation and evidence. Recall findings before repeating an approach.

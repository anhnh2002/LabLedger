---
name: brainstorm
description: "Discuss a research decision and hand off the agreed direction to a fresh planning session."
---

Use the LabLedger 0.1.0 backend bundled with this plugin.
Perform the workflow inside this Codex or Claude Code session. Discuss missing
information and material decisions with the user; inspect the repository first.
Create every JSON request yourself from the discussion and observed evidence,
then invoke the private helper. Never delegate payload creation or backend
commands to the user. Continue routine steps already authorized.

Read [the private backend protocol](../../resources/backend.md) for helper
invocation, operations, schemas, runtime setup, and error handling.
Read [the brainstorm workflow](../../resources/workflows/brainstorm.md).
Read [research conventions](../../resources/conventions.md) for the shared boundaries.
In native Plan Mode, inspect and discuss without writing project files; defer
persistence until execution. The host's tool permissions still apply.
After agreement, read [handoff](../../resources/workflows/handoff.md) and finish at that boundary.

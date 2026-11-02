# Discuss a research direction

Read the charter and task status; inspect relevant code and permitted findings. Use
backend operation `recall` with `arguments.query` before proposing a repeated or new
approach. Explain which conditions have changed when revisiting a negative finding.

Present the problem, evidence, viable options, tradeoffs, assumptions, expected cost,
and an experiment that could distinguish the options. Recommend a direction with a short
evidence-based explanation. Do not invent alternatives to fill a quota. A bounded
exploration can be the approved direction when evidence is insufficient.

Use `task.new`, `decision.new`, and revision-checked `decision.update` to preserve the
discussion. Decisions default to proposed. Mark approved only after actual user
confirmation, with a selected option ID, approved scope, and approval evidence
containing summary and source. Use a real source description when no stable message
reference exists; never fabricate IDs or treat silence as approval. Link the task's
decision_refs to the exact approved revisions.

After agreement, perform the handoff workflow below using the shared handoff reference
in this package. Produce BRIEF.md, HANDOFF.md, task STATUS.md, and the filled paste
prompt. Finish this session at the handoff boundary. Tell the user to open a NEW session
in the same repository, enable native Plan Mode, paste the prompt, then review the plan
and switch to execution after approval. Do not begin planning or implementation in this
brainstorming session. You cannot switch modes or open a session on the user's behalf.

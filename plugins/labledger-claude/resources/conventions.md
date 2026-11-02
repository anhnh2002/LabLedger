# LabLedger research conventions

Read the charter under the research_dir configured in `.labledger/config.toml` and the active task's status before research work.
Use the installed LabLedger workflows for init, brainstorm, handoff, recall, run,
analyze, resume, doctor, report, and review-generalization inside the current
Codex or Claude Code session. The agent creates JSON requests and uses the backend
bundled with the plugin; the user supplies goals and decisions, not payload files
or backend commands. There is no separate LabLedger executable or core install.

Before a research decision, review evidence, present viable options and tradeoffs,
and obtain the user's decision. Continue routine steps within already approved scope.

After an agreed brainstorm, persist a brief and handoff, then finish at the handoff
boundary. Tell the user to open a NEW session in the same repository, enable native
Plan Mode, and paste the generated prompt. Never claim that the session opened or
read the documents without observing it.

In that planning session, inspect the repository and referenced records. Present a
plan for review. Discuss material departures from the approved research direction.
Planning must work without writing repository files. After approval and transition
to execution, persist the approved plan before changing research code.

Implement for the declared problem class; document assumptions and evidence beyond
the triggering case. Avoid benchmark-specific branches solely to improve scores.
Register experiments before running them. Preserve failures, cancellations, negative
results, and pending analysis. Exit code establishes execution status, not findings.
Link observations and claims to evidence with scope and limitations. Recall findings
before repeating an approach and explain changed conditions. Preserve corrections.
Keep development feedback separate from restricted evaluation analysis; record known
exposure and protocol changes. Never inject held-out details into development recall.
Update durable task status. Do not invent approvals, runs, costs, or transitions.

These conventions operate within the host's instructions and permissions. Backend checks
validate recorded prerequisites; they do not authenticate user approval or prevent
execution outside LabLedger. Hooks are optional reminders.

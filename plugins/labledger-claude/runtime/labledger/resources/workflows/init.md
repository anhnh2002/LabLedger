# Initialize a research ledger in this session

Inspect applicable repository instructions, existing code, environment files, and
build/test entry points. Report confirmed facts and unknowns. Do not run unknown scripts
merely to identify a project. If a ledger exists, read its charter first.

Agree a charter with the researcher: questions and motivation; scope, assumptions,
non-goals; baseline and success criteria; dataset provenance and split roles;
time/compute/API budget and stopping conditions; decision approval policy; authorized
routine actions; known build, test, and experiment commands. Use facts and answers
already available. Ask only for missing material information. An explicit existing
instruction can approve bounded work. Do not reopen already approved steps.

After agreement, create the JSON request yourself using backend operation `init`. The
payload contains `name`, `charter` (Markdown), and optional `research_dir` and
`artifacts_dir`. Use the repository's absolute root. Never ask the user to create
init.json, fill a JSON template, or invoke a backend command.

First use `arguments: {"dry_run": true}` to inspect exact proposed files and conflicts.
Explain material changes in ordinary language. Apply the same agreed payload with
`dry_run: false` when authorized; no extra approval is needed for routine agreed setup.
Resolve conflicts with the researcher before applying conflicting changes. Do not
overwrite instructions or move code/datasets. Check the returned doctor result and
explain created files and the next session action. Repeated init preserves the existing
charter and user-authored content; it does not change policy.

In native Plan Mode, complete inspection and discussion only. Keep the proposed payload
in the conversation and defer file creation and initialization to execution.

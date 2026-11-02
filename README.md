# LabLedger

LabLedger is a plugin for research work inside **Codex and Claude Code sessions**.
Discuss goals and decisions with your coding agent; it inspects the repository,
creates JSON requests, keeps durable records, runs approved experiments, and
reports evidence. Every LabLedger workflow happens in the session.

There is no separate LabLedger CLI or core installation. Each plugin includes the
Python backend, schemas, workflows, and private helpers. Python 3.11+ on macOS or
Linux is required. On first use, the agent's helper prepares pinned dependencies
in a user cache; that step needs package-index access. No API key or server is needed.

## Use in a coding-agent session

Install the host plugin using [the installation guide](docs/INSTALLATION.md), then
open the repository in Codex or Claude Code.

| Workflow | Codex skill | Claude Code skill |
| --- | --- | --- |
| Initialize | `$labledger-init` | `/labledger:init` |
| Discuss a direction | `$labledger-brainstorm` | `/labledger:brainstorm` |
| Prepare a handoff | `$labledger-handoff` | `/labledger:handoff` |
| Recall findings | `$labledger-recall` | `/labledger:recall` |
| Run an experiment | `$labledger-run` | `/labledger:run` |
| Analyze evidence | `$labledger-analyze` | `/labledger:analyze` |
| Resume work | `$labledger-resume` | `/labledger:resume` |
| Diagnose problems | `$labledger-doctor` | `/labledger:doctor` |
| Report results | `$labledger-report` | `/labledger:report` |
| Review generalization | `$labledger-review-generalization` | `/labledger:review-generalization` |

You can also ask the agent in ordinary language to use LabLedger. For example:
“Use LabLedger to initialize this repository. Discuss the research goals with me,
then create the files from what we agree.” You do not prepare an init.json or
operate the backend yourself.

1. Invoke init. The agent reads the repo, discusses the charter, previews changes,
   initializes the ledger, and explains the result.
2. Brainstorm a direction. After agreement, the agent saves the brief, handoff,
   task status, and filled prompt.
3. Open a **new session** in the same repository and enable **native Plan Mode**.
   Paste the handoff prompt and review the proposed plan.
4. After approval and switching to execution, the agent persists the plan before
   implementation, registers approved experiments, and preserves every attempt.
5. Ask for analysis, recall, reports, or resume in this session or on the other host.

Existing authorization carries forward within its scope. The agent asks about
missing information and material decisions. Native planning works without writing
project files; persistence waits for execution.

## Durable records

JSON records and immutable revisions are canonical. Markdown retains human context.
Durable run records live in `research/runs/`; large logs and input snapshots live in
ignored `artifacts/runs/`. Back up or commit research metadata and task documents;
Git is optional. Existing records remain readable across the two hosts.

Writes are atomic and journaled. Ask the doctor skill to inspect interruptions and
repair the diagnosed operation; external edits that conflict with recovery are
reported instead of overwritten. Corrections preserve earlier wording and evidence.
Resume and doctor never relaunch experiments. Hooks are optional reminders.

The runner enforces run-count and wall-time limits. Token/cost limits are recorded
but require provider telemetry for enforcement. Approval evidence records available
confirmation; it does not authenticate it. Visibility filtering is not filesystem
access isolation. Keep secrets out of metadata, commands, and captured inputs.

## Develop and validate

These commands build and check the plugin source; research workflows use the skills above.

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python scripts/build_plugins.py
uv run python scripts/build_plugins.py --hooks
uv run python scripts/smoke_release.py
```

Archives are generated under `dist/plugins/`. The release smoke check extracts each
archive to a new location and exercises its bundled backend with a clean Python
environment, without installing LabLedger separately. It does not establish actual
host behavior; see [validation](docs/VALIDATION.md) and the [spec](LabLedger_SPEC.md).
Backend development details are in [docs/BACKEND.md](docs/BACKEND.md).

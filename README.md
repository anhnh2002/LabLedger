# LabLedger

**Durable research workflows and experiment records for Codex and Claude Code.**

[![Latest release](https://img.shields.io/github/v/release/anhnh2002/LabLedger)](https://github.com/anhnh2002/LabLedger/releases/latest)

LabLedger helps you and your coding agent discuss research decisions, run traceable
experiments, and retain evidence across sessions. It keeps goals, plans, attempts,
and findings in your repository so the next session can continue from recorded
context.

You work through skills or ordinary conversation in Codex or Claude Code. The agent
reads the repository, prepares records, runs approved experiments, and explains the
evidence. Each plugin bundles its Python backend and resources; there is no separate
LabLedger CLI, server, or API key to configure.

[Get started](#getting-started) · [Workflows](#available-workflows) ·
[Releases](https://github.com/anhnh2002/LabLedger/releases) ·
[Documentation](#documentation) · [Contributing](#contributing)

## Why LabLedger?

Research context often ends up scattered across chat history, terminal output, and
files with unclear origins. A new session may repeat a failed approach, overlook a
negative result, or mistake a successful command for a successful experiment.

LabLedger gives that work a persistent structure:

- **Decisions with context.** Record the question, viable options, agreed direction,
  approval evidence, and scope before implementation.
- **Handoffs between sessions.** Save a brief, handoff, and ready-to-paste prompt for
  a fresh session using the host's native Plan Mode.
- **Traceable experiments.** Link approved protocols to individual attempts, captured
  inputs, logs, and analysis. Preserve failures, cancellations, and negative results.
- **Evidence you can revisit.** Recall findings before repeating an approach, link
  claims to supporting and conflicting evidence, and retain earlier revisions when
  correcting a conclusion.
- **Shared records across hosts.** Continue in Codex or Claude Code using the same
  repository documents and records.
- **Evaluation context.** Record dataset roles, held-out exposure, protocol changes,
  and limitations when assessing how far a result generalizes.

LabLedger is designed for research and experimental development in a local
repository. Planning and implementation use your coding agent's existing tools;
LabLedger supplies the workflows and durable record of the work.

## Getting started

### Requirements

| Requirement | Details |
| --- | --- |
| Coding-agent host | Codex or Claude Code with plugin support on the surface you use |
| Operating system | macOS or Linux |
| Python | Python 3.11+ available to the host's command tool |
| Installation network access | GitHub access to download the plugin; package-index access to prepare pinned dependencies on first use |
| Git | Required by the host to fetch the remote marketplace |

On first use, the agent's helper prepares an isolated runtime in your user cache.
Later requests reuse that environment. This setup leaves the research project's
dependencies and global Python installation unchanged.

### 1. Install a host plugin

Install the released plugin directly from GitHub. You do not need a source checkout,
`uv`, or a separate LabLedger installation.

**Codex** — run in your terminal:

```sh
codex plugin marketplace add anhnh2002/LabLedger --ref marketplace
codex plugin add labledger@labledger
```

**Claude Code** — run inside a Claude Code session:

```text
/plugin marketplace add anhnh2002/LabLedger#marketplace
/plugin install labledger@labledger
```

Start a fresh host session after installation. Both hosts download a ready-to-use
plugin from the `marketplace` branch, including the backend and all ten workflows.
The agent prepares Python dependencies on first use.

Remote installation has been verified with Codex CLI 0.166.0 and Claude Code
2.1.296 on macOS. See the [validation results](docs/VALIDATION.md) for the tested
scope.

Versioned plugin ZIPs and checksums are also available from
[GitHub Releases](https://github.com/anhnh2002/LabLedger/releases/latest).

See the [installation guide](docs/INSTALLATION.md) for updates, release ZIPs,
host compatibility, and optional reminder hooks. Source builds are documented under
[Contributing](#contributing).

### 2. Initialize your research repository

Open your research repository in a fresh host session and invoke:

| Codex | Claude Code |
| --- | --- |
| `$labledger-init` | `/labledger:init` |

You can also ask in ordinary language:

> Use LabLedger to initialize this repository. Discuss the research goals, baseline,
> success criteria, and budget with me, then preview the files you will create.

The agent inspects the repository, agrees on a research charter with you, previews
the changes, and initializes the ledger. Existing repository instructions are
preserved; conflicting edits to LabLedger's managed sections are reported for
reconciliation. You supply goals and decisions; the agent prepares the backend
requests.

### 3. Take a research task through the workflow

1. **Discuss a direction.** Use brainstorm to review evidence, compare viable
   approaches, and agree on a bounded task. The agent saves the brief, handoff,
   task status, and filled prompt.
2. **Start a fresh planning session.** Open a new session in the same repository,
   enable the host's native Plan Mode, and paste the generated handoff prompt.
   Review the proposed plan and any material changes to the agreed direction.
3. **Approve and execute.** After approval and switching to execution, the agent
   saves the approved plan before implementation, registers experiments, and
   preserves each attempt and its evidence.
4. **Analyze and continue.** Ask for findings, a report, or a generalization review.
   Use resume in a later session, including on the other host, to recover context
   and identify the next action.

Planning can proceed without writing project files; persistence waits for execution.
Existing authorization carries forward within its scope. The agent asks when
information is missing or a material research decision needs your input.

## Available workflows

| Workflow | Purpose | Codex skill | Claude Code skill |
| --- | --- | --- | --- |
| Initialize | Agree on a charter and set up repository conventions | `$labledger-init` | `/labledger:init` |
| Brainstorm | Discuss evidence, options, and a research direction | `$labledger-brainstorm` | `/labledger:brainstorm` |
| Handoff | Prepare or validate context for a fresh planning session | `$labledger-handoff` | `/labledger:handoff` |
| Recall | Find relevant findings before trying an approach | `$labledger-recall` | `/labledger:recall` |
| Run | Register and execute an experiment with an approved protocol | `$labledger-run` | `/labledger:run` |
| Analyze | Interpret run evidence and retain findings or corrections | `$labledger-analyze` | `/labledger:analyze` |
| Resume | Recover task context, outstanding analysis, and next actions | `$labledger-resume` | `/labledger:resume` |
| Doctor | Diagnose integrity, stale context, and runtime problems | `$labledger-doctor` | `/labledger:doctor` |
| Report | Summarize results, failures, limitations, and evidence | `$labledger-report` | `/labledger:report` |
| Review generalization | Assess scope, independent cases, and evaluation leakage risks | `$labledger-review-generalization` | `/labledger:review-generalization` |

Codex may display skills with a plugin namespace, depending on the surface.
All workflows run inside the coding-agent session. For example:

> Use LabLedger to recall what we learned about the previous approach before we try it again.

> Use LabLedger to analyze the latest experiment, including failed attempts and missing evidence.

> Use LabLedger to resume this task and explain what still needs analysis.

## What LabLedger stores

With the default configuration, initialization and subsequent workflows create the
following structure as work progresses:

```text
your-research-repository/
├── AGENTS.md                    # Codex instructions, with a managed LabLedger section
├── CLAUDE.md                    # Claude Code instructions, with a managed LabLedger section
├── .labledger/
│   ├── config.toml              # Project paths and workflow settings
│   ├── schemas/                 # Versioned record schemas
│   ├── policy/                  # Research policy and its revisions
│   └── cache/                   # Rebuildable derived data
├── research/
│   ├── CHARTER.md               # Goals, scope, criteria, and budget
│   ├── STATUS.md                # Project entry point
│   ├── tasks/<task-id>/         # Task records, brief, handoff, prompt, plan, and status
│   ├── decisions/               # Research decisions and approval evidence
│   ├── experiments/             # Protocols and their revisions
│   ├── runs/                    # Durable run records
│   ├── findings/                # Evidence, lessons, and corrections
│   └── claims/                  # Scoped conclusions and evidence references
└── artifacts/runs/<run-id>/     # Run logs, captured inputs, and outputs
```

**JSON records and their immutable revisions are the canonical structured data.**
Markdown documents carry human context, including the charter and session handoffs.
Paths for research records and artifacts are configurable in
`.labledger/config.toml`.

Commit or back up research metadata, task documents, and non-secret configuration.
Raw run artifacts, derived cache, and transaction journals are ignored by the
generated Git rules. Back up any raw evidence you need separately.

Writes are atomic and journaled. If an operation is interrupted, ask doctor to
diagnose it and repair the diagnosed write. Recovery reports conflicting external
edits instead of overwriting them. Corrections retain earlier wording and evidence.
Resume and doctor never relaunch experiments.

## Research safeguards and limits

- **Execution and research outcomes are separate.** A zero exit code records a
  completed process. An assessed research outcome needs analysis, evidence, and
  limitations; analysis can remain pending or be explicitly deferred.
- **Budgets have defined enforcement.** The runner enforces run-count and wall-time
  limits. Token and cost budgets are recorded, but enforcement requires provider
  telemetry.
- **Approval evidence has a trust boundary.** Records preserve the available
  confirmation and approved scope. They do not authenticate who approved the work
  or prevent commands from being run outside LabLedger.
- **Visibility controls filter agent context.** Restricted evaluation records are
  excluded from development reads. This filtering does not provide filesystem
  access isolation. Keep secrets out of metadata, commands, and captured inputs.
- **Hooks are optional reminders.** Default packages contain no hooks. Separate
  hook variants use an already prepared runtime and never install dependencies,
  approve work, run experiments, or block host tools.

Backend and packaging checks are automated. Interactive host conversations, native
mode transitions, handoffs between hosts, and desktop hook delivery require
separate observation. See the [validation guide](docs/VALIDATION.md) for recorded
results and the manual evaluation protocol.

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/INSTALLATION.md) | Host setup, package loading, and optional hooks |
| [Releasing](docs/RELEASING.md) | Publish the remote marketplace and downloadable plugin packages |
| [Backend development](docs/BACKEND.md) | Bundled runtime, persistence semantics, and developer checks |
| [Validation](docs/VALIDATION.md) | Automated coverage, observed results, and manual host evaluation |

## Contributing

Bug reports, documentation improvements, and focused code changes are welcome.
For a bug report, include the host and version, operating system, Python version,
steps to reproduce, expected behavior, and relevant sanitized output. Describe the
problem and intended behavior when proposing a new workflow or feature.

### Development setup and checks

From the repository root:

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

These checks cover backend behavior and generated packages. Run the relevant
checks for your change and describe the validation in your pull request.

For runtime, workflow, or packaging changes, build both plugin variants and run the
release smoke check:

```sh
uv run python scripts/build_plugins.py
uv run python scripts/build_plugins.py --hooks
uv run python scripts/smoke_release.py
uv run python scripts/build_marketplace.py
```

The smoke check extracts each archive to a new location and exercises its bundled
backend in a clean Python environment. It uses synthetic fixtures and needs
package-index access to prepare dependencies. Interactive host behavior needs the
separate checks described in the validation guide.

### Source layout

| Path | Purpose |
| --- | --- |
| `src/labledger/` | Backend, storage, research records, runner, and packaging |
| `src/labledger/resources/workflows/` | Shared workflow instructions used by both hosts |
| `src/labledger/resources/` | Schemas, defaults, conventions, and bundled runtime helpers |
| `scripts/` | Plugin build and release smoke-check entry points |
| `tests/` | Backend, workflow, runner, and packaging tests |
| `docs/` | Installation, backend, and validation guides |
| `dist/plugins/` | Generated plugin directories and archives; ignored by Git |

Edit the source workflows and packaging code when changing an adapter. Rebuild the
packages to update the generated files under `dist/plugins/`.

## License

A license has not yet been specified in this repository.

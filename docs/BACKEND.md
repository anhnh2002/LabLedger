# Bundled backend development

The backend is private infrastructure for skills running inside Codex or Claude Code.
There is no LabLedger executable or `python -m labledger` entry point. Each generated
plugin includes `runtime/labledger/`, pinned dependencies, and `scripts/backend.py`.
Users interact with their agent; the agent creates requests and interprets responses.

The authoritative request shape, helper invocation, operation catalog, and response
codes are in [the shared backend protocol](../src/labledger/resources/backend.md).
That file is bundled into both host adapters. The dispatcher is
[backend.py](../src/labledger/backend.py); record inputs use
[schema.json](../src/labledger/resources/schema.json).

## Runtime and packaging

The launcher uses an isolated Python 3.11+ virtual environment under the user cache.
The cache key covers the locked requirements, Python major/minor version, and base
interpreter location. An OS lock serializes first-time setup. Interrupted setup is
rebuilt on retry. Dependencies are installed only in this cache, not globally or
in the research repo. The launcher replaces itself with the prepared interpreter
before handling stdin, preserving runner PID and signal semantics.

The helper loads the core from its own plugin root, ignoring PYTHONPATH and the
working directory. Plugins work after relocation and do not depend on a developer
checkout. Optional hooks reuse an existing runtime and never bootstrap one.
The backend remains host-neutral and calls no LLM or external agent API.

When updating dependencies, refresh the bundled lock from the source lock:

```sh
uv export --locked --no-dev --no-emit-project --no-hashes --output-file src/labledger/resources/runtime-requirements.txt
```

## Persistence and research semantics

- The explicit absolute project root is used for every request. Init never guesses
  a destination. An existing ledger's configured directories remain authoritative.
- Init takes an agent-authored charter. Dry-run returns exact proposed changes
  without project writes; repeated init is idempotent. Existing instructions and
  edited managed blocks are preserved or reported as conflicts.
- Record updates are shallow patches using `expected_revision`. Arrays and nested
  objects replace prior values. Identity/timestamps are generated and immutable
  history is retained. Approval evidence contains a summary and an honest source.
- Handoff produces BRIEF.md, HANDOFF.md, PROMPT.txt, and STATUS.md. It records
  ready_for_planning, not an observed planning session. Plan attachment requires
  execution mode and actual approval/planning evidence; stale dependencies fail.
- Run inputs include real argv and explicit capture paths. Runs preserve failures,
  cancellations, logs, and missing provenance. Execution success never establishes
  a positive research result. Failed execution still returns its durable run record.
- Protocol changes after results require renewed approval, a revision reason, and
  disclosure of observed results. Prior runs retain their protocol revision.
- Analysis requires evidence and limitations for assessed outcomes. Deferred analysis
  requires a reason. Findings/corrections preserve wording and review dependencies;
  claims include supporting and counterevidence with scope and limitations.
- Imported attempts keep missing metadata explicit and never execute automatically.
  Reconciliation checks process identity; uncertainty requires observed cessation.
- Reports include failed and pending attempts. An explicit output exports a new file
  and refuses replacement. Recall/status/resume/doctor do not write project files;
  resume and doctor never start experiments. Explicit repair only repairs diagnosed
  journaled writes and refuses conflicting external edits.
- Restricted records are excluded from development reads. This is context filtering,
  not filesystem isolation. Artifact redaction creates a derivative; tombstones
  preserve metadata without deleting original files. Nothing is uploaded automatically.

## Checks

`uv run pytest` covers backend validation, state transitions, storage recovery,
privacy, runner signals/concurrency, and generated packages. Build both plugin
variants and run `uv run python scripts/smoke_release.py` to exercise relocated
archives with a clean Python environment. Host conversation behavior needs actual
interactive evaluation as described in [VALIDATION.md](VALIDATION.md).

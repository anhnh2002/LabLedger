# Acceptance and compatibility validation

Automated tests use synthetic fixtures in temporary directories. Their approvals,
observations, datasets, and findings are not real research results. Run `uv run pytest`.
Host evaluations below require actual independent sessions; do not mark them passed
because instructions contain the right wording or a host executable is installed.

| Criteria | Automated evidence | Additional host evaluation |
| --- | --- | --- |
| AC-01–03 | Idempotent init, instruction conflicts, exact dry-run snapshots | Review init conversation and agreed charter |
| AC-04 | Draft default and approval prerequisites | Researcher receives meaningful options; no invented approval |
| AC-05 | Validated handoff files, filled prompt, archived document revisions | Confirm brief captures agreed direction |
| AC-06 | Handoff generator returns fresh-session instructions | Brainstorm stops at handoff; no implementation |
| AC-07 | Fresh Store reads complete handoff without chat | New Codex and Claude sessions plan from docs/code |
| AC-08 | Generation leaves ready_for_planning | No invented session observation |
| AC-09 | Stale dependency checks | Planning discusses infeasible direction rather than silently changing it |
| AC-10–11 | Execution-only plan attachment, plan/status and read-only tests | Native Plan Mode requires no repository writes; execution persists plan first |
| AC-12 | Decision/document drift checks | User reviews affected changes |
| AC-13–14 | Manifest observed by child; completed-negative versus failed-not_assessed | Analysis distinguishes research and execution success |
| AC-15–17 | Spawn failure, nonzero exit, timeout, SIGINT descendants, killed runner, retry lineage | Explain uncertain state honestly |
| AC-18 | Pending defaults and explicit analysis prerequisites | Do not invent findings to clear pending work |
| AC-19 | Search returns scoped evidence and relevance | Explain changed conditions before repeating an approach |
| AC-20 | Correction preserves old record and warns transitive dependents | Review strength of affected claims |
| AC-21 | Held-out freeze/exposure records and context filtering | Record known feedback reuse; discuss new independent confirmation |
| AC-22 | Parallel subprocesses, budget race, unique IDs and separate logs | None beyond supported OS checks |
| AC-23 | Incomplete import retains missing metadata | Confirm no guessed provenance |
| AC-24 | Shared-source generation and host-neutral context | Handoff Codex to Claude and Claude to Codex |
| AC-25 | Separate hook-free variants, read-only optional reminder | Complete workflow with hooks disabled |
| AC-26 | Failed/pending run report inventory and evidence links | Review statistical interpretation and exclusion rules |
| AC-27 | Filtering before matching, report/cache/status privacy | Avoid manually injecting restricted details |
| AC-28 | Cache removal/rebuild leaves canonical bytes unchanged | None |

Additional tests cover transaction fault recovery and external-edit refusal, schema
versions, malformed timestamps, path containment, process identity reuse, explicit
artifact retirement, and streamed redaction across chunk boundaries.

## Manual host protocol

Record host version, OS, plugin/backend versions, test task, observed actions, evidence,
failures, and context/question overhead. Use a fresh repository containing a small
real failure class and independent verification cases; keep evaluation examples
separate from the examples used to refine workflows.

1. Load the default plugin and verify all ten workflow entry points. Keep hooks off.
2. In a session without a separately installed LabLedger core, invoke init and discuss
   goals. Confirm the agent creates every payload and invokes its bundled helper;
   the user never writes JSON or runs backend commands. Initialize an existing
   repository without losing instructions. Brainstorm two
   viable directions or honestly state when only one is supported. Before approval,
   confirm the decision stays proposed/discussed.
3. Approve bounded work. Confirm generated docs contain the actual scope, budget,
   references, and filled prompt, and that the session stops at handoff.
4. Start a genuinely new host session without prior chat. Enable native Plan Mode.
   Read handoff/code, detect deliberately stale context, discuss a material change,
   and present the plan without requiring repository writes.
5. Approve and switch to execution. Observe PLAN.md persistence before code changes.
   Run an approved experiment with a positive result, negative result, and execution
   failure. Confirm separate execution/outcome/analysis semantics and preserved logs.
6. Resume on the other host. Recall an old negative finding, explain changed
   conditions, record a correction, and report failures and scoped claims.
7. For supported local installations only, repeat with reminder hooks enabled and
   confirm they neither block nor mutate. Repeat with no prepared runtime (hooks must not install it), then with hooks disabled.

Initial installed versions discovered during planning: Codex CLI 0.166.0 and Claude
Code 2.1.296 on macOS. This is inventory, not a behavioral pass. Linux and Python
3.11/3.14 are configured in CI; actual CI outcomes must be recorded after CI runs.

## Bundled-plugin implementation validation — 2026-11-02

The former CLI release checks have been replaced by private backend and relocated
plugin checks. Historical installed-wheel results do not establish this version's
plugin behavior. The results below distinguish backend checks from interactive host behavior.

- Backend unit/integration tests cover request validation, dry-run/idempotence,
  revisions, visibility, failed-run response records, and runner signals/concurrency.
- Packaging tests verify the bundled core/resources, absence of CLI entry modules,
  shared workflows, relative paths, deterministic archives, and separate hook variants.
- `scripts/smoke_release.py` extracts each archive to a new path with spaces, creates
  a clean Python environment with no LabLedger installed, and exercises init,
  decisions, handoff, execution-time plan, registered runs, negative analysis,
  finding/recall, report, resume, and doctor through the archive's private helper.
- Static skill validation and host manifest validation are separate from behavior.
- Actual interactive conversation, native planning/handoff across both hosts,
  Linux CI outcomes, and desktop hook behavior must be recorded independently.
  No such sessions are claimed observed by automated checks.

### Observed local results

- 69 automated tests passed on Darwin arm64, Python 3.12.12.
- Ruff lint and formatting checks passed. Source/wheel builds passed; the wheel
  contains no CLI module, module entry point, or console-script entry points.
- All four generated plugin archives passed the relocated synthetic lifecycle,
  including helper-process cancellation. Later requests succeeded with package-index
  access disabled. Cross-package resume read the same ledger without changing it.
- Synthetic hook checks passed with a cold cache (no setup or cache writes) and a
  warm cache (read-only reminder). These are helper checks, not desktop host events.
- All 40 generated skills passed skill-creator static validation. Both Claude Code
  manifests passed host validation with the existing missing-author metadata warning.
- Interactive Codex/Claude conversations, actual mode transitions, host-to-host
  session handoff, desktop event delivery, and Linux CI remain unobserved here.

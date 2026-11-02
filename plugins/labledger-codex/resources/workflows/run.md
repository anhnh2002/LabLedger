# Execute a traceable experiment

Read the charter, approved task plan and decisions. Recall related findings before
repeating an approach. Create or revise the experiment payload yourself using
`experiment.new` or `experiment.update`; inspect backend `schema` with kind
`experiment`. Include hypothesis, baseline/version, intervention/confounders, dataset
versions/provenance/roles, primary metric with direction/unit/denominator, secondary
metrics, independent evaluation unit, repetitions, budget, success/stop conditions,
failure handling, and analysis plan.

Discuss material choices and record real approval evidence and approved scope. Protocol
changes after results require new approval, revision reason, and disclosure of existing
runs. Keep old runs pinned to old protocol revisions. Confirmatory held-out evaluation
requires frozen code, config, evaluator, metric, selection rule, and restricted
visibility. Record known prior exposure; a renamed split is not fresh.

Invoke backend `run.start` with `experiment`, an `argv` array, and optional `capture`
project-relative input paths. Use argv arguments, not hidden shell interpolation. Supply
only secret-free, relevant inputs; capture a dependency lock where available. Do not
promise token/cost limits are enforced: doctor reports telemetry limitations. Do not
bypass exhausted budgets. Use `parent` and `retry_reason` for a retry, which creates a
new run ID.

Preserve failed, cancelled, and interrupted attempts. A successful process is not a
positive research result. Read the returned run ID and analysis status. Analyze or
explicitly defer analysis. External runs use `run.import` with the supplied manifest as
payload; leave unknown metadata unknown. Resume/doctor never rerun automatically;
uncertain executions require manual inspection and reconciliation. Use signals to stop
the runner, which cancels its group.

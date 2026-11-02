# Analyze evidence and retain findings

Read the experiment revision pinned by each run, logs, metrics, and known exclusions.
Compare task set, dataset/evaluator versions, budget, code/config, and evaluation unit
before interpreting an improvement. Report mismatches, numerator/denominator, missing
samples, failed attempts, and selection rules. Distinguish independent units from
repeated seeds. Use paired comparisons and uncertainty at the appropriate level when
supported by the available data. State exploratory versus confirmatory analysis.

Keep execution status separate from research outcome. With insufficient evidence, leave
not_assessed/pending or record inconclusive; do not invent a finding. Create the
analysis payload yourself and use `run.annotate` with run ID and expected_revision to
persist analysis summary, evidence, limitations, outcome, and analyzed/deferred status.
Deferred needs a reason.

Use `finding.add` with a payload you create from the evidence for scoped observations,
hypotheses, lessons, or corrections. Include evidence_refs, limitations, confidence,
alternative explanations, next_action, and correct visibility. One finding can summarize
several runs. Separate what was observed from causal interpretation. Use correction plus
supersedes when new evidence contradicts an old finding; retain prior wording and review
dependent claims/decisions. Update task status with evidence and remaining work.

Record held-out feedback used for development with `exposure.add`; explain why it limits
independent confirmation. Never declassify restricted history by editing it.

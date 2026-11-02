# Report research with traceable claims

Review all task protocols/revisions, runs, analyses, findings/corrections, and claims.
Use backend `claim.add`/`claim.update` with agent-authored payloads for conclusions with
scope, supporting and counterevidence, limitations, and report references. Claims must
match evidence strength. Review doctor warnings when evidence is corrected or
superseded.

Use backend `report` with the task ID for an evidence inventory and comparison warnings.
An explicit `output` path exports a new report file without replacing old versions.
Expand the analysis only from observed evidence. Include question, frozen versus
exploratory protocol, compared versions, results, failures, uncertainty, scope,
limitations, exclusions/selection rules, pending analysis, and next decisions. Link
important claims to exact record revisions and artifacts. Do not omit bad runs or choose
the best seed unless the protocol declared that rule.

Development reports exclude restricted findings. Export restricted analysis only when
requested and keep it out of development context. The generated inventory does not
compute significance, establish causality, or prove generalization.

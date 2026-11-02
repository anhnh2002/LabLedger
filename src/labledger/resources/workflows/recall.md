# Recall research findings

Search permitted findings using backend `recall` with `arguments.query`, optionally
filtered by task. Use component, failure type, hypothesis, method, dataset, model, and
budget terms relevant to the question. Load only relevant evidence; do not read all
history by default. Results include scope, evidence, limitations, confidence, status,
and matching terms. Check corrections before relying on an older statement.

Explain why the finding applies or which changed conditions warrant retrying an
approach. Negative results are evidence within scope, not permanent prohibitions.
Development recall excludes restricted findings before matching. Use
`include_restricted: true` only for an explicitly requested restricted evaluation
analysis; never use it merely to improve development suggestions.

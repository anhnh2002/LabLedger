# Diagnose ledger integrity and host capabilities

Invoke backend `doctor` in this session. Explain schema/reference errors, incomplete
transactions, stale handoffs/plans, checksum mismatches, pending analysis, correction
dependencies, and host capability limitations. Do not treat installed host detection as
a passed behavioral test. Session workflows remain available without hooks.

Repair only the diagnosed operation: `doctor` with `repair: true` rolls incomplete
journaled writes forward and refuses conflicting external edits. It does not fix
arbitrary corrupt records, approve decisions, reconcile unknown executions as
successful, or rerun experiments. Preserve conflicting data for manual review. Cache is
derived; `cache.rebuild` recreates development metadata without changing canonical
history.

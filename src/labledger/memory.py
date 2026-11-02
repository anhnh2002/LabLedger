import json
import os
import re

from .errors import LedgerError
from .runner import inspect_execution
from .storage import atomic_write, digest, encoded
from .workflows import reference_label


def visible(records, restricted=False):
    return [record for record in records if restricted or record["visibility"] == "development"]


def superseded_ids(records):
    return {record["supersedes"]["id"] for record in records if record.get("supersedes")}


def dependent_warnings(store, records=None, restricted=False):
    records = store.all() if records is None else records
    affected = superseded_ids(records)
    current = {record["id"]: record for record in records}
    for record in records:
        if record.get("status") in ("superseded", "withdrawn", "contested"):
            affected.add(record["id"])
    warnings = []
    changed = True
    while changed:
        changed = False
        for record in records:
            if record["id"] in affected or record["entity_type"] not in ("decision", "claim"):
                continue
            refs = {ref["id"] for ref in store.references(record) if "id" in ref}
            stale = {
                ref["id"]
                for ref in store.references(record)
                if "id" in ref
                and ref["id"] in current
                and ref["revision"] != current[ref["id"]]["revision"]
            }
            if refs & affected or stale:
                warnings.append(
                    {
                        "id": record["id"],
                        "needs_review": True,
                        "affected_evidence": sorted((refs & affected) | stale),
                    }
                )
                affected.add(record["id"])
                changed = True
    return [
        item
        for item in warnings
        if restricted or current[item["id"]]["visibility"] == "development"
    ]


def recall(store, query, task_id=None, restricted=False, limit=10):
    terms = set(re.findall(r"\w+", query.casefold()))
    if not terms or limit < 1 or limit > 100:
        raise LedgerError("Recall requires a nonempty query and a limit from 1 to 100")
    all_findings = store.all("finding")
    records = visible(all_findings, restricted)
    superseded = superseded_ids(all_findings)
    results = []
    for record in records:
        if task_id and record.get("task_id") != task_id:
            continue
        text = json.dumps(record, ensure_ascii=False).casefold()
        matches = sorted(term for term in terms if term in text)
        if not matches:
            continue
        results.append(
            {
                "id": record["id"],
                "revision": record["revision"],
                "statement": record["statement"],
                "scope": record["scope"],
                "evidence_refs": record["evidence_refs"],
                "limitations": record["limitations"],
                "confidence": record["confidence"],
                "status": "superseded" if record["id"] in superseded else "current",
                "relevance": f"Matched: {', '.join(matches)}",
                "score": len(matches),
                "next_action": record["next_action"],
                "visibility": record["visibility"],
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["id"]))[:limit]


def rebuild_cache(store):
    with store.locked():
        # Only development metadata is cached. Recall always consults canonical records.
        records = visible(store.all("finding"))
        data = {
            "schema_version": 1,
            "generated": True,
            "records": records,
            "source_checksum": digest(encoded(records)),
        }
        path = store.meta / "cache/findings.json"
        atomic_write(path, encoded(data))
        return {
            "path": store.relative(path),
            "count": len(records),
            "canonical_records_modified": False,
        }


def status(store, task_id=None, restricted=False):
    with store.locked():
        all_records = store.all()
        records = visible(all_records, restricted)
        if task_id:
            task = store.read("task", task_id)
            if task["visibility"] != "development" and not restricted:
                raise LedgerError("Task unavailable in development view")
            records = [r for r in records if r.get("task_id") == task_id or r["id"] == task_id]
        tasks = [r for r in records if r["entity_type"] == "task"]
        runs = [r for r in records if r["entity_type"] == "run"]
        return {
            "tasks": tasks,
            "runs": [
                {
                    "id": r["id"],
                    "execution_status": r["execution_status"],
                    "research_outcome": r["research_outcome"],
                    "analysis_status": r["analysis_status"],
                    "execution": inspect_execution(r),
                }
                for r in runs
            ],
            "outstanding_analysis": [r["id"] for r in runs if r["analysis_status"] == "pending"],
            "deferred_analysis": [r["id"] for r in runs if r["analysis_status"] == "deferred"],
            "review_warnings": [
                warning
                for warning in dependent_warnings(store, all_records, restricted)
                if not task_id or warning["id"] in {record["id"] for record in records}
            ],
        }


def resume(store, task_id, restricted=False):
    summary = status(store, task_id, restricted)
    task = summary["tasks"][0]
    base = store.relative(store.location("task", task_id).parent)
    summary["read_first"] = [store.relative(store.research / "CHARTER.md"), f"{base}/STATUS.md"]
    if task.get("handoff"):
        summary["read_first"] += [f"{base}/HANDOFF.md", f"{base}/BRIEF.md"]
    if task.get("plan"):
        summary["read_first"].append(f"{base}/PLAN.md")
    summary["next_action"] = task.get(
        "next_action", "Inspect records and discuss unresolved decisions."
    )
    summary["execution_policy"] = "Resume reads context only. No experiment is relaunched."
    return summary


def report(store, task_id, restricted=False, destination=None):
    with store.locked():
        base = destination.parent if destination else store.root

        def link(ref):
            label = reference_label(ref)
            if "id" in ref:
                path = store.location(ref["type"], ref["id"], ref["revision"])
                target = os.path.relpath(path, base)
            else:
                target = ref.get("uri") or os.path.relpath(store.path(ref["path"]), base)
            return f"[{label}]({target})"

        summary = status(store, task_id, restricted)
        records = visible(store.all(), restricted)
        records = [r for r in records if r.get("task_id") == task_id or r["id"] == task_id]
        runs = [r for r in records if r["entity_type"] == "run"]
        experiments = [r for r in records if r["entity_type"] == "experiment"]
        findings = [r for r in records if r["entity_type"] == "finding"]
        claims = [r for r in records if r["entity_type"] == "claim"]
        task = summary["tasks"][0]
        lines = [
            f"# Research report: {task['title']}",
            "",
            f"Task: {task_id}",
            "",
            "Generated from recorded evidence. No automatic significance or causal conclusions.",
            "",
            "## Question and protocol",
            "",
        ]
        for experiment in experiments:
            lines += [
                f"- {experiment['id']}@{experiment['revision']}: {experiment['hypothesis']}",
                f"  Baseline: {experiment.get('baseline', 'unknown')}; analysis: {experiment.get('analysis_plan', 'unknown')}",
            ]
        lines += [
            "",
            "## Results and failures",
            "",
            "| Run | Protocol revision | Execution | Outcome | Analysis | Evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for run in runs:
            evidence = link(store.ref(run))
            lines.append(
                f"| {run['id']} | {run.get('experiment_id', 'unknown')}@{run.get('experiment_revision', 'unknown')} | {run['execution_status']} | {run['research_outcome']} | {run['analysis_status']} | {evidence} |"
            )
        lines += ["", "## Comparability and uncertainty", ""]
        comparisons = set()
        for run in runs:
            if run.get("experiment_id") and run.get("experiment_revision"):
                protocol = store.read(
                    "experiment", run["experiment_id"], run["experiment_revision"]
                )
                comparisons.add(
                    json.dumps(
                        {
                            k: protocol.get(k)
                            for k in (
                                "dataset_refs",
                                "primary_metric",
                                "budget",
                                "analysis_plan",
                                "evaluation_unit",
                                "baseline",
                                "freeze",
                            )
                        },
                        sort_keys=True,
                    )
                )
        if len(comparisons) > 1:
            lines.append(
                "WARNING: compared protocols differ in data, metric, budget, evaluator/freeze, baseline, or analysis. Review before interpreting improvement."
            )
        else:
            lines.append(
                "No aggregate improvement is inferred. Check sample denominators, missing samples, seeds versus independent units, and paired uncertainty in the recorded analyses."
            )
        for run in runs:
            lines += [
                f"- {run['id']}: {run.get('analysis', {}).get('summary', 'Analysis pending or not supplied.')}",
                f"  Limitations: {run.get('analysis', {}).get('limitations', [])}; missing metadata: {run['missing_metadata']}",
            ]
        lines += ["", "## Findings and claims", ""]
        superseded = superseded_ids(records)
        for record in findings + claims:
            evidence = link(store.ref(record))
            state = "superseded" if record["id"] in superseded else record.get("status", "current")
            lines += [
                f"- {evidence} ({state}): {record['statement']}",
                f"  Scope: {record['scope']}; limitations: {record['limitations']}",
                f"  Evidence: {', '.join(map(link, record['evidence_refs']))}",
            ]
        lines += [
            "",
            "## Selection, exclusions, and next decisions",
            "",
            "Every visible registered run for this task is listed, including failures and pending analysis. No automatic exclusions or seed selection.",
            f"Next action: {summary.get('next_action', task.get('next_action', 'Review the evidence.'))}",
            f"Dependent claims/decisions requiring review: {summary['review_warnings']}",
            "Restricted evaluation details are excluded from development reports."
            if not restricted
            else "This report includes restricted evaluation analysis; do not inject it into development memory.",
            "",
        ]
        return "\n".join(lines)

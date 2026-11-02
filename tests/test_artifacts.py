import sys

from labledger.artifacts import add, redact, tombstone
from labledger.doctor import doctor
from labledger.runner import start


def test_redacted_derivative_and_explicit_tombstone(store, experiment):
    secret = "SYNTHETIC_NOT_A_REAL_SECRET"
    run, _ = start(store, experiment["id"], [sys.executable, "-c", f"print({secret!r})"])
    source = next(
        ref["path"] for ref in run["outputs"]["logs"] if ref["path"].endswith("stdout.log")
    )
    output = source.replace("stdout.log", "stdout.redacted.log")
    before = (store.root / source).read_bytes()
    redacted = redact(
        store,
        run["id"],
        source,
        output,
        {
            "reason": "Synthetic redaction fixture",
            "replacements": [{"text": secret, "replacement": "[REDACTED]"}],
        },
        run["revision"],
    )
    assert secret not in (store.root / output).read_text()
    assert (store.root / source).read_bytes() == before
    event = redacted["annotations"][-1]
    assert event["replacement_count"] == 1 and event["original_preserved"]
    assert secret not in str(event)
    retired = tombstone(
        store, run["id"], source, "Synthetic retention policy", redacted["revision"]
    )
    assert (store.root / source).exists()  # No implicit deletion.
    (store.root / source).unlink()  # Explicit operator action in the fixture.
    assert retired["annotations"][-1]["previous_metadata"][0]["checksum"]
    assert doctor(store)["ok"]


def test_redaction_matches_across_stream_chunk_boundary(store, experiment):
    run, _ = start(store, experiment["id"], [sys.executable, "-c", "pass"])
    source = store.artifacts / run["id"] / "large.txt"
    source.write_bytes(b"x" * (1024 * 1024 - 3) + b"SECRET" + b"y" * 9)
    registered = add(store, run["id"], {"path": store.relative(source)}, run["revision"])
    output = store.relative(source.with_suffix(".redacted.txt"))
    redacted = redact(
        store,
        run["id"],
        store.relative(source),
        output,
        {
            "reason": "Synthetic boundary fixture",
            "replacements": [{"text": "SECRET", "replacement": "[MASK]"}],
        },
        registered["revision"],
    )
    assert (store.root / output).read_bytes() == b"x" * (1024 * 1024 - 3) + b"[MASK]" + b"y" * 9
    assert redacted["annotations"][-1]["replacement_count"] == 1


def test_registered_artifact_retirement_keeps_audit_references_usable(store, experiment):
    run, _ = start(store, experiment["id"], [sys.executable, "-c", "pass"])
    path = store.artifacts / run["id"] / "metrics.json"
    path.write_text('{"synthetic": true}')
    run = add(store, run["id"], {"path": store.relative(path)}, run["revision"])
    run = tombstone(store, run["id"], store.relative(path), "Synthetic retirement", run["revision"])
    path.unlink()
    assert doctor(store)["ok"]
    from labledger.runner import annotate

    annotate(
        store,
        run["id"],
        {"analysis_status": "deferred", "analysis": {"summary": "Synthetic explicit deferral"}},
        run["revision"],
    )

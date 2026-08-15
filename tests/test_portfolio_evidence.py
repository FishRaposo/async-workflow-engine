"""Contracts for the reproducible, offline portfolio evidence bundle."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def _evidence_modules():
    root = Path(__file__).parents[1]
    demo_spec = importlib.util.spec_from_file_location(
        "portfolio_demo", root / "scripts" / "portfolio_demo.py"
    )
    verify_spec = importlib.util.spec_from_file_location(
        "verify_portfolio_evidence", root / "scripts" / "verify_portfolio_evidence.py"
    )
    assert demo_spec and demo_spec.loader
    assert verify_spec and verify_spec.loader
    demo = importlib.util.module_from_spec(demo_spec)
    verifier = importlib.util.module_from_spec(verify_spec)
    demo_spec.loader.exec_module(demo)
    verify_spec.loader.exec_module(verifier)
    return demo, verifier


def _rewrite_checksums(output: Path) -> None:
    (output / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}"
            for name in ("evidence.json", "manifest.json", "report.md")
        )
        + "\n"
    )


def test_generator_is_reproducible_and_exercises_real_offline_capabilities(tmp_path):
    demo, verifier = _evidence_modules()
    first = demo.generate_evidence(tmp_path / "first")
    second = demo.generate_evidence(tmp_path / "second")

    assert first["reproducibility_hash"] == second["reproducibility_hash"]
    assert (
        verifier.verify_evidence(tmp_path / "first")["reproducibility_hash"]
        == first["reproducibility_hash"]
    )
    report = json.loads((tmp_path / "first" / "evidence.json").read_text())
    assert report["validation"]["cycle_refused"] is True
    assert report["validation"]["unknown_task_refused"] is True
    assert report["execution"]["branch_statuses"]["notify_spam"] == "SKIPPED"
    assert report["execution"]["typed_io"] == {
        "kind": "typed",
        "params": {"proof": "TaskInput->TaskResult"},
    }
    assert report["execution"]["bounded_parallel"]["observed_max"] == 2
    assert report["execution"]["partial_failure_step_statuses"] == {
        "parse": "COMPLETED",
        "fail": "FAILED",
    }
    assert report["execution"]["dlq_attempts"] == 2
    assert report["execution"]["retry_backoff"] == {
        "observed_seconds": [0.5],
        "retry_events": [{"kind": "step.retry", "attempt": 1}],
    }
    assert report["runtime"]["sqlite_round_trip"] is True
    assert report["runtime"]["schedule_due_dispatch"] == ["evidence-schedule"]
    assert report["runtime"]["schedule_duplicate_dispatch"] == []
    assert report["security"]["webhook_hmac"]["valid"] is True
    assert report["security"]["idempotency"] == [True, False]
    assert report["dashboard_fixture"]["events"]


@pytest.mark.parametrize(
    "mutation",
    ["missing", "malformed", "extra", "extra-directory", "tampered", "checksum"],
)
def test_verifier_rejects_invalid_or_unexpected_artifact_files(tmp_path, mutation):
    demo, verifier = _evidence_modules()
    output = tmp_path / mutation
    demo.generate_evidence(output)

    if mutation == "missing":
        (output / "report.md").unlink()
    elif mutation == "malformed":
        (output / "manifest.json").write_text("not json")
    elif mutation == "extra":
        (output / "unexpected.txt").write_text("unexpected")
    elif mutation == "extra-directory":
        (output / "unexpected").mkdir()
    elif mutation == "tampered":
        (output / "evidence.json").write_text("{}")
    else:
        (output / "checksums.sha256").write_text("0" * 64 + "  evidence.json\n")

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)


def test_normalized_evidence_matches_the_committed_golden_fixture(tmp_path):
    demo, _ = _evidence_modules()
    demo.generate_evidence(tmp_path / "evidence")
    generated = json.loads((tmp_path / "evidence" / "evidence.json").read_text())
    golden = json.loads(
        (
            Path(__file__).parent / "fixtures" / "golden" / "portfolio-evidence.json"
        ).read_text()
    )

    assert generated == golden


def test_verifier_rejects_a_self_consistent_but_non_golden_evidence_bundle(tmp_path):
    demo, verifier = _evidence_modules()
    output = tmp_path / "self-consistent-tamper"
    manifest = demo.generate_evidence(output)
    evidence = json.loads((output / "evidence.json").read_text())
    evidence["runtime"]["sqlite_round_trip"] = False
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    (output / "evidence.json").write_bytes(canonical + b"\n")
    manifest["reproducibility_hash"] = hashlib.sha256(canonical).hexdigest()
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )
    (output / "report.md").write_text(
        f"# altered\n\nReproducibility hash: `{manifest['reproducibility_hash']}`\n"
    )
    (output / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}"
            for name in ("evidence.json", "manifest.json", "report.md")
        )
        + "\n"
    )

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)


def test_verifier_rejects_a_self_consistent_tampered_manifest(tmp_path):
    demo, verifier = _evidence_modules()
    output = tmp_path / "manifest-tamper"
    manifest = demo.generate_evidence(output)
    manifest["schema_version"] = 999
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    )
    (output / "checksums.sha256").write_text(
        "\n".join(
            f"{hashlib.sha256((output / name).read_bytes()).hexdigest()}  {name}"
            for name in ("evidence.json", "manifest.json", "report.md")
        )
        + "\n"
    )

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)


@pytest.mark.parametrize("filename", ["evidence.json", "manifest.json"])
def test_verifier_rejects_self_consistent_pretty_reordered_json(tmp_path, filename):
    demo, verifier = _evidence_modules()
    output = tmp_path / filename
    demo.generate_evidence(output)
    value = json.loads((output / filename).read_text())
    reordered = dict(reversed(tuple(value.items())))
    (output / filename).write_text(
        json.dumps(reordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _rewrite_checksums(output)

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)


@pytest.mark.parametrize("filename", ["evidence.json", "manifest.json"])
def test_verifier_rejects_json_without_the_canonical_trailing_newline(
    tmp_path, filename
):
    demo, verifier = _evidence_modules()
    output = tmp_path / f"no-newline-{filename}"
    demo.generate_evidence(output)
    (output / filename).write_bytes((output / filename).read_bytes().rstrip(b"\n"))
    _rewrite_checksums(output)

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)


def test_verifier_rejects_a_self_consistent_tampered_report(tmp_path):
    demo, verifier = _evidence_modules()
    output = tmp_path / "report-tamper"
    manifest = demo.generate_evidence(output)
    report = (output / "report.md").read_text(encoding="utf-8")
    (output / "report.md").write_text(
        report.replace("fixtures are recorded.", "fixtures are archived."),
        encoding="utf-8",
    )
    assert manifest["reproducibility_hash"] in (output / "report.md").read_text(
        encoding="utf-8"
    )
    _rewrite_checksums(output)

    with pytest.raises(verifier.EvidenceVerificationError):
        verifier.verify_evidence(output)

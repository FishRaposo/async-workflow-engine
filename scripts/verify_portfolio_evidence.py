"""Verify the closed, reproducible portfolio evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {"checksums.sha256", "evidence.json", "manifest.json", "report.md"}
ARTIFACT_FILES = ("evidence.json", "manifest.json", "report.md")


class EvidenceVerificationError(ValueError):
    """Raised when an evidence directory is incomplete or has been altered."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _canonical_checksums(directory: Path) -> bytes:
    return (
        "\n".join(
            f"{_sha256(directory / filename)}  {filename}"
            for filename in ARTIFACT_FILES
        )
        + "\n"
    ).encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceVerificationError(f"Malformed JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise EvidenceVerificationError(f"JSON object required: {path.name}")
    return value


def _checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceVerificationError("Missing checksums.sha256") from exc
    for line in lines:
        try:
            checksum, filename = line.split("  ", maxsplit=1)
        except ValueError as exc:
            raise EvidenceVerificationError("Malformed checksums.sha256") from exc
        if len(checksum) != 64 or any(
            char not in "0123456789abcdef" for char in checksum
        ):
            raise EvidenceVerificationError("Invalid SHA-256 checksum")
        if filename in checksums or filename not in REQUIRED_FILES - {
            "checksums.sha256"
        }:
            raise EvidenceVerificationError("Unexpected checksum entry")
        checksums[filename] = checksum
    if set(checksums) != REQUIRED_FILES - {"checksums.sha256"}:
        raise EvidenceVerificationError("Incomplete checksums.sha256")
    return checksums


def _expected_report(evidence: dict[str, Any], reproducibility_hash: str) -> str:
    return "\n".join(
        [
            "# Async Workflow Engine evidence",
            "",
            f"Reproducibility hash: `{reproducibility_hash}`",
            "",
            "- Offline SQLite and in-memory storage exercised.",
            "- Validation, execution, runtime, security, tasks, and dashboard fixtures "
            "are recorded.",
            f"- Branch result: `{evidence['execution']['branch_statuses']}`.",
            "",
        ]
    )


def verify_evidence(output_dir: str | Path) -> dict[str, Any]:
    """Return the manifest only when the evidence bundle is exact and intact."""
    directory = Path(output_dir)
    if not directory.is_dir():
        raise EvidenceVerificationError("Evidence directory is missing")
    actual = {path.name for path in directory.iterdir()}
    if actual != REQUIRED_FILES:
        raise EvidenceVerificationError("Evidence files are missing or unexpected")

    manifest = _read_json(directory / "manifest.json")
    _read_json(directory / "evidence.json")
    golden = _read_json(
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "golden"
        / "portfolio-evidence.json"
    )
    checksums = _checksums(directory / "checksums.sha256")
    for filename, expected in checksums.items():
        if _sha256(directory / filename) != expected:
            raise EvidenceVerificationError(f"Checksum mismatch: {filename}")
    if (directory / "checksums.sha256").read_bytes() != _canonical_checksums(directory):
        raise EvidenceVerificationError("checksums.sha256 is not canonical")

    canonical_evidence = _canonical_json(golden)
    if (directory / "evidence.json").read_bytes() != canonical_evidence + b"\n":
        raise EvidenceVerificationError(
            "Evidence JSON is not the canonical normalized golden fixture"
        )
    reproducibility_hash = hashlib.sha256(canonical_evidence).hexdigest()
    expected_manifest = {
        "artifact_files": list(ARTIFACT_FILES),
        "reproducibility_hash": reproducibility_hash,
        "schema_version": 1,
    }
    if (directory / "manifest.json").read_bytes() != _canonical_json(
        expected_manifest
    ) + b"\n":
        raise EvidenceVerificationError("Manifest JSON is not canonical")
    report = (directory / "report.md").read_text(encoding="utf-8")
    if report != _expected_report(golden, reproducibility_hash):
        raise EvidenceVerificationError(
            "Markdown report does not match normalized evidence"
        )
    return manifest


if __name__ == "__main__":  # pragma: no cover - command line convenience
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify_evidence(args.output_dir), indent=2, sort_keys=True))

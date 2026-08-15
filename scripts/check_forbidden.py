"""Reject retired dependencies and credential-shaped values in tracked text."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_TRACKED_PREFIXES = (
    ".commandcode/",
    ".superpowers/",
)
ALLOWED_PATTERN_PATHS = {
    # These files exercise or disclose the retired dependency text intentionally.
    "retired shared_core dependency": {
        "tests/test_self_containment.py",
        "tests/test_tooling_contracts.py",
        "THIRD_PARTY_NOTICES.md",
    },
    # The tooling contract constructs a synthetic token to prove detection.
    "GitHub token": {"tests/test_tooling_contracts.py"},
}
PATTERNS = {
    "retired shared_core dependency": re.compile(
        r"\b(?:from|import)\s+shared" r"_core\b|shared" r"-core",
        re.IGNORECASE,
    ),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
}


def _files(root: Path) -> list[Path]:
    """Return tracked text/config candidates, excluding local agent reports."""
    if root != REPOSITORY_ROOT:
        return sorted(path for path in root.rglob("*") if path.is_file())

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return sorted(
        root / relative
        for relative in result.stdout.splitlines()
        if relative
        and not relative.replace("\\", "/").startswith(EXCLUDED_TRACKED_PREFIXES)
    )


def find_violations(root: Path) -> list[str]:
    """Return deterministic descriptions for every forbidden value found."""
    violations: list[str] = []
    for path in _files(root):
        relative = path.relative_to(root).as_posix()
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(contents) and relative not in ALLOWED_PATTERN_PATHS.get(
                label, set()
            ):
                violations.append(f"{relative}: {label}")
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    args = parser.parse_args()
    violations = find_violations(args.root.resolve())
    if violations:
        print("Forbidden dependency or secret-like value found:", file=sys.stderr)
        print("\n".join(violations), file=sys.stderr)
        return 1
    print("Forbidden dependency and secret scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reject retired dependencies and credential-shaped values in tracked code."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = (
    ".github",
    "alembic",
    "examples",
    "scripts",
    "src",
    "frontend/.env.example",
    "frontend/Dockerfile",
    "frontend/next.config.js",
    "frontend/package.json",
    "frontend/playwright.config.ts",
    "frontend/src",
    "frontend/vitest.config.ts",
    "docker-compose.yml",
    "Makefile",
    "pyproject.toml",
)
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
    """Return the checked source/configuration files under ``root``."""
    if root != REPOSITORY_ROOT:
        return sorted(path for path in root.rglob("*") if path.is_file())

    files: list[Path] = []
    for relative in DEFAULT_PATHS:
        candidate = root / relative
        if candidate.is_file():
            files.append(candidate)
        elif candidate.is_dir():
            files.extend(path for path in candidate.rglob("*") if path.is_file())
    return sorted(files)


def find_violations(root: Path) -> list[str]:
    """Return deterministic descriptions for every forbidden value found."""
    violations: list[str] = []
    for path in _files(root):
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(contents):
                violations.append(f"{path.relative_to(root)}: {label}")
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

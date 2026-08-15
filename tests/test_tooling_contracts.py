"""Regression contracts for the repository's reproducible quality gates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_covers_offline_python_and_frontend_quality_gates() -> None:
    """CI keeps the full local verification path explicit and reproducible."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")

    required_commands = (
        'python -m pip install -e ".[dev]"',
        "python -m ruff check src tests examples alembic scripts",
        "python -m ruff format --check src tests examples alembic scripts",
        "python -m pyright src/",
        "python scripts/check_forbidden.py",
        "python scripts/check_package.py",
        "python scripts/check_sqlite_migrations.py",
        "python scripts/portfolio_demo.py",
        "python scripts/verify_portfolio_evidence.py",
        "python -m pytest",
        "npm ci",
        "npm run test",
        "npm run lint",
        "npm run build",
        "npx playwright install --with-deps chromium",
        "npm run test:e2e",
        "docker compose config",
        "docker build --file frontend/Dockerfile frontend",
    )

    assert all(command in ci for command in required_commands)


def test_frontend_install_and_generated_artifact_contracts() -> None:
    """The frontend image uses lockfile installs and local output stays ignored."""
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text("utf-8")
    ignored = (REPO_ROOT / ".gitignore").read_text("utf-8")

    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "RUN npm install" not in dockerfile
    assert "frontend/node_modules/" in ignored
    assert "frontend/.next/" in ignored
    assert "frontend/playwright-report/" in ignored
    assert "frontend/test-results/" in ignored
    dockerignore = (REPO_ROOT / "frontend" / ".dockerignore").read_text("utf-8")
    assert ".env" in dockerignore
    assert ".env.*" in dockerignore


def test_make_targets_use_the_selected_python_interpreter() -> None:
    """Local test execution follows the canonical interpreter-owned install."""
    makefile = (REPO_ROOT / "Makefile").read_text("utf-8")

    assert "test:\n\tpython -m pytest" in makefile
    assert "lint:\n\tpython -m ruff check" in makefile
    assert "typecheck:\n\tpython -m pyright" in makefile


def test_frontend_declares_the_linter_required_by_its_script() -> None:
    """`next lint` remains reproducible after the lockfile-only install."""
    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text("utf-8"))
    dev_dependencies = package["devDependencies"]

    assert "eslint" in dev_dependencies
    assert "eslint-config-next" in dev_dependencies


def test_frontend_readme_uses_the_lockfile_install_command() -> None:
    """The documented local setup matches CI and the Docker build."""
    readme = (REPO_ROOT / "frontend" / "README.md").read_text("utf-8")

    assert "npm ci" in readme


def test_pyright_uses_supported_basic_configuration_keys() -> None:
    """The type-check gate must not silently ignore its configured mode."""
    config = json.loads((REPO_ROOT / "pyrightconfig.json").read_text("utf-8"))

    assert "analysis" not in config
    assert config["typeCheckingMode"] == "basic"
    assert config["useLibraryCodeForTypes"] is True


def test_forbidden_scan_refuses_legacy_imports_and_secret_like_values(
    tmp_path: Path,
) -> None:
    """The scan rejects the retired dependency and obvious committed secrets."""
    (tmp_path / "legacy.py").write_text("import shared_core\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "scripts/check_forbidden.py", "--root", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "legacy.py" in result.stderr

    (tmp_path / "legacy.py").write_text(
        "token = 'ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN'\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "scripts/check_forbidden.py", "--root", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "legacy.py" in result.stderr


def test_repository_forbidden_scan_passes() -> None:
    """The scanner does not reject its own patterns or approved repository code."""
    result = subprocess.run(
        [sys.executable, "scripts/check_forbidden.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_sqlite_migration_check_applies_the_live_revision_chain() -> None:
    """The standalone migration gate validates the tables migrations actually own."""
    result = subprocess.run(
        [sys.executable, "scripts/check_sqlite_migrations.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

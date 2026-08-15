"""Regression contracts for the repository's reproducible quality gates."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from pytest import MonkeyPatch

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_IMAGE = (
    "node:20.20.1-alpine3.22@"
    "sha256:c0a3cda003a229d51f0f118c12a706842f43450ae505ed6825d66b5acdef127f"
)


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
    assert ".env*" in dockerignore
    assert "!.env.example" in dockerignore
    frontend_ignore = (REPO_ROOT / "frontend" / ".gitignore").read_text("utf-8")
    assert ".env*" in frontend_ignore
    assert "!.env.example" in frontend_ignore
    assert "\ndebug.log\n" in frontend_ignore


def test_frontend_container_runtime_uses_production_dependencies_only() -> None:
    """The runtime stage must not inherit frontend test and lint tooling."""
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text("utf-8")
    package = json.loads((REPO_ROOT / "frontend" / "package.json").read_text("utf-8"))
    runtime_stage = dockerfile.split("FROM base AS runner", maxsplit=1)[1]

    assert f"FROM {NODE_IMAGE} AS base" in dockerfile
    assert "FROM dependencies AS dev" in dockerfile
    assert "FROM base AS production-dependencies" in dockerfile
    assert "RUN npm ci --omit=dev" in dockerfile
    assert (
        "COPY --from=production-dependencies /app/node_modules ./node_modules"
        in dockerfile
    )
    assert "COPY --from=builder /app/node_modules ./node_modules" not in dockerfile
    assert {"vitest", "@playwright/test", "eslint"} <= set(package["devDependencies"])
    assert "COPY --from=builder /app/node_modules" not in runtime_stage


def test_frontend_node_runtime_is_pinned_consistently_in_ci_and_docker() -> None:
    """A patch-level CI runtime and immutable image avoid drifting Node builds."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text("utf-8")

    assert "node-version: '20.20.1'" in ci
    assert f"FROM {NODE_IMAGE} AS base" in dockerfile


def test_make_targets_use_the_selected_python_interpreter() -> None:
    """Local test execution follows the canonical interpreter-owned install."""
    makefile = (REPO_ROOT / "Makefile").read_text("utf-8")

    assert "test:\n\tpython -m pytest" in makefile
    assert "lint:\n\tpython -m ruff check" in makefile
    assert "format:\n\tpython -m ruff format" in makefile
    assert "format-check:\n\tpython -m ruff format --check" in makefile
    assert "typecheck:\n\tpython -m pyright" in makefile
    assert "package-check:\n\tpython -m scripts.check_package" in makefile
    assert "migration-check:\n\tpython -m scripts.check_sqlite_migrations" in makefile
    assert "evidence-check:\n\tpython -m scripts.portfolio_demo" in makefile
    assert "\tpython -m scripts.verify_portfolio_evidence" in makefile


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


def test_forbidden_scan_checks_tracked_frontend_environment_files(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """A tracked production env file is scanned even though local envs are ignored."""
    repository = tmp_path / "repository"
    environment_file = repository / "frontend" / ".env.production"
    environment_file.parent.mkdir(parents=True)
    environment_file.write_text("API_KEY=sk-" + "a" * 24 + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "add", "-f", "frontend/.env.production"],
        check=True,
    )

    spec = importlib.util.spec_from_file_location(
        "forbidden_scan_test_module", REPO_ROOT / "scripts" / "check_forbidden.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "REPOSITORY_ROOT", repository)

    assert module.find_violations(repository) == [
        "frontend/.env.production: OpenAI-style API key"
    ]


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

"""Packaging contracts for the self-contained workflow-engine distribution."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]

ACTIONABLE_FILES = [
    ".github/workflows/ci.yml",
    "Makefile",
    "alembic/env.py",
    "AGENTS.md",
    "README.md",
    "docs/EXECUTION_PLAN.md",
    "docs/architecture.md",
    "docs/design-decisions.md",
    "docs/failure-modes.md",
    "docs/implementation_plan.md",
    "docs/roadmap.md",
    "docs/security.md",
]


def test_wheel_contains_and_imports_internal_vendor_core(tmp_path: Path) -> None:
    """A no-dependency wheel exposes vendored code without ``shared_core``."""
    wheel_dir = tmp_path / "wheel"
    target_dir = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-cache-dir",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            ".",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("async_workflow_engine-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        assert "workflow_engine/internal/vendor_core/__init__.py" in archive.namelist()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target_dir),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    isolated_import = "\n".join(
        [
            "import importlib.util",
            "import sys",
            f"target = {str(target_dir)!r}",
            "sys.path[:] = [target] + [entry for entry in sys.path "
            "if 'site-packages' not in entry]",
            "assert importlib.util.find_spec('shared_core') is None",
            "import workflow_engine.internal.vendor_core",
        ]
    )
    subprocess.run(
        [sys.executable, "-I", "-c", isolated_import],
        check=True,
        capture_output=True,
        text=True,
    )


def test_installation_and_operational_references_are_self_contained() -> None:
    """No operational path installs or imports the former shared package."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    dependencies = project["project"]["dependencies"]
    assert all("shared-core" not in dependency for dependency in dependencies)
    assert {"llm", "document-parsers"} <= set(
        project["project"]["optional-dependencies"]
    )
    for relative_path in ACTIONABLE_FILES:
        contents = (REPO_ROOT / relative_path).read_text("utf-8")
        assert "shared_core" not in contents
        assert "shared-core" not in contents
        assert "operator-shared-core" not in contents


def test_dev_extra_supports_toml_parsing_on_python_310() -> None:
    """The packaging contract test remains collectable on the supported floor."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))
    assert (
        "tomli>=2.0.0; python_version < '3.11'"
        in project["project"]["optional-dependencies"]["dev"]
    )

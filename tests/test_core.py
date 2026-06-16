"""Smoke tests: the demo runs end-to-end and the package imports cleanly."""

import runpy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO = PROJECT_ROOT / "examples" / "run_demo.py"


def test_demo_runs_without_error(monkeypatch, capsys):
    """The shipped demo must run to completion (exit 0) with no DB/keys."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", [str(DEMO)])
    runpy.run_path(str(DEMO), run_name="__main__")
    out = capsys.readouterr().out
    assert "Demo complete" in out


def test_all_modules_import():
    import importlib

    for module in (
        "workflow_engine.main",
        "workflow_engine.worker",
        "workflow_engine.runner",
        "workflow_engine.executor",
        "workflow_engine.parser",
        "workflow_engine.scheduler",
        "workflow_engine.webhooks",
        "workflow_engine.dag",
        "workflow_engine.db",
        "workflow_engine.tasks",
        "workflow_engine.storage",
        "workflow_engine.storage_db",
        "workflow_engine.models",
    ):
        assert importlib.import_module(module) is not None

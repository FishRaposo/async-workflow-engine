"""Tests for the database availability probe and storage selection."""

import workflow_engine.db as db_module
from workflow_engine.config import AppConfig
from workflow_engine.storage import InMemoryWorkflowStorage
from workflow_engine.storage_db import DatabaseWorkflowStorage


def test_probe_database_falls_back_when_unreachable(monkeypatch):
    # Point at an unreachable host so the probe must fail fast and fall back.
    cfg = AppConfig()
    monkeypatch.setattr(
        cfg, "DATABASE_URL", "postgresql+psycopg://x:x@127.0.0.1:1/none"
    )
    # Reset module cache so a fresh manager is built for the bad URL.
    monkeypatch.setattr(db_module, "_db_manager", None)
    monkeypatch.setattr(db_module, "db_available", False)
    available = db_module.probe_database(cfg)
    assert available is False
    assert db_module.db_available is False


def test_get_storage_returns_in_memory_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(db_module, "db_available", False)
    storage = db_module.get_storage()
    assert isinstance(storage, InMemoryWorkflowStorage)


def test_probe_database_succeeds_with_sqlite(monkeypatch, tmp_path):
    cfg = AppConfig()
    db_file = tmp_path / "probe.db"
    monkeypatch.setattr(cfg, "DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setattr(db_module, "_db_manager", None)
    monkeypatch.setattr(db_module, "db_available", False)
    available = db_module.probe_database(cfg)
    assert available is True
    storage = db_module.get_storage(cfg)
    assert isinstance(storage, DatabaseWorkflowStorage)
    # Clean up the cached manager so other tests start fresh.
    monkeypatch.setattr(db_module, "_db_manager", None)
    monkeypatch.setattr(db_module, "db_available", False)

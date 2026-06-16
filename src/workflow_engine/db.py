"""Database availability probe and storage selection.

PostgreSQL persistence is the *default* backend. On startup we probe the
configured database with a cheap ``SELECT 1``; if it is reachable we use
:class:`DatabaseWorkflowStorage`, otherwise we transparently fall back to the
in-memory store so tests, the demo, and offline development all run with no
database. This mirrors the ``db_available`` pattern used across the migrated
services in the portfolio.
"""

from typing import Optional, Union

from loguru import logger
from shared_core.database import DatabaseManager
from sqlalchemy import text

from .config import AppConfig
from .storage import InMemoryWorkflowStorage
from .storage_db import DatabaseWorkflowStorage

Storage = Union[DatabaseWorkflowStorage, InMemoryWorkflowStorage]

# Module-level cache so the API and worker share one probe result.
db_available: bool = False
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(config: Optional[AppConfig] = None) -> DatabaseManager:
    """Return a lazily-constructed shared ``DatabaseManager``."""
    global _db_manager
    if _db_manager is None:
        config = config or AppConfig()
        _db_manager = DatabaseManager(
            config.DATABASE_URL,
            pool_size=config.DB_POOL_SIZE,
            max_overflow=config.DB_MAX_OVERFLOW,
            pool_timeout=config.DB_POOL_TIMEOUT,
        )
    return _db_manager


def _connect_timeout_args(db_url: str, seconds: int = 2) -> dict:
    """Driver-specific connect-timeout kwargs so a probe fails fast, not hangs."""
    if db_url.startswith(("postgresql", "postgres")):
        return {"connect_args": {"connect_timeout": seconds}}
    return {}


def probe_database(config: Optional[AppConfig] = None) -> bool:
    """Probe DB connectivity, create tables if reachable, cache the result.

    Uses a short connect timeout so an unreachable database fails fast and we
    fall back to in-memory storage rather than blocking startup/tests.
    """
    global db_available
    config = config or AppConfig()
    try:
        from sqlalchemy import create_engine

        probe_engine = create_engine(
            config.DATABASE_URL,
            pool_pre_ping=True,
            **_connect_timeout_args(config.DATABASE_URL),
        )
        with probe_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        probe_engine.dispose()
        get_db_manager(config).create_tables()
        db_available = True
        logger.info("Database reachable — using DatabaseWorkflowStorage.")
    except Exception as exc:
        db_available = False
        logger.warning(
            f"Database unavailable ({exc}) — falling back to in-memory storage."
        )
    return db_available


def get_storage(config: Optional[AppConfig] = None) -> Storage:
    """Return the active storage backend based on the probe result."""
    if db_available:
        manager = get_db_manager(config)
        return DatabaseWorkflowStorage(manager.get_session)
    return InMemoryWorkflowStorage()

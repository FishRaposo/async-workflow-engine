"""Apply all Alembic revisions to a disposable SQLite database."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "alembic_version",
    "workflow_runs",
    "step_executions",
    "schedules",
    "webhook_registrations",
    "workflow_definitions",
    "idempotency_records",
    "execution_events",
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="awfe-migrations-") as temporary:
        database = Path(temporary) / "workflow.db"
        environment = os.environ.copy()
        environment["DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT,
            env=environment,
            check=True,
        )
        connection = sqlite3.connect(database)
        try:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            revision = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
        finally:
            connection.close()
        missing = EXPECTED_TABLES - tables
        if missing:
            raise RuntimeError(f"SQLite migrations missed tables: {sorted(missing)}")
        if revision != ("0002_runtime_persistence",):
            raise RuntimeError(f"SQLite migration head is unexpected: {revision}")
    print("SQLite migrations passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

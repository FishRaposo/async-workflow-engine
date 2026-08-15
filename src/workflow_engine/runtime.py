"""Runtime-owned stores shared by API and eager Celery execution.

The default bundle is deliberately process-local and offline-safe.  Once the
database probe succeeds, callers receive SQLAlchemy-backed adapters, allowing
separate API and worker processes to see the same schedules, webhooks, versions,
idempotency claims, and execution events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterator

from sqlalchemy.orm import Session

from .contracts import InMemoryIdempotencyStore
from .scheduler import InMemoryScheduleStore, WorkflowScheduler
from .storage_db import (
    DatabaseExecutionEventStore,
    DatabaseIdempotencyStore,
    DatabaseScheduleStore,
    DatabaseWebhookStore,
    DatabaseWorkflowVersionStore,
)
from .trace_store import InMemoryExecutionEventStore
from .versions import InMemoryWorkflowVersionStore
from .webhooks import InMemoryWebhookStore, WebhookRegistry


@dataclass
class RuntimeServices:
    scheduler: WorkflowScheduler
    webhooks: WebhookRegistry
    versions: Any
    idempotency: Any
    events: Any

    @classmethod
    def in_memory(cls) -> "RuntimeServices":
        return cls(
            scheduler=WorkflowScheduler(store=InMemoryScheduleStore()),
            webhooks=WebhookRegistry(store=InMemoryWebhookStore()),
            versions=InMemoryWorkflowVersionStore(),
            idempotency=InMemoryIdempotencyStore(),
            events=InMemoryExecutionEventStore(),
        )

    @classmethod
    def database(
        cls, session_factory: Callable[[], Iterator[Session]]
    ) -> "RuntimeServices":
        return cls(
            scheduler=WorkflowScheduler(store=DatabaseScheduleStore(session_factory)),
            webhooks=WebhookRegistry(store=DatabaseWebhookStore(session_factory)),
            versions=DatabaseWorkflowVersionStore(session_factory),
            idempotency=DatabaseIdempotencyStore(session_factory),
            events=DatabaseExecutionEventStore(session_factory),
        )


_offline_services = RuntimeServices.in_memory()


def get_runtime_services() -> RuntimeServices:
    """Select durable adapters only after the established DB availability probe."""
    from . import db

    if db.db_available:
        return RuntimeServices.database(db.get_db_manager().get_session)
    return _offline_services

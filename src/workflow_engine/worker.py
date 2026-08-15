"""Celery worker — real background workflow dispatch.

The ``run_workflow_task`` runs a full workflow (parse → execute → persist) in a
background worker. It is importable with no broker running (Celery only connects
lazily when a worker starts or ``.delay()`` actually enqueues), so tests and the
API can import it freely. The API enqueues this task for async dispatch when a
broker is available, otherwise it runs the workflow inline.
"""

import os
from typing import Any, Dict, Optional

from loguru import logger

from workflow_engine.internal.vendor_core.tasks import create_celery_app

from .config import AppConfig
from .db import get_storage, probe_database
from .runner import run_workflow
from .runtime import get_runtime_services
from .trace import TraceContext

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)
beat_services = get_runtime_services()
beat_scheduler = beat_services.scheduler
beat_idempotency = beat_services.idempotency


def _celery_beat_enabled() -> bool:
    return os.getenv("WORKFLOW_CELERY_BEAT", "").lower() in {"1", "true", "yes"}


def _run_due_definition(yaml_definition: str) -> Dict[str, Any]:
    """Local due-run dispatch used by the optional beat task."""
    probe_database(config)
    services = get_runtime_services()
    return run_workflow(
        yaml_definition,
        get_storage(config),
        trace=TraceContext(),
        version_store=services.versions,
        event_store=services.events,
    )


@celery_app.task(name="workflow_engine.run_workflow", bind=True, max_retries=2)
def run_workflow_task(
    self: Any,
    yaml_definition: str,
    run_id: Optional[str] = None,
    version_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a workflow in the background and persist the result.

    Probes the database (so the worker process picks the right storage backend
    independently of the API) and delegates to the shared runner.
    """
    logger.info("Worker received workflow dispatch")
    probe_database(config)
    storage = get_storage(config)
    services = get_runtime_services()
    try:
        if version_hash is not None and services.versions.get(version_hash) is None:
            services.versions.put(yaml_definition)
        return run_workflow(
            yaml_definition,
            storage,
            run_id=run_id,
            trace=TraceContext(run_id=run_id),
            version_store=services.versions,
            version_hash=version_hash,
            event_store=services.events,
        )
    except Exception as exc:  # pragma: no cover - retry path needs a live broker
        logger.error(f"Worker workflow execution failed: {exc}")
        raise self.retry(exc=exc, countdown=2) from exc


@celery_app.task(name="workflow_engine.run_due_schedules")
def run_due_schedules() -> Dict[str, Any]:
    """Optional Celery-beat tick over the in-process schedule registry.

    Deployment must explicitly opt in with ``WORKFLOW_CELERY_BEAT=1``.  Without
    it, import and eager execution remain broker-free no-ops.
    """
    if not _celery_beat_enabled():
        logger.info("run_due_schedules tick skipped (Celery beat disabled)")
        return {"dispatched": []}
    active_services = get_runtime_services()
    return {
        "dispatched": active_services.scheduler.dispatch_due(
            _run_due_definition, idempotency=active_services.idempotency
        )
    }

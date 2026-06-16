"""Celery worker — real background workflow dispatch.

The ``run_workflow_task`` runs a full workflow (parse → execute → persist) in a
background worker. It is importable with no broker running (Celery only connects
lazily when a worker starts or ``.delay()`` actually enqueues), so tests and the
API can import it freely. The API enqueues this task for async dispatch when a
broker is available, otherwise it runs the workflow inline.
"""

from typing import Any, Dict, Optional

from loguru import logger
from shared_core.tasks import create_celery_app

from .config import AppConfig
from .db import get_storage, probe_database
from .runner import run_workflow

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)


@celery_app.task(name="workflow_engine.run_workflow", bind=True, max_retries=2)
def run_workflow_task(
    self: Any,
    yaml_definition: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a workflow in the background and persist the result.

    Probes the database (so the worker process picks the right storage backend
    independently of the API) and delegates to the shared runner.
    """
    logger.info("Worker received workflow dispatch")
    probe_database(config)
    storage = get_storage(config)
    try:
        return run_workflow(yaml_definition, storage, run_id=run_id)
    except Exception as exc:  # pragma: no cover - retry path needs a live broker
        logger.error(f"Worker workflow execution failed: {exc}")
        raise self.retry(exc=exc, countdown=2) from exc


@celery_app.task(name="workflow_engine.run_due_schedules")
def run_due_schedules() -> Dict[str, Any]:
    """Celery-beat entry point: a placeholder hook for periodic scheduling.

    Real scheduling state lives in :mod:`workflow_engine.scheduler`; wiring this
    to beat is a deployment concern. Returns an empty dispatch summary so the
    task is callable and testable without a broker.
    """
    logger.info("run_due_schedules tick (no schedules wired in this process)")
    return {"dispatched": []}

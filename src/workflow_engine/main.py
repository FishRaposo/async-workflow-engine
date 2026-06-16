"""FastAPI application — the HTTP surface of the workflow engine.

Exposes everything a dashboard needs: synchronous and async workflow dispatch,
rerun, webhook triggers, cron schedules, run listing/inspection, a DAG
projection, and the dead-letter queue. Storage defaults to PostgreSQL and falls
back to in-memory when no database is reachable (probed at startup).
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from shared_core.errors import BaseApplicationError, application_error_handler
from shared_core.health import check_health
from shared_core.logging import setup_logging
from shared_core.redis import RedisManager

from . import db as db_module
from .config import AppConfig
from .dag import build_dag
from .db import get_db_manager, get_storage, probe_database
from .parser import WorkflowValidationError, load_workflow_yaml
from .runner import run_workflow
from .scheduler import WorkflowScheduler, is_valid_cron
from .tasks import TASK_REGISTRY
from .webhooks import WebhookRegistry

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

db_manager = get_db_manager(config)
redis_manager = RedisManager(config.REDIS_URL)
scheduler = WorkflowScheduler()
webhooks = WebhookRegistry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    probe_database(config)
    yield


app = FastAPI(title=config.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_exception_handler(BaseApplicationError, application_error_handler)


def _storage() -> Any:
    """Resolve the active storage backend for the current request."""
    return get_storage(config)


def _celery_enabled() -> bool:
    """Async dispatch is opt-in via env so the default path stays offline."""
    return os.getenv("WORKFLOW_ASYNC", "").lower() in {"1", "true", "yes"}


def _should_dispatch_async(force_async: bool) -> bool:
    """Async when the request asks for it or the env flag enables it."""
    return force_async or _celery_enabled()


# --------------------------------------------------------------------------- #
# Request/response models
# --------------------------------------------------------------------------- #
class WorkflowPayload(BaseModel):
    yaml_definition: str
    async_dispatch: bool = False


class SchedulePayload(BaseModel):
    name: str
    cron: str
    yaml_definition: str


class WebhookRegisterPayload(BaseModel):
    yaml_definition: str
    description: str = ""


class RerunPayload(BaseModel):
    async_dispatch: bool = False


# --------------------------------------------------------------------------- #
# Workflow execution
# --------------------------------------------------------------------------- #
def _dispatch(
    yaml_definition: str,
    *,
    run_id: Optional[str] = None,
    force_async: bool = False,
) -> dict:
    """Run a workflow inline, or enqueue it on Celery when async is enabled."""
    if _should_dispatch_async(force_async):
        try:
            from .worker import run_workflow_task

            async_result = run_workflow_task.delay(yaml_definition, run_id)
            return {
                "dispatched": "async",
                "task_id": async_result.id,
                "run_id": run_id,
            }
        except Exception as exc:  # pragma: no cover - needs a live broker
            raise HTTPException(
                status_code=503, detail=f"Async dispatch failed: {exc}"
            ) from exc
    result = run_workflow(yaml_definition, _storage(), run_id=run_id)
    result["dispatched"] = "sync"
    return result


@app.post("/workflows/validate")
def validate_workflow(payload: WorkflowPayload):
    try:
        config_wf = load_workflow_yaml(payload.yaml_definition)
        from .executor import WorkflowExecutor

        WorkflowExecutor(config_wf, TASK_REGISTRY).validate_registry()
        return {
            "valid": True,
            "workflow": config_wf.name,
            "steps": [
                {"id": s.id, "task": s.task, "depends_on": s.depends_on}
                for s in config_wf.steps
            ],
        }
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/workflows/run")
def run_workflow_endpoint(payload: WorkflowPayload):
    try:
        return _dispatch(payload.yaml_definition, force_async=payload.async_dispatch)
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/workflows/{run_id}/rerun")
def rerun_workflow(run_id: str, payload: Optional[RerunPayload] = None):
    record = _storage().get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    yaml_definition = record.get("yaml_definition")
    if not yaml_definition:
        raise HTTPException(
            status_code=409, detail="Original run has no stored definition to rerun"
        )
    force_async = bool(payload.async_dispatch) if payload else False
    try:
        return _dispatch(yaml_definition, run_id=run_id, force_async=force_async)
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/workflows")
def list_workflows():
    return {"runs": _storage().list_runs()}


# Declared before the dynamic ``/workflows/{run_id}`` route so the static path
# is not captured as a run id.
@app.get("/workflows/dead-letters")
def list_dead_letters(run_id: Optional[str] = None):
    return {"dead_letters": _storage().get_dead_letters(run_id)}


@app.get("/workflows/{run_id}")
def get_workflow_run(run_id: str):
    record = _storage().get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return record


@app.get("/workflows/{run_id}/dag")
def get_workflow_dag(run_id: str):
    record = _storage().get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    yaml_definition = record.get("yaml_definition")
    if not yaml_definition:
        raise HTTPException(status_code=409, detail="Run has no stored definition")
    config_wf = load_workflow_yaml(yaml_definition)
    return build_dag(config_wf, record.get("step_statuses"))


# --------------------------------------------------------------------------- #
# Webhooks
# --------------------------------------------------------------------------- #
@app.post("/webhooks/{name}/register")
def register_webhook(name: str, payload: WebhookRegisterPayload):
    try:
        load_workflow_yaml(payload.yaml_definition)
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    webhooks.register(name, payload.yaml_definition, payload.description)
    return {"registered": name}


@app.get("/webhooks")
def list_webhooks():
    return {"webhooks": webhooks.list_triggers()}


@app.post("/webhooks/{name}")
async def trigger_webhook(name: str, request: Request):
    trigger = webhooks.get(name)
    if not trigger:
        raise HTTPException(status_code=404, detail=f"Webhook '{name}' not registered")
    try:
        result = _dispatch(trigger.yaml_definition)
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"triggered": name, **result}


# --------------------------------------------------------------------------- #
# Schedules
# --------------------------------------------------------------------------- #
@app.post("/schedules")
def create_schedule(payload: SchedulePayload):
    if not is_valid_cron(payload.cron):
        raise HTTPException(
            status_code=422, detail=f"Invalid cron expression: {payload.cron}"
        )
    try:
        load_workflow_yaml(payload.yaml_definition)
    except (WorkflowValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sched = scheduler.register(payload.name, payload.cron, payload.yaml_definition)
    return {
        "name": sched.name,
        "cron": sched.cron,
        "next_run": sched.next_run.isoformat() if sched.next_run else None,
    }


@app.get("/schedules")
def list_schedules():
    return {"schedules": scheduler.list_schedules()}


@app.delete("/schedules/{name}")
def delete_schedule(name: str):
    if not scheduler.unregister(name):
        raise HTTPException(status_code=404, detail=f"Schedule '{name}' not found")
    return {"deleted": name}


@app.post("/schedules/run-due")
def run_due_schedules():
    """Fire any schedules whose next_run time has passed (manual tick)."""
    dispatched = []
    for sched in scheduler.due():
        result = _dispatch(sched.yaml_definition)
        scheduler.mark_ran(sched.name)
        dispatched.append({"name": sched.name, "run_id": result.get("run_id")})
    return {"dispatched": dispatched}


# --------------------------------------------------------------------------- #
# Introspection / health
# --------------------------------------------------------------------------- #
@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {"name": name, "description": (fn.__doc__ or "").strip().split("\n")[0]}
            for name, fn in sorted(TASK_REGISTRY.items())
        ]
    }


@app.get("/health")
def health_check():
    result = check_health(db_manager, redis_manager, config.APP_NAME)
    result["storage"] = "database" if db_module.db_available else "in-memory"
    return result


def main() -> None:  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()

"""Offline-first FastAPI surface for declarative workflow execution."""

import os
import uuid
from contextlib import asynccontextmanager
from functools import wraps
from inspect import iscoroutinefunction
from typing import Any, NoReturn, Optional, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.types import ExceptionHandler

from workflow_engine.internal.vendor_core.errors import (
    BaseApplicationError,
    application_error_handler,
)
from workflow_engine.internal.vendor_core.health import check_health
from workflow_engine.internal.vendor_core.logging import setup_logging

try:
    from workflow_engine.internal.vendor_core.redis import RedisManager
except ImportError:  # pragma: no cover - Redis remains an optional runtime aid
    RedisManager = None  # type: ignore[assignment]

from . import db as db_module
from .auth import AuthPolicy, LocalRateLimiter, Role
from .config import AppConfig
from .dag import build_dag
from .db import get_db_manager, get_storage, probe_database
from .locks import InMemoryLockProvider, RedisLockProvider
from .parser import WorkflowValidationError, load_workflow_yaml
from .runner import run_workflow
from .runtime import get_runtime_services
from .scheduler import is_valid_cron
from .tasks import TASK_REGISTRY
from .trace import TraceContext
from .versions import canonical_yaml_hash

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

db_manager = get_db_manager(config)
redis_manager = RedisManager(config.REDIS_URL) if RedisManager else None
services = get_runtime_services()
scheduler = services.scheduler
webhooks = services.webhooks
run_locks = InMemoryLockProvider()


def _auth_policy() -> AuthPolicy:
    roles = {"viewer": Role.VIEWER, "operator": Role.OPERATOR, "admin": Role.ADMIN}
    keys = {}
    for mapping in config.WORKFLOW_API_KEYS.split(","):
        key, separator, role = mapping.strip().partition(":")
        if key and separator and role.lower() in roles:
            keys[key] = roles[role.lower()]
    return AuthPolicy(api_keys=keys, required=config.WORKFLOW_AUTH_REQUIRED)


auth_policy = _auth_policy()
rate_limiter = (
    LocalRateLimiter(
        limit=config.WORKFLOW_RATE_LIMIT,
        window_seconds=config.WORKFLOW_RATE_LIMIT_WINDOW_SECONDS,
        recognized_api_keys=set(auth_policy.api_keys),
    )
    if config.WORKFLOW_RATE_LIMIT > 0
    else None
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global services, scheduler, webhooks
    if probe_database(config):
        services = get_runtime_services()
        scheduler = services.scheduler
        webhooks = services.webhooks
    yield


app = FastAPI(title=config.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_exception_handler(
    BaseApplicationError, cast(ExceptionHandler, application_error_handler)
)


@app.exception_handler(HTTPException)
async def compatible_http_error(_: Request, exc: HTTPException) -> JSONResponse:
    """Preserve the established detail key while adding a stable error code."""
    detail = exc.detail
    message = detail if isinstance(detail, str) else str(detail)
    code = (exc.headers or {}).get("X-Workflow-Error-Code", "request_failed")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "error": {"code": code, "message": message}},
    )


@app.exception_handler(RequestValidationError)
async def compatible_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """Add the stable error envelope without changing FastAPI's detail payload."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "error": {
                "code": "validation_failed",
                "message": "Request validation failed",
            },
        },
    )


def _storage() -> Any:
    return get_storage(config)


def _active_services() -> Any:
    return get_runtime_services() if db_module.db_available else services


def _raise(status_code: int, detail: str, code: str) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail=detail,
        headers={"X-Workflow-Error-Code": code},
    )


def _persistence_errors(handler: Any) -> Any:
    """Translate every storage read/write failure to the public error contract."""

    if iscoroutinefunction(handler):

        @wraps(handler)
        async def async_wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                return await handler(*args, **kwargs)
            except SQLAlchemyError as exc:
                _raise(503, f"Persistence failed: {exc}", "persistence_failed")

        return async_wrapped

    @wraps(handler)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return handler(*args, **kwargs)
        except SQLAlchemyError as exc:
            _raise(503, f"Persistence failed: {exc}", "persistence_failed")

    return wrapped


def _check_access(request: Request, minimum_role: Role) -> None:
    api_key = request.headers.get("X-API-Key")
    if rate_limiter is not None and not rate_limiter.allow(
        api_key=api_key,
        client_id=request.client.host if request.client else None,
    ):
        _raise(429, "Rate limit exceeded", "rate_limited")
    if not auth_policy.authorize(api_key, minimum_role):
        _raise(
            401 if not api_key else 403,
            "Authentication required" if not api_key else "Insufficient role",
            "unauthorized" if not api_key else "forbidden",
        )


def _claim_idempotency(namespace: str, key: Optional[str]) -> None:
    if key and not _active_services().idempotency.claim(namespace, key):
        _raise(409, "Duplicate idempotency key", "idempotency_conflict")


def _celery_enabled() -> bool:
    return os.getenv("WORKFLOW_ASYNC", "").lower() in {"1", "true", "yes"}


def _should_dispatch_async(force_async: bool) -> bool:
    return force_async or _celery_enabled()


def _lock_provider() -> InMemoryLockProvider | RedisLockProvider:
    """Use Redis locks only when explicitly configured and importable."""
    if config.WORKFLOW_REDIS_LOCKING_ENABLED and redis_manager is not None:
        return RedisLockProvider.from_manager(redis_manager)
    return run_locks


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
    secret: Optional[str] = None


class RerunPayload(BaseModel):
    async_dispatch: bool = False


def _dispatch(
    yaml_definition: str,
    *,
    run_id: Optional[str] = None,
    force_async: bool = False,
    version_hash: Optional[str] = None,
) -> dict:
    """Use the same runner for inline API and broker-backed execution."""
    services_for_run = _active_services()
    run_id = run_id or str(uuid.uuid4())
    if _should_dispatch_async(force_async):
        try:
            from .worker import run_workflow_task

            version = services_for_run.versions.put(yaml_definition)
            async_result = run_workflow_task.delay(
                yaml_definition,
                run_id,
                version_hash or version.content_hash,
                config.WORKFLOW_CONCURRENCY_LIMIT,
            )
            return {
                "dispatched": "async",
                "task_id": async_result.id,
                "run_id": run_id,
                "version_hash": version.content_hash,
            }
        except Exception as exc:  # pragma: no cover - requires a live broker
            _raise(503, f"Async dispatch failed: {exc}", "dispatch_failed")

    trace = TraceContext(trigger_id=str(uuid.uuid4()), run_id=run_id)

    def execute() -> dict:
        return run_workflow(
            yaml_definition,
            _storage(),
            run_id=run_id,
            trace=trace,
            version_store=services_for_run.versions,
            version_hash=version_hash,
            event_store=services_for_run.events,
            concurrency_limit=config.WORKFLOW_CONCURRENCY_LIMIT,
        )

    if config.WORKFLOW_LOCKING_ENABLED:
        with _lock_provider().acquire(
            f"workflow:{canonical_yaml_hash(yaml_definition)}"
        ) as held:
            if not held:
                _raise(409, "Workflow is already running", "lock_conflict")
            result = execute()
    else:
        result = execute()
    result["dispatched"] = "sync"
    return result


@app.post("/workflows/validate")
def validate_workflow(payload: WorkflowPayload, request: Request):
    _check_access(request, Role.VIEWER)
    try:
        workflow = load_workflow_yaml(payload.yaml_definition)
        from .executor import WorkflowExecutor

        WorkflowExecutor(workflow, TASK_REGISTRY).validate_registry()
        return {
            "valid": True,
            "workflow": workflow.name,
            "steps": [
                {"id": step.id, "task": step.task, "depends_on": step.depends_on}
                for step in workflow.steps
            ],
        }
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")


@app.post("/workflows/run")
def run_workflow_endpoint(payload: WorkflowPayload, request: Request):
    _check_access(request, Role.OPERATOR)
    try:
        _claim_idempotency("workflow:run", request.headers.get("Idempotency-Key"))
        return _dispatch(payload.yaml_definition, force_async=payload.async_dispatch)
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")
    except SQLAlchemyError as exc:
        _raise(503, f"Persistence failed: {exc}", "persistence_failed")


@app.post("/workflows/{run_id}/rerun")
@_persistence_errors
def rerun_workflow(
    run_id: str, request: Request, payload: Optional[RerunPayload] = None
):
    _check_access(request, Role.OPERATOR)
    record = _storage().get_run(run_id)
    if not record:
        _raise(404, f"Run '{run_id}' not found", "not_found")
    yaml_definition = record.get("yaml_definition")
    if not yaml_definition:
        _raise(
            409, "Original run has no stored definition to rerun", "rerun_unavailable"
        )
    try:
        return _dispatch(
            yaml_definition,
            run_id=run_id,
            force_async=bool(payload.async_dispatch) if payload else False,
            version_hash=record.get("version_hash"),
        )
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")


@app.get("/workflows")
@_persistence_errors
def list_workflows(request: Request):
    _check_access(request, Role.VIEWER)
    return {"runs": _storage().list_runs()}


# Keep this static route before ``/workflows/{run_id}``.
@app.get("/workflows/dead-letters")
@_persistence_errors
def list_dead_letters(request: Request, run_id: Optional[str] = None):
    _check_access(request, Role.VIEWER)
    return {"dead_letters": _storage().get_dead_letters(run_id)}


@app.get("/workflows/{run_id}")
@_persistence_errors
def get_workflow_run(run_id: str, request: Request):
    _check_access(request, Role.VIEWER)
    record = _storage().get_run(run_id)
    if not record:
        _raise(404, f"Run '{run_id}' not found", "not_found")
    return {**record, "events": _active_services().events.list(run_id)}


@app.get("/workflows/{run_id}/dag")
@_persistence_errors
def get_workflow_dag(run_id: str, request: Request):
    _check_access(request, Role.VIEWER)
    record = _storage().get_run(run_id)
    if not record:
        _raise(404, f"Run '{run_id}' not found", "not_found")
    yaml_definition = record.get("yaml_definition")
    if not yaml_definition:
        _raise(409, "Run has no stored definition", "dag_unavailable")
    return build_dag(load_workflow_yaml(yaml_definition), record.get("step_statuses"))


@app.post("/webhooks/{name}/register")
def register_webhook(name: str, payload: WebhookRegisterPayload, request: Request):
    _check_access(request, Role.OPERATOR)
    try:
        load_workflow_yaml(payload.yaml_definition)
        webhooks.register(
            name, payload.yaml_definition, payload.description, secret=payload.secret
        )
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")
    except SQLAlchemyError as exc:
        _raise(503, f"Persistence failed: {exc}", "persistence_failed")
    return {"registered": name}


@app.get("/webhooks")
@_persistence_errors
def list_webhooks(request: Request):
    _check_access(request, Role.VIEWER)
    return {"webhooks": webhooks.list_triggers()}


@app.post("/webhooks/{name}")
@_persistence_errors
async def trigger_webhook(name: str, request: Request):
    _check_access(request, Role.OPERATOR)
    trigger = webhooks.get(name)
    if not trigger:
        _raise(404, f"Webhook '{name}' not registered", "not_found")
    if not webhooks.verify_signature(
        name, await request.body(), request.headers.get("X-Hub-Signature-256")
    ):
        _raise(401, "Webhook signature is invalid", "webhook_signature_invalid")
    _claim_idempotency(f"webhook:{name}", request.headers.get("Idempotency-Key"))
    try:
        return {"triggered": name, **_dispatch(trigger.yaml_definition)}
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")


@app.post("/schedules")
def create_schedule(payload: SchedulePayload, request: Request):
    _check_access(request, Role.OPERATOR)
    if not is_valid_cron(payload.cron):
        _raise(422, f"Invalid cron expression: {payload.cron}", "validation_failed")
    try:
        load_workflow_yaml(payload.yaml_definition)
        schedule = scheduler.register(
            payload.name, payload.cron, payload.yaml_definition
        )
    except (WorkflowValidationError, ValueError) as exc:
        _raise(422, str(exc), "validation_failed")
    except SQLAlchemyError as exc:
        _raise(503, f"Persistence failed: {exc}", "persistence_failed")
    return {
        "name": schedule.name,
        "cron": schedule.cron,
        "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
    }


@app.get("/schedules")
@_persistence_errors
def list_schedules(request: Request):
    _check_access(request, Role.VIEWER)
    return {"schedules": scheduler.list_schedules()}


@app.delete("/schedules/{name}")
@_persistence_errors
def delete_schedule(name: str, request: Request):
    _check_access(request, Role.ADMIN)
    if not scheduler.unregister(name):
        _raise(404, f"Schedule '{name}' not found", "not_found")
    return {"deleted": name}


@app.post("/schedules/run-due")
@_persistence_errors
def run_due_schedules(request: Request):
    _check_access(request, Role.OPERATOR)
    return {
        "dispatched": scheduler.dispatch_due(
            _dispatch, idempotency=_active_services().idempotency
        )
    }


@app.get("/tasks")
def list_tasks(request: Request):
    _check_access(request, Role.VIEWER)
    return {
        "tasks": [
            {"name": name, "description": (fn.__doc__ or "").strip().split("\n")[0]}
            for name, fn in sorted(TASK_REGISTRY.items())
        ]
    }


@app.get("/health")
def health_check(request: Request):
    _check_access(request, Role.VIEWER)
    result = check_health(db_manager, redis_manager, config.APP_NAME)
    result["storage"] = "database" if db_module.db_available else "in-memory"
    return result


def main() -> None:  # pragma: no cover - manual entry point
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":  # pragma: no cover
    main()

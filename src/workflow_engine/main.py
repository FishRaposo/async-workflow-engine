import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from shared_core.database import DatabaseManager
from shared_core.errors import BaseApplicationError, application_error_handler
from shared_core.health import check_health
from shared_core.logging import setup_logging
from shared_core.redis import RedisManager

from .config import AppConfig
from .parser import WorkflowValidationError, load_workflow_yaml
from .storage import InMemoryWorkflowStorage
from .tasks import TASK_REGISTRY

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

app = FastAPI(title=config.APP_NAME, version="0.1.0")
db_manager = DatabaseManager(
    config.DATABASE_URL,
    pool_size=config.DB_POOL_SIZE,
    max_overflow=config.DB_MAX_OVERFLOW,
    pool_timeout=config.DB_POOL_TIMEOUT,
)
redis_manager = RedisManager(config.REDIS_URL)

app.add_exception_handler(BaseApplicationError, application_error_handler)
storage = InMemoryWorkflowStorage()


class WorkflowPayload(BaseModel):
    yaml_definition: str


class RunStatus(BaseModel):
    run_id: str
    workflow_name: str
    status: str
    step_statuses: dict[str, str]
    created_at: str
    completed_at: Optional[str] = None


@app.post("/workflows/validate")
def validate_workflow(payload: WorkflowPayload):
    try:
        config_wf = load_workflow_yaml(payload.yaml_definition)
        from .executor import WorkflowExecutor

        executor = WorkflowExecutor(config_wf, TASK_REGISTRY)
        executor.validate_registry()
        return {
            "valid": True,
            "workflow": config_wf.name,
            "steps": [
                {"id": s.id, "task": s.task, "depends_on": s.depends_on}
                for s in config_wf.steps
            ],
        }
    except (WorkflowValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/workflows/run")
def run_workflow(payload: WorkflowPayload):
    try:
        config_wf = load_workflow_yaml(payload.yaml_definition)
        from .executor import WorkflowExecutor

        executor = WorkflowExecutor(config_wf, TASK_REGISTRY)
        statuses = executor.execute()
        run_id = str(uuid.uuid4())
        storage.save_run(run_id, config_wf.name, statuses, executor.results)
        record = storage.get_run(run_id)
        return {
            "run_id": run_id,
            "workflow": config_wf.name,
            "step_statuses": statuses,
            "created_at": record.get("timestamp") if record else None,
        }
    except (WorkflowValidationError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/workflows/{run_id}")
def get_workflow_run(run_id: str):
    record = storage.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunStatus(
        run_id=run_id,
        workflow_name=record["workflow_name"],
        status="completed",
        step_statuses=record["statuses"],
        created_at=record["timestamp"],
    )


@app.get("/tasks")
def list_tasks():
    return {
        "tasks": [
            {"name": name, "description": fn.__doc__ or ""}
            for name, fn in sorted(TASK_REGISTRY.items())
        ]
    }


@app.get("/health")
def health_check():
    return check_health(db_manager, redis_manager, config.APP_NAME)

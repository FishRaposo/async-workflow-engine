from workflow_engine.internal.vendor_core.config import BaseAppConfig


class AppConfig(BaseAppConfig):
    """Project-specific configuration extending the shared core settings."""

    APP_NAME: str = "async-workflow-engine"
    # All Task 2 behavior changes remain explicit opt-ins.
    WORKFLOW_AUTH_REQUIRED: bool = False
    WORKFLOW_CONCURRENCY_LIMIT: int = 1
    WORKFLOW_CELERY_BEAT: bool = False
    WORKFLOW_REDIS_LOCKING_ENABLED: bool = False

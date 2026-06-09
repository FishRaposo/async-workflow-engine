from shared_core.tasks import create_celery_app

from .config import AppConfig

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)


@celery_app.task
def sample_background_task(x: int, y: int) -> int:
    """A template background task."""
    return x + y

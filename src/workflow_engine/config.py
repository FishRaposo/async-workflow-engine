from shared_core.config import BaseAppConfig


class AppConfig(BaseAppConfig):
    """Project-specific configuration extending the shared core settings."""

    # Developers can declare project-specific config values here
    # Example:
    # CUSTOM_API_URL: str = "https://api.example.com"
    APP_NAME: str = "async-workflow-engine"

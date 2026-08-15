# Expose the vendored implementation to avoid duplicate code.
from workflow_engine.internal.vendor_core.errors import (
    application_error_handler,  # noqa: F401
)

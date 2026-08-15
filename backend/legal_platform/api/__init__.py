"""Platform API (tasks/014-api.md, module Gateway).

The Platform API exposes all platform capabilities through a stable, versioned
interface. It is the only public entry point for applications interacting with
the platform.

Business logic remains inside internal services. The API handles:
    - Authentication
    - Authorization
    - Input validation
    - Request routing
    - Response aggregation
    - Standardized errors
"""

from legal_platform.api.server import PlatformAPI, create_app
from legal_platform.api.models import (
    ApiResponse,
    ApiError,
    ErrorCategory,
    HealthStatus,
    PaginatedResponse,
)
from legal_platform.api.handlers import (
    AuthHandler,
    VaultHandler,
    DocumentHandler,
    UploadHandler,
    SearchHandler,
    AnswerHandler,
    AdminHandler,
    HealthHandler,
)

__all__ = [
    "PlatformAPI",
    "create_app",
    "ApiResponse",
    "ApiError",
    "ErrorCategory",
    "HealthStatus",
    "PaginatedResponse",
    "AuthHandler",
    "VaultHandler",
    "DocumentHandler",
    "UploadHandler",
    "SearchHandler",
    "AnswerHandler",
    "AdminHandler",
    "HealthHandler",
]
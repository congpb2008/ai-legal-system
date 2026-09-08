"""API response models (tasks/014-api.md).

Defines the standardized response format, error model, and health status
used by all Platform API endpoints.

Per the spec:
    - Every response includes: Request ID, Timestamp, Status, Payload,
      Optional Metadata, Optional Warnings
    - Errors follow a standardized schema: Error Code, Message, Category,
      Correlation ID, Retryable Indicator, Optional Details
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc


class ErrorCategory(str, Enum):
    """Error categories (tasks/014-api.md #ErrorModel)."""

    VALIDATION = "VALIDATION"           # Invalid input
    AUTHENTICATION = "AUTHENTICATION"    # Not authenticated
    AUTHORIZATION = "AUTHORIZATION"      # Not authorized
    NOT_FOUND = "NOT_FOUND"             # Resource not found
    CONFLICT = "CONFLICT"               # Resource conflict (e.g. duplicate)
    RATE_LIMITED = "RATE_LIMITED"       # Rate limit exceeded
    INTERNAL = "INTERNAL"               # Internal server error
    DEPENDENCY = "DEPENDENCY"           # Downstream service failure
    TIMEOUT = "TIMEOUT"                 # Request timeout


@dataclass
class ApiError:
    """A single error in the standardized error format.

    Fields:
        code: machine-readable error code (e.g. "VAULT_NOT_FOUND").
        message: human-readable error message.
        category: error category.
        correlation_id: request ID for tracing.
        retryable: whether the client may retry.
        details: optional additional error details (never internal stack traces).
    """

    code: str
    message: str
    category: ErrorCategory = ErrorCategory.INTERNAL
    correlation_id: Optional[str] = None
    retryable: bool = False
    details: Optional[dict[str, Any]] = None


@dataclass
class ApiResponse:
    """Standardized API response envelope.

    Fields:
        request_id: unique request identifier for tracing.
        timestamp: when the response was generated.
        status: HTTP status code.
        success: whether the request succeeded.
        data: response payload (None on error).
        err: error details (None on success).
        warnings: optional warning messages.
        metadata: optional response metadata.
    """

    request_id: str
    timestamp: str
    status: int
    success: bool
    data: Any = None
    err: Optional[ApiError] = None
    warnings: list[str] = field(default_factory=list)
    metadata: Optional[dict[str, Any]] = None

    @classmethod
    def ok(
        cls,
        data: Any = None,
        *,
        request_id: "str | None" = None,
        status: int = 200,
        warnings: "list[str] | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> ApiResponse:
        """Create a success response."""
        return cls(
            request_id=request_id or str(uuid4()),
            timestamp=now_utc().isoformat(),
            status=status,
            success=True,
            data=data,
            warnings=warnings or [],
            metadata=metadata,
        )

    @classmethod
    def err_response(
        cls,
        api_error: ApiError,
        *,
        request_id: "str | None" = None,
        status: "int | None" = None,
    ) -> ApiResponse:
        """Create an error response."""
        return cls(
            request_id=request_id or str(uuid4()),
            timestamp=now_utc().isoformat(),
            status=status or _category_status(api_error.category),
            success=False,
            err=api_error,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        result: dict[str, Any] = {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "success": self.success,
        }
        if self.data is not None:
            # Serialize PaginatedResponse to dict before JSON encoding
            if isinstance(self.data, PaginatedResponse):
                result["data"] = self.data.to_dict()
            else:
                result["data"] = self.data
        if self.err is not None:
            result["error"] = {
                "code": self.err.code,
                "message": self.err.message,
                "category": self.err.category.value,
                "correlation_id": self.err.correlation_id or self.request_id,
                "retryable": self.err.retryable,
            }
            if self.err.details:
                result["error"]["details"] = self.err.details
        if self.warnings:
            result["warnings"] = self.warnings
        if self.metadata:
            result["metadata"] = self.metadata
        return result


def _category_status(category: ErrorCategory) -> int:
    """Map an error category to an HTTP status code."""
    mapping = {
        ErrorCategory.VALIDATION: 400,
        ErrorCategory.AUTHENTICATION: 401,
        ErrorCategory.AUTHORIZATION: 403,
        ErrorCategory.NOT_FOUND: 404,
        ErrorCategory.CONFLICT: 409,
        ErrorCategory.RATE_LIMITED: 429,
        ErrorCategory.INTERNAL: 500,
        ErrorCategory.DEPENDENCY: 502,
        ErrorCategory.TIMEOUT: 504,
    }
    return mapping.get(category, 500)


@dataclass
class PaginatedResponse:
    """Pagination metadata for list endpoints.

    Fields:
        items: the page of results.
        total: total number of items across all pages.
        limit: maximum items per page.
        offset: zero-based offset of this page.
        has_more: whether there are more pages.
    """

    items: list[Any]
    total: int
    limit: int = 100
    offset: int = 0

    @property
    def has_more(self) -> bool:
        return (self.offset + self.limit) < self.total

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "items": self.items,
            "total": self.total,
            "limit": self.limit,
            "offset": self.offset,
            "has_more": self.has_more,
        }


@dataclass
class HealthStatus:
    """Health check response (tasks/014-api.md #HealthAPIs).

    Fields:
        status: overall health ("healthy", "degraded", "unhealthy").
        version: platform version.
        uptime_seconds: seconds since service start.
        checks: per-component health checks.
    """

    status: str = "healthy"
    version: str = "0.2.0"
    uptime_seconds: float = 0.0
    checks: dict[str, str] = field(default_factory=dict)
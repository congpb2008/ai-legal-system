"""Health check endpoints (tasks/014-api.md #HealthAPIs)."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from legal_platform import __version__
from legal_platform.api.handlers.common import _START_TIME
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory, HealthStatus
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.vector_index.service import VectorIndexService


class HealthHandler:
    """Health check endpoints (tasks/014-api.md #HealthAPIs)."""

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        *,
        storage: Any = None,
        vector_index: "VectorIndexService | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        worker_alive: Any = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.storage = storage
        self.vector_index = vector_index
        self.embedding = embedding_service
        self.worker_alive = worker_alive

    def _checks(self) -> dict[str, str]:
        checks: dict[str, str] = {}
        try:
            row = self.registry.repo.conn.execute("SELECT 1").fetchone()
            checks["database"] = "healthy" if row else "unhealthy: query returned no row"
        except Exception as exc:
            checks["database"] = f"unhealthy: {type(exc).__name__}"

        if self.storage is None:
            checks["storage"] = "not_checked"
        else:
            root = getattr(self.storage, "base_path", None)
            if root is not None and Path(root).is_dir() and os.access(root, os.R_OK | os.W_OK):
                checks["storage"] = "healthy"
            else:
                checks["storage"] = "unhealthy: configured root is unavailable"

        if self.vector_index is None:
            checks["index"] = "not_checked"
        else:
            try:
                count = len(self.vector_index.entries_snapshot())
                checks["index"] = f"healthy ({count} entries)"
            except Exception as exc:
                checks["index"] = f"unhealthy: {type(exc).__name__}"

        if self.worker_alive is None:
            checks["worker"] = "not_checked"
        else:
            checks["worker"] = "healthy" if self.worker_alive() else "unhealthy: stopped"

        if self.embedding is None:
            checks["embedding"] = "not_checked"
        else:
            model = getattr(self.embedding.engine, "MODEL_NAME", None)
            checks["embedding"] = f"configured ({model})" if model else "unhealthy: no model"

        from legal_platform.modules.generation.provider import is_configured
        checks["generation"] = "configured" if is_configured() else "not_configured"
        return checks

    def health(self) -> ApiResponse:
        """GET /health — overall health check."""
        checks = self._checks()
        status = HealthStatus(
            status=("degraded" if any(v.startswith("unhealthy") for v in checks.values()) else "healthy"),
            version=__version__,
            uptime_seconds=time.time() - _START_TIME,
            checks=checks,
        )
        return ApiResponse.ok(data={
            "status": status.status,
            "version": status.version,
            "uptime_seconds": round(status.uptime_seconds, 2),
            "checks": status.checks,
        })

    def ready(self) -> ApiResponse:
        """GET /ready — readiness check."""
        checks = self._checks()
        failures = {key: value for key, value in checks.items() if value.startswith("unhealthy")}
        if failures:
            return ApiResponse.err_response(
                ApiError(
                    code="NOT_READY",
                    message="One or more required runtime components are unavailable.",
                    category=ErrorCategory.DEPENDENCY,
                    retryable=True,
                    details={"checks": failures},
                ),
                status=503,
            )
        return ApiResponse.ok(data={"status": "ready", "checks": checks})

    def live(self) -> ApiResponse:
        """GET /live — liveness check."""
        return ApiResponse.ok(data={"status": "alive"})

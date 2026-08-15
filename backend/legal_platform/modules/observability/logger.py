"""Structured logger (tasks/016-observability.md #Logs).

Every service produces structured logs with minimum fields:
    Timestamp, Service, Module, Request ID, Job ID, Severity, Message, Metadata

Logs are machine-readable. Sensitive information is never logged.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso


_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}


@dataclass
class LogEntry:
    """A single structured log entry.

    Fields (per tasks/016 #Logs):
        timestamp: when the event occurred.
        service: the service name.
        module: the module within the service.
        request_id: correlation ID for the request.
        job_id: correlation ID for the job (if applicable).
        severity: DEBUG | INFO | WARN | ERROR.
        message: human-readable message.
        metadata: structured key-value data (never sensitive).
    """

    timestamp: str
    service: str
    module: str
    severity: str = "INFO"
    message: str = ""
    request_id: Optional[str] = None
    job_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "service": self.service,
            "module": self.module,
            "severity": self.severity,
            "message": self.message,
        }
        if self.request_id:
            d["request_id"] = self.request_id
        if self.job_id:
            d["job_id"] = self.job_id
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class StructuredLogger:
    """Structured logger that writes JSON log entries.

    Wraps Python's stdlib logging with structured output. Each log entry
    is a single line of JSON for machine readability.

    Usage::

        logger = StructuredLogger("document-registry", "registry")
        logger.info("Document created", document_id=str(doc_id))
        logger.error("Upload failed", metadata={"reason": str(e)})
    """

    def __init__(
        self,
        service: str,
        module: str,
        *,
        level: str = "INFO",
        output: "Any | None" = None,
    ):
        self.service = service
        self.module = module
        self._level = _LOG_LEVELS.get(level.upper(), 20)
        self._output = output or sys.stderr

    def _log(
        self,
        severity: str,
        message: str,
        *,
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        if _LOG_LEVELS.get(severity, 0) < self._level:
            return

        entry = LogEntry(
            timestamp=utc_iso(now_utc()),
            service=self.service,
            module=self.module,
            severity=severity,
            message=message,
            request_id=request_id,
            job_id=job_id,
            metadata=metadata or {},
        )
        print(entry.to_json(), file=self._output, flush=True)

    def debug(
        self,
        message: str,
        *,
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        self._log("DEBUG", message, request_id=request_id, job_id=job_id, metadata=metadata)

    def info(
        self,
        message: str,
        *,
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        self._log("INFO", message, request_id=request_id, job_id=job_id, metadata=metadata)

    def warn(
        self,
        message: str,
        *,
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        self._log("WARN", message, request_id=request_id, job_id=job_id, metadata=metadata)

    def error(
        self,
        message: str,
        *,
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        self._log("ERROR", message, request_id=request_id, job_id=job_id, metadata=metadata)


# Module-level loggers registry
_loggers: dict[str, StructuredLogger] = {}


def get_logger(service: str, module: str, **kwargs: Any) -> StructuredLogger:
    """Get or create a structured logger."""
    key = f"{service}.{module}"
    if key not in _loggers:
        _loggers[key] = StructuredLogger(service, module, **kwargs)
    return _loggers[key]
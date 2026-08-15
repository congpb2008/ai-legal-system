"""Distributed tracing (tasks/016-observability.md #Traces).

Long-running operations generate distributed traces. Each stage records:
    Start Time, End Time, Duration, Status, Errors

Trace IDs propagate across services. Traces never influence business logic.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc, utc_iso


@dataclass
class Span:
    """A single span within a trace.

    Fields:
        span_id: unique identifier for this span.
        parent_span_id: the parent span (None for root spans).
        operation: the operation being traced.
        service: the service that created this span.
        module: the module within the service.
        start_time: when the span started.
        end_time: when the span ended (None if still open).
        duration_ms: duration in milliseconds (None if still open).
        status: OK | ERROR.
        error: error message if status is ERROR.
        metadata: additional key-value data.
    """

    span_id: str
    parent_span_id: Optional[str] = None
    operation: str = ""
    service: str = ""
    module: str = ""
    start_time: str = field(default_factory=lambda: utc_iso(now_utc()))
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    status: str = "OK"
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, *, status: str = "OK", error: "str | None" = None) -> None:
        """Mark the span as finished."""
        self.end_time = utc_iso(now_utc())
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time)
        self.duration_ms = (end - start).total_seconds() * 1000
        self.status = status
        self.error = error


@dataclass
class TraceContext:
    """The context for a distributed trace.

    Fields:
        trace_id: unique identifier for the entire trace.
        root_span_id: the root span ID.
        current_span_id: the current active span.
    """

    trace_id: str
    root_span_id: str
    current_span_id: str


# Context variable for propagating trace context across async boundaries
_trace_context: ContextVar[Optional[TraceContext]] = ContextVar("trace_context", default=None)


class Tracer:
    """Distributed tracer.

    Creates and manages spans within a trace. Trace IDs propagate across
    services via TraceContext.

    Usage::

        tracer = Tracer("document-registry", "registry")
        with tracer.span("document.create") as span:
            # ... do work ...
            span.metadata["document_id"] = str(doc_id)
    """

    def __init__(self, service: str, module: str):
        self.service = service
        self.module = module
        self._spans: list[Span] = []

    def start_trace(self, operation: str) -> Span:
        """Start a new root trace.

        Returns:
            The root span.
        """
        trace_id = str(uuid4())
        span = Span(
            span_id=str(uuid4()),
            operation=operation,
            service=self.service,
            module=self.module,
        )
        self._spans.append(span)
        ctx = TraceContext(
            trace_id=trace_id,
            root_span_id=span.span_id,
            current_span_id=span.span_id,
        )
        _trace_context.set(ctx)
        return span

    def start_span(self, operation: str) -> Span:
        """Start a child span within the current trace.

        Returns:
            The child span, or a root span if no trace context exists.
        """
        ctx = _trace_context.get()
        if ctx is None:
            return self.start_trace(operation)

        span = Span(
            span_id=str(uuid4()),
            parent_span_id=ctx.current_span_id,
            operation=operation,
            service=self.service,
            module=self.module,
        )
        self._spans.append(span)
        ctx.current_span_id = span.span_id
        _trace_context.set(ctx)
        return span

    def span(self, operation: str):
        """Context manager for creating and finishing a span.

        Usage::

            with tracer.span("process.document") as span:
                span.metadata["doc_id"] = str(doc_id)
        """
        return _SpanContextManager(self, operation)

    def get_trace_context(self) -> Optional[TraceContext]:
        """Get the current trace context."""
        return _trace_context.get()

    def set_trace_context(self, ctx: TraceContext) -> None:
        """Set the trace context (for cross-service propagation)."""
        _trace_context.set(ctx)

    def get_spans(self, trace_id: "str | None" = None) -> list[Span]:
        """Get all spans, optionally filtered by trace."""
        return self._spans

    def get_trace_summary(self, trace_id: str) -> dict[str, Any]:
        """Get a summary of a trace."""
        spans = [s for s in self._spans]
        if not spans:
            return {"trace_id": trace_id, "spans": [], "total_duration_ms": 0}
        total = sum(s.duration_ms for s in spans if s.duration_ms is not None)
        return {
            "trace_id": trace_id,
            "span_count": len(spans),
            "total_duration_ms": round(total, 2),
            "spans": [
                {
                    "span_id": s.span_id,
                    "operation": s.operation,
                    "service": s.service,
                    "module": s.module,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                    "error": s.error,
                }
                for s in spans
            ],
        }


class _SpanContextManager:
    """Context manager for tracing spans."""

    def __init__(self, tracer: Tracer, operation: str):
        self._tracer = tracer
        self._operation = operation
        self._span: Optional[Span] = None

    def __enter__(self) -> Span:
        self._span = self._tracer.start_span(self._operation)
        return self._span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._span is not None:
            if exc_type is not None:
                self._span.finish(status="ERROR", error=str(exc_val))
            else:
                self._span.finish()


# Module-level tracers
_tracers: dict[str, Tracer] = {}


def get_tracer(service: str, module: str) -> Tracer:
    """Get or create a tracer."""
    key = f"{service}.{module}"
    if key not in _tracers:
        _tracers[key] = Tracer(service, module)
    return _tracers[key]
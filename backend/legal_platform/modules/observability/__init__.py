"""Observability Platform (tasks/016-observability.md, module Observability).

Provides visibility into the health, performance and correctness of the system.
Enables monitoring, debugging and continuous improvement.

Observability shall NOT affect business logic:
    - Executes no business logic
    - Modifies no data
    - Influences neither retrieval nor generation

Pillars (tasks/016 #ObservabilityPillars):
    - Logs
    - Metrics
    - Traces
    - Evaluations
"""

from legal_platform.modules.observability.logger import (
    StructuredLogger,
    get_logger,
    LogEntry,
)
from legal_platform.modules.observability.metrics import (
    MetricsCollector,
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricSnapshot,
)
from legal_platform.modules.observability.tracing import (
    Tracer,
    Span,
    TraceContext,
    get_tracer,
)
from legal_platform.modules.observability.jobs import (
    JobMonitor,
    JobStatus,
    JobRecord,
)
from legal_platform.modules.observability.alerts import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertRecord,
)
from legal_platform.modules.observability.service import ObservabilityService

__all__ = [
    "StructuredLogger",
    "get_logger",
    "LogEntry",
    "MetricsCollector",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "MetricSnapshot",
    "Tracer",
    "Span",
    "TraceContext",
    "get_tracer",
    "JobMonitor",
    "JobStatus",
    "JobRecord",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "AlertRecord",
    "ObservabilityService",
]
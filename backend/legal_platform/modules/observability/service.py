"""Observability Service (tasks/016-observability.md).

Orchestrates the four observability pillars:
    - Logs (StructuredLogger)
    - Metrics (MetricsCollector)
    - Traces (Tracer)
    - Evaluations (via metric snapshots + alert rules)

Plus job monitoring and alert management.

Observability never affects business logic.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from legal_platform.modules.observability.alerts import AlertManager, AlertRecord, AlertRule, AlertSeverity
from legal_platform.modules.observability.jobs import JobMonitor, JobRecord, JobStatus
from legal_platform.modules.observability.logger import StructuredLogger, get_logger
from legal_platform.modules.observability.metrics import MetricsCollector, get_metrics
from legal_platform.modules.observability.tracing import Tracer, Span, TraceContext, get_tracer
from legal_platform.storage.eventlog import init_audit_log, log_event


class ObservabilityService:
    """The Observability Service.

    Provides visibility into the health, performance and correctness of the
    system. Orchestrates logs, metrics, traces, job monitoring, alerts, and
    evaluation support.

    Observability shall NOT affect business logic:
        - Executes no business logic
        - Modifies no data
        - Influences neither retrieval nor generation
    """

    def __init__(
        self,
        logger: "StructuredLogger | None" = None,
        metrics: "MetricsCollector | None" = None,
        tracer: "Tracer | None" = None,
        job_monitor: "JobMonitor | None" = None,
        alert_manager: "AlertManager | None" = None,
    ):
        self.logger = logger or get_logger("observability", "service")
        self.metrics = metrics or get_metrics()
        self.tracer = tracer or get_tracer("observability", "service")
        self.jobs = job_monitor or JobMonitor()
        self.alerts = alert_manager or AlertManager()

        # Register default alert rules
        self._register_default_rules()

    # ------------------------------------------------------------------
    # Default alert rules
    # ------------------------------------------------------------------

    def _register_default_rules(self) -> None:
        """Register default alert rules (tasks/016 #Alerts)."""
        rules = [
            AlertRule(
                name="search_latency_warning",
                metric="retrieval.latency_ms",
                operator="gt",
                threshold=2000.0,
                severity=AlertSeverity.WARNING,
                message_template="Search latency {value}ms exceeds {threshold}ms threshold",
            ),
            AlertRule(
                name="search_latency_critical",
                metric="retrieval.latency_ms",
                operator="gt",
                threshold=5000.0,
                severity=AlertSeverity.CRITICAL,
                message_template="Search latency {value}ms exceeds critical {threshold}ms threshold",
            ),
            AlertRule(
                name="generation_latency_warning",
                metric="generation.latency_ms",
                operator="gt",
                threshold=5000.0,
                severity=AlertSeverity.WARNING,
                message_template="Generation latency {value}ms exceeds {threshold}ms threshold",
            ),
            AlertRule(
                name="generation_latency_critical",
                metric="generation.latency_ms",
                operator="gt",
                threshold=15000.0,
                severity=AlertSeverity.CRITICAL,
                message_template="Generation latency {value}ms exceeds critical {threshold}ms threshold",
            ),
            AlertRule(
                name="ocr_failure_rate",
                metric="ocr.failure_count",
                operator="gt",
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                message_template="OCR failure count {value} exceeds {threshold}",
            ),
            AlertRule(
                name="parser_failure_rate",
                metric="parser.failure_count",
                operator="gt",
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                message_template="Parser failure count {value} exceeds {threshold}",
            ),
            AlertRule(
                name="citation_coverage_low",
                metric="citation.coverage",
                operator="lt",
                threshold=0.5,
                severity=AlertSeverity.WARNING,
                message_template="Citation coverage {value} is below {threshold} threshold",
            ),
        ]
        for rule in rules:
            self.alerts.add_rule(rule)

    # ------------------------------------------------------------------
    # Logging convenience
    # ------------------------------------------------------------------

    def log(
        self,
        service: str,
        module: str,
        message: str,
        *,
        severity: str = "INFO",
        request_id: "str | None" = None,
        job_id: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> None:
        """Log a structured message."""
        logger = get_logger(service, module)
        if severity == "DEBUG":
            logger.debug(message, request_id=request_id, job_id=job_id, metadata=metadata)
        elif severity == "WARN":
            logger.warn(message, request_id=request_id, job_id=job_id, metadata=metadata)
        elif severity == "ERROR":
            logger.error(message, request_id=request_id, job_id=job_id, metadata=metadata)
        else:
            logger.info(message, request_id=request_id, job_id=job_id, metadata=metadata)

    # ------------------------------------------------------------------
    # Metric recording
    # ------------------------------------------------------------------

    def record_upload(self, size_bytes: int) -> None:
        """Record an upload event."""
        self.metrics.inc_counter("upload.count")
        self.metrics.observe_histogram("upload.size_bytes", float(size_bytes))

    def record_ocr_result(self, success: bool) -> None:
        """Record an OCR result."""
        self.metrics.inc_counter("ocr.total_count")
        if success:
            self.metrics.inc_counter("ocr.success_count")
        else:
            self.metrics.inc_counter("ocr.failure_count")

    def record_parser_result(self, success: bool) -> None:
        """Record a parser result."""
        self.metrics.inc_counter("parser.total_count")
        if success:
            self.metrics.inc_counter("parser.success_count")
        else:
            self.metrics.inc_counter("parser.failure_count")

    def record_retrieval_latency(self, latency_ms: float) -> None:
        """Record retrieval latency."""
        self.metrics.observe_histogram("retrieval.latency_ms", latency_ms)

    def record_generation_latency(self, latency_ms: float) -> None:
        """Record generation latency."""
        self.metrics.observe_histogram("generation.latency_ms", latency_ms)

    def record_api_latency(self, endpoint: str, latency_ms: float) -> None:
        """Record API endpoint latency."""
        self.metrics.observe_histogram("api.latency_ms", latency_ms, labels={"endpoint": endpoint})
        self.metrics.inc_counter("api.request_count", labels={"endpoint": endpoint})

    def record_citation_coverage(self, coverage: float) -> None:
        """Record citation coverage."""
        self.metrics.set_gauge("citation.coverage", coverage)

    def set_index_size(self, size: int) -> None:
        """Record index size."""
        self.metrics.set_gauge("index.size", float(size))

    # ------------------------------------------------------------------
    # Job tracking
    # ------------------------------------------------------------------

    def create_job(
        self,
        job_type: str,
        document_id: str,
        *,
        metadata: "dict[str, Any] | None" = None,
    ) -> JobRecord:
        """Create and return a new job record."""
        return self.jobs.create_job(job_type, document_id, metadata=metadata)

    def start_job(self, job_id: str) -> JobRecord:
        """Mark a job as started."""
        return self.jobs.start_job(job_id)

    def complete_job(self, job_id: str) -> JobRecord:
        """Mark a job as completed."""
        return self.jobs.complete_job(job_id)

    def fail_job(self, job_id: str, error: str) -> JobRecord:
        """Mark a job as failed."""
        return self.jobs.fail_job(job_id, error)

    # ------------------------------------------------------------------
    # Alert evaluation
    # ------------------------------------------------------------------

    def evaluate_alerts(self) -> list[AlertRecord]:
        """Evaluate all alert rules against current metrics.

        Returns:
            A list of newly fired alerts.
        """
        snapshot = self.metrics.to_dict()
        return self.alerts.evaluate_snapshot(snapshot)

    # ------------------------------------------------------------------
    # Snapshot / status
    # ------------------------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        """Get a comprehensive observability status snapshot."""
        metrics_snap = self.metrics.to_dict()
        fired = self.evaluate_alerts()
        recent_jobs = self.jobs.list_jobs(limit=10)

        return {
            "metrics": metrics_snap,
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "rule_name": a.rule_name,
                    "severity": a.severity.value,
                    "metric": a.metric,
                    "value": a.value,
                    "message": a.message,
                    "fired_at": a.fired_at,
                    "acknowledged": a.acknowledged,
                }
                for a in fired
            ],
            "recent_jobs": [
                {
                    "job_id": j.job_id,
                    "job_type": j.job_type,
                    "document_id": j.document_id,
                    "status": j.status.value if isinstance(j.status, JobStatus) else j.status,
                    "duration_ms": j.duration_ms,
                    "error": j.error,
                }
                for j in recent_jobs
            ],
        }
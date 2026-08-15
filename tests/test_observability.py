"""Tests for the Observability Platform (Task 016).

Covers:
    - Structured logging (structured logs, severity levels, metadata)
    - Metrics (counters, gauges, histograms, percentiles, snapshot)
    - Distributed tracing (spans, trace context, error tracking)
    - Job monitoring (create, start, complete, fail, cancel, list)
    - Alert management (rules, evaluation, firing, acknowledgment)
    - ObservabilityService integration (default rules, status snapshot)

The authoritative source is the Observability specification
(tasks/016-observability.md).
"""

import io
import json
from uuid import UUID

import pytest

from legal_platform.modules.observability.alerts import (
    AlertManager,
    AlertRecord,
    AlertRule,
    AlertSeverity,
)
from legal_platform.modules.observability.jobs import (
    JobMonitor,
    JobRecord,
    JobStatus,
)
from legal_platform.modules.observability.logger import (
    LogEntry,
    StructuredLogger,
    get_logger,
)
from legal_platform.modules.observability.metrics import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricsCollector,
    MetricSnapshot,
)
from legal_platform.modules.observability.service import ObservabilityService
from legal_platform.modules.observability.tracing import (
    Span,
    Tracer,
    TraceContext,
    get_tracer,
)


# ======================================================================
# 1. Structured Logger
# ======================================================================


class TestStructuredLogger:
    """Structured logging (tasks/016 #Logs)."""

    def test_log_entry_fields(self):
        entry = LogEntry(
            timestamp="2026-08-07T00:00:00Z",
            service="test-service",
            module="test-module",
            severity="INFO",
            message="Test message",
            request_id="req-1",
            job_id="job-1",
            metadata={"key": "value"},
        )
        assert entry.service == "test-service"
        assert entry.module == "test-module"
        assert entry.severity == "INFO"
        assert entry.request_id == "req-1"
        assert entry.job_id == "job-1"

    def test_log_entry_to_dict(self):
        entry = LogEntry(
            timestamp="2026-08-07T00:00:00Z",
            service="svc",
            module="mod",
            severity="INFO",
            message="hello",
            request_id="req-1",
        )
        d = entry.to_dict()
        assert d["service"] == "svc"
        assert d["module"] == "mod"
        assert d["request_id"] == "req-1"
        assert d["severity"] == "INFO"

    def test_log_entry_to_json(self):
        entry = LogEntry(
            timestamp="2026-08-07T00:00:00Z",
            service="svc",
            module="mod",
            severity="INFO",
            message="hello",
        )
        parsed = json.loads(entry.to_json())
        assert parsed["message"] == "hello"

    def test_logger_writes_json(self):
        buf = io.StringIO()
        logger = StructuredLogger("test", "module", output=buf)
        logger.info("Test message", request_id="req-1")
        buf.seek(0)
        line = buf.readline().strip()
        parsed = json.loads(line)
        assert parsed["service"] == "test"
        assert parsed["module"] == "module"
        assert parsed["severity"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["request_id"] == "req-1"

    def test_logger_levels(self):
        buf = io.StringIO()
        logger = StructuredLogger("test", "module", level="WARN", output=buf)
        logger.info("Should not appear")
        logger.warn("Should appear")
        buf.seek(0)
        content = buf.read()
        assert "Should not appear" not in content
        assert "Should appear" in content

    def test_logger_error_with_metadata(self):
        buf = io.StringIO()
        logger = StructuredLogger("test", "module", output=buf)
        logger.error("Failed", metadata={"reason": "timeout"})
        buf.seek(0)
        parsed = json.loads(buf.readline().strip())
        assert parsed["severity"] == "ERROR"
        assert parsed["metadata"]["reason"] == "timeout"

    def test_get_logger_singleton(self):
        l1 = get_logger("svc", "mod")
        l2 = get_logger("svc", "mod")
        assert l1 is l2


# ======================================================================
# 2. Metrics
# ======================================================================


class TestMetrics:
    """Metrics collection (tasks/016 #Metrics)."""

    def test_counter(self):
        mc = MetricsCollector()
        mc.inc_counter("upload.count")
        mc.inc_counter("upload.count")
        c = mc.counter("upload.count")
        assert c.value == 2

    def test_counter_with_labels(self):
        mc = MetricsCollector()
        mc.inc_counter("api.request_count", {"endpoint": "/v1/search"})
        mc.inc_counter("api.request_count", {"endpoint": "/v1/search"})
        c = mc.counter("api.request_count", {"endpoint": "/v1/search"})
        assert c.value == 2

    def test_gauge(self):
        mc = MetricsCollector()
        mc.set_gauge("index.size", 100)
        mc.set_gauge("index.size", 200)
        g = mc.gauge("index.size")
        assert g.value == 200

    def test_histogram(self):
        mc = MetricsCollector()
        for v in [10, 20, 30, 40, 50]:
            mc.observe_histogram("latency.ms", v)
        h = mc.histogram("latency.ms")
        assert h.count == 5
        assert h.sum == 150
        assert h.avg == 30
        assert h.min == 10
        assert h.max == 50

    def test_histogram_percentiles(self):
        h = HistogramMetric(name="latency.ms")
        for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            h.observe(v)
        # Median of 1..10 is 5.5 (average of 5 and 6)
        assert h.p50 == 5.5
        # 95th percentile of 10 values = 10th value (nearest-rank)
        assert h.p95 == 10
        assert h.p99 == 10

    def test_snapshot(self):
        mc = MetricsCollector()
        mc.inc_counter("test.count")
        mc.set_gauge("test.gauge", 5.0)
        mc.observe_histogram("test.hist", 10.0)
        snap = mc.snapshot()
        assert isinstance(snap, MetricSnapshot)
        assert "test.count" in snap.counters
        assert "test.gauge" in snap.gauges
        assert "test.hist" in snap.histograms

    def test_to_dict(self):
        mc = MetricsCollector()
        mc.inc_counter("upload.count")
        mc.set_gauge("index.size", 42)
        mc.observe_histogram("retrieval.latency_ms", 100.0)
        d = mc.to_dict()
        assert "counters" in d
        assert "gauges" in d
        assert "histograms" in d

    def test_empty_histogram_percentiles(self):
        h = HistogramMetric(name="empty")
        assert h.avg == 0.0
        assert h.p50 == 0.0
        assert h.p95 == 0.0
        assert h.p99 == 0.0


# ======================================================================
# 3. Distributed Tracing
# ======================================================================


class TestTracing:
    """Distributed traces (tasks/016 #Traces)."""

    def test_start_trace(self):
        tracer = Tracer("test", "module")
        span = tracer.start_trace("process.document")
        assert span.span_id is not None
        assert span.operation == "process.document"
        assert span.service == "test"
        assert span.status == "OK"

    def test_start_child_span(self):
        tracer = Tracer("test", "module")
        root = tracer.start_trace("process")
        child = tracer.start_span("substep")
        assert child.parent_span_id == root.span_id
        assert child.operation == "substep"

    def test_span_finish(self):
        tracer = Tracer("test", "module")
        span = tracer.start_trace("op")
        span.finish()
        assert span.status == "OK"
        assert span.end_time is not None
        assert span.duration_ms is not None

    def test_span_finish_error(self):
        tracer = Tracer("test", "module")
        span = tracer.start_trace("op")
        span.finish(status="ERROR", error="something broke")
        assert span.status == "ERROR"
        assert span.error == "something broke"

    def test_span_context_manager(self):
        tracer = Tracer("test", "module")
        with tracer.span("my_op") as span:
            span.metadata["key"] = "value"
        assert span.status == "OK"
        assert span.duration_ms is not None
        assert span.metadata["key"] == "value"

    def test_span_context_manager_error(self):
        tracer = Tracer("test", "module")
        with pytest.raises(RuntimeError):
            with tracer.span("failing_op"):
                raise RuntimeError("boom")
        # The span should be marked as errored
        spans = tracer.get_spans()
        failing = [s for s in spans if s.operation == "failing_op"]
        assert failing[0].status == "ERROR"
        assert "boom" in failing[0].error

    def test_trace_context(self):
        tracer = Tracer("test", "module")
        root = tracer.start_trace("op")
        ctx = tracer.get_trace_context()
        assert ctx is not None
        assert ctx.trace_id is not None
        assert ctx.root_span_id == root.span_id

    def test_get_tracer_singleton(self):
        t1 = get_tracer("svc", "mod")
        t2 = get_tracer("svc", "mod")
        assert t1 is t2


# ======================================================================
# 4. Job Monitoring
# ======================================================================


class TestJobMonitoring:
    """Job monitoring (tasks/016 #JobMonitoring)."""

    def test_create_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        assert job.job_id is not None
        assert job.job_type == "ocr"
        assert job.document_id == "doc-1"
        assert job.status == JobStatus.PENDING

    def test_get_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("parse", "doc-1")
        fetched = monitor.get_job(job.job_id)
        assert fetched is not None
        assert fetched.job_id == job.job_id

    def test_start_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        started = monitor.start_job(job.job_id)
        assert started.status == JobStatus.RUNNING
        assert started.started_at is not None

    def test_complete_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        monitor.start_job(job.job_id)
        completed = monitor.complete_job(job.job_id)
        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.duration_ms is not None

    def test_fail_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        monitor.start_job(job.job_id)
        failed = monitor.fail_job(job.job_id, "OCR engine unavailable")
        assert failed.status == JobStatus.FAILED
        assert failed.error == "OCR engine unavailable"

    def test_cancel_job(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        cancelled = monitor.cancel_job(job.job_id)
        assert cancelled.status == JobStatus.CANCELLED

    def test_list_jobs(self):
        monitor = JobMonitor()
        monitor.create_job("ocr", "doc-1")
        monitor.create_job("parse", "doc-2")
        jobs = monitor.list_jobs()
        assert len(jobs) >= 2

    def test_list_jobs_by_type(self):
        monitor = JobMonitor()
        monitor.create_job("ocr", "doc-1")
        monitor.create_job("parse", "doc-2")
        ocr_jobs = monitor.list_jobs(job_type="ocr")
        assert all(j.job_type == "ocr" for j in ocr_jobs)

    def test_list_jobs_by_status(self):
        monitor = JobMonitor()
        job = monitor.create_job("ocr", "doc-1")
        monitor.complete_job(job.job_id)
        completed = monitor.list_jobs(status=JobStatus.COMPLETED)
        assert all(j.status == JobStatus.COMPLETED for j in completed)

    def test_get_nonexistent_job(self):
        monitor = JobMonitor()
        assert monitor.get_job("nonexistent") is None

    def test_manage_nonexistent_job(self):
        monitor = JobMonitor()
        with pytest.raises(KeyError):
            monitor.start_job("nonexistent")


# ======================================================================
# 5. Alert Management
# ======================================================================


class TestAlerts:
    """Alert management (tasks/016 #Alerts)."""

    def test_add_rule(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        assert len(mgr.list_rules()) == 1

    def test_remove_rule(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        mgr.remove_rule("latency")
        assert len(mgr.list_rules()) == 0

    def test_evaluate_gt(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        fired = mgr.evaluate({"latency_ms": 150})
        assert len(fired) == 1
        assert fired[0].rule_name == "latency"
        assert fired[0].value == 150

    def test_evaluate_no_fire(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        fired = mgr.evaluate({"latency_ms": 50})
        assert len(fired) == 0

    def test_evaluate_lt(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="coverage", metric="coverage", operator="lt", threshold=0.5))
        fired = mgr.evaluate({"coverage": 0.3})
        assert len(fired) == 1

    def test_evaluate_multiple_rules(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="a", metric="x", operator="gt", threshold=10))
        mgr.add_rule(AlertRule(name="b", metric="y", operator="gt", threshold=10))
        fired = mgr.evaluate({"x": 20, "y": 5})
        assert len(fired) == 1
        assert fired[0].rule_name == "a"

    def test_alert_record_fields(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        fired = mgr.evaluate({"latency_ms": 150})
        record = fired[0]
        assert record.alert_id is not None
        assert record.severity == AlertSeverity.WARNING
        assert record.metric == "latency_ms"
        assert record.value == 150
        assert record.threshold == 100
        assert record.acknowledged is False

    def test_list_alerts(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        mgr.evaluate({"latency_ms": 150})
        alerts = mgr.list_alerts()
        assert len(alerts) == 1

    def test_acknowledge_alert(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="latency_ms", operator="gt", threshold=100))
        fired = mgr.evaluate({"latency_ms": 150})
        assert mgr.acknowledge(fired[0].alert_id) is True
        alerts = mgr.list_alerts()
        assert alerts[0].acknowledged is True

    def test_evaluate_snapshot(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="latency", metric="retrieval.latency_ms", operator="gt", threshold=100))
        snapshot = {
            "counters": {"upload.count": {"value": 5}},
            "gauges": {},
            "histograms": {"retrieval.latency_ms": {"avg": 150}},
        }
        fired = mgr.evaluate_snapshot(snapshot)
        assert len(fired) == 1


# ======================================================================
# 6. Observability Service
# ======================================================================


class TestObservabilityService:
    """ObservabilityService integration."""

    def test_init_registers_default_rules(self):
        svc = ObservabilityService()
        assert len(svc.alerts.list_rules()) >= 7

    def test_record_upload(self):
        svc = ObservabilityService()
        svc.record_upload(1024)
        c = svc.metrics.counter("upload.count")
        assert c.value == 1

    def test_record_ocr_success(self):
        svc = ObservabilityService()
        svc.record_ocr_result(True)
        assert svc.metrics.counter("ocr.total_count").value == 1
        assert svc.metrics.counter("ocr.success_count").value == 1

    def test_record_ocr_failure(self):
        svc = ObservabilityService()
        svc.record_ocr_result(False)
        assert svc.metrics.counter("ocr.failure_count").value == 1

    def test_record_retrieval_latency(self):
        svc = ObservabilityService()
        svc.record_retrieval_latency(100.0)
        h = svc.metrics.histogram("retrieval.latency_ms")
        assert h.count == 1

    def test_record_generation_latency(self):
        svc = ObservabilityService()
        svc.record_generation_latency(500.0)
        h = svc.metrics.histogram("generation.latency_ms")
        assert h.count == 1

    def test_record_api_latency(self):
        svc = ObservabilityService()
        svc.record_api_latency("/v1/search", 50.0)
        c = svc.metrics.counter("api.request_count", {"endpoint": "/v1/search"})
        assert c.value == 1

    def test_record_citation_coverage(self):
        svc = ObservabilityService()
        svc.record_citation_coverage(0.8)
        g = svc.metrics.gauge("citation.coverage")
        assert g.value == 0.8

    def test_set_index_size(self):
        svc = ObservabilityService()
        svc.set_index_size(1000)
        g = svc.metrics.gauge("index.size")
        assert g.value == 1000

    def test_create_and_complete_job(self):
        svc = ObservabilityService()
        job = svc.create_job("ocr", "doc-1")
        svc.start_job(job.job_id)
        completed = svc.complete_job(job.job_id)
        assert completed.status == JobStatus.COMPLETED

    def test_fail_job(self):
        svc = ObservabilityService()
        job = svc.create_job("parse", "doc-1")
        svc.start_job(job.job_id)
        failed = svc.fail_job(job.job_id, "validation failed")
        assert failed.status == JobStatus.FAILED

    def test_evaluate_alerts(self):
        svc = ObservabilityService()
        svc.record_retrieval_latency(6000.0)  # exceeds critical threshold
        fired = svc.evaluate_alerts()
        assert len(fired) >= 1

    def test_get_status(self):
        svc = ObservabilityService()
        svc.record_upload(1024)
        status = svc.get_status()
        assert "metrics" in status
        assert "alerts" in status
        assert "recent_jobs" in status

    def test_log_method(self):
        svc = ObservabilityService()
        # Should not raise
        svc.log("test-service", "test-module", "Hello world", severity="INFO")


# ======================================================================
# 7. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_empty_metrics_snapshot(self):
        mc = MetricsCollector()
        snap = mc.snapshot()
        assert snap.counters == {}
        assert snap.gauges == {}
        assert snap.histograms == {}

    def test_alert_rule_unknown_metric(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="x", metric="nonexistent", operator="gt", threshold=1))
        fired = mgr.evaluate({"other": 100})
        assert len(fired) == 0

    def test_alert_operators(self):
        mgr = AlertManager()
        mgr.add_rule(AlertRule(name="gte", metric="m", operator="gte", threshold=10))
        mgr.add_rule(AlertRule(name="lte", metric="n", operator="lte", threshold=10))
        mgr.add_rule(AlertRule(name="eq", metric="o", operator="eq", threshold=5))
        fired = mgr.evaluate({"m": 10, "n": 10, "o": 5})
        assert len(fired) == 3

    def test_job_with_metadata(self):
        monitor = JobMonitor()
        job = monitor.create_job("embed", "doc-1", metadata={"model": "v1"})
        assert job.metadata["model"] == "v1"
        fetched = monitor.get_job(job.job_id)
        assert fetched.metadata["model"] == "v1"

    def test_span_without_parent(self):
        tracer = Tracer("test", "module")
        span = tracer.start_trace("root")
        assert span.parent_span_id is None
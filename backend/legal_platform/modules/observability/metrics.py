"""Metrics collector (tasks/016-observability.md #Metrics).

The platform exposes metrics including:
    Upload Count, OCR Success Rate, Parser Success Rate, KT Build Time,
    Chunk Count, Embedding Throughput, Index Size, Retrieval Latency,
    Generation Latency, Citation Coverage, API Latency

Metrics support historical analysis. They never influence business logic.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso


@dataclass
class CounterMetric:
    """A monotonically increasing counter.

    Fields:
        name: metric name.
        value: current counter value.
        labels: key-value dimensions for filtering.
        created_at: when the counter was created.
        updated_at: when the counter was last incremented.
    """

    name: str
    value: int = 0
    labels: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    updated_at: str = field(default_factory=lambda: utc_iso(now_utc()))


@dataclass
class GaugeMetric:
    """A point-in-time measurement.

    Fields:
        name: metric name.
        value: current gauge value.
        labels: key-value dimensions for filtering.
        created_at: when the gauge was created.
        updated_at: when the gauge was last set.
    """

    name: str
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    updated_at: str = field(default_factory=lambda: utc_iso(now_utc()))


@dataclass
class HistogramMetric:
    """A distribution of values over time.

    Fields:
        name: metric name.
        values: all recorded values.
        count: number of observations.
        sum: sum of all values.
        min: minimum value observed.
        max: maximum value observed.
        labels: key-value dimensions for filtering.
        created_at: when the histogram was created.
        updated_at: when the histogram was last updated.
    """

    name: str
    values: list[float] = field(default_factory=list)
    count: int = 0
    sum: float = 0.0
    min: float = float("inf")
    max: float = float("-inf")
    labels: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    updated_at: str = field(default_factory=lambda: utc_iso(now_utc()))

    def observe(self, value: float) -> None:
        """Record an observation."""
        self.values.append(value)
        self.count += 1
        self.sum += value
        if value < self.min:
            self.min = value
        if value > self.max:
            self.max = value
        self.updated_at = utc_iso(now_utc())

    @property
    def avg(self) -> float:
        """Mean of observed values."""
        return self.sum / self.count if self.count > 0 else 0.0

    @property
    def p50(self) -> float:
        """Median (50th percentile)."""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        n = len(sorted_vals)
        if n % 2 == 1:
            return sorted_vals[n // 2]
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    @property
    def p95(self) -> float:
        """95th percentile (nearest-rank)."""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = max(0, min(len(sorted_vals) - 1, int(math.ceil(0.95 * len(sorted_vals))) - 1))
        return sorted_vals[idx]

    @property
    def p99(self) -> float:
        """99th percentile (nearest-rank)."""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = max(0, min(len(sorted_vals) - 1, int(math.ceil(0.99 * len(sorted_vals))) - 1))
        return sorted_vals[idx]


@dataclass
class MetricSnapshot:
    """A snapshot of all metrics at a point in time.

    Fields:
        timestamp: when the snapshot was taken.
        counters: all counter metrics.
        gauges: all gauge metrics.
        histograms: all histogram metrics.
    """

    timestamp: str
    counters: dict[str, CounterMetric] = field(default_factory=dict)
    gauges: dict[str, GaugeMetric] = field(default_factory=dict)
    histograms: dict[str, HistogramMetric] = field(default_factory=dict)


class MetricsCollector:
    """Collects and exposes platform metrics.

    Thread-safe. Metrics never influence business logic.

    Usage::

        metrics = MetricsCollector()
        metrics.counter("upload.count", {"type": "pdf"}).inc()
        metrics.gauge("index.size", {}).set(1234)
        metrics.histogram("retrieval.latency_ms", {}).observe(45.2)
    """

    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, CounterMetric] = {}
        self._gauges: dict[str, GaugeMetric] = {}
        self._histograms: dict[str, HistogramMetric] = {}

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    def counter(self, name: str, labels: "dict[str, str] | None" = None) -> CounterMetric:
        """Get or create a counter metric."""
        key = self._key(name, labels)
        with self._lock:
            if key not in self._counters:
                self._counters[key] = CounterMetric(name=name, labels=labels or {})
            return self._counters[key]

    def inc_counter(self, name: str, labels: "dict[str, str] | None" = None, value: int = 1) -> None:
        """Increment a counter."""
        c = self.counter(name, labels)
        with self._lock:
            c.value += value
            c.updated_at = utc_iso(now_utc())

    # ------------------------------------------------------------------
    # Gauges
    # ------------------------------------------------------------------

    def gauge(self, name: str, labels: "dict[str, str] | None" = None) -> GaugeMetric:
        """Get or create a gauge metric."""
        key = self._key(name, labels)
        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(name=name, labels=labels or {})
            return self._gauges[key]

    def set_gauge(self, name: str, value: float, labels: "dict[str, str] | None" = None) -> None:
        """Set a gauge value."""
        g = self.gauge(name, labels)
        with self._lock:
            g.value = value
            g.updated_at = utc_iso(now_utc())

    # ------------------------------------------------------------------
    # Histograms
    # ------------------------------------------------------------------

    def histogram(self, name: str, labels: "dict[str, str] | None" = None) -> HistogramMetric:
        """Get or create a histogram metric."""
        key = self._key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = HistogramMetric(name=name, labels=labels or {})
            return self._histograms[key]

    def observe_histogram(self, name: str, value: float, labels: "dict[str, str] | None" = None) -> None:
        """Record an observation in a histogram."""
        h = self.histogram(name, labels)
        with self._lock:
            h.observe(value)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self) -> MetricSnapshot:
        """Take a point-in-time snapshot of all metrics."""
        with self._lock:
            return MetricSnapshot(
                timestamp=utc_iso(now_utc()),
                counters=dict(self._counters),
                gauges=dict(self._gauges),
                histograms=dict(self._histograms),
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize all metrics to a JSON-compatible dict."""
        snap = self.snapshot()
        return {
            "timestamp": snap.timestamp,
            "counters": {
                k: {"value": c.value, "labels": c.labels}
                for k, c in snap.counters.items()
            },
            "gauges": {
                k: {"value": g.value, "labels": g.labels}
                for k, g in snap.gauges.items()
            },
            "histograms": {
                k: {
                    "name": h.name,
                    "count": h.count,
                    "sum": round(h.sum, 2),
                    "avg": round(h.avg, 2),
                    "min": round(h.min, 2) if h.count > 0 else 0,
                    "max": round(h.max, 2) if h.count > 0 else 0,
                    "p50": round(h.p50, 2),
                    "p95": round(h.p95, 2),
                    "p99": round(h.p99, 2),
                    "labels": h.labels,
                }
                for k, h in snap.histograms.items()
            },
        }

    @staticmethod
    def _key(name: str, labels: "dict[str, str] | None") -> str:
        """Generate a unique key for a metric name + labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"


# Singleton
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics
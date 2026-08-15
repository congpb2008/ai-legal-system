"""Alert manager (tasks/016-observability.md #Alerts).

Triggers alerts based on metric thresholds. Alert examples:
    - OCR failure rate exceeds threshold
    - Parser validation failures increase
    - Embedding queue backlog
    - Search latency exceeds SLA
    - Generation timeout
    - Citation validation failures

Alert routing is implementation-specific. Alerts never affect business logic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.storage.db import in_memory


class AlertSeverity(str, Enum):
    """Severity of an alert.

    - INFO: informational.
    - WARNING: potential problem.
    - CRITICAL: requires immediate attention.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class AlertRule:
    """A rule that triggers an alert when a condition is met.

    Fields:
        name: unique rule name.
        metric: the metric name to evaluate.
        operator: comparison operator (gt, lt, gte, lte, eq).
        threshold: the threshold value.
        severity: severity of the triggered alert.
        message_template: template for the alert message.
    """

    name: str
    metric: str
    operator: str = "gt"  # gt, lt, gte, lte, eq
    threshold: float = 0.0
    severity: AlertSeverity = AlertSeverity.WARNING
    message_template: str = "{metric} = {value} (threshold {threshold})"


@dataclass
class AlertRecord:
    """A fired alert.

    Fields:
        alert_id: unique identifier for this alert.
        rule_name: the rule that triggered this alert.
        severity: alert severity.
        metric: the metric that triggered the alert.
        value: the metric value at trigger time.
        threshold: the configured threshold.
        message: human-readable alert message.
        fired_at: when the alert fired.
        acknowledged: whether the alert has been acknowledged.
    """

    alert_id: str
    rule_name: str
    severity: AlertSeverity
    metric: str
    value: float
    threshold: float
    message: str
    fired_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    acknowledged: bool = False


_ALERT_SCHEMA = """
CREATE TABLE IF NOT EXISTS observability_alerts (
    alert_id       TEXT PRIMARY KEY,
    rule_name      TEXT NOT NULL,
    severity       TEXT NOT NULL,
    metric         TEXT NOT NULL,
    value          REAL NOT NULL,
    threshold      REAL NOT NULL,
    message        TEXT NOT NULL,
    fired_at       TEXT NOT NULL,
    acknowledged   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_obs_alerts_rule ON observability_alerts(rule_name);
CREATE INDEX IF NOT EXISTS idx_obs_alerts_sev  ON observability_alerts(severity);
"""


class AlertManager:
    """Evaluates alert rules against metric values and fires alerts.

    Usage::

        alerts = AlertManager()
        alerts.add_rule(AlertRule(
            name="search_latency_sla",
            metric="retrieval.latency_ms",
            operator="gt",
            threshold=1000,
            severity=AlertSeverity.WARNING,
        ))
        fired = alerts.evaluate({"retrieval.latency_ms": 1500})
    """

    def __init__(self, conn: "sqlite3.Connection | None" = None):
        self._conn = conn or in_memory()
        self._conn.executescript(_ALERT_SCHEMA)
        self._conn.commit()
        self._rules: dict[str, AlertRule] = {}

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def add_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> None:
        """Remove an alert rule."""
        self._rules.pop(name, None)

    def list_rules(self) -> list[AlertRule]:
        """List all registered rules."""
        return list(self._rules.values())

    def evaluate(self, metric_values: dict[str, float]) -> list[AlertRecord]:
        """Evaluate all rules against metric values.

        Args:
            metric_values: a mapping of metric name -> value.

        Returns:
            A list of fired AlertRecords.
        """
        fired: list[AlertRecord] = []
        for rule in self._rules.values():
            if rule.metric not in metric_values:
                continue
            value = metric_values[rule.metric]
            if self._condition_met(rule.operator, value, rule.threshold):
                record = self._fire(rule, value)
                fired.append(record)
        return fired

    def evaluate_snapshot(self, metrics: dict[str, Any]) -> list[AlertRecord]:
        """Evaluate rules against a metrics snapshot.

        Extracts scalar values from the snapshot (counters, gauges, histogram avgs).

        Args:
            metrics: the metrics snapshot dict (from MetricsCollector.to_dict()).

        Returns:
            A list of fired AlertRecords.
        """
        values: dict[str, float] = {}
        for name, c in metrics.get("counters", {}).items():
            values[name] = float(c.get("value", 0))
        for name, g in metrics.get("gauges", {}).items():
            values[name] = float(g.get("value", 0))
        for name, h in metrics.get("histograms", {}).items():
            # Use the histogram's own name attribute (strip label suffix)
            base_name = h.get("name", name)
            values[base_name] = float(h.get("avg", 0))
            values[f"{base_name}_avg"] = float(h.get("avg", 0))
            values[f"{base_name}_p95"] = float(h.get("p95", 0))
        return self.evaluate(values)

    def list_alerts(
        self,
        *,
        severity: "AlertSeverity | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AlertRecord]:
        """List fired alerts."""
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if severity is not None:
            clauses.append("severity = :severity")
            params["severity"] = severity.value if isinstance(severity, AlertSeverity) else severity
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM observability_alerts{where} ORDER BY fired_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return [self._row_to_alert(r) for r in rows]

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an alert (marks it as handled)."""
        cur = self._conn.execute(
            "UPDATE observability_alerts SET acknowledged = 1 WHERE alert_id = ?",
            (alert_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _condition_met(self, operator: str, value: float, threshold: float) -> bool:
        if operator == "gt":
            return value > threshold
        if operator == "lt":
            return value < threshold
        if operator == "gte":
            return value >= threshold
        if operator == "lte":
            return value <= threshold
        if operator == "eq":
            return abs(value - threshold) < 1e-9
        return False

    def _fire(self, rule: AlertRule, value: float) -> AlertRecord:
        import uuid
        record = AlertRecord(
            alert_id=str(uuid.uuid4()),
            rule_name=rule.name,
            severity=rule.severity,
            metric=rule.metric,
            value=value,
            threshold=rule.threshold,
            message=rule.message_template.format(
                metric=rule.metric, value=value, threshold=rule.threshold
            ),
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO observability_alerts
                    (alert_id, rule_name, severity, metric, value, threshold,
                     message, fired_at, acknowledged)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    record.alert_id,
                    record.rule_name,
                    record.severity.value,
                    record.metric,
                    record.value,
                    record.threshold,
                    record.message,
                    record.fired_at,
                ),
            )
        return record

    def _row_to_alert(self, row: sqlite3.Row) -> AlertRecord:
        return AlertRecord(
            alert_id=row["alert_id"],
            rule_name=row["rule_name"],
            severity=AlertSeverity(row["severity"]),
            metric=row["metric"],
            value=row["value"],
            threshold=row["threshold"],
            message=row["message"],
            fired_at=row["fired_at"],
            acknowledged=bool(row["acknowledged"]),
        )
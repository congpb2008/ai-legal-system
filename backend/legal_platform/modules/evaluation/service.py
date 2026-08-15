"""Evaluation Service (tasks/017-evaluation.md).

Orchestrates benchmark execution, metric collection, report generation,
and regression detection. Evaluation never modifies production data.
"""

from __future__ import annotations

import json
import sqlite3
import time
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.modules.evaluation.models import (
    BenchmarkCase,
    BenchmarkSuite,
    CaseCategory,
    CaseDifficulty,
    Dataset,
    DatasetType,
    EvaluationMetric,
    EvaluationReport,
    EvaluationResult,
    FailureCategory,
    MetricValue,
    RegressionResult,
)
from legal_platform.modules.evaluation.runner import (
    CitationEvaluator,
    EvaluationRunner,
    GenerationEvaluator,
    ParserEvaluator,
    PipelineEvaluator,
    RetrievalEvaluator,
)
from legal_platform.storage.db import in_memory
from legal_platform.storage.eventlog import init_audit_log, log_event


_EVAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_reports (
    report_id       TEXT PRIMARY KEY,
    suite_name      TEXT NOT NULL,
    dataset_name    TEXT NOT NULL,
    system_version  TEXT NOT NULL,
    executed_at     TEXT NOT NULL,
    total_cases     INTEGER NOT NULL,
    passed_cases    INTEGER NOT NULL,
    failed_cases    INTEGER NOT NULL,
    pass_rate       REAL NOT NULL,
    execution_time_ms REAL NOT NULL,
    report_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_reports_suite ON evaluation_reports(suite_name);
CREATE INDEX IF NOT EXISTS idx_eval_reports_date ON evaluation_reports(executed_at);
"""


class EvaluationService:
    """The Evaluation Service.

    Measures the quality, correctness and performance of the platform.
    Evaluation is independent from production traffic and never modifies
    production data.

    Orchestrates:
        - Benchmark suite execution
        - Metric collection
        - Report generation
        - Regression detection
        - Historical tracking
    """

    def __init__(
        self,
        runner: "EvaluationRunner | None" = None,
        conn: "sqlite3.Connection | None" = None,
    ):
        self.runner = runner or EvaluationRunner()
        self._conn = conn or in_memory()
        self._conn.executescript(_EVAL_SCHEMA)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # ------------------------------------------------------------------
    # Run evaluation
    # ------------------------------------------------------------------

    def run_evaluation(
        self,
        dataset: Dataset,
        *,
        components: "list[str] | None" = None,
    ) -> EvaluationReport:
        """Run evaluation on a dataset.

        Args:
            dataset: the dataset to evaluate.
            components: which components to evaluate.

        Returns:
            An EvaluationReport.
        """
        start = time.time()

        report = self.runner.run_dataset(dataset, components=components)

        report.execution_time_ms = round((time.time() - start) * 1000, 2)

        # Persist
        self._persist_report(report)

        return report

    # ------------------------------------------------------------------
    # Report management
    # ------------------------------------------------------------------

    def get_report(self, report_id: str) -> Optional[EvaluationReport]:
        """Retrieve a stored evaluation report."""
        row = self._conn.execute(
            "SELECT report_json FROM evaluation_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        if row is None:
            return None
        return self._report_from_json(row["report_json"])

    def list_reports(
        self,
        *,
        suite_name: "str | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvaluationReport]:
        """List evaluation reports."""
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if suite_name is not None:
            clauses.append("suite_name = :suite_name")
            params["suite_name"] = suite_name
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT report_json FROM evaluation_reports{where} "
            f"ORDER BY executed_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return [self._report_from_json(r["report_json"]) for r in rows]

    def delete_report(self, report_id: str) -> bool:
        """Delete a stored evaluation report."""
        cur = self._conn.execute(
            "DELETE FROM evaluation_reports WHERE report_id = ?",
            (report_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Regression detection
    # ------------------------------------------------------------------

    def compare_reports(
        self,
        current_report_id: str,
        baseline_report_id: str,
        *,
        threshold: float = 0.05,
    ) -> RegressionResult:
        """Compare two evaluation reports and detect regressions.

        Args:
            current_report_id: the current evaluation report ID.
            baseline_report_id: the baseline evaluation report ID.
            threshold: minimum change to consider a regression.

        Returns:
            A RegressionResult.
        """
        current = self.get_report(current_report_id)
        baseline = self.get_report(baseline_report_id)

        if current is None:
            raise KeyError(f"Current report {current_report_id} not found")
        if baseline is None:
            raise KeyError(f"Baseline report {baseline_report_id} not found")

        return self.runner.detect_regressions(current, baseline, threshold=threshold)

    # ------------------------------------------------------------------
    # Convenience: create sample datasets
    # ------------------------------------------------------------------

    @staticmethod
    def create_sample_dataset(
        *,
        name: str = "Sample Dataset",
        dataset_type: "str | DatasetType" = DatasetType.UNIT,
        count: int = 3,
    ) -> Dataset:
        """Create a sample dataset for testing.

        Args:
            name: dataset name.
            dataset_type: dataset type.
            count: number of benchmark cases.

        Returns:
            A Dataset with sample cases.
        """
        if isinstance(dataset_type, str):
            dataset_type = DatasetType(dataset_type.upper())

        import uuid
        cases = [
            BenchmarkCase(
                id=f"sample-{i}",
                title=f"Sample case {i}",
                category=CaseCategory.FACT_LOOKUP,
                difficulty=CaseDifficulty.MEDIUM,
                question=f"Câu hỏi mẫu số {i}",
                expected_documents=["doc-1"],
                expected_nodes=["node-1"],
                expected_citations=[
                    {"document": "doc-1", "reference": "Điều 1"},
                ],
            )
            for i in range(count)
        ]

        return Dataset(
            id=f"ds-{uuid.uuid4().hex[:8]}",
            name=name,
            dataset_type=dataset_type,
            cases=cases,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_report(self, report: EvaluationReport) -> None:
        """Persist an evaluation report."""
        import dataclasses
        import json as _json

        def _serialize(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj):
                return {f.name: _serialize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            return obj

        report_json = _json.dumps(_serialize(report), ensure_ascii=False)

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO evaluation_reports
                    (report_id, suite_name, dataset_name, system_version,
                     executed_at, total_cases, passed_cases, failed_cases,
                     pass_rate, execution_time_ms, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.suite_name,
                    report.dataset_name,
                    report.system_version,
                    report.executed_at,
                    report.total_cases,
                    report.passed_cases,
                    report.failed_cases,
                    report.pass_rate,
                    report.execution_time_ms,
                    report_json,
                ),
            )

    @staticmethod
    def _report_from_json(json_str: str) -> EvaluationReport:
        """Reconstruct an EvaluationReport from JSON."""
        import dataclasses
        import json as _json
        from datetime import datetime

        data = _json.loads(json_str)

        def _deserialize(obj: Any, target_type: Any) -> Any:
            if target_type == EvaluationReport:
                return EvaluationReport(
                    report_id=obj["report_id"],
                    suite_name=obj.get("suite_name", ""),
                    dataset_name=obj.get("dataset_name", ""),
                    system_version=obj.get("system_version", "0.1.0"),
                    executed_at=obj.get("executed_at", ""),
                    total_cases=obj.get("total_cases", 0),
                    passed_cases=obj.get("passed_cases", 0),
                    failed_cases=obj.get("failed_cases", 0),
                    component_metrics=[
                        _deserialize(m, EvaluationMetric)
                        for m in obj.get("component_metrics", [])
                    ],
                    results=[
                        _deserialize(r, EvaluationResult)
                        for r in obj.get("results", [])
                    ],
                    execution_time_ms=obj.get("execution_time_ms", 0.0),
                    metadata=obj.get("metadata", {}),
                )
            if target_type == EvaluationMetric:
                from legal_platform.modules.evaluation.models import EvaluationMetric as EM
                return EM(
                    component=obj.get("component", ""),
                    metrics=[_deserialize(m, MetricValue) for m in obj.get("metrics", [])],
                )
            if target_type == MetricValue:
                from legal_platform.modules.evaluation.models import MetricValue as MV
                return MV(
                    name=obj.get("name", ""),
                    value=obj.get("value", 0.0),
                    unit=obj.get("unit", ""),
                    description=obj.get("description", ""),
                )
            if target_type == EvaluationResult:
                from legal_platform.modules.evaluation.models import EvaluationResult as ER
                return ER(
                    case_id=obj.get("case_id", ""),
                    passed=obj.get("passed", True),
                    retrieval_metrics=_deserialize(obj["retrieval_metrics"], EvaluationMetric) if obj.get("retrieval_metrics") else None,
                    citation_metrics=_deserialize(obj["citation_metrics"], EvaluationMetric) if obj.get("citation_metrics") else None,
                    generation_metrics=_deserialize(obj["generation_metrics"], EvaluationMetric) if obj.get("generation_metrics") else None,
                    failure_category=FailureCategory(obj["failure_category"]) if obj.get("failure_category") else None,
                    failure_detail=obj.get("failure_detail"),
                    execution_time_ms=obj.get("execution_time_ms", 0.0),
                    warnings=obj.get("warnings", []),
                )
            return obj

        return _deserialize(data, EvaluationReport)
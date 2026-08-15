"""Evaluation domain models (tasks/017-evaluation.md, benchmark-dataset-spec.md).

Defines the benchmark hierarchy:
    Benchmark Suite → Dataset → Benchmark Case → Evaluation Result

Plus metrics, reports, and regression analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from legal_platform.contracts.common import now_utc, utc_iso


class DatasetType(str, Enum):
    """Types of benchmark datasets (benchmark-dataset-spec.md #DatasetTypes).

    - UNIT: small, focused tests for a single component.
    - COMPONENT: tests for a specific module.
    - REGRESSION: broad tests for regression detection.
    - RELEASE: pre-release validation.
    - PRODUCTION_REPLAY: replayed production traffic.
    - RESEARCH: experimental datasets.
    """

    UNIT = "UNIT"
    COMPONENT = "COMPONENT"
    REGRESSION = "REGRESSION"
    RELEASE = "RELEASE"
    PRODUCTION_REPLAY = "PRODUCTION_REPLAY"
    RESEARCH = "RESEARCH"


class CaseDifficulty(str, Enum):
    """Difficulty levels (benchmark-dataset-spec.md #DifficultyLevels)."""

    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class CaseCategory(str, Enum):
    """Question categories (benchmark-dataset-spec.md #Categories)."""

    DEFINITION = "DEFINITION"
    REQUIREMENT = "REQUIREMENT"
    PROCEDURE = "PROCEDURE"
    EXCEPTION = "EXCEPTION"
    COMPARISON = "COMPARISON"
    THRESHOLD = "THRESHOLD"
    RESPONSIBILITY = "RESPONSIBILITY"
    PENALTY = "PENALTY"
    NAVIGATION = "NAVIGATION"
    CROSS_DOCUMENT = "CROSS_DOCUMENT"
    FACT_LOOKUP = "FACT_LOOKUP"
    SUMMARY = "SUMMARY"
    CALCULATION = "CALCULATION"


class FailureCategory(str, Enum):
    """Failure categories (benchmark-dataset-spec.md #FailureCategories)."""

    WRONG_RETRIEVAL = "WRONG_RETRIEVAL"
    WRONG_RANKING = "WRONG_RANKING"
    WRONG_CITATION = "WRONG_CITATION"
    WRONG_GENERATION = "WRONG_GENERATION"
    PARSER_ERROR = "PARSER_ERROR"
    HIERARCHY_ERROR = "HIERARCHY_ERROR"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    PERMISSION_ERROR = "PERMISSION_ERROR"
    TIMEOUT = "TIMEOUT"


@dataclass
class BenchmarkCase:
    """A single benchmark case (benchmark-dataset-spec.md #BenchmarkCase).

    Fields:
        id: unique case identifier.
        version: case version.
        title: short description.
        category: question category.
        difficulty: difficulty level.
        language: content language.
        vault: target vault scope.
        question: the input question.
        expected_documents: list of expected document identifiers.
        expected_nodes: list of expected knowledge node paths.
        expected_citations: list of expected citations (document + reference).
        expected_answer: optional expected answer description.
        evaluation: which evaluations to run (retrieval, citation, generation).
        tags: optional classification tags.
    """

    id: str
    version: str = "1.0"
    title: str = ""
    category: CaseCategory = CaseCategory.FACT_LOOKUP
    difficulty: CaseDifficulty = CaseDifficulty.MEDIUM
    language: str = "vi"
    vault: str = "common"
    question: str = ""
    expected_documents: list[str] = field(default_factory=list)
    expected_nodes: list[str] = field(default_factory=list)
    expected_citations: list[dict[str, str]] = field(default_factory=list)
    expected_answer: Optional[str] = None
    evaluation: dict[str, bool] = field(default_factory=lambda: {
        "retrieval": True, "citation": True, "generation": True,
    })
    tags: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    """A benchmark dataset (benchmark-dataset-spec.md #Dataset).

    Fields:
        id: unique dataset identifier.
        name: human-readable name.
        dataset_type: the type of dataset.
        version: dataset version.
        description: description of the dataset.
        cases: the benchmark cases.
        created_at: when the dataset was created.
        metadata: additional metadata.
    """

    id: str
    name: str
    dataset_type: DatasetType = DatasetType.COMPONENT
    version: str = "1.0"
    description: str = ""
    cases: list[BenchmarkCase] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def case_count(self) -> int:
        return len(self.cases)


@dataclass
class BenchmarkSuite:
    """A collection of datasets forming a benchmark run.

    Fields:
        id: unique suite identifier.
        name: human-readable name.
        datasets: the datasets in this suite.
        created_at: when the suite was created.
        metadata: additional metadata.
    """

    id: str
    name: str
    datasets: list[Dataset] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricValue:
    """A single metric value with metadata.

    Fields:
        name: metric name (e.g. "recall@10").
        value: the numeric value.
        unit: unit of measurement.
        description: human-readable description.
    """

    name: str
    value: float
    unit: str = ""
    description: str = ""


@dataclass
class EvaluationMetric:
    """A collection of metric values for a component.

    Fields:
        component: the component being evaluated.
        metrics: the metric values.
    """

    component: str
    metrics: list[MetricValue] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """The result of evaluating a single benchmark case.

    Fields:
        case_id: the benchmark case ID.
        passed: whether the case passed evaluation.
        retrieval_metrics: retrieval evaluation metrics.
        citation_metrics: citation evaluation metrics.
        generation_metrics: generation evaluation metrics.
        failure_category: the primary failure category (if failed).
        failure_detail: detailed failure description.
        execution_time_ms: execution time in milliseconds.
        warnings: any warnings.
    """

    case_id: str
    passed: bool = True
    retrieval_metrics: Optional[EvaluationMetric] = None
    citation_metrics: Optional[EvaluationMetric] = None
    generation_metrics: Optional[EvaluationMetric] = None
    failure_category: Optional[FailureCategory] = None
    failure_detail: Optional[str] = None
    execution_time_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    """A complete evaluation report (tasks/017 #Reporting).

    Fields:
        report_id: unique report identifier.
        suite_name: the benchmark suite name.
        dataset_name: the dataset name.
        system_version: the platform version.
        executed_at: when the evaluation was executed.
        total_cases: total number of cases.
        passed_cases: number of passed cases.
        failed_cases: number of failed cases.
        component_metrics: per-component aggregate metrics.
        results: per-case results.
        regression: regression analysis (optional).
        execution_time_ms: total execution time.
        metadata: additional metadata.
    """

    report_id: str
    suite_name: str = ""
    dataset_name: str = ""
    system_version: str = "0.1.0"
    executed_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    component_metrics: list[EvaluationMetric] = field(default_factory=list)
    results: list[EvaluationResult] = field(default_factory=list)
    regression: Optional[RegressionResult] = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Fraction of cases that passed (0.0 - 1.0)."""
        if self.total_cases == 0:
            return 1.0
        return self.passed_cases / self.total_cases


@dataclass
class RegressionResult:
    """Regression analysis comparing two evaluation runs.

    Fields:
        baseline_report_id: the baseline report.
        current_report_id: the current report.
        regressions: list of metrics that regressed.
        improvements: list of metrics that improved.
        unchanged: list of metrics that stayed the same.
        threshold: the regression threshold.
    """

    baseline_report_id: str
    current_report_id: str
    regressions: list[dict[str, Any]] = field(default_factory=list)
    improvements: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[dict[str, Any]] = field(default_factory=list)
    threshold: float = 0.05
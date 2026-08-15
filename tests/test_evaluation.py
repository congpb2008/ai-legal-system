"""Tests for the Evaluation Platform (Task 017).

Covers:
    - Domain models (BenchmarkCase, Dataset, EvaluationReport, RegressionResult)
    - Metrics (recall@K, precision@K, MRR, nDCG, F1, citation metrics)
    - Evaluators (Retrieval, Citation, Generation, Parser, Pipeline)
    - EvaluationRunner (dataset execution, regression detection)
    - EvaluationService (report persistence, comparison)

The authoritative source is the Evaluation specification
(tasks/017-evaluation.md) and the Benchmark Dataset Spec
(design/benchmark-dataset-spec.md).
"""

import pytest

from legal_platform.modules.evaluation.metrics import (
    citation_precision,
    citation_recall,
    compute_citation_metrics,
    compute_generation_metrics,
    compute_retrieval_metrics,
    f1_score,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
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
from legal_platform.modules.evaluation.service import EvaluationService
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vector_index.service import VectorIndexService


def _test_components():
    """Build an isolated evaluation stack with an explicit test embedder."""
    registry = DocumentRegistry()
    retrieval = RetrievalService(
        registry=registry,
        vector_index=VectorIndexService(registry=registry),
        embedding_service=EmbeddingService(
            registry=registry,
            engine=PlaceholderEmbedder(),
        ),
    )
    generation = GenerationService(
        registry=registry,
        reranker_service=RerankerService(
            registry=registry,
            retrieval_service=retrieval,
        ),
    )
    return retrieval, generation


def _test_runner():
    retrieval, generation = _test_components()
    retrieval_evaluator = RetrievalEvaluator(retrieval)
    citation_evaluator = CitationEvaluator(generation)
    generation_evaluator = GenerationEvaluator(generation)
    return EvaluationRunner(
        retrieval_evaluator=retrieval_evaluator,
        citation_evaluator=citation_evaluator,
        generation_evaluator=generation_evaluator,
        pipeline_evaluator=PipelineEvaluator(
            retrieval_evaluator=retrieval_evaluator,
            citation_evaluator=citation_evaluator,
            generation_evaluator=generation_evaluator,
        ),
    )


def _test_evaluation_service():
    return EvaluationService(runner=_test_runner())


# ======================================================================
# 1. Domain Models
# ======================================================================


class TestDomainModels:
    """Evaluation domain models."""

    def test_benchmark_case_defaults(self):
        case = BenchmarkCase(id="test-1", question="What is the law?")
        assert case.version == "1.0"
        assert case.difficulty == CaseDifficulty.MEDIUM
        assert case.language == "vi"
        assert case.evaluation["retrieval"] is True

    def test_dataset_properties(self):
        cases = [
            BenchmarkCase(id="c1", question="q1"),
            BenchmarkCase(id="c2", question="q2"),
        ]
        ds = Dataset(id="ds-1", name="Test Dataset", cases=cases)
        assert ds.case_count == 2
        assert ds.dataset_type == DatasetType.COMPONENT

    def test_evaluation_report_pass_rate(self):
        report = EvaluationReport(
            report_id="r1",
            total_cases=10,
            passed_cases=7,
            failed_cases=3,
        )
        assert report.pass_rate == 0.7

    def test_evaluation_report_empty_pass_rate(self):
        report = EvaluationReport(report_id="r1")
        assert report.pass_rate == 1.0

    def test_regression_result(self):
        result = RegressionResult(
            baseline_report_id="baseline",
            current_report_id="current",
            regressions=[{"metric": "recall", "diff": -0.1}],
            improvements=[{"metric": "precision", "diff": 0.05}],
        )
        assert len(result.regressions) == 1
        assert len(result.improvements) == 1

    def test_metric_value(self):
        mv = MetricValue(name="recall@10", value=0.85)
        assert mv.name == "recall@10"
        assert mv.value == 0.85

    def test_evaluation_metric(self):
        em = EvaluationMetric(
            component="retrieval",
            metrics=[MetricValue(name="recall", value=0.9)],
        )
        assert em.component == "retrieval"
        assert len(em.metrics) == 1

    def test_evaluation_result_defaults(self):
        result = EvaluationResult(case_id="c1")
        assert result.passed is True
        assert result.execution_time_ms == 0.0
        assert result.warnings == []

    def test_dataset_types(self):
        assert DatasetType.UNIT.value == "UNIT"
        assert DatasetType.REGRESSION.value == "REGRESSION"
        assert DatasetType.RELEASE.value == "RELEASE"

    def test_case_difficulties(self):
        assert CaseDifficulty.EASY.value == "EASY"
        assert CaseDifficulty.EXPERT.value == "EXPERT"

    def test_failure_categories(self):
        assert FailureCategory.WRONG_RETRIEVAL.value == "WRONG_RETRIEVAL"
        assert FailureCategory.UNSUPPORTED_CLAIM.value == "UNSUPPORTED_CLAIM"


# ======================================================================
# 2. Metrics
# ======================================================================


class TestMetrics:
    """Evaluation metrics (tasks/017 #RetrievalEvaluation, #CitationEvaluation)."""

    def test_recall_at_k(self):
        assert recall_at_k(3, 5, 10) == 0.6
        assert recall_at_k(5, 5, 10) == 1.0
        assert recall_at_k(0, 5, 10) == 0.0

    def test_recall_at_k_no_relevant(self):
        assert recall_at_k(0, 0, 10) == 1.0

    def test_recall_at_k_zero_k(self):
        assert recall_at_k(3, 5, 0) == 0.0

    def test_precision_at_k(self):
        assert precision_at_k(3, 10) == 0.3
        assert precision_at_k(10, 10) == 1.0
        assert precision_at_k(0, 10) == 0.0

    def test_precision_at_k_zero_k(self):
        assert precision_at_k(3, 0) == 0.0

    def test_mrr(self):
        assert mean_reciprocal_rank([1, 2, 3]) == pytest.approx(
            (1/1 + 1/2 + 1/3) / 3
        )
        assert mean_reciprocal_rank([1]) == 1.0
        assert mean_reciprocal_rank([]) == 0.0
        assert mean_reciprocal_rank([0, 0]) == 0.0

    def test_ndcg(self):
        # Perfect ranking: all relevant
        assert ndcg_at_k([3, 2, 1], 3) == pytest.approx(1.0, rel=0.01)
        # No relevance
        assert ndcg_at_k([0, 0, 0], 3) == 0.0
        # Empty
        assert ndcg_at_k([], 3) == 0.0
        # Zero k
        assert ndcg_at_k([3, 2, 1], 0) == 0.0

    def test_f1_score(self):
        assert f1_score(1.0, 1.0) == 1.0
        assert f1_score(0.5, 0.5) == 0.5
        assert f1_score(0.0, 0.0) == 0.0
        assert f1_score(1.0, 0.0) == 0.0

    def test_citation_precision(self):
        assert citation_precision(5, 5) == 1.0
        assert citation_precision(3, 5) == 0.6
        assert citation_precision(0, 5) == 0.0
        assert citation_precision(0, 0) == 1.0  # No citations = no errors

    def test_citation_recall(self):
        assert citation_recall(5, 5) == 1.0
        assert citation_recall(3, 5) == 0.6
        assert citation_recall(0, 5) == 0.0
        assert citation_recall(0, 0) == 1.0

    def test_compute_retrieval_metrics(self):
        metrics = compute_retrieval_metrics(
            retrieved_docs={"doc-1", "doc-2"},
            expected_docs={"doc-1", "doc-3"},
            retrieved_nodes={"node-1"},
            expected_nodes={"node-1", "node-2"},
            k=10,
        )
        assert "recall_at_k" in metrics
        assert "doc_recall" in metrics
        assert "node_recall" in metrics
        assert metrics["doc_recall"] == 0.5  # 1 of 2 docs found
        assert metrics["node_recall"] == 0.5  # 1 of 2 nodes found

    def test_compute_citation_metrics(self):
        metrics = compute_citation_metrics(
            generated_citations=[
                {"document": "doc-1", "reference": "Điều 1"},
                {"document": "doc-2", "reference": "Điều 2"},
            ],
            expected_citations=[
                {"document": "doc-1", "reference": "Điều 1"},
            ],
        )
        assert metrics["citation_precision"] == 0.5  # 1 of 2 correct
        assert metrics["citation_recall"] == 1.0  # 1 of 1 expected found
        assert metrics["citation_f1"] > 0

    def test_compute_generation_metrics(self):
        metrics = compute_generation_metrics(
            has_answer=True,
            has_citations=True,
            has_unsupported_claims=False,
            confidence_score=0.85,
        )
        assert metrics["answer_present"] == 1.0
        assert metrics["citations_present"] == 1.0
        assert metrics["unsupported_claims_detected"] == 0.0
        assert metrics["confidence"] == 0.85


# ======================================================================
# 3. Evaluators
# ======================================================================


class TestEvaluators:
    """Per-component evaluators."""

    def test_retrieval_evaluator(self):
        case = BenchmarkCase(
            id="ret-test",
            question="mua sắm máy chủ",
            expected_documents=["doc-1"],
            expected_nodes=["Điều 1"],
        )
        retrieval, _ = _test_components()
        evaluator = RetrievalEvaluator(retrieval)
        result = evaluator.evaluate(case)
        assert result.case_id == "ret-test"
        assert result.retrieval_metrics is not None
        assert result.retrieval_metrics.component == "retrieval"

    def test_citation_evaluator(self):
        case = BenchmarkCase(
            id="cit-test",
            question="mua sắm máy chủ",
            expected_citations=[
                {"document": "doc-1", "reference": "Điều 1"},
            ],
        )
        _, generation = _test_components()
        evaluator = CitationEvaluator(generation)
        result = evaluator.evaluate(case)
        assert result.case_id == "cit-test"
        assert result.citation_metrics is not None

    def test_generation_evaluator(self):
        case = BenchmarkCase(
            id="gen-test",
            question="mua sắm máy chủ",
        )
        _, generation = _test_components()
        evaluator = GenerationEvaluator(generation)
        result = evaluator.evaluate(case)
        assert result.case_id == "gen-test"
        assert result.generation_metrics is not None

    def test_parser_evaluator(self):
        case = BenchmarkCase(id="parse-test", question="test")
        evaluator = ParserEvaluator()
        result = evaluator.evaluate(case)
        assert result.case_id == "parse-test"
        assert result.passed is True  # Stub always passes

    def test_pipeline_evaluator(self):
        case = BenchmarkCase(
            id="pipe-test",
            question="mua sắm máy chủ",
            expected_documents=["doc-1"],
            expected_citations=[{"document": "doc-1", "reference": "Điều 1"}],
        )
        evaluator = _test_runner().pipeline_eval
        result = evaluator.evaluate(case)
        assert result.case_id == "pipe-test"
        assert result.retrieval_metrics is not None or result.generation_metrics is not None


# ======================================================================
# 4. EvaluationRunner
# ======================================================================


class TestEvaluationRunner:
    """EvaluationRunner (benchmark execution)."""

    def test_run_dataset(self):
        cases = [
            BenchmarkCase(id="c1", question="mua sắm máy chủ"),
            BenchmarkCase(id="c2", question="quy định mua sắm"),
        ]
        ds = Dataset(id="ds-1", name="Test", cases=cases)
        runner = _test_runner()
        report = runner.run_dataset(ds)
        assert report.total_cases == 2
        assert report.report_id is not None
        assert len(report.results) == 2

    def test_run_dataset_with_components(self):
        cases = [BenchmarkCase(id="c1", question="test query")]
        ds = Dataset(id="ds-2", name="Retrieval Only", cases=cases)
        runner = _test_runner()
        report = runner.run_dataset(ds, components=["retrieval"])
        assert report.total_cases == 1
        for r in report.results:
            assert r.retrieval_metrics is not None

    def test_detect_regressions(self):
        runner = _test_runner()

        # Create two reports with different pass rates
        baseline = EvaluationReport(
            report_id="baseline",
            total_cases=10,
            passed_cases=8,
            failed_cases=2,
            component_metrics=[
                EvaluationMetric(
                    component="retrieval",
                    metrics=[MetricValue(name="recall@10", value=0.8)],
                ),
            ],
        )
        current = EvaluationReport(
            report_id="current",
            total_cases=10,
            passed_cases=6,
            failed_cases=4,
            component_metrics=[
                EvaluationMetric(
                    component="retrieval",
                    metrics=[MetricValue(name="recall@10", value=0.6)],
                ),
            ],
        )

        result = runner.detect_regressions(current, baseline, threshold=0.05)
        assert len(result.regressions) >= 1
        assert result.baseline_report_id == "baseline"
        assert result.current_report_id == "current"

    def test_detect_improvements(self):
        runner = _test_runner()
        baseline = EvaluationReport(
            report_id="base",
            total_cases=10, passed_cases=5, failed_cases=5,
            component_metrics=[
                EvaluationMetric(
                    component="retrieval",
                    metrics=[MetricValue(name="recall@10", value=0.5)],
                ),
            ],
        )
        current = EvaluationReport(
            report_id="curr",
            total_cases=10, passed_cases=9, failed_cases=1,
            component_metrics=[
                EvaluationMetric(
                    component="retrieval",
                    metrics=[MetricValue(name="recall@10", value=0.9)],
                ),
            ],
        )
        result = runner.detect_regressions(current, baseline, threshold=0.05)
        assert len(result.improvements) >= 1


# ======================================================================
# 5. EvaluationService
# ======================================================================


class TestEvaluationService:
    """EvaluationService integration."""

    def test_create_sample_dataset(self):
        ds = EvaluationService.create_sample_dataset()
        assert ds.name == "Sample Dataset"
        assert ds.case_count == 3

    def test_create_sample_dataset_custom(self):
        ds = EvaluationService.create_sample_dataset(
            name="Custom", dataset_type="REGRESSION", count=5
        )
        assert ds.dataset_type == DatasetType.REGRESSION
        assert ds.case_count == 5

    def test_run_and_persist(self):
        svc = _test_evaluation_service()
        ds = EvaluationService.create_sample_dataset(count=2)
        report = svc.run_evaluation(ds)
        assert report.report_id is not None
        assert report.total_cases == 2

        # Retrieve from storage
        fetched = svc.get_report(report.report_id)
        assert fetched is not None
        assert fetched.total_cases == 2

    def test_list_reports(self):
        svc = _test_evaluation_service()
        ds = EvaluationService.create_sample_dataset(count=1)
        svc.run_evaluation(ds)
        reports = svc.list_reports()
        assert len(reports) >= 1

    def test_delete_report(self):
        svc = _test_evaluation_service()
        ds = EvaluationService.create_sample_dataset(count=1)
        report = svc.run_evaluation(ds)
        assert svc.delete_report(report.report_id) is True
        assert svc.get_report(report.report_id) is None

    def test_compare_reports(self):
        svc = _test_evaluation_service()
        ds = EvaluationService.create_sample_dataset(count=3)

        # Run baseline
        baseline = svc.run_evaluation(ds)

        # Run current
        current = svc.run_evaluation(ds)

        # Compare
        result = svc.compare_reports(current.report_id, baseline.report_id)
        assert result.baseline_report_id == baseline.report_id
        assert result.current_report_id == current.report_id

    def test_compare_nonexistent(self):
        svc = _test_evaluation_service()
        with pytest.raises(KeyError):
            svc.compare_reports("nonexistent", "also-nonexistent")


# ======================================================================
# 6. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_empty_dataset(self):
        ds = Dataset(id="empty", name="Empty", cases=[])
        runner = _test_runner()
        report = runner.run_dataset(ds)
        assert report.total_cases == 0
        assert report.passed_cases == 0
        assert report.pass_rate == 1.0

    def test_benchmark_suite(self):
        ds = Dataset(id="ds-1", name="Test", cases=[
            BenchmarkCase(id="c1", question="q1"),
        ])
        suite = BenchmarkSuite(id="suite-1", name="Test Suite", datasets=[ds])
        assert len(suite.datasets) == 1
        assert suite.datasets[0].case_count == 1

    def test_metric_value_units(self):
        mv = MetricValue(name="latency", value=150.0, unit="ms",
                         description="Average retrieval latency")
        assert mv.unit == "ms"
        assert mv.description == "Average retrieval latency"

    def test_evaluation_result_with_failure(self):
        result = EvaluationResult(
            case_id="failing",
            passed=False,
            failure_category=FailureCategory.WRONG_RETRIEVAL,
            failure_detail="No relevant documents retrieved.",
        )
        assert result.passed is False
        assert result.failure_category == FailureCategory.WRONG_RETRIEVAL
        assert "No relevant documents" in result.failure_detail

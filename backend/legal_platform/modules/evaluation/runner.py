"""Evaluation runner (tasks/017-evaluation.md).

Executes benchmark cases against platform components and collects metrics.
Supports per-component evaluation: Retrieval, Citation, Generation, Parser,
and End-to-End Pipeline.

Evaluation never modifies production data.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.answer import Answer, AnswerStatus
from legal_platform.contracts.retrieval import RetrievalResult
from legal_platform.modules.evaluation.metrics import (
    compute_citation_metrics,
    compute_generation_metrics,
    compute_retrieval_metrics,
)
from legal_platform.modules.evaluation.models import (
    BenchmarkCase,
    EvaluationMetric,
    EvaluationResult,
    FailureCategory,
    MetricValue,
)
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.retrieval.service import RetrievalService


class RetrievalEvaluator:
    """Evaluates retrieval quality for benchmark cases."""

    def __init__(self, retrieval_service: "RetrievalService | None" = None):
        self.retrieval = retrieval_service or RetrievalService()

    def evaluate(self, case: BenchmarkCase) -> EvaluationResult:
        """Evaluate retrieval for a single benchmark case.

        Args:
            case: the benchmark case to evaluate.

        Returns:
            An EvaluationResult.
        """
        start = time.time()

        result = self.retrieval.search(
            case.question,
            top_k=10,
        )

        elapsed_ms = (time.time() - start) * 1000

        # Extract retrieved document IDs and node paths
        retrieved_docs = set()
        retrieved_nodes = set()
        for ev in result.evidence:
            retrieved_docs.add(str(ev.document_id))
            if ev.source_anchor and ev.source_anchor.canonical_reference:
                retrieved_nodes.add(ev.source_anchor.canonical_reference)

        expected_docs = set(case.expected_documents)
        expected_nodes = set(case.expected_nodes)

        metrics = compute_retrieval_metrics(
            retrieved_docs=retrieved_docs,
            expected_docs=expected_docs,
            retrieved_nodes=retrieved_nodes,
            expected_nodes=expected_nodes,
            k=10,
        )

        # Determine pass/fail
        doc_recall = metrics.get("doc_recall", 0.0)
        passed = doc_recall >= 0.5  # At least 50% document recall

        metric_list = [
            MetricValue(name=k, value=v, description=k.replace("_", " ").title())
            for k, v in metrics.items()
        ]

        failure = None if passed else FailureCategory.WRONG_GENERATION
        if not passed:
            failure = FailureCategory.WRONG_RETRIEVAL

        return EvaluationResult(
            case_id=case.id,
            passed=passed,
            retrieval_metrics=EvaluationMetric(component="retrieval", metrics=metric_list),
            failure_category=failure,
            failure_detail=(
                f"Document recall {doc_recall:.2f} below 0.5 threshold. "
                f"Expected docs: {expected_docs}, Retrieved: {retrieved_docs}"
            ) if not passed else None,
            execution_time_ms=round(elapsed_ms, 2),
        )


class CitationEvaluator:
    """Evaluates citation quality for benchmark cases."""

    def __init__(self, generation_service: "GenerationService | None" = None):
        self.generation = generation_service or GenerationService()

    def evaluate(self, case: BenchmarkCase) -> EvaluationResult:
        """Evaluate citations for a single benchmark case.

        Args:
            case: the benchmark case to evaluate.

        Returns:
            An EvaluationResult.
        """
        start = time.time()

        answer = self.generation.answer_query(case.question)

        elapsed_ms = (time.time() - start) * 1000

        # Extract generated citations
        generated_citations = [
            {"document": str(c.document_id), "reference": c.source_anchor.canonical_reference if c.source_anchor else ""}
            for c in answer.citations
        ]

        expected_citations = case.expected_citations

        metrics = compute_citation_metrics(
            generated_citations=generated_citations,
            expected_citations=expected_citations,
        )

        citation_prec = metrics.get("citation_precision", 0.0)
        citation_rec = metrics.get("citation_recall", 0.0)
        passed = citation_prec >= 0.5 and citation_rec >= 0.3

        metric_list = [
            MetricValue(name=k, value=v, description=k.replace("_", " ").title())
            for k, v in metrics.items()
        ]

        failure = None if passed else FailureCategory.WRONG_GENERATION
        if not passed:
            failure = FailureCategory.WRONG_CITATION

        return EvaluationResult(
            case_id=case.id,
            passed=passed,
            citation_metrics=EvaluationMetric(component="citation", metrics=metric_list),
            failure_category=failure,
            failure_detail=(
                f"Citation precision {citation_prec:.2f}, recall {citation_rec:.2f}"
            ) if not passed else None,
            execution_time_ms=round(elapsed_ms, 2),
        )


class GenerationEvaluator:
    """Evaluates generation quality for benchmark cases."""

    def __init__(self, generation_service: "GenerationService | None" = None):
        self.generation = generation_service or GenerationService()

    def evaluate(self, case: BenchmarkCase) -> EvaluationResult:
        """Evaluate generation for a single benchmark case.

        Args:
            case: the benchmark case to evaluate.

        Returns:
            An EvaluationResult.
        """
        start = time.time()

        answer = self.generation.answer_query(case.question)

        elapsed_ms = (time.time() - start) * 1000

        has_answer = bool(answer.response and answer.response.content)
        has_citations = len(answer.citations) > 0
        has_unsupported = any(
            "unsupported" in (l.description or "").lower()
            for l in answer.limitations
        )

        metrics = compute_generation_metrics(
            has_answer=has_answer,
            has_citations=has_citations,
            has_unsupported_claims=has_unsupported,
            confidence_score=answer.confidence.score if answer.confidence else 0.0,
        )

        # Corpus-specific assertions are not a substitute for expert correctness review.
        import unicodedata
        normalize = lambda value: ' '.join(unicodedata.normalize('NFC', value).casefold().split())
        actual = normalize(answer.response.content)
        expected_abstention = case.expected_abstention or case.category.value == 'ABSTENTION'
        if expected_abstention:
            passed = answer.status == AnswerStatus.NO_EVIDENCE and not has_citations
        else:
            required = case.required_phrases or ([case.expected_answer] if case.expected_answer else [])
            cited_docs = {str(c.document_id) for c in answer.citations}
            passed = bool(required) and has_answer and has_citations and all(normalize(p) in actual for p in required)
            passed = passed and all(normalize(p) not in actual for p in case.forbidden_phrases)
            passed = passed and set(case.expected_documents).issubset(cited_docs)
        metrics['expected_abstention'] = float(expected_abstention)
        metrics['expert_approved'] = float(case.expert_approved)

        metric_list = [
            MetricValue(name=k, value=v, description=k.replace("_", " ").title())
            for k, v in metrics.items()
        ]

        failure = None if passed else FailureCategory.WRONG_GENERATION
        if not passed:
            if not has_answer:
                failure = FailureCategory.WRONG_GENERATION
            elif not has_citations:
                failure = FailureCategory.MISSING_EVIDENCE

        return EvaluationResult(
            case_id=case.id,
            passed=passed,
            generation_metrics=EvaluationMetric(component="generation", metrics=metric_list),
            failure_category=failure,
            failure_detail=(
                f"Has answer: {has_answer}, Has citations: {has_citations}"
            ) if not passed else None,
            execution_time_ms=round(elapsed_ms, 2),
        )


class ParserEvaluator:
    """Evaluates parser quality for benchmark cases.

    This is a stub; full parser evaluation requires ground-truth
    Knowledge Trees for comparison.
    """

    def evaluate(self, case: BenchmarkCase) -> EvaluationResult:
        """Evaluate parser quality (stub).

        Returns a failed, not-evaluated result because parser evaluation requires
        document-level ground truth that is not part of standard
        benchmark cases.
        """
        return EvaluationResult(
            case_id=case.id,
            passed=False,
            failure_category=FailureCategory.PARSER_ERROR,
            failure_detail='Not evaluated: document-level ground truth is required.',
            retrieval_metrics=EvaluationMetric(
                component="parser",
                metrics=[
                    MetricValue(name="parser_evaluated", value=0.0,
                                description="Parser evaluation requires document ground truth"),
                ],
            ),
            warnings=["Parser evaluation requires document-level ground truth."],
        )


class PipelineEvaluator:
    """Evaluates the end-to-end pipeline for benchmark cases."""

    def __init__(
        self,
        retrieval_evaluator: "RetrievalEvaluator | None" = None,
        citation_evaluator: "CitationEvaluator | None" = None,
        generation_evaluator: "GenerationEvaluator | None" = None,
    ):
        self.retrieval = retrieval_evaluator or RetrievalEvaluator()
        self.citation = citation_evaluator or CitationEvaluator()
        self.generation = generation_evaluator or GenerationEvaluator()

    def evaluate(self, case: BenchmarkCase) -> EvaluationResult:
        """Evaluate the full pipeline for a single benchmark case.

        Runs retrieval, generation (which includes citation), and
        aggregates the results.

        Args:
            case: the benchmark case to evaluate.

        Returns:
            An EvaluationResult with all component metrics.
        """
        start = time.time()

        # Run retrieval evaluation
        retrieval_result = self.retrieval.evaluate(case)

        # Run generation evaluation (includes citation)
        generation_result = self.generation.evaluate(case)
        citation_result = self.citation.evaluate(case) if case.evaluation.get('citation', True) and not case.expected_abstention else None

        elapsed_ms = (time.time() - start) * 1000

        # Aggregate: pass if all enabled components pass
        passed = True
        failures: list[str] = []

        if case.evaluation.get("retrieval", True) and not retrieval_result.passed:
            passed = False
            failures.append(f"Retrieval: {retrieval_result.failure_detail}")

        if case.evaluation.get("generation", True) and not generation_result.passed:
            passed = False
            failures.append(f"Generation: {generation_result.failure_detail}")

        if citation_result is not None and not citation_result.passed:
            passed = False
            failures.append(f'Citation: {citation_result.failure_detail}')
        # Determine primary failure category
        failure_category = None
        if not passed:
            if retrieval_result.failure_category:
                failure_category = retrieval_result.failure_category
            elif generation_result.failure_category:
                failure_category = generation_result.failure_category
            elif citation_result is not None:
                failure_category = citation_result.failure_category

        return EvaluationResult(
            case_id=case.id,
            passed=passed,
            retrieval_metrics=retrieval_result.retrieval_metrics,
            citation_metrics=citation_result.citation_metrics if citation_result else None,
            generation_metrics=generation_result.generation_metrics,
            failure_category=failure_category,
            failure_detail="; ".join(failures) if failures else None,
            execution_time_ms=round(elapsed_ms, 2),
        )


class EvaluationRunner:
    """Runs benchmark suites and produces evaluation reports.

    Orchestrates the evaluation pipeline:
        Benchmark Suite → Dataset → Execution → Metric Collection → Report
    """

    def __init__(
        self,
        retrieval_evaluator: "RetrievalEvaluator | None" = None,
        citation_evaluator: "CitationEvaluator | None" = None,
        generation_evaluator: "GenerationEvaluator | None" = None,
        parser_evaluator: "ParserEvaluator | None" = None,
        pipeline_evaluator: "PipelineEvaluator | None" = None,
    ):
        self.retrieval_eval = retrieval_evaluator or RetrievalEvaluator()
        self.citation_eval = citation_evaluator or CitationEvaluator()
        self.generation_eval = generation_evaluator or GenerationEvaluator()
        self.parser_eval = parser_evaluator or ParserEvaluator()
        self.pipeline_eval = pipeline_evaluator or PipelineEvaluator()

    def run_dataset(
        self,
        dataset: "Any",
        *,
        components: "list[str] | None" = None,
    ) -> "Any":
        """Run evaluation on all cases in a dataset.

        Args:
            dataset: the Dataset to evaluate.
            components: which components to evaluate (default: all).
                Options: "retrieval", "citation", "generation", "parser", "pipeline".

        Returns:
            An EvaluationReport.
        """
        from legal_platform.modules.evaluation.models import (
            Dataset as DatasetModel,
            EvaluationReport,
        )

        import uuid
        report_id = str(uuid.uuid4())
        start = time.time()

        allowed = components or ["retrieval", "citation", "generation", "pipeline"]

        results: list[EvaluationResult] = []
        for case in dataset.cases:
            if "pipeline" in allowed:
                result = self.pipeline_eval.evaluate(case)
            else:
                # Evaluate individual components
                retrieval_result = None
                citation_result = None
                generation_result = None

                if "retrieval" in allowed:
                    retrieval_result = self.retrieval_eval.evaluate(case)
                if "citation" in allowed:
                    citation_result = self.citation_eval.evaluate(case)
                if "generation" in allowed:
                    generation_result = self.generation_eval.evaluate(case)

                # Merge results
                passed = all(
                    r.passed for r in [
                        retrieval_result, citation_result, generation_result
                    ] if r is not None
                )
                result = EvaluationResult(
                    case_id=case.id,
                    passed=passed,
                    retrieval_metrics=retrieval_result.retrieval_metrics if retrieval_result else None,
                    citation_metrics=citation_result.citation_metrics if citation_result else None,
                    generation_metrics=generation_result.generation_metrics if generation_result else None,
                    failure_category=next(
                        (r.failure_category for r in [
                            retrieval_result, citation_result, generation_result
                        ] if r is not None and not r.passed),
                        None,
                    ),
                    execution_time_ms=round(
                        sum(
                            r.execution_time_ms for r in [
                                retrieval_result, citation_result, generation_result
                            ] if r is not None
                        ), 2
                    ),
                )
            results.append(result)

        elapsed_ms = (time.time() - start) * 1000

        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed)

        # Aggregate component metrics
        component_metrics_map: dict[str, list[MetricValue]] = {}
        for r in results:
            for m in [r.retrieval_metrics, r.citation_metrics, r.generation_metrics]:
                if m is not None:
                    if m.component not in component_metrics_map:
                        component_metrics_map[m.component] = []
                    component_metrics_map[m.component].extend(m.metrics)

        component_metrics = [
            EvaluationMetric(component=comp, metrics=metrics)
            for comp, metrics in component_metrics_map.items()
        ]

        report = EvaluationReport(
            report_id=report_id,
            suite_name="ad-hoc",
            dataset_name=dataset.name,
            total_cases=len(results),
            passed_cases=passed_count,
            failed_cases=failed_count,
            component_metrics=component_metrics,
            results=results,
            execution_time_ms=round(elapsed_ms, 2),
        )

        return report

    def detect_regressions(
        self,
        current_report: "Any",
        baseline_report: "Any",
        *,
        threshold: float = 0.05,
    ) -> "Any":
        """Compare two evaluation reports and detect regressions.

        Args:
            current_report: the current evaluation report.
            baseline_report: the baseline evaluation report.
            threshold: minimum change to consider a regression (default 0.05 = 5%).

        Returns:
            A RegressionResult.
        """
        from legal_platform.modules.evaluation.models import RegressionResult

        regressions: list[dict[str, Any]] = []
        improvements: list[dict[str, Any]] = []
        unchanged: list[dict[str, Any]] = []

        # Compare pass rates
        current_pass = current_report.pass_rate
        baseline_pass = baseline_report.pass_rate
        diff = current_pass - baseline_pass

        entry = {
            "metric": "pass_rate",
            "baseline": round(baseline_pass, 4),
            "current": round(current_pass, 4),
            "diff": round(diff, 4),
        }
        if diff < -threshold:
            entry["status"] = "regression"
            regressions.append(entry)
        elif diff > threshold:
            entry["status"] = "improvement"
            improvements.append(entry)
        else:
            entry["status"] = "unchanged"
            unchanged.append(entry)

        # Compare component metrics
        current_metrics = {
            m.component: {mv.name: mv.value for mv in m.metrics}
            for m in current_report.component_metrics
        }
        baseline_metrics = {
            m.component: {mv.name: mv.value for mv in m.metrics}
            for m in baseline_report.component_metrics
        }

        for component, c_metrics in current_metrics.items():
            b_metrics = baseline_metrics.get(component, {})
            for name, c_val in c_metrics.items():
                b_val = b_metrics.get(name, c_val)
                diff = c_val - b_val
                entry = {
                    "metric": f"{component}.{name}",
                    "baseline": round(b_val, 4),
                    "current": round(c_val, 4),
                    "diff": round(diff, 4),
                }
                if diff < -threshold:
                    entry["status"] = "regression"
                    regressions.append(entry)
                elif diff > threshold:
                    entry["status"] = "improvement"
                    improvements.append(entry)
                else:
                    entry["status"] = "unchanged"
                    unchanged.append(entry)

        return RegressionResult(
            baseline_report_id=baseline_report.report_id,
            current_report_id=current_report.report_id,
            regressions=regressions,
            improvements=improvements,
            unchanged=unchanged,
            threshold=threshold,
        )
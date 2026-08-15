"""Evaluation Platform (tasks/017-evaluation.md, module Evaluation).

Measures the quality, correctness and performance of the platform.
Evaluation is independent from production traffic and never modifies
production data.

The Evaluation Platform provides repeatable benchmarks across all
platform components: OCR, Parser, Knowledge Tree, Chunking, Embedding,
Retrieval, Ranking, Generation, Citation, and End-to-End Pipeline.
"""

from legal_platform.modules.evaluation.models import (
    BenchmarkSuite,
    Dataset,
    DatasetType,
    BenchmarkCase,
    CaseDifficulty,
    CaseCategory,
    EvaluationResult,
    EvaluationMetric,
    MetricValue,
    FailureCategory,
    EvaluationReport,
    RegressionResult,
)
from legal_platform.modules.evaluation.metrics import (
    recall_at_k,
    precision_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    f1_score,
    citation_precision,
    citation_recall,
    compute_retrieval_metrics,
    compute_citation_metrics,
    compute_generation_metrics,
)
from legal_platform.modules.evaluation.runner import (
    EvaluationRunner,
    RetrievalEvaluator,
    CitationEvaluator,
    GenerationEvaluator,
    ParserEvaluator,
    PipelineEvaluator,
)
from legal_platform.modules.evaluation.service import EvaluationService

__all__ = [
    "BenchmarkSuite",
    "Dataset",
    "DatasetType",
    "BenchmarkCase",
    "CaseDifficulty",
    "CaseCategory",
    "EvaluationResult",
    "EvaluationMetric",
    "MetricValue",
    "FailureCategory",
    "EvaluationReport",
    "RegressionResult",
    "recall_at_k",
    "precision_at_k",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "f1_score",
    "citation_precision",
    "citation_recall",
    "compute_retrieval_metrics",
    "compute_citation_metrics",
    "compute_generation_metrics",
    "EvaluationRunner",
    "RetrievalEvaluator",
    "CitationEvaluator",
    "GenerationEvaluator",
    "ParserEvaluator",
    "PipelineEvaluator",
    "EvaluationService",
]
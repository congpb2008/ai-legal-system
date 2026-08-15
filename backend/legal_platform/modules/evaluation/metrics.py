"""Evaluation metrics (tasks/017-evaluation.md).

Standard information retrieval metrics plus platform-specific metrics
for retrieval, citation, and generation evaluation.

Metrics implemented:
    - recall@K
    - precision@K
    - Mean Reciprocal Rank (MRR)
    - nDCG@K
    - F1 Score
    - Citation Precision / Recall
    - Retrieval evaluation
    - Citation evaluation
    - Generation evaluation
"""

from __future__ import annotations

import math
from typing import Any, Optional


def recall_at_k(
    relevant_retrieved: int,
    total_relevant: int,
    k: int,
) -> float:
    """Recall@K: fraction of relevant items retrieved in top K.

    Args:
        relevant_retrieved: number of relevant items in the top K results.
        total_relevant: total number of relevant items in the corpus.
        k: the cutoff.

    Returns:
        Recall@K (0.0 - 1.0). Returns 1.0 if total_relevant is 0.
    """
    if total_relevant == 0:
        return 1.0
    if k == 0:
        return 0.0
    return min(relevant_retrieved / total_relevant, 1.0)


def precision_at_k(
    relevant_retrieved: int,
    k: int,
) -> float:
    """Precision@K: fraction of retrieved items that are relevant.

    Args:
        relevant_retrieved: number of relevant items in the top K results.
        k: the cutoff.

    Returns:
        Precision@K (0.0 - 1.0). Returns 0.0 if k is 0.
    """
    if k == 0:
        return 0.0
    return relevant_retrieved / k


def mean_reciprocal_rank(ranks: list[int]) -> float:
    """Mean Reciprocal Rank: average of reciprocal ranks.

    MRR = (1/N) * sum(1/rank_i) where rank_i is the rank of the first
    relevant item for query i. Returns 0 if no relevant items found.

    Args:
        ranks: list of ranks (1-indexed) of the first relevant item per query.
            Use 0 to indicate no relevant item found.

    Returns:
        MRR (0.0 - 1.0).
    """
    if not ranks:
        return 0.0
    return sum(1.0 / r for r in ranks if r > 0) / len(ranks)


def ndcg_at_k(
    relevance_scores: list[float],
    k: int,
) -> float:
    """Normalized Discounted Cumulative Gain@K.

    nDCG = DCG / IDCG where DCG uses the actual relevance scores and
    IDCG uses the ideal (sorted) relevance scores.

    Args:
        relevance_scores: relevance scores of the retrieved items (top K).
        k: the cutoff.

    Returns:
        nDCG@K (0.0 - 1.0).
    """
    if not relevance_scores or k == 0:
        return 0.0

    scores = relevance_scores[:k]
    dcg = sum((2**s - 1) / math.log2(i + 2) for i, s in enumerate(scores))

    ideal = sorted(relevance_scores, reverse=True)[:k]
    idcg = sum((2**s - 1) / math.log2(i + 2) for i, s in enumerate(ideal))

    if idcg == 0:
        return 0.0
    return dcg / idcg


def f1_score(precision: float, recall: float) -> float:
    """F1 Score: harmonic mean of precision and recall.

    Args:
        precision: precision value (0.0 - 1.0).
        recall: recall value (0.0 - 1.0).

    Returns:
        F1 score (0.0 - 1.0). Returns 0.0 if both are 0.
    """
    if precision + recall == 0:
        return 0.0
    return 2 * (precision * recall) / (precision + recall)


def citation_precision(
    correct_citations: int,
    total_citations: int,
) -> float:
    """Citation precision: fraction of generated citations that are correct.

    Args:
        correct_citations: number of citations that match ground truth.
        total_citations: total number of citations generated.

    Returns:
        Citation precision (0.0 - 1.0).
    """
    if total_citations == 0:
        return 1.0  # No citations = no incorrect citations
    return correct_citations / total_citations


def citation_recall(
    correct_citations: int,
    expected_citations: int,
) -> float:
    """Citation recall: fraction of expected citations that were generated.

    Args:
        correct_citations: number of expected citations that were generated.
        expected_citations: total number of expected citations.

    Returns:
        Citation recall (0.0 - 1.0).
    """
    if expected_citations == 0:
        return 1.0
    return correct_citations / expected_citations


# ---------------------------------------------------------------------------
# Composite metric functions
# ---------------------------------------------------------------------------


def compute_retrieval_metrics(
    *,
    retrieved_docs: set[str],
    expected_docs: set[str],
    retrieved_nodes: set[str],
    expected_nodes: set[str],
    retrieved_ranks: "list[int] | None" = None,
    k: int = 10,
) -> dict[str, float]:
    """Compute retrieval evaluation metrics.

    Args:
        retrieved_docs: set of document IDs retrieved.
        expected_docs: set of expected document IDs.
        retrieved_nodes: set of knowledge node paths retrieved.
        expected_nodes: set of expected knowledge node paths.
        retrieved_ranks: ranks of first relevant item per query (for MRR).
        k: cutoff for recall/precision@K.

    Returns:
        Dict of metric name -> value.
    """
    doc_overlap = retrieved_docs & expected_docs
    node_overlap = retrieved_nodes & expected_nodes

    return {
        "recall_at_k": recall_at_k(len(doc_overlap), len(expected_docs), k),
        "precision_at_k": precision_at_k(len(doc_overlap), k),
        "doc_recall": recall_at_k(len(doc_overlap), len(expected_docs), k),
        "doc_precision": precision_at_k(len(doc_overlap), k),
        "node_recall": recall_at_k(len(node_overlap), len(expected_nodes), k),
        "node_precision": precision_at_k(len(node_overlap), k),
        "mrr": mean_reciprocal_rank(retrieved_ranks or []) if retrieved_ranks else 0.0,
    }


def compute_citation_metrics(
    *,
    generated_citations: "list[dict[str, str]]",
    expected_citations: "list[dict[str, str]]",
) -> dict[str, float]:
    """Compute citation evaluation metrics.

    Args:
        generated_citations: list of citation dicts with 'document' and 'reference'.
        expected_citations: list of expected citation dicts.

    Returns:
        Dict of metric name -> value.
    """
    # Match citations by document + reference
    generated_set = {
        (c.get("document", ""), c.get("reference", ""))
        for c in generated_citations
    }
    expected_set = {
        (c.get("document", ""), c.get("reference", ""))
        for c in expected_citations
    }

    correct = len(generated_set & expected_set)
    total_gen = len(generated_set)
    total_exp = len(expected_set)

    return {
        "citation_precision": citation_precision(correct, total_gen),
        "citation_recall": citation_recall(correct, total_exp),
        "citation_f1": f1_score(
            citation_precision(correct, total_gen),
            citation_recall(correct, total_exp),
        ),
    }


def compute_generation_metrics(
    *,
    has_answer: bool,
    has_citations: bool,
    has_unsupported_claims: bool,
    confidence_score: float = 0.0,
) -> dict[str, float]:
    """Compute generation evaluation metrics.

    Args:
        has_answer: whether an answer was generated.
        has_citations: whether citations were attached.
        has_unsupported_claims: whether unsupported claims were detected.
        confidence_score: the confidence score (0.0 - 1.0).

    Returns:
        Dict of metric name -> value.
    """
    return {
        "answer_present": 1.0 if has_answer else 0.0,
        "citations_present": 1.0 if has_citations else 0.0,
        "unsupported_claims_detected": 1.0 if has_unsupported_claims else 0.0,
        "confidence": confidence_score,
    }
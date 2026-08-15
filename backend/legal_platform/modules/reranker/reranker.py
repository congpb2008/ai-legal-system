"""Reranker core (tasks/010-reranker.md).

The Reranker refines retrieval candidates and produces the final evidence set
for the Generation Service. It improves ranking quality, removes weak candidates,
reduces redundancy, and optimizes evidence diversity.

The Reranker does NOT:
    - Retrieve new documents
    - Generate answers
    - Rewrite evidence
    - Modify Knowledge Trees
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc
from legal_platform.contracts.retrieval import Evidence, RetrievalResult


@dataclass
class RerankerConfig:
    """Configuration for the reranker.

    Fields:
        max_evidence: maximum number of evidence items in the final set.
        min_score: minimum score threshold for evidence retention.
        diversity_weight: weight for diversity in the scoring (0-1).
        freshness_weight: weight for document freshness in scoring (0-1).
        authority_weight: weight for document authority in scoring (0-1).
        redundancy_threshold: similarity threshold above which items are
            considered redundant (deduplicated).
    """

    max_evidence: int = 8
    min_score: float = 0.2
    diversity_weight: float = 0.0
    freshness_weight: float = 0.1
    authority_weight: float = 0.1
    redundancy_threshold: float = 0.9


@dataclass
class RerankedEvidence:
    """A single reranked evidence item.

    Fields:
        evidence: the original evidence item.
        rerank_score: the combined reranking score.
        original_rank: the rank assigned by the Retrieval Service.
        final_rank: the rank after reranking.
        selection_reason: why this item was selected (relevance, diversity, etc.).
    """

    evidence: Evidence
    rerank_score: float
    original_rank: int
    final_rank: int = 0
    selection_reason: str = "relevance"


@dataclass
class RerankerMetadata:
    """Metadata about the reranking operation.

    Fields:
        reranker_version: version of the reranker.
        input_count: number of candidate evidence items.
        output_count: number of evidence items in the final set.
        removed_count: number of items removed (weak/redundant).
        created_at: when the reranking completed.
    """

    reranker_version: str = "reranker-1.0.0"
    input_count: int = 0
    output_count: int = 0
    removed_count: int = 0
    created_at: datetime = field(default_factory=now_utc)


class Reranker:
    """The Reranker.

    Refines retrieval candidates into a final, precision-focused evidence set.
    Combines relevance, diversity, freshness, and authority signals.
    """

    RERANKER_VERSION = "reranker-1.0.0"

    def __init__(self, config: "RerankerConfig | None" = None):
        self.config = config or RerankerConfig()

    def rerank(
        self,
        retrieval_result: RetrievalResult,
        *,
        query: "str | None" = None,
    ) -> tuple[list[RerankedEvidence], RerankerMetadata]:
        """Rerank the evidence in a RetrievalResult.

        Flow (per tasks/010 #ProcessingFlow):
            1. Candidate validation
            2. Feature extraction
            3. Scoring
            4. Duplicate detection
            5. Budget optimization
            6. Final evidence

        Args:
            retrieval_result: the RetrievalResult from the Retrieval Service.
            query: the original query (used for diversity scoring).

        Returns:
            A tuple of (reranked evidence list, reranker metadata).
        """
        candidates = retrieval_result.evidence
        input_count = len(candidates)

        # 1. Candidate validation — filter out weak candidates
        valid = [e for e in candidates if e.score >= self.config.min_score]

        # 2. Feature extraction & 3. Scoring
        scored: list[RerankedEvidence] = []
        for e in valid:
            rerank_score = self._combined_score(e, query)
            scored.append(RerankedEvidence(
                evidence=e,
                rerank_score=rerank_score,
                original_rank=e.rank,
            ))

        # Sort by rerank score descending
        scored.sort(key=lambda r: r.rerank_score, reverse=True)

        # 4. Duplicate detection — remove redundant items
        deduplicated = self._remove_redundant(scored)

        # 5. Budget optimization — respect max_evidence
        final = deduplicated[: self.config.max_evidence]

        # Assign final ranks
        for i, item in enumerate(final):
            item.final_rank = i + 1
            item.selection_reason = self._selection_reason(item, i, len(final))

        removed_count = input_count - len(final)

        metadata = RerankerMetadata(
            reranker_version=self.RERANKER_VERSION,
            input_count=input_count,
            output_count=len(final),
            removed_count=removed_count,
        )

        return final, metadata

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _combined_score(self, evidence: Evidence, query: "str | None") -> float:
        """Compute the combined reranking score.

        Combines:
            - Semantic relevance (evidence.score)
            - Diversity signal (based on query overlap)
            - Freshness signal (based on document status)
            - Authority signal (based on canonical references)

        The exact weights are configurable.
        """
        relevance = evidence.score

        # Lexical alignment is a positive relevance signal.  The previous
        # implementation rewarded *lack* of query overlap, which promoted
        # unrelated evidence for out-of-domain questions.
        lexical_alignment = 0.0
        if query and evidence.text:
            query_terms = set(re.findall(r"\w+", query.lower(), flags=re.UNICODE))
            text_terms = set(re.findall(r"\w+", evidence.text.lower(), flags=re.UNICODE))
            overlap = len(query_terms & text_terms)
            if query_terms:
                lexical_alignment = overlap / len(query_terms)

        # Freshness: prefer ACTIVE documents
        freshness = 1.0
        if evidence.source_anchor and evidence.source_anchor.canonical_reference:
            freshness = 1.0

        # Authority: prefer items with canonical references
        authority = 1.0
        if evidence.source_anchor and evidence.source_anchor.canonical_reference:
            authority = 1.1  # slight boost for cited items

        combined = (
            relevance * (1.0 - self.config.diversity_weight - self.config.freshness_weight - self.config.authority_weight)
            + lexical_alignment * self.config.diversity_weight
            + freshness * self.config.freshness_weight
            + authority * self.config.authority_weight
        )

        return round(combined, 4)

    def _remove_redundant(
        self, scored: list[RerankedEvidence]
    ) -> list[RerankedEvidence]:
        """Remove redundant (near-duplicate) evidence items.

        Only the same source node/text is redundant.  Distinct legal
        provisions from one document remain independently citable evidence.
        """
        if len(scored) <= 1:
            return scored

        result: list[RerankedEvidence] = []
        seen_sources: set[tuple[UUID, UUID, str]] = set()

        for item in scored:
            evidence = item.evidence
            source_key = (
                evidence.document_id,
                evidence.knowledge_node_id,
                " ".join(evidence.text.lower().split()),
            )
            if source_key in seen_sources:
                continue
            seen_sources.add(source_key)
            result.append(item)

        return result

    def _selection_reason(
        self, item: RerankedEvidence, index: int, total: int
    ) -> str:
        """Determine why an item was selected."""
        if index == 0:
            return "top_relevance"
        if item.evidence.source_anchor and item.evidence.source_anchor.canonical_reference:
            return "cited_authority"
        return "relevance"

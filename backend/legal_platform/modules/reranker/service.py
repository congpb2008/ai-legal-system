"""Reranker Service (tasks/010-reranker.md).

The Reranker Service orchestrates the reranking pipeline:
    1. Receives a RetrievalResult (from the Retrieval Service, Task 009).
    2. Runs the Reranker to score, deduplicate, and optimize candidates.
    3. Returns the reranked evidence set for the Generation Service (Task 011).

Per the spec:
    - The Retrieval Service prioritizes recall.
    - The Reranker prioritizes precision.
    - The Reranker does NOT retrieve new documents, generate answers,
      rewrite evidence, or modify Knowledge Trees.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from legal_platform.contracts.retrieval import RetrievalResult
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.reranker.reranker import (
    Reranker,
    RerankerConfig,
    RerankerMetadata,
    RerankedEvidence,
)
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.storage.eventlog import init_audit_log, log_event


class RerankerService:
    """The Reranker Service.

    Orchestrates reranking of retrieval candidates into a precision-focused
    evidence set for the Generation Service.

    Integrates with:
        - RetrievalService (Task 009) for retrieval results.
        - DocumentRegistry (Task 001) for audit logging.
        - Reranker (replaceable) for the actual scoring and ranking.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        retrieval_service: "RetrievalService | None" = None,
        reranker: "Reranker | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.retrieval_service = retrieval_service or RetrievalService(
            registry=self.registry,
        )
        self.reranker = reranker or Reranker()
        init_audit_log(self.registry.repo.conn)

    # ------------------------------------------------------------------
    # Rerank a RetrievalResult
    # ------------------------------------------------------------------

    def rerank(
        self,
        retrieval_result: RetrievalResult,
        *,
        query: "str | None" = None,
    ) -> tuple[list[RerankedEvidence], RerankerMetadata]:
        """Rerank the evidence in a RetrievalResult.

        Args:
            retrieval_result: the RetrievalResult from the Retrieval Service.
            query: the original query (used for diversity scoring).

        Returns:
            A tuple of (reranked evidence list, reranker metadata).
        """
        reranked, metadata = self.reranker.rerank(
            retrieval_result,
            query=query,
        )

        # Audit
        log_event(
            self.registry.repo.conn,
            service="reranker-service",
            module="reranker",
            event="reranker.complete",
            entity_type="query",
            entity_id=retrieval_result.query_id,
            severity="INFO",
            message=f"Reranking completed: {metadata.input_count} -> {metadata.output_count} items",
            metadata={
                "input_count": metadata.input_count,
                "output_count": metadata.output_count,
                "removed_count": metadata.removed_count,
                "reranker_version": metadata.reranker_version,
            },
        )

        return reranked, metadata

    # ------------------------------------------------------------------
    # Convenience: search + rerank
    # ------------------------------------------------------------------

    def search_and_rerank(
        self,
        query: str,
        *,
        vault_id: "UUID | None" = None,
        vault_ids: "set[UUID] | None" = None,
        document_id: "UUID | None" = None,
        top_k: int = 20,
        strategy: str = "HYBRID",
    ) -> tuple[list[RerankedEvidence], RerankerMetadata]:
        """Execute a search and rerank the results.

        This is a convenience method that combines search and reranking
        into a single call. The Retrieval Service retrieves more candidates
        (top_k * 2), and the Reranker selects the best final set.

        Args:
            query: the user's natural language query.
            vault_id: restrict search to a specific vault.
            vault_ids: authorized vault scope from the API boundary.
            document_id: restrict search to a specific document.
            top_k: number of candidates to retrieve from the index.

        Returns:
            A tuple of (reranked evidence list, reranker metadata).
        """
        # Retrieve more candidates for the reranker to work with
        retrieval_result = self.retrieval_service.search(
            query,
            vault_id=vault_id,
            vault_ids=vault_ids,
            document_id=document_id,
            top_k=top_k,
            strategy=strategy,
        )

        return self.rerank(retrieval_result, query=query)

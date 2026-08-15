"""Tests for the Reranker (Task 010).

Covers:
    - Reranking retrieval candidates
    - Scoring (relevance, diversity, freshness, authority)
    - Redundancy removal (deduplication)
    - Budget optimization (max evidence)
    - Weak candidate removal (min score)
    - Reranker metadata
    - Integration with Retrieval Service
    - Audit logging

The authoritative source is the Reranker specification (tasks/010-reranker.md).
"""

from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.contracts.retrieval import (
    Evidence,
    RetrievalResult,
    RetrievalStrategy,
    SourceAnchor,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.reranker.reranker import (
    Reranker,
    RerankerConfig,
    RerankedEvidence,
)
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vector_index.service import VectorIndexService
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def reranker():
    return Reranker()


@pytest.fixture
def reranker_service():
    registry = DocumentRegistry()
    retrieval = RetrievalService(
        registry=registry,
        vector_index=VectorIndexService(registry=registry),
        embedding_service=EmbeddingService(
            registry=registry,
            engine=PlaceholderEmbedder(),
        ),
    )
    return RerankerService(
        registry=registry,
        retrieval_service=retrieval,
    )


@pytest.fixture
def sample_result() -> RetrievalResult:
    """A RetrievalResult with several evidence items."""
    doc_a = new_id()
    doc_b = new_id()
    return RetrievalResult(
        query_id=new_id(),
        strategy=RetrievalStrategy.HYBRID,
        query="mua sắm máy chủ",
        evidence=[
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=doc_a,
                document_version_id=new_id(),
                score=0.95,
                rank=1,
                text="Điều 1. Phạm vi điều chỉnh mua sắm máy chủ",
                source_anchor=SourceAnchor(canonical_reference="Điều 1"),
            ),
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=doc_a,
                document_version_id=new_id(),
                score=0.90,
                rank=2,
                text="Điều 2. Đối tượng áp dụng quy chế mua sắm",
                source_anchor=SourceAnchor(canonical_reference="Điều 2"),
            ),
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=doc_b,
                document_version_id=new_id(),
                score=0.85,
                rank=3,
                text="Điều 3. Yêu cầu cấu hình máy chủ",
                source_anchor=SourceAnchor(canonical_reference="Điều 3"),
            ),
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=doc_b,
                document_version_id=new_id(),
                score=0.80,
                rank=4,
                text="Điều 4. Trách nhiệm phòng công nghệ thông tin",
                source_anchor=SourceAnchor(canonical_reference="Điều 4"),
            ),
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=doc_b,
                document_version_id=new_id(),
                score=0.10,
                rank=5,
                text="Điều 5. Quy trình thẩm định và phê duyệt",
                source_anchor=SourceAnchor(canonical_reference="Điều 5"),
            ),
        ],
    )


# ======================================================================
# 1. Basic Reranking
# ======================================================================


class TestBasicReranking:
    """Basic reranking behavior."""

    def test_rerank_returns_items(self, reranker, sample_result):
        reranked, metadata = reranker.rerank(sample_result)
        assert isinstance(reranked, list)
        assert all(isinstance(r, RerankedEvidence) for r in reranked)
        assert metadata.input_count == 5

    def test_rerank_removes_weak(self, reranker, sample_result):
        """Items below min_score should be removed."""
        reranked, metadata = reranker.rerank(sample_result)
        # The 0.10-score item should be removed
        assert len(reranked) < 5
        assert metadata.removed_count >= 1

    def test_rerank_respects_max_evidence(self, reranker, sample_result):
        """Output should not exceed max_evidence."""
        config = RerankerConfig(max_evidence=3)
        r = Reranker(config=config)
        reranked, metadata = r.rerank(sample_result)
        assert len(reranked) <= 3

    def test_rerank_assigns_final_ranks(self, reranker, sample_result):
        reranked, metadata = reranker.rerank(sample_result)
        ranks = [item.final_rank for item in reranked]
        assert ranks == sorted(ranks)
        assert ranks[0] == 1

    def test_rerank_preserves_distinct_nodes_from_same_document(self, reranker, sample_result):
        """Distinct provisions in one legal document remain citable."""
        reranked, metadata = reranker.rerank(sample_result)
        doc_ids = [item.evidence.document_id for item in reranked]
        assert len(doc_ids) > len(set(doc_ids))

    def test_rerank_removes_exact_source_duplicate(self, reranker, sample_result):
        original = sample_result.evidence[0]
        sample_result.evidence.append(original.model_copy(update={"id": new_id()}))
        reranked, metadata = reranker.rerank(sample_result)
        matching = [
            item for item in reranked
            if item.evidence.knowledge_node_id == original.knowledge_node_id
            and item.evidence.text == original.text
        ]
        assert len(matching) == 1


# ======================================================================
# 2. Scoring
# ======================================================================


class TestScoring:
    """Combined scoring (relevance, diversity, freshness, authority)."""

    def test_rerank_score_present(self, reranker, sample_result):
        reranked, _ = reranker.rerank(sample_result)
        for item in reranked:
            assert item.rerank_score > 0

    def test_highest_relevance_first(self, reranker, sample_result):
        """The highest-relevance item should be ranked first."""
        reranked, _ = reranker.rerank(sample_result)
        assert reranked[0].evidence.score >= reranked[-1].evidence.score

    def test_selection_reason(self, reranker, sample_result):
        reranked, _ = reranker.rerank(sample_result)
        for item in reranked:
            assert item.selection_reason in ("top_relevance", "cited_authority", "relevance")


# ======================================================================
# 3. Configuration
# ======================================================================


class TestConfiguration:
    """Reranker configuration."""

    def test_custom_min_score(self, sample_result):
        """Higher min_score removes more items."""
        config = RerankerConfig(min_score=0.85)
        r = Reranker(config=config)
        reranked, metadata = r.rerank(sample_result)
        # Only items with score >= 0.85 remain
        assert all(item.evidence.score >= 0.85 for item in reranked)

    def test_custom_max_evidence(self, sample_result):
        config = RerankerConfig(max_evidence=2)
        r = Reranker(config=config)
        reranked, metadata = r.rerank(sample_result)
        assert len(reranked) <= 2


# ======================================================================
# 4. Service Integration
# ======================================================================


class TestServiceIntegration:
    """RerankerService integration."""

    def test_rerank_service(self, reranker_service, sample_result):
        reranked, metadata = reranker_service.rerank(sample_result, query="mua sắm máy chủ")
        assert len(reranked) > 0
        assert metadata.input_count == 5

    def test_audit_logged(self, reranker_service, sample_result):
        reranked, metadata = reranker_service.rerank(sample_result)
        events = recent_events(
            reranker_service.registry.repo.conn,
            entity_id=str(sample_result.query_id),
        )
        rerank_events = [e for e in events if e["event"] == "reranker.complete"]
        assert len(rerank_events) >= 1

    def test_search_and_rerank(self, reranker_service):
        """End-to-end: search then rerank."""
        # This requires a populated index; test with empty index returns empty
        reranked, metadata = reranker_service.search_and_rerank(
            "máy chủ",
            vault_id=new_id(),
        )
        assert isinstance(reranked, list)
        assert metadata is not None


# ======================================================================
# 5. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_empty_result(self, reranker):
        result = RetrievalResult(
            query_id=new_id(),
            strategy=RetrievalStrategy.HYBRID,
            query="empty",
            evidence=[],
        )
        reranked, metadata = reranker.rerank(result)
        assert reranked == []
        assert metadata.input_count == 0
        assert metadata.output_count == 0

    def test_single_item(self, reranker):
        result = RetrievalResult(
            query_id=new_id(),
            strategy=RetrievalStrategy.HYBRID,
            query="single",
            evidence=[
                Evidence(
                    id=new_id(),
                    knowledge_node_id=new_id(),
                    document_id=new_id(),
                    document_version_id=new_id(),
                    score=0.9,
                    rank=1,
                    text="Single item",
                ),
            ],
        )
        reranked, metadata = reranker.rerank(result)
        assert len(reranked) == 1
        assert reranked[0].final_rank == 1

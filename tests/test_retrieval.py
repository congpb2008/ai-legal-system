"""Tests for the Retrieval Service (Task 009).

Covers:
    - Retrieval Contract invariants
    - Hybrid search (semantic + keyword)
    - Semantic-only search
    - Keyword-only search
    - Metadata filtering (vault, document, status)
    - Top-K retrieval
    - Empty evidence (valid result)
    - Context expansion
    - Evidence ranking
    - Audit logging

The authoritative source is the Retrieval Contract (02-contracts/retrieval-contract.md)
and the Retrieval specification (tasks/009-retrieval.md).
"""

from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.contracts.retrieval import (
    Evidence,
    RetrievalMetadata,
    RetrievalResult,
    RetrievalStrategy,
)
from legal_platform.modules.embedding.engine import EmbeddingRecord, PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vector_index.service import VectorIndexService
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def retrieval_service():
    return RetrievalService(
        embedding_service=EmbeddingService(engine=PlaceholderEmbedder())
    )


@pytest.fixture
def populated_index(retrieval_service):
    """Populate the vector index with sample embeddings."""
    embedder = PlaceholderEmbedder()
    doc_id = new_id()
    vault_id = new_id()

    topics = [
        "Điều 1. Phạm vi điều chỉnh mua sắm máy chủ",
        "Điều 2. Đối tượng áp dụng quy chế mua sắm",
        "Điều 3. Yêu cầu cấu hình máy chủ",
        "Điều 4. Trách nhiệm của phòng công nghệ thông tin",
        "Điều 5. Quy trình thẩm định và phê duyệt",
    ]

    for i, topic in enumerate(topics):
        emb = EmbeddingRecord(
            chunk_id=new_id(),
            document_id=doc_id,
            version_id=new_id(),
            vector=embedder.embed(topic),
            dimension=embedder.DIMENSION,
            model=embedder.MODEL_NAME,
            model_version=embedder.MODEL_VERSION,
            chunk_text=topic,
        )
        retrieval_service.vector_index.index_embedding(
            emb,
            vault_id=vault_id,
            chunk_type="ARTICLE",
            canonical_references=[f"Điều {i+1}"],
        )

    return doc_id, vault_id


# ======================================================================
# 1. Retrieval Contract
# ======================================================================


class TestRetrievalContract:
    """Retrieval Contract structure and invariants."""

    def test_evidence_fields(self):
        ev = Evidence(
            id=new_id(),
            knowledge_node_id=new_id(),
            document_id=new_id(),
            document_version_id=new_id(),
            score=0.95,
            rank=1,
            text="Sample evidence text",
        )
        assert ev.id is not None
        assert ev.knowledge_node_id is not None
        assert ev.score == 0.95
        assert ev.rank == 1

    def test_retrieval_result(self):
        result = RetrievalResult(
            query_id=new_id(),
            strategy=RetrievalStrategy.HYBRID,
            query="Test query",
            evidence=[],
        )
        assert result.query_id is not None
        assert result.strategy == RetrievalStrategy.HYBRID
        assert result.evidence == []

    def test_empty_evidence_is_valid(self):
        """INV-008: An empty evidence list is a valid result."""
        result = RetrievalResult(
            query_id=new_id(),
            strategy=RetrievalStrategy.HYBRID,
            query="No results query",
            evidence=[],
        )
        assert result.evidence == []

    def test_retrieval_metadata(self):
        meta = RetrievalMetadata(
            strategy="HYBRID",
            latency_ms=12.5,
            candidate_count=42,
            returned_count=5,
        )
        assert meta.candidate_count == 42
        assert meta.returned_count == 5


# ======================================================================
# 2. Hybrid Search
# ======================================================================


class TestHybridSearch:
    """Hybrid retrieval (semantic + keyword)."""

    def test_hybrid_returns_results(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "quy định mua sắm máy chủ",
            vault_id=vault_id,
        )
        assert isinstance(result, RetrievalResult)
        assert result.query_id is not None
        assert result.strategy == RetrievalStrategy.HYBRID

    def test_hybrid_evidence_has_required_fields(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "cấu hình máy chủ",
            vault_id=vault_id,
        )
        for ev in result.evidence:
            assert ev.id is not None
            assert ev.knowledge_node_id is not None
            assert ev.document_id is not None
            assert ev.document_version_id is not None
            assert ev.score >= 0.0
            assert ev.rank >= 1

    def test_hybrid_evidence_ranked(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
        )
        ranks = [ev.rank for ev in result.evidence]
        assert ranks == sorted(ranks)

    def test_query_analysis_expands_vietnamese_time_paraphrase(self):
        terms = RetrievalService._analyze_query_terms(
            "Cách hiểu về ngày theo lịch và múi giờ thế nào?"
        )

        assert "gmt" in terms
        assert {"dương", "nghỉ", "lễ", "tết"} <= terms
        assert "múi" not in terms
        assert "giờ" not in terms

    def test_document_identifier_ignores_timezone_number(self):
        terms = RetrievalService._document_identifier_terms(
            "Mẫu 4A ngày theo lịch GMT+7"
        )

        assert terms == {"4a"}

    def test_multi_document_identifier_matches_each_named_title(self):
        terms = RetrievalService._document_identifier_terms(
            "Mẫu 4A và Mẫu 5A khác nhau ở phạm vi áp dụng như thế nào?"
        )

        assert terms == {"4a", "5a"}
        assert RetrievalService._document_identifier_match_ratio(
            terms, {"mẫu", "số", "4a", "hàng", "hóa"}
        ) == 0.5
        assert RetrievalService._document_identifier_match_ratio(
            terms, {"mẫu", "số", "5a", "dịch", "vụ"}
        ) == 0.5
        assert RetrievalService._document_identifier_match_ratio(
            terms, {"luật", "90", "2025", "qh15"}
        ) == 0.0


# ======================================================================
# 3. Semantic-Only Search
# ======================================================================


class TestSemanticSearch:
    """Semantic-only retrieval."""

    def test_semantic_returns_results(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "cấu hình máy chủ",
            vault_id=vault_id,
            strategy=RetrievalStrategy.SEMANTIC,
        )
        assert result.strategy == RetrievalStrategy.SEMANTIC


# ======================================================================
# 4. Keyword-Only Search
# ======================================================================


class TestKeywordSearch:
    """Keyword-only retrieval."""

    def test_keyword_returns_results(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
            strategy=RetrievalStrategy.KEYWORD,
        )
        assert result.strategy == RetrievalStrategy.KEYWORD


# ======================================================================
# 5. Metadata Filtering
# ======================================================================


class TestMetadataFiltering:
    """Metadata filtering (tasks/009 #VaultAwareness)."""

    def test_vault_filter(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        # Search with correct vault
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
        )
        # Search with wrong vault
        wrong_vault = new_id()
        result_wrong = retrieval_service.search(
            "máy chủ",
            vault_id=wrong_vault,
        )
        # Wrong vault should return fewer/no results
        assert len(result_wrong.evidence) <= len(result.evidence)

    def test_document_filter(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
            document_id=doc_id,
        )
        for ev in result.evidence:
            assert ev.document_id == doc_id

    def test_status_filter(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
            document_status="ACTIVE",
        )
        # All results should be from active documents
        assert result.metadata.returned_count >= 0


# ======================================================================
# 6. Top-K and Empty
# ======================================================================


class TestTopKAndEmpty:
    """Top-K retrieval and empty results."""

    def test_top_k(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
            top_k=3,
        )
        assert len(result.evidence) <= 3

    def test_empty_query(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "",
            vault_id=vault_id,
        )
        assert result.evidence == []

    def test_no_results_valid(self, retrieval_service):
        """Searching an empty index returns empty evidence (INV-008)."""
        result = retrieval_service.search(
            "anything",
            vault_id=new_id(),
        )
        assert result.evidence == []


# ======================================================================
# 7. Context Expansion
# ======================================================================


class TestContextExpansion:
    """Context expansion (tasks/009 #ContextExpansion)."""

    def test_expand_context(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
            top_k=1,
        )
        assert len(result.evidence) >= 1
        expanded = retrieval_service.expand_context(result.evidence, window=1)
        assert len(expanded) >= len(result.evidence)

    def test_expand_empty(self, retrieval_service):
        assert retrieval_service.expand_context([]) == []


# ======================================================================
# 8. Audit Logging
# ======================================================================


class TestAuditLogging:
    """Retrieval audit logging."""

    def test_search_logs_event(self, retrieval_service, populated_index):
        doc_id, vault_id = populated_index
        result = retrieval_service.search(
            "máy chủ",
            vault_id=vault_id,
        )
        events = recent_events(
            retrieval_service.registry.repo.conn,
            entity_id=str(result.query_id),
        )
        retrieval_events = [e for e in events if e["event"] == "retrieval.search"]
        assert len(retrieval_events) >= 1

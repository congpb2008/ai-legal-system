"""Tests for the Vector Index (Task 008).

Covers:
    - Indexing embedding records
    - Similarity search
    - Metadata filtering (vault, document, status, chunk type, model, language)
    - Top-K retrieval
    - Threshold search
    - Index lifecycle (insert, delete, rebuild)
    - Bulk import
    - Cosine similarity correctness
    - Engine replaceability / derived datastore semantics

The authoritative source is the Vector Index specification (tasks/008-vector-index.md).
"""

from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.modules.embedding.engine import EmbeddingRecord, PlaceholderEmbedder
from legal_platform.modules.vector_index.index import (
    IndexEntry,
    SearchResult,
    SimilarityFunction,
    cosine_similarity,
)
from legal_platform.modules.vector_index.service import VectorIndexService


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def index_service():
    return VectorIndexService()


@pytest.fixture
def embedder():
    return PlaceholderEmbedder()


@pytest.fixture
def sample_embedding(embedder) -> EmbeddingRecord:
    return EmbeddingRecord(
        chunk_id=new_id(),
        document_id=new_id(),
        version_id=new_id(),
        vector=embedder.embed("Điều 1. Phạm vi điều chỉnh"),
        dimension=embedder.DIMENSION,
        model=embedder.MODEL_NAME,
        model_version=embedder.MODEL_VERSION,
        chunk_text="Điều 1. Phạm vi điều chỉnh",
    )


# ======================================================================
# 1. Cosine Similarity
# ======================================================================


class TestCosineSimilarity:
    """Cosine similarity correctness."""

    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_dimension_mismatch(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


# ======================================================================
# 2. Indexing
# ======================================================================


class TestIndexing:
    """Indexing embedding records."""

    def test_index_single(self, index_service, sample_embedding):
        entry = index_service.index_embedding(sample_embedding)
        assert entry is not None
        assert entry.embedding_id == sample_embedding.embedding_id
        assert entry.document_id == sample_embedding.document_id
        assert entry.dimension == sample_embedding.dimension

    def test_index_bulk(self, index_service, embedder):
        doc_id = new_id()
        embeddings = [
            EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Chunk {i}"), dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            for i in range(5)
        ]
        entries = index_service.index_embeddings(embeddings)
        assert len(entries) == 5

    def test_stats(self, index_service, sample_embedding):
        index_service.index_embedding(sample_embedding)
        stats = index_service.stats()
        assert stats["total_entries"] == 1
        assert stats["active_entries"] == 1


# ======================================================================
# 3. Search
# ======================================================================


class TestSearch:
    """Similarity search."""

    def test_search_returns_nearest(self, index_service, embedder):
        doc_id = new_id()
        # Index several embeddings
        for i in range(5):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Text about server procurement {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        # Query with a similar text
        query = embedder.embed("server procurement")
        results = index_service.search(query, top_k=3)
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)

    def test_search_ranks_by_score(self, index_service, embedder):
        doc_id = new_id()
        for i in range(3):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Topic {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        query = embedder.embed("Topic 1")
        results = index_service.search(query, top_k=3)
        # Scores should be descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_top_k(self, index_service, embedder):
        doc_id = new_id()
        for i in range(10):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Item {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        query = embedder.embed("Item")
        results = index_service.search(query, top_k=5)
        assert len(results) == 5

    def test_search_threshold(self, index_service, embedder):
        doc_id = new_id()
        for i in range(3):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Different topic {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        query = embedder.embed("Something completely unrelated")
        results = index_service.search(query, top_k=3, threshold=0.999)
        # With a high threshold, likely no results (placeholder vectors are hash-based)
        assert len(results) == 0


# ======================================================================
# 4. Metadata Filtering
# ======================================================================


class TestMetadataFiltering:
    """Metadata filtering (tasks/008 #MetadataFiltering)."""

    def test_filter_by_vault(self, index_service, embedder):
        doc_id = new_id()
        vault_a = new_id()
        vault_b = new_id()

        for vault in [vault_a, vault_b]:
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Content for {vault}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb, vault_id=vault)

        query = embedder.embed("Content")
        results_a = index_service.search(query, top_k=10, vault_id=vault_a)
        assert all(r.entry.vault_id == vault_a for r in results_a)

    def test_filter_by_document(self, index_service, embedder):
        doc_a = new_id()
        doc_b = new_id()
        for doc in [doc_a, doc_b]:
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc, version_id=new_id(),
                vector=embedder.embed(f"Doc {doc} content"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        query = embedder.embed("content")
        results = index_service.search(query, top_k=10, document_id=doc_a)
        assert all(r.entry.document_id == doc_a for r in results)

    def test_filter_by_status(self, index_service, embedder):
        doc_id = new_id()
        for status in ["ACTIVE", "ARCHIVED"]:
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Status {status}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb, document_status=status)

        query = embedder.embed("Status")
        results = index_service.search(query, top_k=10, document_status="ACTIVE")
        assert all(r.entry.document_status == "ACTIVE" for r in results)

    def test_filter_by_chunk_type(self, index_service, embedder):
        doc_id = new_id()
        for ct in ["ARTICLE", "CLAUSE"]:
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Type {ct}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb, chunk_type=ct)

        query = embedder.embed("Type")
        results = index_service.search(query, top_k=10, chunk_types=["ARTICLE"])
        assert all(r.entry.chunk_type == "ARTICLE" for r in results)

    def test_filter_by_model(self, index_service, embedder):
        doc_id = new_id()
        emb1 = EmbeddingRecord(
            chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
            vector=embedder.embed("Model A content"),
            dimension=embedder.DIMENSION, model="model-a", model_version="1.0",
        )
        emb2 = EmbeddingRecord(
            chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
            vector=embedder.embed("Model B content"),
            dimension=embedder.DIMENSION, model="model-b", model_version="1.0",
        )
        index_service.index_embedding(emb1)
        index_service.index_embedding(emb2)

        query = embedder.embed("content")
        results = index_service.search(query, top_k=10, model="model-a")
        assert all(r.entry.model == "model-a" for r in results)


# ======================================================================
# 5. Index Lifecycle
# ======================================================================


class TestIndexLifecycle:
    """Index lifecycle operations (tasks/008 #IndexLifecycle)."""

    def test_delete_entry(self, index_service, sample_embedding):
        entry = index_service.index_embedding(sample_embedding)
        assert index_service.delete_entry(entry.entry_id) is True
        assert index_service.delete_entry(entry.entry_id) is False

    def test_delete_document_entries(self, index_service, embedder):
        doc_id = new_id()
        for i in range(3):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Doc {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        deleted = index_service.delete_document_entries(doc_id)
        assert deleted == 3
        assert index_service.stats()["total_entries"] == 0

    def test_rebuild(self, index_service, embedder):
        doc_id = new_id()
        for i in range(3):
            emb = EmbeddingRecord(
                chunk_id=new_id(), document_id=doc_id, version_id=new_id(),
                vector=embedder.embed(f"Rebuild {i}"),
                dimension=embedder.DIMENSION,
                model=embedder.MODEL_NAME, model_version=embedder.MODEL_VERSION,
            )
            index_service.index_embedding(emb)

        # Simulate a fresh instance loading from persisted store
        index_service._entries.clear()
        count = index_service.rebuild()
        assert count == 3
        assert index_service.stats()["total_entries"] == 3

    def test_rebuild_preserves_source_pages(self, index_service, sample_embedding):
        entry = index_service.index_embedding(
            sample_embedding,
            page_start=7,
            page_end=9,
        )
        index_service._entries.clear()

        assert index_service.rebuild() == 1
        restored = index_service._entries[entry.entry_id]
        assert restored.page_start == 7
        assert restored.page_end == 9


# ======================================================================
# 6. Similarity Function
# ======================================================================


class TestSimilarityFunction:
    """Similarity function dispatch."""

    def test_cosine(self):
        score = SimilarityFunction.compute("cosine", [1.0, 0.0], [1.0, 0.0])
        assert score == pytest.approx(1.0)

    def test_dot(self):
        score = SimilarityFunction.compute("dot", [1.0, 2.0], [3.0, 4.0])
        assert score == pytest.approx(11.0)

    def test_euclidean(self):
        score = SimilarityFunction.compute("euclidean", [0.0, 0.0], [0.0, 0.0])
        assert score == pytest.approx(1.0)

    def test_unknown(self):
        with pytest.raises(ValueError):
            SimilarityFunction.compute("unknown", [1.0], [1.0])

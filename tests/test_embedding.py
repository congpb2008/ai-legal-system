"""Tests for the Embedding Service (Task 007).

Covers:
    - Embedding generation from chunks
    - Embedding metadata (model, version, dimension)
    - Embedding persistence and retrieval
    - Batch embedding
    - Versioning / staleness detection
    - Error handling (empty text, dimension mismatch)
    - Engine replaceability

The authoritative source is the Embedding specification (tasks/007-embedding.md).
"""

import json
import urllib.error
from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.modules.chunking.chunker import (
    Chunk,
    ChunkCollection,
    ChunkType,
)
from legal_platform.modules.embedding.engine import (
    EmbeddingEngineError,
    EmbeddingRecord,
    OllamaEmbeddingEngine,
    PlaceholderEmbedder,
)
from legal_platform.modules.embedding.service import EmbeddingService


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def embedding_service():
    return EmbeddingService(engine=PlaceholderEmbedder())


@pytest.fixture
def placeholder_embedder():
    return PlaceholderEmbedder()


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        chunk_id=new_id(),
        document_id=new_id(),
        version_id=new_id(),
        chunk_type=ChunkType.ARTICLE,
        text="Điều 1. Phạm vi điều chỉnh\nQuy chế này quy định việc mua sắm máy chủ.",
        estimated_tokens=20,
        hierarchy_path="1.1",
        page_start=1,
        page_end=1,
    )


@pytest.fixture
def sample_collection(sample_chunk) -> ChunkCollection:
    chunk2 = Chunk(
        chunk_id=new_id(),
        document_id=sample_chunk.document_id,
        version_id=sample_chunk.version_id,
        chunk_type=ChunkType.CLAUSE,
        text="1. Áp dụng đối với toàn bộ đơn vị trực thuộc Khối Công nghệ Thông tin.",
        estimated_tokens=15,
        hierarchy_path="1.1.1",
        page_start=1,
        page_end=1,
    )
    return ChunkCollection(
        chunks=[sample_chunk, chunk2],
        document_id=sample_chunk.document_id,
        version_id=sample_chunk.version_id,
    )


# ======================================================================
# 1. Placeholder Embedder
# ======================================================================


class TestPlaceholderEmbedder:
    """Placeholder embedding engine."""

    def test_embed_returns_vector(self, placeholder_embedder):
        vector = placeholder_embedder.embed("Hello world")
        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)

    def test_embed_dimension(self, placeholder_embedder):
        vector = placeholder_embedder.embed("Test text")
        assert len(vector) == placeholder_embedder.DIMENSION

    def test_embed_deterministic(self, placeholder_embedder):
        """Same text should produce same vector."""
        v1 = placeholder_embedder.embed("Same text")
        v2 = placeholder_embedder.embed("Same text")
        assert v1 == v2

    def test_embed_normalized(self, placeholder_embedder):
        """Vector should be unit-normalized."""
        vector = placeholder_embedder.embed("Test")
        magnitude = sum(v * v for v in vector) ** 0.5
        assert abs(magnitude - 1.0) < 0.01

    def test_embed_empty_raises(self, placeholder_embedder):
        with pytest.raises(EmbeddingEngineError):
            placeholder_embedder.embed("")

    def test_embed_batch(self, placeholder_embedder):
        vectors = placeholder_embedder.embed_batch(["one", "two", "three"])
        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)


class _JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class TestOllamaEmbeddingEngine:
    """Native Ollama integration validates model and vector contracts."""

    def test_uses_native_api_and_persists_digest(self, monkeypatch):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            if request.full_url.endswith("/api/tags"):
                return _JsonResponse({
                    "models": [{"name": "test-embed:latest", "digest": "sha256:test"}]
                })
            assert request.full_url.endswith("/api/embed")
            body = json.loads(request.data)
            assert body == {
                "model": "test-embed:latest",
                "input": ["một", "hai"],
                "truncate": False,
            }
            return _JsonResponse({"embeddings": [[1, 0, 0], [0, 1, 0]]})

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        engine = OllamaEmbeddingEngine(
            base_url="https://ollama.example/v1",
            model="test-embed:latest",
            api_key="compatibility-value",
            expected_dimension=3,
        )
        vectors = engine.embed_batch(["một", "hai"])

        assert vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        assert engine.MODEL_VERSION == "sha256:test"
        assert engine.DIMENSION == 3
        assert [r.full_url for r, _ in requests] == [
            "https://ollama.example/api/tags",
            "https://ollama.example/api/embed",
        ]
        assert requests[0][0].get_header("Authorization") == (
            "Bearer compatibility-value"
        )

    def test_missing_model_is_observable(self, monkeypatch):
        monkeypatch.setattr(
            "urllib.request.urlopen",
            lambda *_args, **_kwargs: _JsonResponse({"models": []}),
        )
        engine = OllamaEmbeddingEngine(
            base_url="http://ollama.example",
            model="missing:latest",
        )
        with pytest.raises(EmbeddingEngineError, match="not available"):
            engine.embed("legal text")

    def test_dimension_mismatch_is_rejected(self, monkeypatch):
        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/api/tags"):
                return _JsonResponse({
                    "models": [{"name": "test:latest", "digest": "digest"}]
                })
            return _JsonResponse({"embeddings": [[1.0, 2.0]]})

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        engine = OllamaEmbeddingEngine(
            base_url="http://ollama.example",
            model="test:latest",
            expected_dimension=3,
        )
        with pytest.raises(EmbeddingEngineError, match="dimension mismatch"):
            engine.embed("legal text")

    def test_backend_failure_does_not_expose_key(self, monkeypatch):
        def fail(*_args, **_kwargs):
            raise urllib.error.URLError("private transport detail")

        monkeypatch.setattr("urllib.request.urlopen", fail)
        engine = OllamaEmbeddingEngine(
            base_url="http://ollama.example",
            model="test:latest",
            api_key="never-report-this",
        )
        with pytest.raises(EmbeddingEngineError) as exc_info:
            engine.embed("legal text")
        assert "never-report-this" not in str(exc_info.value)


# ======================================================================
# 2. Embedding Service — Single Chunk
# ======================================================================


class TestEmbedSingleChunk:
    """Embedding a single chunk."""

    def test_embed_chunk(self, embedding_service, sample_chunk):
        record = embedding_service.embed_chunk(sample_chunk)
        assert record is not None
        assert record.chunk_id == sample_chunk.chunk_id
        assert record.document_id == sample_chunk.document_id
        assert record.dimension == 384
        assert record.model == "placeholder"
        assert len(record.vector) == 384

    def test_embed_chunk_persists(self, embedding_service, sample_chunk):
        record = embedding_service.embed_chunk(sample_chunk)
        retrieved = embedding_service.get_embedding(record.embedding_id)
        assert retrieved is not None
        assert retrieved.embedding_id == record.embedding_id
        assert retrieved.vector == record.vector

    def test_embed_chunk_metadata(self, embedding_service, sample_chunk):
        record = embedding_service.embed_chunk(sample_chunk)
        assert record.chunk_text == sample_chunk.text
        assert record.status == "ACTIVE"


# ======================================================================
# 3. Embedding Service — Collection
# ======================================================================


class TestEmbedCollection:
    """Embedding a chunk collection."""

    def test_embed_collection(self, embedding_service, sample_collection):
        collection = embedding_service.embed_collection(sample_collection)
        assert collection.total_embeddings == 2
        assert collection.model == "placeholder"

    def test_embed_collection_persists(self, embedding_service, sample_collection):
        collection = embedding_service.embed_collection(sample_collection)
        # Verify each embedding is retrievable
        for record in collection.embeddings:
            retrieved = embedding_service.get_embedding(record.embedding_id)
            assert retrieved is not None

    def test_embed_collection_audit(self, embedding_service, sample_collection):
        from legal_platform.storage.eventlog import recent_events
        embedding_service.embed_collection(sample_collection)
        events = recent_events(
            embedding_service.registry.repo.conn,
            entity_id=str(sample_collection.document_id),
        )
        embed_events = [e for e in events if e["event"] == "embedding.complete"]
        assert len(embed_events) >= 1


# ======================================================================
# 4. Retrieval
# ======================================================================


class TestEmbeddingRetrieval:
    """Embedding retrieval operations."""

    def test_get_embeddings_for_chunk(self, embedding_service, sample_chunk):
        embedding_service.embed_chunk(sample_chunk)
        records = embedding_service.get_embeddings_for_chunk(sample_chunk.chunk_id)
        assert len(records) >= 1

    def test_get_embeddings_for_document(self, embedding_service, sample_collection):
        embedding_service.embed_collection(sample_collection)
        records = embedding_service.get_embeddings_for_document(sample_collection.document_id)
        assert len(records) >= 1

    def test_get_nonexistent(self, embedding_service):
        assert embedding_service.get_embedding(new_id()) is None


# ======================================================================
# 5. Versioning / Staleness
# ======================================================================


class TestEmbeddingVersioning:
    """Embedding versioning and staleness (tasks/007 #Versioning)."""

    def test_mark_stale(self, embedding_service, sample_chunk):
        embedding_service.embed_chunk(sample_chunk)
        count = embedding_service.mark_stale(sample_chunk.document_id, model="new-model")
        # The placeholder model embeddings should be marked stale
        assert count >= 1

    def test_detect_outdated(self, embedding_service, sample_chunk):
        embedding_service.embed_chunk(sample_chunk)
        outdated = embedding_service.detect_outdated(
            sample_chunk.document_id,
            current_model="new-model",
            current_model_version="2.0.0",
        )
        assert len(outdated) >= 1

    def test_no_outdated_when_current(self, embedding_service, sample_chunk):
        embedding_service.embed_chunk(sample_chunk)
        outdated = embedding_service.detect_outdated(
            sample_chunk.document_id,
            current_model="placeholder",
            current_model_version="1.0.0",
        )
        assert len(outdated) == 0


# ======================================================================
# 6. Engine Replaceability
# ======================================================================


class TestEngineReplaceability:
    """Embedding engine is replaceable (architecture.md)."""

    def test_custom_engine(self, sample_collection):
        """A custom engine with different dimension should work."""
        class CustomEngine:
            MODEL_NAME = "custom"
            MODEL_VERSION = "1.0.0"
            DIMENSION = 128

            def embed(self, text):
                return [0.1] * self.DIMENSION

            def embed_batch(self, texts):
                return [[0.1] * self.DIMENSION for _ in texts]

        svc = EmbeddingService(engine=CustomEngine())
        collection = svc.embed_collection(sample_collection)
        assert collection.total_embeddings == 2
        assert collection.model == "custom"
        assert collection.embeddings[0].dimension == 128

    def test_engine_replaceable_without_service_change(self, sample_collection):
        """Swapping the engine should not require changing the service."""
        class AnotherEngine:
            MODEL_NAME = "another"
            MODEL_VERSION = "2.0.0"
            DIMENSION = 256

            def embed(self, text):
                return [0.5] * self.DIMENSION

            def embed_batch(self, texts):
                return [[0.5] * self.DIMENSION for _ in texts]

        svc = EmbeddingService(engine=AnotherEngine())
        collection = svc.embed_collection(sample_collection)
        assert collection.model == "another"
        assert collection.model_version == "2.0.0"
        assert collection.embeddings[0].dimension == 256

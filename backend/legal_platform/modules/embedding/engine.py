"""Embedding engine abstraction (tasks/007-embedding.md).

The embedding engine is replaceable (architecture.md Replaceability). The
``EmbeddingEngine`` Protocol defines the interface; concrete implementations
handle vector generation.

Available implementations:
    - ``OllamaEmbeddingEngine``: native Ollama ``/api/embed`` integration used
      by the application runtime.
    - ``PlaceholderEmbedder``: deterministic hash-based test double only.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc
from legal_platform.modules.chunking.chunker import Chunk


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class EmbeddingRecord:
    """A single embedding vector with metadata."""

    embedding_id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    vector: list[float] = field(default_factory=list)
    dimension: int = 0
    model: str = "unknown"
    model_version: str = "0.0.0"
    chunk_text: str = ""
    knowledge_tree_version: str = ""
    created_at: datetime = field(default_factory=now_utc)
    status: str = "ACTIVE"


@dataclass
class EmbeddingCollection:
    """A collection of embeddings for one document version."""

    embeddings: list[EmbeddingRecord] = field(default_factory=list)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    model: str = "unknown"
    model_version: str = "0.0.0"
    created_at: datetime = field(default_factory=now_utc)

    @property
    def total_embeddings(self) -> int:
        return len(self.embeddings)


# ---------------------------------------------------------------------------
# Engine Protocol
# ---------------------------------------------------------------------------


class EmbeddingEngineError(RuntimeError):
    """Raised when embedding generation fails."""


class EmbeddingEngine(Protocol):
    """Abstract embedding engine.

    All implementations must:
        - Accept chunk text and return vectors.
        - Produce vectors of consistent dimension.
        - Raise ``EmbeddingEngineError`` on failure.
        - Be replaceable without changing the Embedding Service.
    """

    MODEL_NAME: str = "unknown"
    MODEL_VERSION: str = "0.0.0"
    DIMENSION: int = 0

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text string.

        Args:
            text: the text to embed.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            EmbeddingEngineError: if embedding fails.
        """
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for a batch of texts.

        The default implementation calls ``embed`` for each text.
        Subclasses should override for batched inference performance.
        """
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# Native Ollama embedder (runtime)
# ---------------------------------------------------------------------------


class OllamaEmbeddingEngine:
    """Embedding engine backed by Ollama's native ``/api/embed`` endpoint.

    Model availability and digest are verified against ``/api/tags`` once per
    engine instance.  The response dimension is validated on every request so
    an incompatible model/configuration can never be mixed into an active index.
    """

    DEFAULT_MODEL = "bge-m3:567m-fp16"
    KNOWN_DIMENSIONS = {
        "bge-m3:567m-fp16": 1024,
        "nomic-embed-text-v2-moe:latest": 768,
    }

    def __init__(
        self,
        *,
        base_url: str,
        model: str = DEFAULT_MODEL,
        api_key: str = "",
        timeout_seconds: float = 60.0,
        expected_dimension: "int | None" = None,
    ):
        base_url = base_url.strip().rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Ollama embedding base_url must use http:// or https://")
        if not model.strip():
            raise ValueError("Ollama embedding model is required")
        if timeout_seconds <= 0:
            raise ValueError("Ollama embedding timeout must be positive")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.MODEL_NAME = model.strip()
        self.MODEL_VERSION = "unverified"
        self.DIMENSION = expected_dimension or self.KNOWN_DIMENSIONS.get(
            self.MODEL_NAME, 0
        )
        self._metadata_verified = False

    @classmethod
    def from_environment(cls) -> "OllamaEmbeddingEngine":
        """Build an engine from explicit runtime configuration.

        ``LEGAL_PLATFORM_EMBEDDING_BASE_URL`` may be either an Ollama root URL
        or its OpenAI-compatible ``/v1`` URL; embedding always uses the native
        endpoint because it exposes batching and model metadata consistently.
        """
        base_url = os.environ.get(
            "LEGAL_PLATFORM_EMBEDDING_BASE_URL",
            os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
        model = os.environ.get("LEGAL_PLATFORM_EMBEDDING_MODEL", cls.DEFAULT_MODEL)
        api_key = os.environ.get(
            "LEGAL_PLATFORM_EMBEDDING_API_KEY",
            os.environ.get("OLLAMA_API_KEY", ""),
        )
        try:
            timeout = float(os.environ.get("LEGAL_PLATFORM_EMBEDDING_TIMEOUT", "60"))
        except ValueError as exc:
            raise ValueError(
                "LEGAL_PLATFORM_EMBEDDING_TIMEOUT must be a number"
            ) from exc
        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout,
        )

    def embed(self, text: str) -> list[float]:
        """Embed one non-empty string."""
        vectors = self.embed_batch([text])
        return vectors[0]

    def verify_configuration(self) -> None:
        """Verify model availability and populate its immutable digest."""
        self._verify_model_metadata()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch without truncating legal source text."""
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingEngineError("Cannot embed empty text")

        self._verify_model_metadata()
        data = self._request_json(
            "/api/embed",
            payload={
                "model": self.MODEL_NAME,
                "input": texts,
                "truncate": False,
            },
        )
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise EmbeddingEngineError(
                "Ollama returned an invalid embedding batch response"
            )
        if any(
            not isinstance(vector, list)
            or not vector
            or any(not isinstance(value, (int, float)) for value in vector)
            for vector in vectors
        ):
            raise EmbeddingEngineError("Ollama returned an invalid embedding vector")

        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise EmbeddingEngineError(
                f"Ollama returned inconsistent embedding dimensions: {dimensions}"
            )
        dimension = dimensions.pop()
        if self.DIMENSION and dimension != self.DIMENSION:
            raise EmbeddingEngineError(
                f"Embedding dimension mismatch for {self.MODEL_NAME}: "
                f"expected {self.DIMENSION}, got {dimension}"
            )
        self.DIMENSION = dimension
        return [[float(value) for value in vector] for vector in vectors]

    def _verify_model_metadata(self) -> None:
        if self._metadata_verified:
            return
        data = self._request_json("/api/tags")
        models = data.get("models")
        if not isinstance(models, list):
            raise EmbeddingEngineError("Ollama returned an invalid model catalog")
        match = next(
            (item for item in models if item.get("name") == self.MODEL_NAME),
            None,
        )
        if match is None:
            raise EmbeddingEngineError(
                f"Embedding model '{self.MODEL_NAME}' is not available on Ollama"
            )
        digest = match.get("digest")
        if not isinstance(digest, str) or not digest:
            raise EmbeddingEngineError(
                f"Ollama did not report a digest for '{self.MODEL_NAME}'"
            )
        self.MODEL_VERSION = digest
        self._metadata_verified = True

    def _request_json(
        self,
        path: str,
        *,
        payload: "dict | None" = None,
    ) -> dict:
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.base_url + path,
            data=(json.dumps(payload).encode("utf-8") if payload is not None else None),
            headers=headers,
            method="POST" if payload is not None else "GET",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise EmbeddingEngineError(
                f"Ollama embedding request failed with HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            raise EmbeddingEngineError(
                "Ollama embedding backend is unavailable"
            ) from exc
        except OSError as exc:
            raise EmbeddingEngineError(
                "Ollama embedding request failed"
            ) from exc
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise EmbeddingEngineError(
                "Ollama embedding backend returned invalid JSON"
            ) from exc
        if not isinstance(data, dict):
            raise EmbeddingEngineError(
                "Ollama embedding backend returned an invalid response"
            )
        return data


# ---------------------------------------------------------------------------
# Placeholder embedder (deterministic, for MVP/testing)
# ---------------------------------------------------------------------------


class LocalKeywordEmbedder:
    """Lexical feature hashing for offline ingestion; never labelled semantic AI."""
    MODEL_NAME = 'local-keyword'
    MODEL_VERSION = '1'
    DIMENSION = 384

    def embed(self, text):
        import re
        vector = [0.0] * self.DIMENSION
        for token in re.findall(r'\w+', text.lower()):
            key = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(key[:4], 'big') % self.DIMENSION] += 1.0
        length = sum(v*v for v in vector) ** 0.5
        return [v / length for v in vector] if length else vector

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]

    def verify_configuration(self):
        return None


class PlaceholderEmbedder:
    """Deterministic hash-based embedder for MVP development.

    Produces 384-dimensional vectors from SHA-256 hashes of the input text.
    This is **not suitable for semantic search** — it produces deterministic
    but meaningless vectors. Its purpose is to validate the embedding pipeline
    end-to-end without requiring GPU or model downloads.

    Replace with a real embedding model (e.g., sentence-transformers) for
    production use.
    """

    MODEL_NAME = "placeholder"
    MODEL_VERSION = "1.0.0"
    DIMENSION = 384

    def embed(self, text: str) -> list[float]:
        """Generate a deterministic 384-dim vector from text.

        Uses SHA-256 of the text to seed a deterministic vector.
        The vector is normalized to unit length.
        """
        if not text:
            raise EmbeddingEngineError("Cannot embed empty text")

        # Generate deterministic bytes from the text
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

        # Expand to 384 dimensions by hashing multiple times
        vector: list[float] = []
        seed = hash_bytes
        while len(vector) < self.DIMENSION:
            seed = hashlib.sha256(seed).digest()
            for b in seed:
                # Map byte 0-255 to float -1.0 to 1.0
                vector.append((b / 127.5) - 1.0)
                if len(vector) >= self.DIMENSION:
                    break

        vector = vector[: self.DIMENSION]

        # Normalize to unit length
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embed multiple texts."""
        return [self.embed(t) for t in texts]

    def verify_configuration(self) -> None:
        """Test-double compatibility with the runtime engine contract."""
        return None

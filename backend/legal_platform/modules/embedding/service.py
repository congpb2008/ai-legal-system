"""Embedding Service (tasks/007-embedding.md).

The Embedding Service orchestrates the embedding pipeline:
    1. Receives a ChunkCollection (from the Chunking Service, Task 006).
    2. Renders each chunk into embedding text.
    3. Generates embedding vectors via the embedding engine.
    4. Attaches metadata and versions.
    5. Stores the embeddings.
    6. Returns the EmbeddingCollection.

Per the spec:
    - Every retrieval chunk should have one corresponding embedding.
    - Embeddings are treated as derived data (ADR-003).
    - The Knowledge Tree remains the source of truth.
    - The embedding engine is replaceable.
    - Re-embedding should not interrupt retrieval.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import utc_iso
from legal_platform.modules.chunking.chunker import Chunk, ChunkCollection
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import (
    EmbeddingCollection,
    EmbeddingEngine,
    EmbeddingEngineError,
    EmbeddingRecord,
    OllamaEmbeddingEngine,
)
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# Embedding storage (disposable per ADR-003)
# ---------------------------------------------------------------------------

_EMBEDDING_DDL = """
CREATE TABLE IF NOT EXISTS embedding (
    embedding_id        TEXT PRIMARY KEY,
    chunk_id            TEXT NOT NULL,
    document_id         TEXT NOT NULL,
    version_id          TEXT NOT NULL,
    dimension           INTEGER NOT NULL,
    model               TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    knowledge_tree_version TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at          TEXT NOT NULL,
    vector_json         TEXT NOT NULL,
    chunk_text          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_embedding_chunk     ON embedding(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embedding_document  ON embedding(document_id);
CREATE INDEX IF NOT EXISTS idx_embedding_version   ON embedding(version_id);
CREATE INDEX IF NOT EXISTS idx_embedding_model     ON embedding(model);
"""


class EmbeddingService:
    """The Embedding Service.

    Orchestrates embedding generation for retrieval chunks.
    Integrates with:
        - ChunkingService (Task 006) for chunk collections.
        - DocumentRegistry (Task 001) for audit logging.
        - EmbeddingEngine (replaceable) for vector generation.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        engine: "EmbeddingEngine | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.engine = engine or OllamaEmbeddingEngine.from_environment()
        # Ensure embedding table + audit table exist
        init_audit_log(self.registry.repo.conn)
        self.registry.repo.conn.executescript(_EMBEDDING_DDL)
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Embed a chunk collection
    # ------------------------------------------------------------------

    def embed_collection(self, collection: ChunkCollection) -> EmbeddingCollection:
        """Generate embeddings for all chunks in a collection.

        Args:
            collection: the chunk collection to embed.

        Returns:
            An ``EmbeddingCollection`` with one embedding per chunk.

        Raises:
            EmbeddingEngineError: if embedding generation fails.
        """
        records: list[EmbeddingRecord] = []
        texts = [c.text for c in collection.chunks]

        # Batch embed all texts
        try:
            vectors = self.engine.embed_batch(texts)
        except EmbeddingEngineError:
            raise

        # Validate dimension consistency
        dims = {len(v) for v in vectors}
        if len(dims) > 1:
            raise EmbeddingEngineError(
                f"Inconsistent embedding dimensions: {dims}. "
                "All embeddings must have the same dimension."
            )
        dimension = dims.pop() if dims else 0

        # Build records
        for chunk, vector in zip(collection.chunks, vectors):
            record = EmbeddingRecord(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                version_id=chunk.version_id,
                vector=vector,
                dimension=dimension,
                model=self.engine.MODEL_NAME,
                model_version=self.engine.MODEL_VERSION,
                chunk_text=chunk.text,
                knowledge_tree_version=collection.chunker_version,
            )
            records.append(record)
            self._store_record(record)

        embedding_collection = EmbeddingCollection(
            embeddings=records,
            document_id=collection.document_id,
            version_id=collection.version_id,
            model=self.engine.MODEL_NAME,
            model_version=self.engine.MODEL_VERSION,
        )

        # Audit
        log_event(
            self.registry.repo.conn,
            service="embedding-service",
            module="embedding",
            event="embedding.complete",
            entity_type="document",
            entity_id=collection.document_id,
            severity="INFO",
            message=f"Embedding completed: {len(records)} embeddings",
            metadata={
                "total_embeddings": len(records),
                "model": self.engine.MODEL_NAME,
                "model_version": self.engine.MODEL_VERSION,
                "dimension": dimension,
            },
        )

        return embedding_collection

    # ------------------------------------------------------------------
    # Embed a single chunk
    # ------------------------------------------------------------------

    def embed_chunk(self, chunk: Chunk) -> EmbeddingRecord:
        """Generate an embedding for a single chunk.

        Args:
            chunk: the chunk to embed.

        Returns:
            An ``EmbeddingRecord``.
        """
        try:
            vector = self.engine.embed(chunk.text)
        except EmbeddingEngineError:
            raise

        record = EmbeddingRecord(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            version_id=chunk.version_id,
            vector=vector,
            dimension=len(vector),
            model=self.engine.MODEL_NAME,
            model_version=self.engine.MODEL_VERSION,
            chunk_text=chunk.text,
        )
        self._store_record(record)
        return record

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store_record(self, record: EmbeddingRecord) -> None:
        """Persist an embedding record (disposable per ADR-003)."""
        self.registry.repo.conn.execute(
            """
            INSERT OR REPLACE INTO embedding
                (embedding_id, chunk_id, document_id, version_id, dimension,
                 model, model_version, knowledge_tree_version, status, created_at,
                 vector_json, chunk_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(record.embedding_id),
                str(record.chunk_id),
                str(record.document_id),
                str(record.version_id),
                record.dimension,
                record.model,
                record.model_version,
                record.knowledge_tree_version,
                record.status,
                utc_iso(record.created_at),
                json.dumps(record.vector),
                record.chunk_text,
            ),
        )
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_embedding(self, embedding_id: UUID) -> Optional[EmbeddingRecord]:
        """Retrieve an embedding by its ID."""
        row = self.registry.repo.conn.execute(
            "SELECT * FROM embedding WHERE embedding_id = ?",
            (str(embedding_id),),
        ).fetchone()
        if row is None:
            return None
        return self._record_from_row(row)

    def get_embeddings_for_chunk(self, chunk_id: UUID) -> list[EmbeddingRecord]:
        """Retrieve all embeddings for a chunk."""
        rows = self.registry.repo.conn.execute(
            "SELECT * FROM embedding WHERE chunk_id = ? ORDER BY created_at DESC",
            (str(chunk_id),),
        )
        return [self._record_from_row(r) for r in rows]

    def get_embeddings_for_document(self, document_id: UUID) -> list[EmbeddingRecord]:
        """Retrieve all embeddings for a document."""
        rows = self.registry.repo.conn.execute(
            "SELECT * FROM embedding WHERE document_id = ? ORDER BY created_at DESC",
            (str(document_id),),
        )
        return [self._record_from_row(r) for r in rows]

    def get_active_embeddings(
        self,
        document_id: UUID,
        *,
        version_id: UUID,
        model: str,
        model_version: str,
    ) -> list[EmbeddingRecord]:
        """Return the active, exact-model embeddings for one document version."""
        rows = self.registry.repo.conn.execute(
            """
            SELECT * FROM embedding
            WHERE document_id = ? AND version_id = ? AND status = 'ACTIVE'
              AND model = ? AND model_version = ?
            ORDER BY created_at ASC
            """,
            (str(document_id), str(version_id), model, model_version),
        )
        return [self._record_from_row(row) for row in rows]

    @staticmethod
    def _record_from_row(row: Any) -> EmbeddingRecord:
        """Reconstruct an EmbeddingRecord from a DB row."""
        return EmbeddingRecord(
            embedding_id=UUID(row["embedding_id"]),
            chunk_id=UUID(row["chunk_id"]),
            document_id=UUID(row["document_id"]),
            version_id=UUID(row["version_id"]),
            vector=json.loads(row["vector_json"]),
            dimension=row["dimension"],
            model=row["model"],
            model_version=row["model_version"],
            chunk_text=row["chunk_text"],
            knowledge_tree_version=row["knowledge_tree_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
        )

    # ------------------------------------------------------------------
    # Versioning / staleness
    # ------------------------------------------------------------------

    def mark_stale(self, document_id: UUID, *, model: str) -> int:
        """Mark embeddings for a document as STALE when the model changes.

        Returns the number of embeddings marked stale.
        """
        cur = self.registry.repo.conn.execute(
            """
            UPDATE embedding SET status = 'STALE'
            WHERE document_id = ? AND model != ? AND status = 'ACTIVE'
            """,
            (str(document_id), model),
        )
        self.registry.repo.conn.commit()
        return cur.rowcount

    def mark_document_stale(self, document_id: UUID) -> int:
        """Deactivate every current embedding before a controlled rebuild."""
        cur = self.registry.repo.conn.execute(
            """
            UPDATE embedding SET status = 'STALE'
            WHERE document_id = ? AND status = 'ACTIVE'
            """,
            (str(document_id),),
        )
        self.registry.repo.conn.commit()
        return cur.rowcount

    def detect_outdated(
        self, document_id: UUID, current_model: str, current_model_version: str
    ) -> list[EmbeddingRecord]:
        """Detect embeddings that use an outdated model version.

        Returns embeddings whose model/version differs from the current one.
        """
        rows = self.registry.repo.conn.execute(
            """
            SELECT * FROM embedding
            WHERE document_id = ?
              AND (model != ? OR model_version != ?)
              AND status = 'ACTIVE'
            """,
            (str(document_id), current_model, current_model_version),
        )
        return [self._record_from_row(r) for r in rows]

"""Vector Index Service (tasks/008-vector-index.md).

The Vector Index Service stores and searches embedding vectors with metadata
filtering. It is a derived datastore (ADR-003) — the Knowledge Tree is the
system of record.

The MVP implementation uses an in-memory index (list-based brute-force search).
A production deployment should swap in a proper vector database (Qdrant,
Pinecone, pgvector, etc.) by implementing the same interface.

Per the spec:
    - Required search capabilities: Nearest Neighbor, Metadata Filtering,
      Top-K Retrieval, Threshold Search, Document Filtering, Vault Filtering,
      Version Filtering.
    - Index lifecycle: Insert, Update, Delete, Rebuild, Bulk Import, Bulk Delete.
    - Multiple embedding versions may temporarily coexist; only one active.
    - The index is eventually consistent; Knowledge Tree is authoritative.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import utc_iso
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import EmbeddingRecord
from legal_platform.modules.vector_index.index import (
    IndexEntry,
    SearchResult,
    SimilarityFunction,
    cosine_similarity,
)
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# In-memory index (brute-force, for MVP)
# ---------------------------------------------------------------------------

_INDEX_DDL = """
CREATE TABLE IF NOT EXISTS vector_index (
    entry_id            TEXT PRIMARY KEY,
    embedding_id        TEXT NOT NULL,
    chunk_id            TEXT NOT NULL,
    knowledge_node_id   TEXT NOT NULL DEFAULT '',
    document_id         TEXT NOT NULL,
    version_id          TEXT NOT NULL,
    vault_id            TEXT,
    dimension           INTEGER NOT NULL,
    model               TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    knowledge_tree_version TEXT NOT NULL DEFAULT '',
    chunk_text          TEXT NOT NULL DEFAULT '',
    chunk_type          TEXT NOT NULL DEFAULT 'PARAGRAPH',
    canonical_references TEXT NOT NULL DEFAULT '[]',
    page_start          INTEGER NOT NULL DEFAULT 1,
    page_end            INTEGER NOT NULL DEFAULT 1,
    document_status     TEXT NOT NULL DEFAULT 'ACTIVE',
    language            TEXT NOT NULL DEFAULT 'vi',
    created_at          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ACTIVE',
    vector_json         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vi_document  ON vector_index(document_id);
CREATE INDEX IF NOT EXISTS idx_vi_vault     ON vector_index(vault_id);
CREATE INDEX IF NOT EXISTS idx_vi_status    ON vector_index(status);
CREATE INDEX IF NOT EXISTS idx_vi_model     ON vector_index(model);
CREATE INDEX IF NOT EXISTS idx_vi_chunk     ON vector_index(chunk_id);
"""


class VectorIndexService:
    """The Vector Index Service.

    Stores and searches embedding vectors. The MVP uses an in-memory + SQLite
    hybrid: metadata is persisted in SQLite, vectors are loaded into memory
    for similarity search. A production deployment should use a proper vector
    database.

    Integrates with:
        - EmbeddingService (Task 007) for embedding records.
        - DocumentRegistry (Task 001) for document metadata and audit logging.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self._lock = threading.RLock()
        # In-memory vector store for fast similarity search
        self._entries: dict[UUID, IndexEntry] = {}
        self._dirty = False
        # Ensure index table + audit table exist
        init_audit_log(self.registry.repo.conn)
        self.registry.repo.conn.executescript(_INDEX_DDL)
        # Existing MVP databases pre-date chunk_text.  This is an additive,
        # rebuildable-derived-data migration and is safe for existing indexes.
        columns = {row["name"] for row in self.registry.repo.conn.execute("PRAGMA table_info(vector_index)")}
        if "chunk_text" not in columns:
            self.registry.repo.conn.execute(
                "ALTER TABLE vector_index ADD COLUMN chunk_text TEXT NOT NULL DEFAULT ''"
            )
        if "knowledge_node_id" not in columns:
            self.registry.repo.conn.execute(
                "ALTER TABLE vector_index ADD COLUMN knowledge_node_id TEXT NOT NULL DEFAULT ''"
            )
        if "page_start" not in columns:
            self.registry.repo.conn.execute(
                "ALTER TABLE vector_index ADD COLUMN page_start INTEGER NOT NULL DEFAULT 1"
            )
        if "page_end" not in columns:
            self.registry.repo.conn.execute(
                "ALTER TABLE vector_index ADD COLUMN page_end INTEGER NOT NULL DEFAULT 1"
            )
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Index operations
    # ------------------------------------------------------------------

    def index_embedding(
        self,
        embedding: EmbeddingRecord,
        *,
        vault_id: "UUID | None" = None,
        chunk_type: str = "PARAGRAPH",
        canonical_references: "list[str] | None" = None,
        knowledge_node_id: "UUID | None" = None,
        page_start: int = 1,
        page_end: int = 1,
        document_status: str = "ACTIVE",
        language: str = "vi",
    ) -> IndexEntry:
        """Index a single embedding record.

        Args:
            embedding: the embedding record to index.
            vault_id: the vault the document belongs to.
            chunk_type: type of the originating chunk.
            canonical_references: legal references for the chunk.
            document_status: document lifecycle status.
            language: document language.

        Returns:
            The created ``IndexEntry``.
        """
        entry = IndexEntry(
            embedding_id=embedding.embedding_id,
            chunk_id=embedding.chunk_id,
            knowledge_node_id=knowledge_node_id or embedding.chunk_id,
            document_id=embedding.document_id,
            version_id=embedding.version_id,
            vault_id=vault_id,
            vector=embedding.vector,
            dimension=embedding.dimension,
            model=embedding.model,
            model_version=embedding.model_version,
            knowledge_tree_version=embedding.knowledge_tree_version,
            chunk_text=embedding.chunk_text,
            chunk_type=chunk_type,
            canonical_references=canonical_references or [],
            page_start=page_start,
            page_end=page_end,
            document_status=document_status,
            language=language,
        )
        with self._lock:
            self._entries[entry.entry_id] = entry
            self._persist_entry(entry)
            self._dirty = True
        return entry

    def index_embeddings(
        self,
        embeddings: list[EmbeddingRecord],
        *,
        vault_id: "UUID | None" = None,
        chunk_types: "list[str] | None" = None,
        canonical_references: "list[list[str]] | None" = None,
        knowledge_node_ids: "list[UUID] | None" = None,
        page_starts: "list[int] | None" = None,
        page_ends: "list[int] | None" = None,
        document_status: str = "ACTIVE",
        language: str = "vi",
    ) -> list[IndexEntry]:
        """Index multiple embedding records (bulk import).

        Args:
            embeddings: the embedding records to index.
            vault_id: vault for all embeddings.
            chunk_types: per-embedding chunk types (defaults to PARAGRAPH).
            canonical_references: per-embedding legal references.
            document_status: document lifecycle status.
            language: document language.

        Returns:
            The created ``IndexEntry`` list.
        """
        entries: list[IndexEntry] = []
        for i, emb in enumerate(embeddings):
            ct = (chunk_types or [])[i] if chunk_types and i < len(chunk_types) else "PARAGRAPH"
            refs = (canonical_references or [])[i] if canonical_references and i < len(canonical_references) else []
            entry = self.index_embedding(
                emb,
                vault_id=vault_id,
                chunk_type=ct,
                canonical_references=refs,
                knowledge_node_id=(knowledge_node_ids or [])[i] if knowledge_node_ids and i < len(knowledge_node_ids) else None,
                page_start=(page_starts or [])[i] if page_starts and i < len(page_starts) else 1,
                page_end=(page_ends or [])[i] if page_ends and i < len(page_ends) else 1,
                document_status=document_status,
                language=language,
            )
            entries.append(entry)

        log_event(
            self.registry.repo.conn,
            service="vector-index",
            module="index",
            event="index.bulk_import",
            entity_type="document",
            entity_id=embeddings[0].document_id if embeddings else None,
            severity="INFO",
            message=f"Bulk indexed {len(entries)} embeddings",
            metadata={"count": len(entries)},
        )
        return entries

    def delete_entry(self, entry_id: UUID) -> bool:
        """Delete an index entry.

        Returns True if the entry was found and deleted.
        """
        with self._lock:
            if entry_id in self._entries:
                del self._entries[entry_id]
                self.registry.repo.conn.execute(
                    "DELETE FROM vector_index WHERE entry_id = ?",
                    (str(entry_id),),
                )
                self.registry.repo.conn.commit()
                self._dirty = True
                return True
            return False

    def delete_document_entries(self, document_id: UUID) -> int:
        """Delete all index entries for a document.

        Returns the number of entries deleted.
        """
        with self._lock:
            to_delete = [
                eid for eid, e in self._entries.items()
                if e.document_id == document_id
            ]
            for eid in to_delete:
                del self._entries[eid]
            self.registry.repo.conn.execute(
                "DELETE FROM vector_index WHERE document_id = ?",
                (str(document_id),),
            )
            self.registry.repo.conn.commit()
            self._dirty = True
            return len(to_delete)

    def set_document_status(self, document_id: UUID, status: str) -> int:
        """Keep index filtering aligned with canonical document lifecycle."""
        with self._lock:
            updated = 0
            for entry in self._entries.values():
                if entry.document_id == document_id:
                    entry.document_status = status
                    updated += 1
            cursor = self.registry.repo.conn.execute(
                "UPDATE vector_index SET document_status = ? WHERE document_id = ?",
                (status, str(document_id)),
            )
            self.registry.repo.conn.commit()
            self._dirty = True
            return max(updated, cursor.rowcount)

    def rebuild(self) -> int:
        """Rebuild the in-memory index from the persisted store.

        Returns the number of entries loaded.
        """
        with self._lock:
            self._entries.clear()
            rows = self.registry.repo.conn.execute(
                "SELECT * FROM vector_index WHERE status = 'ACTIVE'"
            )
            count = 0
            for row in rows:
                entry = self._entry_from_row(row)
                self._entries[entry.entry_id] = entry
                count += 1
            self._dirty = False
            return count

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 10,
        threshold: "float | None" = None,
        vault_id: "UUID | None" = None,
        vault_ids: "set[UUID] | None" = None,
        document_id: "UUID | None" = None,
        document_status: "str | None" = None,
        chunk_types: "list[str] | None" = None,
        model: "str | None" = None,
        model_version: "str | None" = None,
        language: "str | None" = None,
        similarity: str = "cosine",
    ) -> list[SearchResult]:
        """Search the index for the nearest neighbors to a query vector.

        Args:
            query_vector: the query embedding vector.
            top_k: maximum number of results to return.
            threshold: minimum similarity score (None = no threshold).
            vault_id: filter by vault.
            vault_ids: restrict results to an authorized set of vaults.
            document_id: filter by document.
            document_status: filter by document status.
            chunk_types: filter by chunk types.
            model: filter by embedding model.
            model_version: filter by the exact embedding model digest/version.
            language: filter by language.
            similarity: similarity function to use.

        Returns:
            A list of ``SearchResult`` sorted by descending score.
        """
        candidates: list[SearchResult] = []

        with self._lock:
            entries = list(self._entries.values())
        for entry in entries:
            if entry.status != "ACTIVE":
                continue

            # Apply filters
            if vault_id is not None and entry.vault_id != vault_id:
                continue
            if vault_ids is not None and entry.vault_id not in vault_ids:
                continue
            if document_id is not None and entry.document_id != document_id:
                continue
            if document_status is not None and entry.document_status != document_status:
                continue
            if chunk_types is not None and entry.chunk_type not in chunk_types:
                continue
            if model is not None and entry.model != model:
                continue
            if model_version is not None and entry.model_version != model_version:
                continue
            if language is not None and entry.language != language:
                continue
            if entry.dimension != len(query_vector):
                continue

            # Compute similarity
            score = SimilarityFunction.compute(similarity, query_vector, entry.vector)

            if threshold is not None and score < threshold:
                continue

            candidates.append(SearchResult(entry=entry, score=score))

        # Sort by descending score
        candidates.sort(key=lambda r: r.score, reverse=True)

        # Assign ranks
        for i, result in enumerate(candidates[:top_k]):
            result.rank = i + 1

        return candidates[:top_k]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist_entry(self, entry: IndexEntry) -> None:
        """Persist an index entry to SQLite."""
        self.registry.repo.conn.execute(
            """
            INSERT OR REPLACE INTO vector_index
                (entry_id, embedding_id, chunk_id, knowledge_node_id, document_id, version_id, vault_id,
                 dimension, model, model_version, knowledge_tree_version, chunk_type,
                 chunk_text, canonical_references, page_start, page_end,
                 document_status, language, created_at, status,
                 vector_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(entry.entry_id),
                str(entry.embedding_id),
                str(entry.chunk_id),
                str(entry.knowledge_node_id),
                str(entry.document_id),
                str(entry.version_id),
                str(entry.vault_id) if entry.vault_id else None,
                entry.dimension,
                entry.model,
                entry.model_version,
                entry.knowledge_tree_version,
                entry.chunk_type,
                entry.chunk_text,
                json.dumps(entry.canonical_references),
                entry.page_start,
                entry.page_end,
                entry.document_status,
                entry.language,
                utc_iso(entry.created_at),
                entry.status,
                json.dumps(entry.vector),
            ),
        )
        self.registry.repo.conn.commit()

    @staticmethod
    def _entry_from_row(row: Any) -> IndexEntry:
        """Reconstruct an IndexEntry from a DB row."""
        return IndexEntry(
            entry_id=UUID(row["entry_id"]),
            embedding_id=UUID(row["embedding_id"]),
            chunk_id=UUID(row["chunk_id"]),
            knowledge_node_id=UUID(row["knowledge_node_id"]) if row["knowledge_node_id"] else UUID(row["chunk_id"]),
            document_id=UUID(row["document_id"]),
            version_id=UUID(row["version_id"]),
            vault_id=UUID(row["vault_id"]) if row["vault_id"] else None,
            vector=json.loads(row["vector_json"]),
            dimension=row["dimension"],
            model=row["model"],
            model_version=row["model_version"],
            knowledge_tree_version=row["knowledge_tree_version"],
            chunk_text=row["chunk_text"],
            chunk_type=row["chunk_type"],
            canonical_references=json.loads(row["canonical_references"]),
            page_start=row["page_start"],
            page_end=row["page_end"],
            document_status=row["document_status"],
            language=row["language"],
            created_at=datetime.fromisoformat(row["created_at"]),
            status=row["status"],
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        with self._lock:
            entries = list(self._entries.values())
        return {
            "total_entries": len(entries),
            "active_entries": sum(1 for e in entries if e.status == "ACTIVE"),
            "models": list({e.model for e in entries}),
            "dimensions": list({e.dimension for e in entries}),
        }

    def entries_snapshot(self) -> list[IndexEntry]:
        """Return a stable shallow snapshot for keyword/context retrieval."""
        with self._lock:
            return list(self._entries.values())

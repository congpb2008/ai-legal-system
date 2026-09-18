"""Chunking Service (tasks/006-chunking.md).

The Chunking Service orchestrates the chunking pipeline:
    1. Receives a Knowledge Tree (from the Builder, Task 005).
    2. Runs the structure-aware chunker.
    3. Stores the chunk collection.
    4. Returns the chunk collection for downstream consumption (Embedding, Task 007).

Per the spec:
    - Chunking is entirely structure-aware.
    - Knowledge Tree boundaries always take priority over token limits.
    - Chunks are derived, disposable artifacts (ADR-003).
    - The Knowledge Tree remains the source of truth.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import utc_iso
from legal_platform.contracts.knowledge_tree import KnowledgeTree
from legal_platform.modules.chunking.chunker import (
    ChunkCollection,
    ChunkerConfig,
    StructureAwareChunker,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.parser.service import ParserService
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# Chunk storage (disposable per ADR-003)
# ---------------------------------------------------------------------------

_CHUNK_DDL = """
CREATE TABLE IF NOT EXISTS chunk_collection (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL,
    version_id      TEXT NOT NULL,
    chunker_version TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    total_chunks    INTEGER NOT NULL,
    collection_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunk_document ON chunk_collection(document_id);
CREATE INDEX IF NOT EXISTS idx_chunk_version  ON chunk_collection(version_id);
"""


class ChunkingService:
    """The Chunking Service.

    Orchestrates chunking of Knowledge Trees into retrieval-ready chunks.
    Integrates with:
        - ParserService (Tasks 004-005) for retrieving trees.
        - DocumentRegistry (Task 001) for state transitions and audit logging.
        - StructureAwareChunker (replaceable) for the actual chunking.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        parser_service: "ParserService | None" = None,
        chunker: "StructureAwareChunker | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.parser_service = parser_service or ParserService(registry=self.registry)
        self.chunker = chunker or StructureAwareChunker()
        # Ensure chunk table + audit table exist
        init_audit_log(self.registry.repo.conn)
        self.registry.repo.conn.executescript(_CHUNK_DDL)
        self.registry.repo.conn.commit()

    def chunk_tree(
        self,
        tree: KnowledgeTree,
        *,
        document_id: UUID,
    ) -> ChunkCollection:
        """Chunk a Knowledge Tree into retrieval-ready chunks.

        Args:
            tree: the validated Knowledge Tree to chunk.
            document_id: the logical document that owns ``tree``.

        Returns:
            A ``ChunkCollection`` with chunks in document order.
        """
        collection = self.chunker.chunk(tree, document_id=document_id)

        # Store the collection
        self._store_collection(collection)

        # Audit
        log_event(
            self.registry.repo.conn,
            service="chunking-service",
            module="chunking",
            event="chunking.complete",
            entity_type="document",
            entity_id=document_id,
            severity="INFO",
            message=f"Chunking completed: {collection.total_chunks} chunks",
            metadata={
                "total_chunks": collection.total_chunks,
                "total_tokens": collection.total_tokens,
                "chunker_version": collection.chunker_version,
                "version_id": str(tree.document_version_id),
            },
        )

        return collection

    def chunk_document(
        self,
        document_id: UUID,
        *,
        version_id: "UUID | None" = None,
    ) -> ChunkCollection:
        """Chunk a document by looking up its Knowledge Tree.

        Args:
            document_id: the document to chunk.
            version_id: the specific version (defaults to latest).

        Returns:
            A ``ChunkCollection``.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        vid = version_id or doc.current_version.version_id

        # Retrieve the Knowledge Tree
        tree = self.parser_service.get_tree_for_version(vid)
        if tree is None:
            raise ValueError(
                f"No Knowledge Tree found for version {vid}. "
                "Run parsing first (Tasks 004-005)."
            )

        return self.chunk_tree(tree, document_id=document_id)

    def _store_collection(self, collection: ChunkCollection) -> None:
        """Persist a chunk collection (disposable per ADR-003)."""
        import dataclasses
        import json as _json

        def _serialize(obj):
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return utc_iso(obj)
            if dataclasses.is_dataclass(obj):
                return {f.name: _serialize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, Enum):
                return obj.value
            return obj

        from datetime import datetime
        from enum import Enum

        collection_id = str(uuid4())
        self.registry.repo.conn.execute(
            """
            INSERT OR REPLACE INTO chunk_collection
                (id, document_id, version_id, chunker_version, created_at, total_chunks, collection_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                collection_id,
                str(collection.document_id),
                str(collection.version_id),
                collection.chunker_version,
                utc_iso(collection.created_at),
                collection.total_chunks,
                _json.dumps(_serialize(collection), ensure_ascii=False, default=str),
            ),
        )
        self.registry.repo.conn.commit()

    def get_collection(self, collection_id: UUID) -> Optional[ChunkCollection]:
        """Retrieve a stored chunk collection by its ID."""
        import json as _json

        row = self.registry.repo.conn.execute(
            "SELECT collection_json FROM chunk_collection WHERE id = ?",
            (str(collection_id),),
        ).fetchone()
        if row is None:
            return None
        data = _json.loads(row["collection_json"])
        return _collection_from_dict(data)

    def get_collections_for_document(self, document_id: UUID) -> list[ChunkCollection]:
        """Retrieve all chunk collections for a document (newest first)."""
        import json as _json

        rows = self.registry.repo.conn.execute(
            "SELECT collection_json FROM chunk_collection WHERE document_id = ? ORDER BY created_at DESC",
            (str(document_id),),
        )
        results: list[ChunkCollection] = []
        for row in rows:
            data = _json.loads(row["collection_json"])
            results.append(_collection_from_dict(data))
        return results


def _collection_from_dict(data: dict) -> ChunkCollection:
    """Reconstruct a ChunkCollection from a JSON-deserialized dict."""
    import dataclasses
    import typing
    from datetime import datetime
    from enum import Enum

    def _deserialize(obj: Any, target_type: Any) -> Any:
        origin = typing.get_origin(target_type)
        args = typing.get_args(target_type)

        if target_type is UUID or (origin is not None and UUID in args):
            if isinstance(obj, str):
                return UUID(obj)
            return obj
        if target_type is datetime or (origin is not None and datetime in args):
            if isinstance(obj, str):
                return datetime.fromisoformat(obj)
            return obj
        if (
            isinstance(target_type, type)
            and issubclass(target_type, Enum)
            and isinstance(obj, str)
        ):
            return target_type(obj)
        if origin is list and isinstance(obj, list):
            item_type = args[0] if args else Any
            return [_deserialize(item, item_type) for item in obj]
        if origin is dict and isinstance(obj, dict):
            val_type = args[1] if len(args) > 1 else Any
            return {k: _deserialize(v, val_type) for k, v in obj.items()}
        if dataclasses.is_dataclass(target_type) and isinstance(obj, dict):
            field_names = {f.name for f in dataclasses.fields(target_type)}
            field_types = typing.get_type_hints(target_type)
            kwargs = {}
            for fname in field_names:
                if fname in obj:
                    kwargs[fname] = _deserialize(obj[fname], field_types.get(fname, Any))
            return target_type(**kwargs)
        return obj

    return _deserialize(data, ChunkCollection)

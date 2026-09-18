"""Runtime document-processing orchestration.

This is deliberately a small coordinator: individual modules still own OCR,
parsing, chunking, embedding, and indexing.  It owns only stage ordering and
the truthfulness of the registry processing state.
"""

from __future__ import annotations

import json
import threading
from uuid import UUID

from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.upload_service.file_storage import FileStorage


class DocumentPipeline:
    def __init__(self, *, registry: DocumentRegistry, storage: FileStorage, ocr, parser, chunking, embedding, vector_index):
        self.registry = registry
        self.storage = storage
        self.ocr = ocr
        self.parser = parser
        self.chunking = chunking
        self.embedding = embedding
        self.vector_index = vector_index
        self._document_locks: dict[UUID, threading.RLock] = {}
        self._document_locks_guard = threading.Lock()
        self.registry.set_ready_validator(self.validate_ready)

    def _document_lock(self, document_id: UUID) -> threading.RLock:
        with self._document_locks_guard:
            return self._document_locks.setdefault(document_id, threading.RLock())

    def validate_ready(self, document_id: UUID) -> list[str]:
        """Return persisted artifact violations for one document.

        READY requires a retrievable immutable source and a complete artifact
        chain for the current Document Version and configured embedding model.
        Counts are checked by distinct ownership IDs to catch partial writes.
        """
        problems: list[str] = []
        document = self.registry.get_document(document_id)
        if document is None:
            return ["document is missing"]
        if not document.versions:
            return ["document has no version"]
        version_id = document.current_version.version_id
        conn = self.registry.repo.conn

        storage_ref = self.registry.get_source_storage_ref(document_id)
        if not storage_ref:
            problems.append("source reference is missing")
        elif not self.storage.exists(storage_ref):
            problems.append("source file is missing")

        ocr_count = conn.execute(
            "SELECT COUNT(*) FROM ocr_result WHERE document_id = ? AND version_id = ?",
            (str(document_id), str(version_id)),
        ).fetchone()[0]
        if ocr_count < 1:
            problems.append("OCR result is missing")

        tree_count = conn.execute(
            "SELECT COUNT(*) FROM knowledge_tree WHERE document_version_id = ?",
            (str(version_id),),
        ).fetchone()[0]
        if tree_count < 1:
            problems.append("Knowledge Tree is missing")

        chunk_row = conn.execute(
            """
            SELECT total_chunks, collection_json
            FROM chunk_collection
            WHERE document_id = ? AND version_id = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (str(document_id), str(version_id)),
        ).fetchone()
        chunk_ids: set[str] = set()
        if chunk_row is None or chunk_row["total_chunks"] < 1:
            problems.append("chunk collection is missing or empty")
            chunk_count = 0
        else:
            try:
                chunks = json.loads(chunk_row["collection_json"])["chunks"]
                chunk_ids = {item["chunk_id"] for item in chunks}
            except (json.JSONDecodeError, KeyError, TypeError):
                chunks = []
            chunk_count = chunk_row["total_chunks"]
            if len(chunks) != chunk_count or len(chunk_ids) != chunk_count:
                problems.append("chunk collection is inconsistent")

        try:
            self.embedding.engine.verify_configuration()
        except Exception as exc:
            problems.append(f"embedding configuration is unavailable ({type(exc).__name__})")
        model = self.embedding.engine.MODEL_NAME
        model_version = self.embedding.engine.MODEL_VERSION
        dimension = self.embedding.engine.DIMENSION

        embedding_row = conn.execute(
            """
            SELECT COUNT(*) AS total, COUNT(DISTINCT chunk_id) AS chunks
            FROM embedding
            WHERE document_id = ? AND version_id = ? AND status = 'ACTIVE'
              AND model = ? AND model_version = ? AND dimension = ?
            """,
            (
                str(document_id), str(version_id), model,
                model_version, dimension,
            ),
        ).fetchone()
        embedding_count = embedding_row["total"]
        if chunk_count < 1 or embedding_count != chunk_count or embedding_row["chunks"] != chunk_count:
            problems.append("active embeddings do not cover every chunk")

        index_row = conn.execute(
            """
            SELECT COUNT(*) AS total, COUNT(DISTINCT chunk_id) AS chunks,
                   COUNT(DISTINCT embedding_id) AS embeddings
            FROM vector_index
            WHERE document_id = ? AND version_id = ? AND status = 'ACTIVE'
              AND model = ? AND model_version = ? AND dimension = ?
            """,
            (
                str(document_id), str(version_id), model,
                model_version, dimension,
            ),
        ).fetchone()
        if (
            chunk_count < 1
            or index_row["total"] != chunk_count
            or index_row["chunks"] != chunk_count
            or index_row["embeddings"] != chunk_count
        ):
            problems.append("active index does not cover every embedding")
        return problems

    def reconcile_ready_documents(self, *, user_id: str = "system") -> dict[str, list[str]]:
        """Downgrade legacy/partial READY rows to recoverable FAILED state.

        This is an explicit startup reconciliation for configured runtimes.  It
        changes only derived processing state; source files and canonical trees
        are never removed or rewritten.
        """
        invalid: dict[str, list[str]] = {}
        for document in self.registry.list_documents(limit=10000):
            if self.registry.get_processing(document.id) != ProcessingState.READY:
                continue
            problems = self.validate_ready(document.id)
            if not problems:
                continue
            invalid[str(document.id)] = problems
            reason = "READY reconciliation failed: " + "; ".join(problems)
            self.registry.repo.set_processing(
                document.id,
                ProcessingState.FAILED,
                failure_reason=reason[:500],
            )
            from legal_platform.storage.eventlog import log_event
            log_event(
                self.registry.repo.conn,
                service="document-pipeline",
                module="processing",
                event="document.ready_reconciled",
                entity_type="document",
                entity_id=document.id,
                severity="WARN",
                message="Invalid READY state changed to FAILED for explicit recovery",
                metadata={"problems": problems, "user_id": user_id},
            )
        return invalid

    def process(self, document_id: UUID, *, user_id: str = "system") -> int:
        """Serialize a full processing attempt for one logical document."""
        with self._document_lock(document_id):
            return self._process_locked(document_id, user_id=user_id)

    def _process_locked(self, document_id: UUID, *, user_id: str = "system") -> int:
        """Process one uploaded document and return indexed entry count.

        READY is emitted only after every downstream derived artifact was made
        durable and searchable.  Exceptions leave the document FAILED with a
        concise operational reason; they are not converted to false success.
        """
        document = self.registry.get_document(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        state = self.registry.get_processing(document_id)
        if state == ProcessingState.READY:
            problems = self.validate_ready(document_id)
            if problems:
                raise ValueError(
                    "READY invariant failed; explicit recovery is required: "
                    + "; ".join(problems)
                )
            return 0
        if state != ProcessingState.UPLOADED:
            raise ValueError(f"Document {document_id} is in {state.value if state else 'no'} state; explicit recovery is required")

        try:
            self.registry.transition_processing(document_id, ProcessingState.OCR_PENDING, user_id=user_id)
            storage_ref = self.registry.get_source_storage_ref(document_id)
            if not storage_ref:
                raise ValueError("Original source file is unavailable")
            ocr_result = self.ocr.process_bytes(document_id, self.storage.retrieve(storage_ref), user_id=user_id)
            if sum(len(page.text) for page in ocr_result.pages) <= 10:
                raise ValueError("OCR produced no meaningful extractable text")

            # Parser advances through its own parsing states but must not claim
            # READY: chunking, embedding, and indexing remain prerequisites.
            self.parser.parse_ocr_result(ocr_result, document_id=document_id, user_id=user_id, mark_ready=False)
            chunks = self.chunking.chunk_document(document_id)
            return self._embed_index_and_finish(
                document,
                chunks,
                user_id=user_id,
            )
        except Exception as exc:
            current = self.registry.get_processing(document_id)
            if current is not None and current not in (ProcessingState.FAILED, ProcessingState.READY):
                self.registry.transition_processing(
                    document_id, ProcessingState.FAILED, user_id=user_id,
                    failure_reason=str(exc)[:500],
                )
            raise

    def reprocess(
        self,
        document_id: UUID,
        *,
        from_stage: str,
        user_id: str = "system",
    ) -> int:
        """Serialize a requested rebuild against worker/manual processing."""
        with self._document_lock(document_id):
            return self._reprocess_locked(
                document_id,
                from_stage=from_stage,
                user_id=user_id,
            )

    def _reprocess_locked(
        self,
        document_id: UUID,
        *,
        from_stage: str,
        user_id: str = "system",
    ) -> int:
        """Rebuild exactly the requested stage and its downstream artifacts.

        Supported values are ``ocr``, ``parse``, ``embed``, and ``index``.
        Upstream immutable source/OCR/tree/chunks are reused when the requested
        operation starts downstream of them.
        """
        stage = from_stage.strip().lower()
        if stage not in {"ocr", "parse", "embed", "index"}:
            raise ValueError(f"Unsupported reprocessing stage: {from_stage}")
        document = self.registry.get_document(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        version_id = document.current_version.version_id

        try:
            if stage == "ocr":
                self.registry.requeue_processing(
                    document_id,
                    ProcessingState.UPLOADED,
                    user_id=user_id,
                    reason="explicit re-OCR",
                )
                self.embedding.mark_document_stale(document_id)
                self.vector_index.delete_document_entries(document_id)
                return self.process(document_id, user_id=user_id)

            if stage == "parse":
                results = self.ocr.get_results_for_document(document_id)
                ocr_result = next(
                    (result for result in results if result.version_id == version_id),
                    None,
                )
                if ocr_result is None:
                    raise ValueError("Re-parse requires a valid OCR result")
                self.registry.requeue_processing(
                    document_id,
                    ProcessingState.OCR_COMPLETED,
                    user_id=user_id,
                    reason="explicit re-parse",
                )
                self.embedding.mark_document_stale(document_id)
                self.vector_index.delete_document_entries(document_id)
                self.parser.parse_ocr_result(
                    ocr_result,
                    document_id=document_id,
                    version_id=version_id,
                    user_id=user_id,
                    mark_ready=False,
                )
                chunks = self.chunking.chunk_document(document_id, version_id=version_id)
                return self._embed_index_and_finish(document, chunks, user_id=user_id)

            collections = self.chunking.get_collections_for_document(document_id)
            chunks = next(
                (item for item in collections if item.version_id == version_id),
                None,
            )
            if chunks is None or not chunks.chunks:
                raise ValueError("Re-embedding/re-indexing requires valid chunks")

            self.registry.requeue_processing(
                document_id,
                ProcessingState.PARSING_RUNNING,
                user_id=user_id,
                reason=f"explicit re-{stage}",
            )
            if stage == "embed":
                self.embedding.mark_document_stale(document_id)
                self.vector_index.delete_document_entries(document_id)
                return self._embed_index_and_finish(document, chunks, user_id=user_id)

            self.embedding.engine.verify_configuration()
            embeddings = self.embedding.get_active_embeddings(
                document_id,
                version_id=version_id,
                model=self.embedding.engine.MODEL_NAME,
                model_version=self.embedding.engine.MODEL_VERSION,
            )
            if len(embeddings) != len(chunks.chunks):
                raise ValueError(
                    "Re-index requires one active current-model embedding per chunk"
                )
            self.vector_index.delete_document_entries(document_id)
            return self._index_and_finish(
                document,
                chunks,
                embeddings,
                user_id=user_id,
            )
        except Exception as exc:
            current = self.registry.get_processing(document_id)
            if current is not None and current not in (
                ProcessingState.FAILED,
                ProcessingState.READY,
            ):
                self.registry.transition_processing(
                    document_id,
                    ProcessingState.FAILED,
                    user_id=user_id,
                    failure_reason=str(exc)[:500],
                )
            raise

    def _embed_index_and_finish(self, document, chunks, *, user_id: str) -> int:
        if not chunks.chunks:
            raise ValueError("Parsing produced no indexable chunks")
        embeddings = self.embedding.embed_collection(chunks)
        if len(embeddings.embeddings) != len(chunks.chunks):
            raise ValueError("Embedding output does not cover every chunk")
        self.vector_index.delete_document_entries(document.id)
        return self._index_and_finish(
            document,
            chunks,
            embeddings.embeddings,
            user_id=user_id,
        )

    def _index_and_finish(
        self,
        document,
        chunks,
        embeddings,
        *,
        user_id: str,
    ) -> int:
        entries = self.vector_index.index_embeddings(
            embeddings,
            vault_id=document.vault_id,
            chunk_types=[chunk.chunk_type.value for chunk in chunks.chunks],
            canonical_references=[chunk.canonical_references for chunk in chunks.chunks],
            knowledge_node_ids=[chunk.node_ids[0] for chunk in chunks.chunks],
            page_starts=[chunk.page_start for chunk in chunks.chunks],
            page_ends=[chunk.page_end for chunk in chunks.chunks],
            document_status=document.status.value,
            language=document.language,
        )
        if not entries:
            raise ValueError("Indexing produced no searchable entries")
        problems = self.validate_ready(document.id)
        if problems:
            raise ValueError("READY invariant failed: " + "; ".join(problems))
        self.registry.transition_processing(
            document.id,
            ProcessingState.READY,
            user_id=user_id,
        )
        return len(entries)

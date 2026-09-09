"""Document Registry Service (tasks/001-document-registry.md).

The Registry is the entry point of the knowledge ingestion pipeline. It:

- Registers newly uploaded documents (assigns stable Document ID).
- Stores document metadata + processing status.
- Tracks document versions.
- Tracks legal status (ACTIVE / ARCHIVED).
- Manages vault ownership.
- Maintains relationships between documents.
- Detects duplicate uploads by checksum.

The Registry does NOT perform OCR, parsing, embedding, Knowledge Tree construction,
or answer generation.

Security: never expose documents outside their vault; every operation requires
authorization; original files remain immutable (BC-004).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from legal_platform.contracts.common import new_id, now_utc, utc_iso
from legal_platform.contracts.document import (
    Document,
    DocumentStatus,
    DocumentType,
    DocumentVersionReference,
    DocumentVersionStatus,
    Metadata,
    Visibility,
)
from legal_platform.modules.document_registry.processing import (
    InvalidTransition,
    ProcessingState,
    assert_transition,
)
from legal_platform.modules.document_registry.repository import (
    DocumentRepository,
    SqliteDocumentRepository,
)
from legal_platform.modules.document_registry.vault import AllowAllVaults, VaultResolver
from legal_platform.storage.eventlog import init_audit_log, log_event


class DocumentRegistry:
    """The Document Registry.

    All public methods accept a ``user_id`` parameter for audit logging and future
    authorization. The current ``AllowAllVaults`` stub permits all operations; Task 013
    will replace it with real vault authorization.
    """

    def __init__(
        self,
        repo: "DocumentRepository | None" = None,
        vault_resolver: "VaultResolver | None" = None,
    ):
        self.repo = repo or SqliteDocumentRepository()
        self.vault = vault_resolver or AllowAllVaults()
        self._ready_validator: "Callable[[UUID], list[str]] | None" = None
        # Ensure audit table exists
        init_audit_log(self.repo.conn)
        # Create doc_source_refs table if not exists
        self.repo.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doc_source_refs (
                doc_id TEXT PRIMARY KEY,
                key TEXT,
                value TEXT
            )
            """
        )
        self.repo.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_source (
                document_id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL DEFAULT '',
                storage_ref TEXT NOT NULL,
                filename TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                size_bytes INTEGER NOT NULL DEFAULT 0,
                checksum_sha256 TEXT NOT NULL DEFAULT '',
                uploaded_by TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE
            )
            """
        )
        self.repo.conn.execute("""CREATE TABLE IF NOT EXISTS document_source_version (
            document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
            version_id TEXT NOT NULL, storage_ref TEXT NOT NULL, filename TEXT NOT NULL,
            mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, checksum_sha256 TEXT NOT NULL,
            uploaded_by TEXT NOT NULL, PRIMARY KEY(document_id, version_id))""")
        self.repo.conn.execute("INSERT OR IGNORE INTO document_source_version SELECT * FROM document_source WHERE version_id != ''")
        # Preserve legacy opaque source references. Rich metadata is populated
        # for all new uploads and legacy rows remain readable/reprocessable.
        self.repo.conn.execute(
            """
            INSERT OR IGNORE INTO document_source (document_id, storage_ref)
            SELECT doc_id, value FROM doc_source_refs WHERE key = 'main'
            """
        )
        self.repo.conn.commit()
        # Create OCR results table (unused — re-processes OCR from storage instead)
        pass  # OCR results stored via process_document method using OcrService.process_bytes

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def register_document(
        self,
        *,
        user_id: str,
        document_type: "str | DocumentType",
        title: str,
        issuing_authority: str,
        vault_id: UUID,
        organization_id: UUID,
        # --- optional metadata ---
        document_number: "str | None" = None,
        short_title: "str | None" = None,
        description: "str | None" = None,
        language: str = "vi",
        visibility: "str | Visibility" = Visibility.DEPARTMENT,
        metadata: "dict[str, Any] | None" = None,
        # --- version info ---
        version_id: "UUID | None" = None,
        version_number: int = 1,
        # --- source file info ---
        source_filename: "str | None" = None,
        source_mime_type: "str | None" = None,
        source_size_bytes: "int | None" = None,
        source_checksum_sha256: "str | None" = None,
        source_storage_ref: "str | None" = None,
        source_uploaded_by: "str | None" = None,
        # --- relationships ---
        supersedes: "list[UUID] | None" = None,
        amends: "list[UUID] | None" = None,
        references: "list[UUID] | None" = None,
    ) -> Document:
        """Register a new Document and its first Document Version.

        Validates vault existence, creates the Document Contract, persists it with
        ``UPLOADED`` processing state, indexes the source file checksum, and records
        any initial relationships.

        Returns the persisted Document with its assigned ``id``.
        """
        # --- vault validation ---
        if not self.vault.vault_exists(vault_id):
            raise ValueError(f"Vault {vault_id} does not exist")
        if not self.vault.user_can_upload_to_vault(user_id, vault_id):
            raise PermissionError(
                f"User {user_id} is not authorized to create documents in vault {vault_id}"
            )

        # --- build Document Contract ---
        doc = Document(
            type=DocumentType.coerce(document_type),
            title=title,
            short_title=short_title,
            description=description,
            issuing_authority=issuing_authority,
            document_number=document_number,
            language=language,
            status=DocumentStatus.ACTIVE,
            visibility=Visibility.coerce(visibility),
            vault_id=vault_id,
            organization_id=organization_id,
            metadata=Metadata(**(metadata or {})),
            versions=[
                DocumentVersionReference(
                    version_id=version_id or new_id(),
                    version_number=version_number,
                    status=DocumentVersionStatus.ACTIVE,
                    created_at=now_utc(),
                )
            ],
        )

        # --- persist ---
        self.repo.save(doc, processing=ProcessingState.UPLOADED)

        # Persist immutable source metadata against the exact document version.
        if source_storage_ref:
            self.repo.conn.execute(
                """
                INSERT OR REPLACE INTO document_source
                    (document_id, version_id, storage_ref, filename, mime_type,
                     size_bytes, checksum_sha256, uploaded_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(doc.id),
                    str(doc.current_version.version_id),
                    source_storage_ref,
                    source_filename or "",
                    source_mime_type or "application/octet-stream",
                    source_size_bytes or 0,
                    source_checksum_sha256 or "",
                    source_uploaded_by or user_id,
                ),
            )
            self.repo.conn.execute("INSERT OR IGNORE INTO document_source_version SELECT * FROM document_source WHERE document_id=?", (str(doc.id),))
            # Keep the former lookup populated for backward compatibility with
            # older tools while the rich table is authoritative.
            self.repo.conn.execute(
                "INSERT OR REPLACE INTO doc_source_refs (doc_id, key, value) VALUES (?, ?, ?)",
                (str(doc.id), "main", source_storage_ref),
            )
            self.repo.conn.commit()

        # --- index checksum (duplicate detection) ---
        if source_checksum_sha256:
            self.repo.add_checksum(
                checksum_sha256=source_checksum_sha256,
                document_id=doc.id,
                version_id=doc.current_version.version_id,
                filename=source_filename,
                uploaded_at=doc.created_at,
            )

        # --- relationships ---
        now = now_utc()
        for target_id in supersedes or []:
            self.repo.add_relationship(doc.id, target_id, "SUPERSEDES", now=now)
        for target_id in amends or []:
            self.repo.add_relationship(doc.id, target_id, "AMENDS", now=now)
        for target_id in references or []:
            self.repo.add_relationship(doc.id, target_id, "REFERENCES", now=now)

        # --- audit ---
        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.create",
            entity_type="document",
            entity_id=doc.id,
            severity="INFO",
            message=f"Document {doc.title} registered",
            metadata={
                "type": doc.type.value,
                "vault_id": str(doc.vault_id),
                "document_number": doc.document_number,
                "version_id": str(doc.current_version.version_id),
                "source_checksum": source_checksum_sha256,
            },
        )

        return doc

    def get_source_storage_ref(self, document_id: "UUID") -> "str | None":
        """Retrieve the source file storage ref stored alongside a Document."""
        row = self.repo.conn.execute(
            "SELECT storage_ref FROM document_source WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()
        if row:
            return row[0]
        row = self.repo.conn.execute(
            "SELECT value FROM doc_source_refs WHERE doc_id = ? AND key = ?",
            (str(document_id), "main"),
        ).fetchone()
        return row[0] if row else None

    def get_source_metadata(self, document_id: UUID, version_id=None):
        if version_id is not None:
            row = self.repo.conn.execute("SELECT * FROM document_source_version WHERE document_id=? AND version_id=?", (str(document_id), str(version_id))).fetchone()
        else:
            row = self.repo.conn.execute("SELECT * FROM document_source WHERE document_id=?", (str(document_id),)).fetchone()
        return dict(row) if row else None

    def save_version_source(self, document_id, version_id, stored, user_id, filename):
        values = (str(document_id), str(version_id), stored.storage_ref, filename, stored.mime_type, stored.size_bytes, stored.checksum_sha256, user_id)
        self.repo.conn.execute("INSERT INTO document_source_version VALUES (?,?,?,?,?,?,?,?)", values)
        self.repo.conn.execute("INSERT OR REPLACE INTO document_source VALUES (?,?,?,?,?,?,?,?)", values)
        self.repo.conn.execute("INSERT OR REPLACE INTO doc_source_refs VALUES (?, 'main', ?)", (str(document_id), stored.storage_ref))
        self.repo.conn.commit()
        self.repo.add_checksum(checksum_sha256=stored.checksum_sha256, document_id=document_id, version_id=version_id, filename=filename, uploaded_at=now_utc())

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------



    def get_document(self, document_id: UUID) -> Optional[Document]:
        """Retrieve a Document by its stable identifier."""
        return self.repo.get(document_id)

    def list_documents(
        self,
        *,
        vault_id: "UUID | None" = None,
        status: "DocumentStatus | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """List Documents with optional vault/status filtering."""
        return self.repo.list_documents(
            vault_id=vault_id, status=status, limit=limit, offset=offset
        )

    # ------------------------------------------------------------------
    # Update metadata
    # ------------------------------------------------------------------

    def query_catalog(self, **filters):
        """Return a page and full count after applying the caller's access scope."""
        return self.repo.query_catalog(**filters)

    def catalog_totals(self, vault_ids):
        return self.repo.catalog_totals(vault_ids)

    def update_metadata(
        self,
        document_id: UUID,
        *,
        user_id: str,
        title: "str | None" = None,
        short_title: "str | None" = None,
        description: "str | None" = None,
        issuing_authority: "str | None" = None,
        document_number: "str | None" = None,
        language: "str | None" = None,
        metadata: "dict[str, Any] | None" = None,
    ) -> Document:
        """Update mutable Document metadata (per DC-003: metadata independent of content).

        Does NOT change ``id``, ``type``, ``vault_id``, ``organization_id``, ``status``,
        ``visibility``, or ``versions`` (those require dedicated operations).
        """
        doc = self.repo.get(document_id)
        if doc is None:
            raise KeyError(f"Document {document_id} not found")

        changed = False
        if title is not None and title != doc.title:
            doc.title = title
            changed = True
        if short_title is not None:
            doc.short_title = short_title
            changed = True
        if description is not None:
            doc.description = description
            changed = True
        if issuing_authority is not None:
            doc.issuing_authority = issuing_authority
            changed = True
        if document_number is not None:
            doc.document_number = document_number
            changed = True
        if language is not None:
            doc.language = language
            changed = True
        if metadata is not None:
            doc.metadata = Metadata(**{**doc.metadata.model_dump(exclude_unset=True), **metadata})
            changed = True

        if changed:
            doc.touch()
            self.repo.save(doc, processing=self.repo.get_processing(document_id) or ProcessingState.UPLOADED)
            log_event(
                self.repo.conn,
                service="document-registry",
                module="registry",
                event="document.metadata_update",
                entity_type="document",
                entity_id=doc.id,
                severity="INFO",
                message=f"Metadata updated for {doc.title}",
            )
        return doc

    # ------------------------------------------------------------------
    # Processing state
    # ------------------------------------------------------------------

    def get_processing(self, document_id: UUID) -> Optional[ProcessingState]:
        """Current processing state of the document."""
        return self.repo.get_processing(document_id)

    def get_processing_failure_reason(self, document_id: UUID) -> Optional[str]:
        """Persisted operational reason for the current failed state, if any."""
        return self.repo.get_processing_failure_reason(document_id)

    def transition_processing(
        self,
        document_id: UUID,
        target: "str | ProcessingState",
        *,
        user_id: str,
        failure_reason: "str | None" = None,
    ) -> ProcessingState:
        """Transition the document's processing state.

        Raises ``InvalidTransition`` if the transition is not allowed by the state
        machine (processing.py). A ``FAILED`` state is terminal; re-queuing requires
        an explicit administrative operation.
        """
        target_state = ProcessingState(target) if isinstance(target, str) else target
        current = self.repo.get_processing(document_id)
        if current is None:
            raise ValueError(f"No processing state for document {document_id}")

        assert_transition(current, target_state)
        if target_state == ProcessingState.READY:
            self.assert_ready(document_id)
        if not self.repo.compare_and_set_processing(
            document_id,
            current,
            target_state,
            failure_reason=failure_reason,
        ):
            actual = self.repo.get_processing(document_id)
            if actual is None:
                raise ValueError(f"No processing state for document {document_id}")
            raise InvalidTransition(actual, target_state)

        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.processing_transition",
            entity_type="document",
            entity_id=document_id,
            severity="WARN" if target_state == ProcessingState.FAILED else "INFO",
            message=f"Processing {current.value} -> {target_state.value}",
            metadata={
                "from": current.value,
                "to": target_state.value,
                "failure_reason": failure_reason,
            },
        )
        return target_state

    def set_ready_validator(
        self,
        validator: "Callable[[UUID], list[str]]",
    ) -> None:
        """Install the runtime's artifact-backed READY invariant validator."""
        self._ready_validator = validator

    def assert_ready(self, document_id: UUID) -> None:
        """Reject READY when any required persisted artifact is absent."""
        if self._ready_validator is None:
            return
        problems = self._ready_validator(document_id)
        if problems:
            raise ValueError(
                "Document is not ready: " + "; ".join(problems)
            )

    def requeue_processing(
        self,
        document_id: UUID,
        target: ProcessingState,
        *,
        user_id: str,
        reason: str,
    ) -> ProcessingState:
        """Begin an explicit, audited recovery/reprocessing cycle.

        This is the only supported way to leave READY or FAILED for an existing
        Document Version.  Targets correspond to the earliest stage that must
        run; callers must invalidate downstream derived artifacts first or as
        part of the same coordinator operation.
        """
        allowed = {
            ProcessingState.UPLOADED,
            ProcessingState.OCR_COMPLETED,
            ProcessingState.PARSING_RUNNING,
        }
        if target not in allowed:
            raise ValueError(f"Unsupported reprocessing target: {target.value}")
        document = self.repo.get(document_id)
        if document is None:
            raise ValueError(f"Document {document_id} not found")
        if document.status == DocumentStatus.ARCHIVED:
            raise ValueError("Archived documents must be restored before reprocessing")
        current = self.repo.get_processing(document_id)
        if current is None:
            raise ValueError(f"No processing state for document {document_id}")
        self.repo.set_processing(document_id, target)
        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.processing_requeued",
            entity_type="document",
            entity_id=document_id,
            severity="WARN",
            message=f"Processing requeued {current.value} -> {target.value}",
            metadata={
                "from": current.value,
                "to": target.value,
                "reason": reason,
                "user_id": user_id,
            },
        )
        return target

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def archive_document(self, document_id: UUID, *, user_id: str) -> Document:
        """Move a Document to ARCHIVED lifecycle status (not processing state).

        The Document's canonical ``status`` becomes ARCHIVED (document-contract.md
        lifecycle: Created -> Active -> Archived). The processing state also moves to
        ARCHIVED. Archived documents remain available for historical reference.
        """
        doc = self.repo.get(document_id)
        if doc is None:
            raise KeyError(f"Document {document_id} not found")
        if doc.status == DocumentStatus.ARCHIVED:
            raise ValueError(f"Document {document_id} is already archived")

        doc.status = DocumentStatus.ARCHIVED
        doc.touch()
        self.repo.save(doc, processing=ProcessingState.ARCHIVED)

        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.archive",
            entity_type="document",
            entity_id=doc.id,
            severity="INFO",
            message=f"Document {doc.title} archived",
        )
        return doc

    def restore_document(self, document_id: UUID, *, user_id: str) -> Document:
        """Restore an archived Document back to ACTIVE lifecycle status."""
        doc = self.repo.get(document_id)
        if doc is None:
            raise KeyError(f"Document {document_id} not found")
        if doc.status != DocumentStatus.ARCHIVED:
            raise ValueError(f"Document {document_id} is not archived")

        # Restoring visibility must not manufacture READY.  The runtime
        # validator proves that the source and all required derived artifacts
        # still exist before the lifecycle status is changed.
        self.assert_ready(document_id)

        doc.status = DocumentStatus.ACTIVE
        doc.touch()
        self.repo.save(doc, processing=ProcessingState.READY)

        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.restore",
            entity_type="document",
            entity_id=doc.id,
            severity="INFO",
            message=f"Document {doc.title} restored",
        )
        return doc

    # ------------------------------------------------------------------
    # Delete (administrative only)
    # ------------------------------------------------------------------

    def delete_document(self, document_id: UUID, *, user_id: str) -> bool:
        """Permanently delete a Document (administrative only).

        Per document-contract.md: "A Document is never physically deleted by normal
        business operations." This is an administrative operation for cleanup/rollback.
        """
        doc = self.repo.get(document_id)
        if doc is None:
            return False

        self.repo.delete(document_id)
        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.delete",
            entity_type="document",
            entity_id=document_id,
            severity="WARN",
            message=f"Document {doc.title} permanently deleted (admin)",
        )
        return True

    # ------------------------------------------------------------------
    # Duplicate detection
    # ------------------------------------------------------------------

    def find_by_checksum(self, checksum_sha256: str) -> list[tuple[UUID, UUID]]:
        """Return (document_id, version_id) pairs for every upload matching the checksum."""
        return self.repo.find_by_checksum(checksum_sha256)

    def compute_checksum(self, file_bytes: bytes) -> str:
        """Compute the SHA-256 checksum of uploaded file content."""
        return hashlib.sha256(file_bytes).hexdigest()

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    def get_relationships(self, document_id: UUID) -> list[tuple[UUID, str]]:
        """Return (related_document_id, kind) pairs."""
        return self.repo.find_relationships(document_id)

    def add_relationship(
        self, source_id: UUID, target_id: UUID, kind: str, *, user_id: str
    ) -> None:
        """Record a relationship between two documents."""
        self.repo.add_relationship(source_id, target_id, kind)
        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.relationship_add",
            entity_type="document",
            entity_id=source_id,
            severity="INFO",
            message=f"Relationship {kind}: {source_id} -> {target_id}",
        )

    # ------------------------------------------------------------------
    # Version management
    # ------------------------------------------------------------------

    def add_version(
        self,
        document_id: UUID,
        *,
        user_id: str,
        version_id: "UUID | None" = None,
        version_number: "int | None" = None,
    ) -> Document:
        """Add a new Document Version to an existing Document.

        The previous active version is marked SUPERSEDED; the new version becomes ACTIVE.
        The Document's ``updated_at`` is bumped.
        """
        doc = self.repo.get(document_id)
        if doc is None:
            raise KeyError(f"Document {document_id} not found")

        # Mark current active as superseded
        for v in doc.versions:
            if v.status == DocumentVersionStatus.ACTIVE:
                v.status = DocumentVersionStatus.SUPERSEDED

        next_num = version_number or (max(v.version_number for v in doc.versions) + 1)
        new_ver = DocumentVersionReference(
            version_id=version_id or new_id(),
            version_number=next_num,
            status=DocumentVersionStatus.ACTIVE,
            created_at=now_utc(),
        )
        doc.versions.append(new_ver)
        doc.touch()

        self.repo.save(doc, processing=self.repo.get_processing(document_id) or ProcessingState.UPLOADED)

        log_event(
            self.repo.conn,
            service="document-registry",
            module="registry",
            event="document.version_add",
            entity_type="document",
            entity_id=doc.id,
            severity="INFO",
            message=f"Version {new_ver.version_number} added to {doc.title}",
            metadata={"version_id": str(new_ver.version_id), "version_number": new_ver.version_number},
        )
        return doc

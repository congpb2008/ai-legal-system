"""Repository interface and SQLite implementation for the Document Registry.

The repository persists the canonical Document (Document Contract) plus the
Registry-owned mutable processing state and the relationships/checksum index used
for duplicate detection. The storage backend is SQLite (stdlib) but accessed through
the ``DocumentRepository`` Protocol so it can be swapped without changing the Registry
service or the Document Contract (architecture.md Replaceability).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable, Optional, Protocol
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.contracts.document import (
    Document,
    DocumentStatus,
    DocumentVersionReference,
    DocumentVersionStatus,
    Metadata,
    Visibility,
)
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.storage.db import in_memory


# ----------------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS document (
    id                  TEXT PRIMARY KEY,                       -- UUID (INV-004 immutable)
    type                TEXT NOT NULL,
    title               TEXT NOT NULL,
    short_title         TEXT,
    description         TEXT,
    issuing_authority   TEXT NOT NULL,
    document_number     TEXT,
    language            TEXT NOT NULL,
    status              TEXT NOT NULL,                          -- ACTIVE | ARCHIVED (canonical)
    visibility          TEXT NOT NULL,                          -- PUBLIC | DEPARTMENT | PERSONAL
    vault_id            TEXT NOT NULL,
    organization_id     TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    metadata            TEXT NOT NULL DEFAULT '{}',             -- JSON (Metadata; mutable, INV does not forbid)
    versions            TEXT NOT NULL DEFAULT '[]'              -- JSON list[DocumentVersionReference]
);

-- Registry-owned mutable processing state. Separate from canonical Document.status
-- per design decision (DC-003 + ADR-003): processing state is disposable; Document
-- lifecycle is canonical.
CREATE TABLE IF NOT EXISTS document_processing (
    document_id         TEXT PRIMARY KEY REFERENCES document(id) ON DELETE CASCADE,
    state               TEXT NOT NULL,
    state_updated_at    TEXT NOT NULL,
    failure_reason      TEXT
);

-- Document relationships (task 001 #Relationships). Identity-only; meaning inferred
-- downstream (not by the Registry).
CREATE TABLE IF NOT EXISTS document_relationship (
    source_id   TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    target_id   TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,   -- SUPERSEDES | SUPERSEDED_BY | AMENDS | AMENDED_BY | REFERENCES
    created_at  TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, kind)
);

-- Checksum index for duplicate detection (task 001 #Duplicate Detection).
-- One checksum may map to many Document versions because the same file may be uploaded
-- as part of multiple Document Versions.
CREATE TABLE IF NOT EXISTS checksum_index (
    checksum_sha256   TEXT NOT NULL,
    document_id       TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    version_id        TEXT NOT NULL,
    filename          TEXT,
    uploaded_at       TEXT NOT NULL,
    PRIMARY KEY (checksum_sha256, version_id)
);

CREATE INDEX IF NOT EXISTS idx_document_vault        ON document(vault_id);
CREATE INDEX IF NOT EXISTS idx_document_status        ON document(status);
CREATE INDEX IF NOT EXISTS idx_document_type         ON document(type);
CREATE INDEX IF NOT EXISTS idx_document_number       ON document(document_number);
CREATE INDEX IF NOT EXISTS idx_processing_state      ON document_processing(state);
"""


# ----------------------------------------------------------------------------
# Repository Protocol
# ----------------------------------------------------------------------------


class DocumentRepository(Protocol):
    """Storage abstraction for the Document Registry.

    All Document Contract invariants are enforced by the ``Document`` model before
    persistence; the repository is a thin storage boundary and never weakens them.
    """

    @property
    def conn(self) -> sqlite3.Connection:
        """The underlying database connection (needed for cross-cutting audit logging)."""
        ...

    def save(self, document: Document, *, processing: ProcessingState) -> None: ...

    def get(self, document_id: UUID) -> Optional[Document]: ...

    def list_documents(
        self,
        *,
        vault_id: Optional[UUID] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]: ...

    def find_by_checksum(self, checksum_sha256: str) -> list[tuple[UUID, UUID]]: ...

    def get_processing(self, document_id: UUID) -> Optional[ProcessingState]: ...

    def set_processing(
        self,
        document_id: UUID,
        state: ProcessingState,
        *,
        failure_reason: "str | None" = None,
    ) -> None: ...

    def compare_and_set_processing(
        self,
        document_id: UUID,
        expected: ProcessingState,
        target: ProcessingState,
        *,
        failure_reason: "str | None" = None,
    ) -> bool: ...

    def find_relationships(self, document_id: UUID) -> list[tuple[UUID, str]]: ...

    def add_relationship(
        self, source_id: UUID, target_id: UUID, kind: str, *, now: "datetime | None" = None
    ) -> None: ...

    def add_checksum(
        self,
        *,
        checksum_sha256: str,
        document_id: UUID,
        version_id: UUID,
        filename: "str | None" = None,
        uploaded_at: "datetime | None" = None,
    ) -> None: ...

    def delete(self, document_id: UUID) -> bool: ...


# ----------------------------------------------------------------------------
# SQLite implementation
# ----------------------------------------------------------------------------


class SqliteDocumentRepository:
    """SQLite-backed ``DocumentRepository``.

    All contract JSON fields (metadata, versions) are stored as JSON blobs; SQLAlchemy/
    a future ORM can normalize columns without changing this interface.
    """

    def __init__(self, conn: "sqlite3.Connection | None" = None):
        self._conn = conn or in_memory()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _doc_from_row(row: sqlite3.Row) -> Document:
        return Document.model_validate(
            {
                "id": UUID(row["id"]),
                "type": row["type"],
                "title": row["title"],
                "short_title": row["short_title"],
                "description": row["description"],
                "issuing_authority": row["issuing_authority"],
                "document_number": row["document_number"],
                "language": row["language"],
                "status": row["status"],
                "visibility": row["visibility"],
                "vault_id": UUID(row["vault_id"]),
                "organization_id": UUID(row["organization_id"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "versions": json.loads(row["versions"] or "[]"),
            }
        )

    @staticmethod
    def _doc_to_row(document: Document) -> dict[str, Any]:
        return {
            "id": str(document.id),
            "type": document.type.value,
            "title": document.title,
            "short_title": document.short_title,
            "description": document.description,
            "issuing_authority": document.issuing_authority,
            "document_number": document.document_number,
            "language": document.language,
            "status": document.status.value,
            "visibility": document.visibility.value,
            "vault_id": str(document.vault_id),
            "organization_id": str(document.organization_id),
            "created_at": utc_iso(document.created_at),
            "updated_at": utc_iso(document.updated_at),
            "metadata": document.metadata.model_dump_json(),
            "versions": json.dumps(
                [v.model_dump(mode="json") for v in document.versions],
            ),
        }

    # ------------------------------------------------------------------ writes
    def save(self, document: Document, *, processing: ProcessingState) -> None:
        row = self._doc_to_row(document)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO document
                  (id,type,title,short_title,description,issuing_authority,document_number,
                   language,status,visibility,vault_id,organization_id,created_at,updated_at,
                   metadata,versions)
                VALUES
                  (:id,:type,:title,:short_title,:description,:issuing_authority,:document_number,
                   :language,:status,:visibility,:vault_id,:organization_id,:created_at,:updated_at,
                   :metadata,:versions)
                ON CONFLICT(id) DO UPDATE SET
                  type=excluded.type, title=excluded.title, short_title=excluded.short_title,
                  description=excluded.description, issuing_authority=excluded.issuing_authority,
                  document_number=excluded.document_number, language=excluded.language,
                  status=excluded.status, visibility=excluded.visibility,
                  vault_id=excluded.vault_id, organization_id=excluded.organization_id,
                  updated_at=excluded.updated_at, metadata=excluded.metadata,
                  versions=excluded.versions
                """,
                row,
            )
            self._conn.execute(
                """
                INSERT INTO document_processing (document_id, state, state_updated_at, failure_reason)
                VALUES (:id, :state, :now, :reason)
                ON CONFLICT(document_id) DO UPDATE SET
                  state=excluded.state, state_updated_at=excluded.state_updated_at,
                  failure_reason=excluded.failure_reason
                """,
                {
                    "id": str(document.id),
                    "state": processing.value,
                    "now": utc_iso(now_utc()),
                    "reason": None,
                },
            )

    def get(self, document_id: UUID) -> Optional[Document]:
        row = self._conn.execute(
            "SELECT * FROM document WHERE id = ?", (str(document_id),)
        ).fetchone()
        return self._doc_from_row(row) if row else None

    def list_documents(
        self,
        *,
        vault_id: Optional[UUID] = None,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if vault_id is not None:
            clauses.append("vault_id = :vault_id")
            params["vault_id"] = str(vault_id)
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status.value
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM document{where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return [self._doc_from_row(r) for r in rows]

    def find_by_checksum(self, checksum_sha256: str) -> list[tuple[UUID, UUID]]:
        rows = self._conn.execute(
            "SELECT document_id, version_id FROM checksum_index WHERE checksum_sha256 = ?",
            (checksum_sha256,),
        )
        return [(UUID(r["document_id"]), UUID(r["version_id"])) for r in rows]

    def get_processing(self, document_id: UUID) -> Optional[ProcessingState]:
        row = self._conn.execute(
            "SELECT state FROM document_processing WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()
        return ProcessingState(row["state"]) if row else None

    def get_processing_failure_reason(self, document_id: UUID) -> Optional[str]:
        row = self._conn.execute(
            "SELECT failure_reason FROM document_processing WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()
        return row["failure_reason"] if row else None

    def set_processing(
        self,
        document_id: UUID,
        state: ProcessingState,
        *,
        failure_reason: "str | None" = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO document_processing (document_id, state, state_updated_at, failure_reason)
                VALUES (:id, :state, :now, :reason)
                ON CONFLICT(document_id) DO UPDATE SET
                  state=excluded.state, state_updated_at=excluded.state_updated_at,
                  failure_reason=excluded.failure_reason
                """,
                {
                    "id": str(document_id),
                    "state": state.value,
                    "now": utc_iso(now_utc()),
                    "reason": failure_reason,
                },
            )

    def compare_and_set_processing(
        self,
        document_id: UUID,
        expected: ProcessingState,
        target: ProcessingState,
        *,
        failure_reason: "str | None" = None,
    ) -> bool:
        """Atomically transition only when the persisted state is unchanged."""
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE document_processing
                SET state = ?, state_updated_at = ?, failure_reason = ?
                WHERE document_id = ? AND state = ?
                """,
                (
                    target.value,
                    utc_iso(now_utc()),
                    failure_reason,
                    str(document_id),
                    expected.value,
                ),
            )
        return cursor.rowcount == 1

    def find_relationships(self, document_id: UUID) -> list[tuple[UUID, str]]:
        rows = self._conn.execute(
            """
            SELECT target_id, kind FROM document_relationship WHERE source_id = ?
            UNION
            SELECT source_id, kind FROM document_relationship WHERE target_id = ?
            """,
            (str(document_id), str(document_id)),
        )
        return [(UUID(r["target_id"] if r["target_id"] else r["source_id"]), r["kind"]) for r in rows]

    def add_relationship(
        self, source_id: UUID, target_id: UUID, kind: str, *, now: "datetime | None" = None
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO document_relationship (source_id, target_id, kind, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(source_id), str(target_id), kind, utc_iso(now or now_utc())),
            )

    def add_checksum(
        self,
        *,
        checksum_sha256: str,
        document_id: UUID,
        version_id: UUID,
        filename: "str | None" = None,
        uploaded_at: "datetime | None" = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO checksum_index
                  (checksum_sha256, document_id, version_id, filename, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    checksum_sha256,
                    str(document_id),
                    str(version_id),
                    filename,
                    utc_iso(uploaded_at or now_utc()),
                ),
            )

    def delete(self, document_id: UUID) -> bool:
        cur = self._conn.execute("DELETE FROM document WHERE id = ?", (str(document_id),))
        self._conn.commit()
        return cur.rowcount > 0

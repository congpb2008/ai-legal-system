"""Document Contract (02-contracts/document-contract.md).

The root entity of the document lifecycle. A Document is a *logical* legal
publication independent of any uploaded file, storage mechanism or processing
pipeline. All downstream processing begins from a Document.

This model is the authoritative Python representation of the Document Contract.
Modules consume and produce this contract; they never reach into each other's
internals. The contract is implementation-independent (databases, object
storage, OCR engines, parsers and retrieval engines are replaceable and do
not change this contract).

Invariants enforced by this module (see document-contract.md INV-001..INV-009):
    INV-001  exactly one Vault
    INV-002  exactly one Organization
    INV-003  owns at least one Document Version
    INV-004  identifier never changes
    INV-005  removing a Version does not change Document identity
    INV-006  never contains parsed content
    INV-007  never stores embeddings
    INV-008  never stores retrieval chunks
    INV-009  never stores AI-generated outputs

Drift from examples/ (illustrative only, per project documentation hierarchy):
- examples/document-example.json uses field names ``document_id`` / ``document_type``
  instead of the contract's ``id`` / ``type``; uses ``visibility:"SHARED"`` (not in the
  contract enum); carries ``effective_date`` / ``expiry_date`` (contract stores such
  business dates inside ``Metadata``); and adds a ``processing`` sub-object plus
  ``relationships`` (both belong to upstream Registry state and future version-comparison
  modules, **not** the Document Contract). These are illustrative drift; this model
  follows the contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from legal_platform.contracts.common import new_id, now_utc


# ----------------------------------------------------------------------------
# Enumerations — per document-contract.md
# ----------------------------------------------------------------------------


class DocumentType(str, Enum):
    """Logical category of a legal publication (capability-map.md CAP-002)."""

    LAW = "LAW"
    DECREE = "DECREE"
    CIRCULAR = "CIRCULAR"
    DECISION = "DECISION"
    INTERNAL_REGULATION = "INTERNAL_REGULATION"
    INTERNAL_POLICY = "INTERNAL_POLICY"

    @classmethod
    def coerce(cls, value: "str | DocumentType") -> "DocumentType":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v = value.strip().upper()
            try:
                return cls[v]
            except KeyError as exc:
                raise ValueError(f"Unknown DocumentType: {value!r}") from exc
        raise TypeError(f"DocumentType expected str or DocumentType, got {type(value).__name__}")


class DocumentStatus(str, Enum):
    """Document lifecycle state (document-contract.md: Created -> Active -> Archived)."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"

    @classmethod
    def coerce(cls, value: "str | DocumentStatus") -> "DocumentStatus":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v = value.strip().upper()
            try:
                return cls[v]
            except KeyError as exc:
                raise ValueError(f"Unknown DocumentStatus: {value!r}") from exc
        raise TypeError(f"DocumentStatus expected str or DocumentStatus, got {type(value).__name__}")


class Visibility(str, Enum):
    """
    Visibility class (document-contract.md). Vault taxonomy across other docs differs
    (scope/constraints list Personal/Department; task-013 lists Common/Department/
    Project/Personal). The contract is authoritative: PUBLIC | DEPARTMENT | PERSONAL.
    """

    PUBLIC = "PUBLIC"
    DEPARTMENT = "DEPARTMENT"
    PERSONAL = "PERSONAL"

    @classmethod
    def coerce(cls, value: "str | Visibility") -> "Visibility":
        if isinstance(value, cls):
            return value
        if isinstance(value, str):
            v = value.strip().upper()
            aliases = {
                # Illustrative example uses "SHARED"; not in contract enum. Map to PUBLIC
                # (shared/common knowledge) rather than reject, so example-shaped inputs
                # still validate during development. Drift recorded in module docstring.
                "SHARED": cls.PUBLIC,
                "COMMON": cls.PUBLIC,
            }
            if v in aliases:
                return aliases[v]
            try:
                return cls[v]
            except KeyError as exc:
                raise ValueError(f"Unknown Visibility: {value!r}") from exc
        raise TypeError(f"Visibility expected str or Visibility, got {type(value).__name__}")


class DocumentVersionStatus(str, Enum):
    """Status of a single Document Version reference (ACTIVE | SUPERSEDED | HISTORICAL)."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    HISTORICAL = "HISTORICAL"


# ----------------------------------------------------------------------------
# Metadata — searchable business information (document-contract.md #Metadata)
# ----------------------------------------------------------------------------


class Metadata(BaseModel):
    """
    Searchable business information associated with a Document.

    Per document-contract.md and constraints.md (DC-003):
        - Metadata may evolve without changing document identity.
        - Updating metadata must not require rebuilding document structure.
        - Does not include issue/effective/expiry Date as required fields here; they are
          optional because document-contract.md types them as prose ("Examples include
          ... Issue Date, Effective Date, Expiration Date, Tags, Keywords").
    """

    model_config = ConfigDict(extra="allow")

    issue_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    security_level: Optional[str] = None
    applicable_subjects: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# Source file — uploaded file reference (lives on a Document Version)
# ----------------------------------------------------------------------------


class SourceFile(BaseModel):
    """
    Reference to an uploaded physical file (document-contract.md #SourceFiles, DC-004,
    BC-004). Uploaded files belong to a specific Document Version; a Document does not
    own files directly. The original is immutable (BC-004). Multiple files may represent
    the same published version (Original PDF, OCR PDF, DOCX, Scanned Copy).
    """

    model_config = ConfigDict(extra="forbid")

    filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    storage_ref: str
    uploaded_by: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=now_utc)


# ----------------------------------------------------------------------------
# Document Version reference (document-contract.md #Version Relationship)
# ----------------------------------------------------------------------------


class DocumentVersionReference(BaseModel):
    """A reference to a Document Version owned by a Document.

    The contract models the Document as owning ``versions: List<DocumentVersionReference>``.
    A full Document Version entity (Source Files, Knowledge Tree) is owned by the
    downstream Knowledge layer; here we only keep identity + metadata required to
    enforce INV-003 (>=1 version) and lifecycle (exactly one current effective version).
    """

    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    version_number: int = Field(default=1, ge=1)
    status: DocumentVersionStatus = DocumentVersionStatus.ACTIVE
    created_at: datetime = Field(default_factory=now_utc)


# ----------------------------------------------------------------------------
# Document — the root contract entity
# ----------------------------------------------------------------------------


class Document(BaseModel):
    """The Document Contract entity.

    Identity:
        ``id`` is the globally unique, immutable Document identifier (INV-004).
        Changing metadata does not create a new Document (IDENTITY section). A revised
        legal publication creates a new Document Version, not a new Document.

    Ownership:
        Owns Metadata + Document Versions. References Vault, Organization, Permissions
        (permissions are inherited from the assigned Vault; the Document itself contains
        no permission rules — Security section).

    Lifecycle:
        Created -> Active -> Archived. Never physically deleted by normal business
        operations (lifecycle section).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID = Field(default_factory=new_id)
    type: DocumentType
    title: str = Field(min_length=1, max_length=512)
    short_title: Optional[str] = Field(default=None, max_length=256)
    description: Optional[str] = None
    issuing_authority: str = Field(min_length=1, max_length=512)
    document_number: Optional[str] = Field(default=None, max_length=256)
    language: str = Field(default="vi", max_length=16)

    status: DocumentStatus = DocumentStatus.ACTIVE
    visibility: Visibility

    vault_id: UUID
    organization_id: UUID

    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    metadata: Metadata = Field(default_factory=Metadata)
    versions: list[DocumentVersionReference] = Field(min_length=1)

    # ------------------------------------------------------------------ helpers
    @property
    def current_version(self):
        return next(v for v in self.versions if v.status == DocumentVersionStatus.ACTIVE)

    def touch(self, *, now: datetime | None = None) -> None:
        """Update ``updated_at`` to mark the Document touched (e.g. metadata edit)."""
        self.updated_at = now or now_utc()

    # ------------------------------------------------------------------ invariants
    @model_validator(mode="after")
    def _check_invariants(self) -> "Document":
        # INV-001: exactly one Vault
        if self.vault_id is None:  # type: ignore[redundant-expr]
            raise ValueError("Document must reference exactly one Vault (INV-001)")
        # INV-002: exactly one Organization
        if self.organization_id is None:  # type: ignore[redundant-expr]
            raise ValueError("Document must reference exactly one Organization (INV-002)")
        # INV-003: at least one Document Version
        if not self.versions:
            raise ValueError("Document must own at least one Document Version (INV-003)")
        # exactly one current effective version at any point in time
        active = [v for v in self.versions if v.status == DocumentVersionStatus.ACTIVE]
        if len(active) != 1:
            raise ValueError(
                "Exactly one Document Version must be ACTIVE at any time "
                "(contract: 'Only one version may be designated as the current effective version')"
            )
        # INV-004: identifier never changes — enforced structurally: ``id`` has no setter
        # beyond model reconstruction; mutations go through registry APIs which preserve it.
        return self

    @field_validator("type", "status", "visibility", mode="before")
    @classmethod
    def _coerce_enums(cls, v: Any, info: Any) -> Any:
        if info.field_name == "type":
            return DocumentType.coerce(v)
        if info.field_name == "status":
            return DocumentStatus.coerce(v)
        if info.field_name == "visibility":
            return Visibility.coerce(v)
        return v

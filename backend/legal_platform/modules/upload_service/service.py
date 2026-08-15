"""Upload Service (tasks/002-upload-service.md).

The Upload Service receives files from users, validates them, stores the original
immutably, computes a SHA-256 checksum, and forwards validated metadata to the
Document Registry. It returns the assigned Document ID.

Per the task spec:
    - Uploading a file is NOT equivalent to registering a document.
    - The Upload Service only handles file transfer and storage.
    - Document identity is assigned by the Document Registry (Task 001).
    - Validation occurs before permanent storage.
    - Duplicate detection by checksum is reported; the policy belongs to the Registry.
    - Failed uploads are cleaned up (no partial state).
"""

from __future__ import annotations

import mimetypes
import zipfile
from io import BytesIO
from xml.etree import ElementTree
from dataclasses import dataclass, field
from datetime import datetime
from typing import BinaryIO, Optional
from uuid import UUID

from legal_platform.contracts.common import new_id, now_utc
from legal_platform.contracts.document import Document, DocumentType, Visibility
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.document_registry.vault import AllowAllVaults, VaultResolver
from legal_platform.modules.upload_service.file_storage import (
    FileStorage,
    LocalFileStorage,
    StorageError,
    StoredFile,
)
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# Supported MIME types (tasks/002 #Inputs)
# ---------------------------------------------------------------------------

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

# Characters that are unsafe in filenames — replaced with underscores
_UNSAFE_FILENAME_CHARS = set('/\\:*?"<>|\x00-\x1f')


def _sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and injection.

    - Replaces unsafe characters with underscores.
    - Collapses multiple path separators.
    - Rejects empty results.
    """
    # Replace unsafe chars
    result = "".join("_" if c in _UNSAFE_FILENAME_CHARS else c for c in filename)
    # Collapse multiple dots, spaces, underscores
    import re as _re
    result = _re.sub(r'[._\s]+', '_', result)
    # Strip leading/trailing separators
    result = result.strip("._- ")
    # Ensure we have something left
    if not result:
        result = "uploaded_file"
    return result

# Future types (per spec): DOC, TIFF, PNG, JPG
FUTURE_MIME_TYPES: dict[str, str] = {
    "application/msword": "doc",
    "image/tiff": "tiff",
    "image/png": "png",
    "image/jpeg": "jpg",
}

# Maximum upload size (configurable; 100 MB default per enterprise document size)
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class UploadResult:
    """Result of an upload operation.

    Fields:
        document_id: the stable Document ID assigned by the Registry.
        storage_ref: opaque reference to the stored original file.
        checksum_sha256: SHA-256 checksum of the uploaded content.
        filename: original filename.
        mime_type: detected/declared MIME type.
        size_bytes: file size in bytes.
        duplicate_candidates: list of (document_id, version_id) for any existing
            uploads with the same checksum (empty list if none).
        status: "ACCEPTED" for a new registration, "DUPLICATE_REPORTED" if
            duplicates were found (the Registry's policy determines the action).
    """

    document_id: UUID
    storage_ref: str
    checksum_sha256: str
    filename: str
    mime_type: str
    size_bytes: int
    duplicate_candidates: list[tuple[UUID, UUID]] = field(default_factory=list)
    status: str = "ACCEPTED"


# ---------------------------------------------------------------------------
# Upload errors
# ---------------------------------------------------------------------------


class UploadError(ValueError):
    """Raised when an upload fails validation or processing."""


class UnsupportedFileType(UploadError):
    """Raised when the uploaded file type is not supported."""


class FileTooLarge(UploadError):
    """Raised when the uploaded file exceeds the maximum size."""


class CorruptedUpload(UploadError):
    """Raised when the upload appears incomplete or corrupted."""


# ---------------------------------------------------------------------------
# Upload Service
# ---------------------------------------------------------------------------


class UploadService:
    """The Upload Service.

    Validates, stores, and registers uploaded legal documents.

    All public methods accept a ``user_id`` parameter for audit logging and future
    authorization. The current ``AllowAllVaults`` stub permits all vault operations;
    Task 013 will replace it with real vault authorization.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        file_storage: "FileStorage | None" = None,
        vault_resolver: "VaultResolver | None" = None,
        *,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ):
        self.registry = registry or DocumentRegistry()
        # The application runtime injects its configured persistent storage.
        # A standalone service gets an isolated temporary backend so tests and
        # ad-hoc tools can never write into a developer's real corpus by accident.
        self.storage = file_storage or LocalFileStorage()
        self.vault = vault_resolver or AllowAllVaults()
        self.max_upload_bytes = max_upload_bytes
        # Ensure audit table exists (shared with Registry)
        init_audit_log(self.registry.repo.conn)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(
        self,
        *,
        user_id: str,
        content: "BinaryIO | bytes",
        filename: str,
        mime_type: "str | None" = None,
        # --- document metadata (forwarded to Registry) ---
        document_type: "str | DocumentType",
        title: str,
        issuing_authority: str,
        vault_id: UUID,
        organization_id: UUID,
        document_number: "str | None" = None,
        short_title: "str | None" = None,
        description: "str | None" = None,
        language: str = "vi",
        visibility: "str | Visibility" = Visibility.DEPARTMENT,
        metadata: "dict | None" = None,
        # --- relationships ---
        supersedes: "list[UUID] | None" = None,
        amends: "list[UUID] | None" = None,
        references: "list[UUID] | None" = None,
    ) -> UploadResult:
        """Upload a file and register it as a new Document.

        Flow (per tasks/002 #ProcessingFlow):
            1. File validation (type, size, integrity)
            2. Vault authorization
            3. Temporary storage
            4. Checksum calculation
            5. Store original file
            6. Register Document with Registry
            7. Return Document ID

        Raises:
            UnsupportedFileType: if the MIME type is not supported.
            FileTooLarge: if the file exceeds ``max_upload_bytes``.
            CorruptedUpload: if the upload appears incomplete.
            UploadError: on other validation failures.
        """
        # --- resolve MIME type ---
        resolved_mime = self._resolve_mime_type(filename, mime_type)

        # Office creates lock files such as ``~$contract.docx`` beside the real
        # document. Folder pickers expose them, but they are not legal sources.
        leaf_name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if leaf_name.startswith("~$"):
            raise CorruptedUpload(
                "Office temporary/lock files beginning with '~$' cannot be uploaded"
            )

        # --- sanitize filename (path traversal / injection protection) ---
        safe_filename = _sanitize_filename(filename)

        # --- read content ---
        raw: bytes
        if isinstance(content, bytes):
            raw = content
        else:
            raw = content.read()

        # --- validation ---
        self._validate(raw, resolved_mime)

        # --- vault authorization ---
        if not self.vault.vault_exists(vault_id):
            raise UploadError(f"Vault {vault_id} does not exist")
        if not self.vault.user_can_upload_to_vault(user_id, vault_id):
            raise UploadError(f"User {user_id} is not authorized to upload to vault {vault_id}")

        # --- compute checksum (before storage for early duplicate check) ---
        checksum = self.registry.compute_checksum(raw)
        size = len(raw)

        # --- check for duplicates (informational) ---
        duplicate_candidates = self.registry.find_by_checksum(checksum)

        # --- store original file ---
        try:
            stored = self.storage.store(
                content=raw,
                filename=safe_filename,
                mime_type=resolved_mime,
            )
        except StorageError as e:
            raise UploadError(f"Failed to store file: {e}") from e

        # --- register document with Registry ---
        try:
            doc = self.registry.register_document(
                user_id=user_id,
                document_type=document_type,
                title=title,
                issuing_authority=issuing_authority,
                vault_id=vault_id,
                organization_id=organization_id,
                document_number=document_number,
                short_title=short_title,
                description=description,
                language=language,
                visibility=visibility,
                metadata=metadata,
                source_checksum_sha256=checksum,
                source_filename=filename,
                source_mime_type=resolved_mime,
                source_size_bytes=size,
                source_storage_ref=stored.storage_ref,
                source_uploaded_by=user_id,
                supersedes=supersedes,
                amends=amends,
                references=references,
            )
        except Exception:
            # Registration failed — clean up stored file
            try:
                self.storage.delete(stored.storage_ref)
            except StorageError:
                pass  # best-effort cleanup
            raise

        # --- audit ---
        log_event(
            self.registry.repo.conn,
            service="upload-service",
            module="upload",
            event="upload.complete",
            entity_type="document",
            entity_id=doc.id,
            severity="INFO",
            message=f"Upload completed for {filename}",
            metadata={
                "filename": filename,
                "mime_type": resolved_mime,
                "size_bytes": size,
                "checksum": checksum,
                "duplicate_count": len(duplicate_candidates),
            },
        )

        return UploadResult(
            document_id=doc.id,
            storage_ref=stored.storage_ref,
            checksum_sha256=checksum,
            filename=filename,
            mime_type=resolved_mime,
            size_bytes=size,
            duplicate_candidates=duplicate_candidates,
            status="DUPLICATE_REPORTED" if duplicate_candidates else "ACCEPTED",
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _resolve_mime_type(self, filename: str, declared: "str | None") -> str:
        """Resolve the MIME type from declaration or filename extension."""
        if declared and declared in SUPPORTED_MIME_TYPES:
            return declared
        if declared and declared in FUTURE_MIME_TYPES:
            raise UnsupportedFileType(
                f"MIME type '{declared}' is not yet supported (future type: {FUTURE_MIME_TYPES[declared]})"
            )
        # Guess from extension
        guessed, _ = mimetypes.guess_type(filename)
        if guessed and guessed in SUPPORTED_MIME_TYPES:
            return guessed
        if guessed and guessed in FUTURE_MIME_TYPES:
            raise UnsupportedFileType(
                f"File type '{guessed}' is not yet supported (future type: {FUTURE_MIME_TYPES[guessed]})"
            )
        raise UnsupportedFileType(
            f"Unsupported file type: {filename} (declared: {declared!r}, guessed: {guessed!r}). "
            f"Supported: {', '.join(sorted(SUPPORTED_MIME_TYPES.keys()))}"
        )

    def _validate(self, content: bytes, mime_type: str) -> None:
        """Validate file content against business rules.

        Raises:
            UnsupportedFileType: if the MIME type is not supported.
            FileTooLarge: if the file exceeds the maximum size.
            CorruptedUpload: if the file is empty or appears corrupted.
        """
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise UnsupportedFileType(
                f"Unsupported MIME type: {mime_type}. "
                f"Supported: {', '.join(sorted(SUPPORTED_MIME_TYPES.keys()))}"
            )

        if not content:
            raise CorruptedUpload("Uploaded file is empty")

        if len(content) > self.max_upload_bytes:
            raise FileTooLarge(
                f"File size {len(content)} bytes exceeds maximum {self.max_upload_bytes} bytes"
            )

        # Basic corruption detection: PDF magic bytes
        if mime_type == "application/pdf" and not content.startswith(b"%PDF"):
            raise CorruptedUpload("File declared as PDF but does not start with PDF magic bytes")

        if mime_type == (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ):
            self._validate_docx(content)

    def _validate_docx(self, content: bytes) -> None:
        """Validate the actual Word package before immutable persistence."""
        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                if package.testzip() is not None:
                    raise CorruptedUpload("DOCX package contains a corrupted entry")
                names = set(package.namelist())
                if "word/document.xml" not in names:
                    raise CorruptedUpload(
                        "DOCX package is missing word/document.xml"
                    )
                total_uncompressed = sum(info.file_size for info in package.infolist())
                if total_uncompressed > self.max_upload_bytes * 10:
                    raise CorruptedUpload(
                        "DOCX expanded content exceeds the safe processing limit"
                    )
                document_xml = package.read("word/document.xml")
        except zipfile.BadZipFile as exc:
            raise CorruptedUpload("File declared as DOCX is not a valid ZIP package") from exc

        try:
            root = ElementTree.fromstring(document_xml)
        except ElementTree.ParseError as exc:
            raise CorruptedUpload("DOCX contains invalid document XML") from exc
        word_namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        if root.tag != f"{{{word_namespace}}}document":
            raise CorruptedUpload("DOCX main part is not a Word document")
        text_nodes = root.findall(f".//{{{word_namespace}}}t")
        if not any((node.text or "").strip() for node in text_nodes):
            raise CorruptedUpload("DOCX contains no extractable document text")

    # ------------------------------------------------------------------
    # Query upload status
    # ------------------------------------------------------------------

    def get_upload_status(self, document_id: UUID) -> Optional[dict]:
        """Query the processing status of a previously uploaded document.

        Returns a dict with document metadata and current processing state,
        or None if the document is not found.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            return None
        processing = self.registry.get_processing(document_id)
        return {
            "document_id": doc.id,
            "title": doc.title,
            "status": doc.status.value,
            "processing_state": processing.value if processing else None,
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }

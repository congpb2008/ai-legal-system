"""File storage abstraction (tasks/002 #StorageRequirements).

The Upload Service stores original files immutably (BC-004). The storage backend
is abstracted behind ``FileStorage`` so it can be swapped (local filesystem, S3,
MinIO, etc.) without changing the service (ADR-003: derived infrastructure is
replaceable).

The original filename is preserved; the storage location is implementation-specific
and the service returns a ``storage_ref`` rather than exposing physical paths.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Optional, Protocol
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc


@dataclass
class StoredFile:
    """Result of a successful file storage operation.

    Fields:
        storage_ref: opaque reference for retrieval (never exposes physical paths).
        checksum_sha256: SHA-256 of the stored content.
        size_bytes: file size in bytes.
        mime_type: detected/declared MIME type.
        filename: original filename preserved from upload.
        stored_at: UTC timestamp of storage.
    """

    storage_ref: str
    checksum_sha256: str
    size_bytes: int
    mime_type: str
    filename: str
    stored_at: datetime = field(default_factory=now_utc)


class FileStorage(Protocol):
    """Abstract file storage backend.

    All operations are idempotent where possible. The storage backend is
    replaceable (ADR-003); the Upload Service depends only on this Protocol.
    """

    def store(
        self,
        *,
        content: "BinaryIO | bytes",
        filename: str,
        mime_type: str,
    ) -> StoredFile:
        """Store an uploaded file immutably.

        Args:
            content: file content (stream or bytes).
            filename: original filename.
            mime_type: declared MIME type.

        Returns:
            A ``StoredFile`` with an opaque ``storage_ref``.

        Raises:
            StorageError: if the store operation fails.
        """
        ...

    def retrieve(self, storage_ref: str) -> bytes:
        """Retrieve stored file content by its storage reference.

        Raises:
            StorageError: if the reference is not found or retrieval fails.
        """
        ...

    def delete(self, storage_ref: str) -> bool:
        """Delete a stored file. Returns True if deleted, False if not found.

        Raises:
            StorageError: on unexpected failure.
        """
        ...

    def exists(self, storage_ref: str) -> bool:
        """True if a file with the given storage reference exists."""
        ...


class StorageError(IOError):
    """Raised when a file storage operation fails."""


# ---------------------------------------------------------------------------
# Local filesystem implementation
# ---------------------------------------------------------------------------


class LocalFileStorage:
    """Filesystem-backed ``FileStorage``.

    Files are stored under ``base_path / <prefix> / <uuid> / <filename>``.
    The ``storage_ref`` is a relative path from ``base_path``, opaque to callers.
    """

    def __init__(self, base_path: "str | Path | None" = None):
        # A bare storage instance is an isolated test/development convenience.
        # The application runtime always supplies its configured persistent root.
        self.base_path = Path(base_path) if base_path is not None else Path(
            tempfile.mkdtemp(prefix="legal-platform-storage-")
        )
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        *,
        content: "BinaryIO | bytes",
        filename: str,
        mime_type: str,
    ) -> StoredFile:
        # Read content (stream or bytes)
        raw: bytes
        if isinstance(content, bytes):
            raw = content
        else:
            raw = content.read()

        if not raw:
            raise StorageError("Cannot store empty file")

        # Compute checksum before writing
        checksum = hashlib.sha256(raw).hexdigest()
        size = len(raw)

        # Determine storage path
        prefix = checksum[:2]  # shard by first two hex chars
        file_id = str(uuid4())
        rel_path = Path(prefix) / file_id / filename
        abs_path = self.base_path / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)

        # Write (atomic via temp + rename to avoid partial writes)
        tmp_path = abs_path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            tmp_path.write_bytes(raw)
            tmp_path.rename(abs_path)
        except OSError as e:
            # Clean up temp on failure
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            raise StorageError(f"Failed to store file: {e}") from e

        return StoredFile(
            storage_ref=str(rel_path),
            checksum_sha256=checksum,
            size_bytes=size,
            mime_type=mime_type,
            filename=filename,
            stored_at=now_utc(),
        )

    def _resolve_ref(self, storage_ref: str) -> Path:
        """Resolve an opaque reference and reject traversal outside the root."""
        candidate = (self.base_path / storage_ref).resolve()
        root = self.base_path.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise StorageError("Invalid storage reference") from exc
        return candidate

    def retrieve(self, storage_ref: str) -> bytes:
        abs_path = self._resolve_ref(storage_ref)
        if not abs_path.exists():
            raise StorageError(f"File not found: {storage_ref}")
        try:
            return abs_path.read_bytes()
        except OSError as e:
            raise StorageError(f"Failed to read file: {e}") from e

    def delete(self, storage_ref: str) -> bool:
        abs_path = self._resolve_ref(storage_ref)
        if not abs_path.exists():
            return False
        try:
            abs_path.unlink()
            # Clean up parent dirs if empty
            parent = abs_path.parent
            while parent != self.base_path:
                if any(parent.iterdir()):
                    break
                parent.rmdir()
                parent = parent.parent
            return True
        except OSError as e:
            raise StorageError(f"Failed to delete file: {e}") from e

    def exists(self, storage_ref: str) -> bool:
        try:
            return self._resolve_ref(storage_ref).exists()
        except StorageError:
            return False

    def cleanup(self) -> None:
        """Remove all stored files (test convenience / temp cleanup)."""
        if self.base_path.exists():
            shutil.rmtree(self.base_path)

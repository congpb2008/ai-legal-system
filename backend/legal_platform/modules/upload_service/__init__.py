"""Upload Service (tasks/002-upload-service.md, module Ingestion).

The Upload Service receives files from users and prepares them for registration.
It validates uploads, stores original files, and forwards valid documents to the
Document Registry.

Per the task, the Upload Service does NOT:
    - parse PDF, OCR images, extract metadata, create Knowledge Trees,
      generate embeddings, or answer user queries.

Design notes (grounded in the specs):
    - Uploading a file is NOT equivalent to registering a document. The Upload
      Service only handles file transfer and storage; Document identity is assigned
      by the Document Registry (Task 001).
    - Original files are immutable (BC-004) and stored via a ``FileStorage``
      abstraction so the backend is replaceable (ADR-003).
    - Validation happens before permanent storage; failed uploads are cleaned up.
    - The service streams large files rather than loading them fully into memory.
    - Duplicate detection by checksum is reported to the caller; the reuse/new-version
      policy belongs to the Document Registry.
"""

from legal_platform.modules.upload_service.file_storage import (
    FileStorage,
    LocalFileStorage,
    StoredFile,
)
from legal_platform.modules.upload_service.service import UploadService, UploadResult

__all__ = [
    "FileStorage",
    "LocalFileStorage",
    "StoredFile",
    "UploadService",
    "UploadResult",
]
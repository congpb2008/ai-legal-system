"""Tests for the Upload Service (Task 002).

Covers:
    - File validation (type, size, corruption)
    - Successful upload flow (store + register + return Document ID)
    - Duplicate detection (checksum-based, informational)
    - Vault authorization (AllowAllVaults stub for now)
    - Error handling (cleanup on registration failure)
    - File storage roundtrip
    - Upload status query
    - Audit logging

The authoritative source is the Document Contract (02-contracts/document-contract.md)
and the Upload Service specification (tasks/002-upload-service.md).
"""

import io
import os
import tempfile
from pathlib import Path
from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.contracts.document import DocumentStatus
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.upload_service.file_storage import (
    LocalFileStorage,
    StorageError,
    StoredFile,
)
from legal_platform.modules.upload_service.service import (
    CorruptedUpload,
    FileTooLarge,
    UnsupportedFileType,
    UploadError,
    UploadResult,
    UploadService,
    DEFAULT_MAX_UPLOAD_BYTES,
)
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def upload_service():
    return UploadService()


@pytest.fixture
def pdf_bytes() -> bytes:
    """Minimal valid PDF content."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF"


@pytest.fixture
def docx_bytes() -> bytes:
    """Minimal valid DOCX content."""
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
        z.writestr(
            "word/document.xml",
            """<?xml version='1.0'?>
            <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
              <w:body><w:p><w:r><w:t>Điều 1. Nội dung pháp lý</w:t></w:r></w:p></w:body>
            </w:document>""",
        )
    return buf.getvalue()


# ======================================================================
# 1. File Validation
# ======================================================================


class TestFileValidation:
    """Upload validation rules (tasks/002 #Validation)."""

    def test_accepts_pdf(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="test.pdf",
            document_type="DECISION",
            title="Test PDF",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert isinstance(result, UploadResult)
        assert result.mime_type == "application/pdf"

    def test_accepts_docx(self, upload_service, docx_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=docx_bytes,
            filename="test.docx",
            document_type="CIRCULAR",
            title="Test DOCX",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert isinstance(result, UploadResult)
        assert result.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_rejects_office_lock_file_before_storage(self, upload_service, docx_bytes):
        with pytest.raises(CorruptedUpload, match="temporary/lock"):
            upload_service.upload(
                user_id="admin",
                content=docx_bytes,
                filename="~$legal-document.docx",
                document_type="CIRCULAR",
                title="Office lock",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )
        assert upload_service.registry.list_documents() == []

    def test_rejects_docx_without_main_document(self, upload_service):
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as package:
            package.writestr("[Content_Types].xml", "<Types />")
        with pytest.raises(CorruptedUpload, match="word/document.xml"):
            upload_service.upload(
                user_id="admin",
                content=buf.getvalue(),
                filename="broken.docx",
                document_type="CIRCULAR",
                title="Broken DOCX",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )
        assert upload_service.registry.list_documents() == []

    def test_rejects_unsupported_type(self, upload_service):
        with pytest.raises(UnsupportedFileType):
            upload_service.upload(
                user_id="admin",
                content=b"some text",
                filename="test.txt",
                document_type="DECISION",
                title="Test",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_rejects_empty_file(self, upload_service):
        with pytest.raises(CorruptedUpload, match="empty"):
            upload_service.upload(
                user_id="admin",
                content=b"",
                filename="empty.pdf",
                mime_type="application/pdf",
                document_type="DECISION",
                title="Empty",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_rejects_corrupted_pdf(self, upload_service):
        with pytest.raises(CorruptedUpload, match="PDF magic bytes"):
            upload_service.upload(
                user_id="admin",
                content=b"not a pdf at all",
                filename="fake.pdf",
                mime_type="application/pdf",
                document_type="DECISION",
                title="Fake",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_rejects_oversized_file(self, upload_service):
        big = b"x" * (DEFAULT_MAX_UPLOAD_BYTES + 1)
        with pytest.raises(FileTooLarge):
            upload_service.upload(
                user_id="admin",
                content=big,
                filename="big.pdf",
                mime_type="application/pdf",
                document_type="DECISION",
                title="Big",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_mime_resolution_from_extension(self, upload_service, pdf_bytes):
        """MIME type should be guessed from filename when not declared."""
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="document.pdf",
            mime_type=None,
            document_type="DECISION",
            title="MIME Guess",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert result.mime_type == "application/pdf"

    def test_rejects_future_type(self, upload_service):
        with pytest.raises(UnsupportedFileType, match="future"):
            upload_service.upload(
                user_id="admin",
                content=b"\x89PNG\r\n\x1a\n",
                filename="test.png",
                mime_type="image/png",
                document_type="DECISION",
                title="PNG",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )


# ======================================================================
# 2. Successful Upload
# ======================================================================


class TestSuccessfulUpload:
    """Happy-path upload flow (tasks/002 #ProcessingFlow)."""

    def test_returns_document_id(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="decision.pdf",
            document_type="DECISION",
            title="Procurement Decision",
            issuing_authority="ABC Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        assert isinstance(result.document_id, UUID)
        assert result.status == "ACCEPTED"
        assert result.filename == "decision.pdf"
        assert result.mime_type == "application/pdf"
        assert result.size_bytes == len(pdf_bytes)
        assert result.checksum_sha256 is not None
        assert result.storage_ref is not None

    def test_document_is_registered(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="regtest.pdf",
            document_type="CIRCULAR",
            title="Registration Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        doc = upload_service.registry.get_document(result.document_id)
        assert doc is not None
        assert doc.title == "Registration Test"
        assert doc.status == DocumentStatus.ACTIVE

    def test_upload_with_full_metadata(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="full.pdf",
            document_type="DECISION",
            title="Full Metadata",
            issuing_authority="Central Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            document_number="01/2026/QD-NH",
            short_title="QD 01/2026",
            description="Test document",
            language="vi",
            visibility="DEPARTMENT",
            metadata={"tags": ["test"], "effective_date": "2026-01-01T00:00:00Z"},
        )
        doc = upload_service.registry.get_document(result.document_id)
        assert doc.document_number == "01/2026/QD-NH"
        assert doc.short_title == "QD 01/2026"
        assert doc.language == "vi"
        assert doc.visibility.value == "DEPARTMENT"
        assert "test" in doc.metadata.tags

    def test_upload_with_relationships(self, upload_service, pdf_bytes):
        # Create a target document first
        target = upload_service.registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Target",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="source.pdf",
            document_type="DECISION",
            title="Source",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            supersedes=[target.id],
            references=[target.id],
        )
        rels = upload_service.registry.get_relationships(result.document_id)
        kinds = {k for _, k in rels}
        assert "SUPERSEDES" in kinds
        assert "REFERENCES" in kinds


# ======================================================================
# 3. Duplicate Detection
# ======================================================================


class TestDuplicateDetection:
    """Checksum-based duplicate detection (tasks/002 #DuplicateUploads)."""

    def test_duplicate_reported(self, upload_service, pdf_bytes):
        # Upload same content twice
        r1 = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="first.pdf",
            document_type="DECISION",
            title="First",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert r1.status == "ACCEPTED"

        r2 = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="second.pdf",
            document_type="DECISION",
            title="Second",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert r2.status == "DUPLICATE_REPORTED"
        assert len(r2.duplicate_candidates) >= 1
        assert r2.duplicate_candidates[0][0] == r1.document_id

    def test_unique_content_no_duplicate(self, upload_service):
        r1 = upload_service.upload(
            user_id="admin",
            content=b"%PDF-1.4\nunique1\n%%EOF",
            filename="a.pdf",
            document_type="DECISION",
            title="A",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        r2 = upload_service.upload(
            user_id="admin",
            content=b"%PDF-1.4\nunique2\n%%EOF",
            filename="b.pdf",
            document_type="DECISION",
            title="B",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert r1.status == "ACCEPTED"
        assert r2.status == "ACCEPTED"
        assert len(r2.duplicate_candidates) == 0


# ======================================================================
# 4. Error Handling
# ======================================================================


class TestErrorHandling:
    """Error conditions (tasks/002 #ErrorHandling)."""

    def test_invalid_vault_raises(self, upload_service, pdf_bytes):
        # Inject a vault resolver that rejects the vault
        class RejectAllVaults:
            def vault_exists(self, vault_id):
                return False
            def user_can_upload_to_vault(self, user_id, vault_id):
                return False

        svc = UploadService(vault_resolver=RejectAllVaults())
        with pytest.raises(UploadError, match="does not exist"):
            svc.upload(
                user_id="admin",
                content=pdf_bytes,
                filename="test.pdf",
                document_type="DECISION",
                title="Test",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_invalid_document_type_raises(self, upload_service, pdf_bytes):
        with pytest.raises((ValueError, TypeError)):
            upload_service.upload(
                user_id="admin",
                content=pdf_bytes,
                filename="test.pdf",
                document_type="INVALID_TYPE",
                title="Test",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

    def test_registration_failure_cleans_up_storage(self, pdf_bytes):
        """If registration fails, the stored file should be cleaned up."""
        # Use a storage that we can inspect
        storage = LocalFileStorage()
        service = UploadService(file_storage=storage)

        with pytest.raises((ValueError, TypeError)):
            service.upload(
                user_id="admin",
                content=pdf_bytes,
                filename="test.pdf",
                document_type="INVALID_TYPE",
                title="Test",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
            )

        # Storage should be empty (cleanup happened)
        base = storage.base_path
        has_files = any(base.rglob("*")) if base.exists() else False
        assert not has_files, "Stored file should have been cleaned up on registration failure"


# ======================================================================
# 5. File Storage
# ======================================================================


class TestFileStorage:
    """File storage operations (tasks/002 #StorageRequirements)."""

    def test_store_and_retrieve(self):
        storage = LocalFileStorage()
        stored = storage.store(content=b"hello world", filename="test.txt", mime_type="text/plain")
        assert stored.filename == "test.txt"
        assert stored.size_bytes == 11
        assert stored.checksum_sha256 is not None
        assert stored.storage_ref is not None

        retrieved = storage.retrieve(stored.storage_ref)
        assert retrieved == b"hello world"

    def test_store_from_stream(self):
        storage = LocalFileStorage()
        buf = io.BytesIO(b"stream content")
        stored = storage.store(content=buf, filename="stream.txt", mime_type="text/plain")
        retrieved = storage.retrieve(stored.storage_ref)
        assert retrieved == b"stream content"

    def test_delete(self):
        storage = LocalFileStorage()
        stored = storage.store(content=b"delete me", filename="del.txt", mime_type="text/plain")
        assert storage.exists(stored.storage_ref)
        assert storage.delete(stored.storage_ref) is True
        assert not storage.exists(stored.storage_ref)

    def test_delete_nonexistent(self):
        storage = LocalFileStorage()
        assert storage.delete("nonexistent/path") is False

    def test_retrieve_nonexistent(self):
        storage = LocalFileStorage()
        with pytest.raises(StorageError, match="not found"):
            storage.retrieve("nonexistent/path")

    def test_rejects_empty_content(self):
        storage = LocalFileStorage()
        with pytest.raises(StorageError, match="empty"):
            storage.store(content=b"", filename="empty.txt", mime_type="text/plain")

    def test_preserves_filename(self):
        storage = LocalFileStorage()
        stored = storage.store(content=b"data", filename="original-name.pdf", mime_type="application/pdf")
        assert stored.filename == "original-name.pdf"

    def test_checksum_consistency(self):
        storage = LocalFileStorage()
        content = b"deterministic content"
        stored1 = storage.store(content=content, filename="a.txt", mime_type="text/plain")
        stored2 = storage.store(content=content, filename="b.txt", mime_type="text/plain")
        assert stored1.checksum_sha256 == stored2.checksum_sha256


# ======================================================================
# 6. Upload Status Query
# ======================================================================


class TestUploadStatus:
    """Upload status query (tasks/002 #API)."""

    def test_get_status(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="status.pdf",
            document_type="DECISION",
            title="Status Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        status = upload_service.get_upload_status(result.document_id)
        assert status is not None
        assert status["document_id"] == result.document_id
        assert status["title"] == "Status Test"
        assert status["processing_state"] == "UPLOADED"

    def test_get_status_nonexistent(self, upload_service):
        assert upload_service.get_upload_status(new_id()) is None


# ======================================================================
# 7. Audit Logging
# ======================================================================


class TestAuditLogging:
    """Audit events are recorded (tasks/002 #Logging)."""

    def test_upload_logs_event(self, upload_service, pdf_bytes):
        result = upload_service.upload(
            user_id="admin",
            content=pdf_bytes,
            filename="audit.pdf",
            document_type="DECISION",
            title="Audit Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        events = recent_events(upload_service.registry.repo.conn, entity_id=str(result.document_id))
        upload_events = [e for e in events if e["event"] == "upload.complete"]
        assert len(upload_events) >= 1


# ======================================================================
# 8. Streaming / Large File Handling
# ======================================================================


class TestStreaming:
    """The service should handle streamed content (tasks/002 #Performance)."""

    def test_upload_from_stream(self, upload_service):
        content = b"%PDF-1.4\nstreamed content\n%%EOF"
        buf = io.BytesIO(content)
        result = upload_service.upload(
            user_id="admin",
            content=buf,
            filename="stream.pdf",
            document_type="DECISION",
            title="Stream Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        assert result.size_bytes == len(content)
        assert result.checksum_sha256 is not None

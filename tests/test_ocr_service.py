"""Tests for the OCR Service (Task 003).

Covers:
    - Digital PDF text extraction (PyMuPDF)
    - Scanned PDF detection and fallback
    - OCR result data models
    - Full OCR pipeline (process_bytes)
    - State machine transitions (OCR_PENDING → OCR_RUNNING → OCR_COMPLETED)
    - Error handling (invalid state, missing document, OCR failure)
    - OCR result persistence and retrieval
    - Audit logging
    - Confidence metadata

The authoritative source is the OCR Service specification
(tasks/003-ocr-service.md) and the Document Contract.
"""

import io
import tempfile
from pathlib import Path
from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.ocr_service.engine import (
    AutoOcrEngine,
    OcrEngineError,
    PyMuPdfDigitalExtractor,
)
from legal_platform.modules.ocr_service.models import (
    OcrConfidence,
    OcrLine,
    OcrPage,
    OcrResult,
)
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def digital_pdf_bytes() -> bytes:
    """A minimal digital PDF with embedded text."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Article 1. Scope of regulation", fontsize=12)
    page.insert_text((50, 80), "This regulation governs server procurement.", fontsize=12)
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Article 2. Subjects of application", fontsize=12)
    page2.insert_text((50, 80), "Applies to all IT department units.", fontsize=12)
    data = doc.write()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    """A PDF with no embedded text (simulates a scanned document)."""
    import pymupdf
    doc = pymupdf.open()
    doc.new_page()  # blank page, no text
    doc.new_page()  # blank page, no text
    data = doc.write()
    doc.close()
    return data


@pytest.fixture
def ocr_service():
    return OcrService()


@pytest.fixture
def registered_document(ocr_service, digital_pdf_bytes):
    """Register a document and put it in OCR_PENDING state for testing."""
    svc = UploadService(registry=ocr_service.registry)
    result = svc.upload(
        user_id="admin",
        content=digital_pdf_bytes,
        filename="test.pdf",
        document_type="DECISION",
        title="Test OCR Document",
        issuing_authority="ABC Bank",
        vault_id=new_id(),
        organization_id=new_id(),
        visibility="PUBLIC",
    )
    # Transition to OCR_PENDING
    ocr_service.registry.transition_processing(
        result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
    )
    return result.document_id, result.storage_ref


# ======================================================================
# 1. OCR Data Models
# ======================================================================


class TestOcrModels:
    """OCR data model construction and properties."""

    def test_ocr_line(self):
        line = OcrLine(text="Test text", confidence=0.95, bbox=[0, 0, 100, 20])
        assert line.text == "Test text"
        assert line.confidence == 0.95

    def test_ocr_page(self):
        lines = [OcrLine(text="Line 1"), OcrLine(text="Line 2")]
        page = OcrPage(page_number=1, lines=lines, text="Line 1\nLine 2", confidence=0.98)
        assert page.page_number == 1
        assert page.text == "Line 1\nLine 2"
        assert page.confidence == 0.98

    def test_ocr_result_properties(self):
        pages = [
            OcrPage(page_number=1, text="Page 1 content"),
            OcrPage(page_number=2, text="Page 2 content"),
        ]
        conf = OcrConfidence(page_average=0.95, page_min=0.90, engine="test")
        result = OcrResult(
            document_id=new_id(),
            version_id=new_id(),
            pages=pages,
            confidence=conf,
            total_pages=2,
        )
        assert result.page_count == 2
        assert "Page 1 content" in result.full_text
        assert "Page 2 content" in result.full_text
        assert "\f" in result.full_text  # form feed separator

    def test_ocr_confidence(self):
        conf = OcrConfidence(page_average=0.95, page_min=0.85, line_average=0.92, engine="tesseract")
        assert conf.page_average == 0.95
        assert conf.page_min == 0.85
        assert conf.line_average == 0.92


# ======================================================================
# 2. Digital PDF Extraction (PyMuPDF)
# ======================================================================


class TestPyMuPdfExtraction:
    """Digital PDF text extraction (tasks/003 #OCRModes)."""

    def test_extracts_text_from_digital_pdf(self, digital_pdf_bytes):
        engine = PyMuPdfDigitalExtractor()
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert result.total_pages == 2
        assert result.ocr_mode == "digital"
        assert result.engine == "pymupdf"
        assert "Article 1" in result.full_text
        assert "Article 2" in result.full_text
        assert "server procurement" in result.full_text

    def test_digital_confidence_is_high(self, digital_pdf_bytes):
        engine = PyMuPdfDigitalExtractor()
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert result.confidence.page_average == 1.0
        assert result.confidence.page_min == 1.0

    def test_preserves_page_boundaries(self, digital_pdf_bytes):
        engine = PyMuPdfDigitalExtractor()
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert len(result.pages) == 2
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 2

    def test_preserves_reading_order(self, digital_pdf_bytes):
        engine = PyMuPdfDigitalExtractor()
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        # Text on page 1 should come before text on page 2
        page1_text = result.pages[0].text
        page2_text = result.pages[1].text
        assert "Article 1" in page1_text
        assert "Article 2" in page2_text

    def test_extracts_line_information(self, digital_pdf_bytes):
        engine = PyMuPdfDigitalExtractor()
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        # Each inserted text line should be a separate line
        assert len(result.pages[0].lines) >= 2

    def test_invalid_pdf_raises(self):
        engine = PyMuPdfDigitalExtractor()
        with pytest.raises(OcrEngineError):
            engine.extract(
                content=b"not a pdf",
                document_id=new_id(),
                version_id=new_id(),
            )


# ======================================================================
# 3. Scanned PDF Detection
# ======================================================================


class TestScannedPdfDetection:
    """Scanned PDF detection and fallback (tasks/003 #OCRModes)."""

    def test_detects_scanned_pdf(self, scanned_pdf_bytes):
        """A blank PDF should be detected as potentially scanned (low text density)."""
        assert OcrService.requires_ocr(scanned_pdf_bytes) is True

    def test_detects_digital_pdf(self, digital_pdf_bytes):
        """A PDF with embedded text should be detected as digital."""
        assert OcrService.requires_ocr(digital_pdf_bytes) is False

    def test_auto_engine_falls_back_to_image(self, scanned_pdf_bytes):
        """AutoOcrEngine should report that image OCR is needed."""
        engine = AutoOcrEngine(digital_engine=PyMuPdfDigitalExtractor())
        with pytest.raises(OcrEngineError, match="scanned"):
            engine.extract(
                content=scanned_pdf_bytes,
                document_id=new_id(),
                version_id=new_id(),
            )


# ======================================================================
# 4. Full OCR Pipeline
# ======================================================================


class TestOcrPipeline:
    """Full OCR pipeline (tasks/003 #ProcessingFlow)."""

    def test_process_bytes_digital(self, ocr_service, digital_pdf_bytes):
        """process_bytes should extract text from a digital PDF."""
        # Register document and put in OCR_PENDING
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="test.pdf",
            document_type="DECISION",
            title="OCR Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        ocr_result = ocr_service.process_bytes(
            result.document_id, digital_pdf_bytes, user_id="admin",
        )
        assert ocr_result.total_pages == 2
        assert ocr_result.ocr_mode == "digital"
        assert "Article 1" in ocr_result.full_text

    def test_state_transitions(self, ocr_service, digital_pdf_bytes):
        """Processing should transition through correct states."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="states.pdf",
            document_type="DECISION",
            title="State Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        assert ocr_service.registry.get_processing(result.document_id) == ProcessingState.OCR_PENDING

        ocr_service.process_bytes(result.document_id, digital_pdf_bytes, user_id="admin")

        assert ocr_service.registry.get_processing(result.document_id) == ProcessingState.OCR_COMPLETED

    def test_process_bytes_wrong_state_raises(self, ocr_service, digital_pdf_bytes):
        """process_bytes should reject documents not in OCR_PENDING."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="wrong.pdf",
            document_type="DECISION",
            title="Wrong State",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        # Document is UPLOADED, not OCR_PENDING
        with pytest.raises(ValueError, match="expected OCR_PENDING"):
            ocr_service.process_bytes(result.document_id, digital_pdf_bytes, user_id="admin")

    def test_process_bytes_nonexistent_document_raises(self, ocr_service, digital_pdf_bytes):
        with pytest.raises(ValueError, match="not found"):
            ocr_service.process_bytes(new_id(), digital_pdf_bytes, user_id="admin")

    def test_ocr_result_persisted(self, ocr_service, digital_pdf_bytes):
        """OCR results should be stored and retrievable."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="persist.pdf",
            document_type="DECISION",
            title="Persist Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        ocr_result = ocr_service.process_bytes(
            result.document_id, digital_pdf_bytes, user_id="admin",
        )

        # Retrieve by OCR ID
        retrieved = ocr_service.get_result(ocr_result.ocr_id)
        assert retrieved is not None
        assert retrieved.ocr_id == ocr_result.ocr_id
        assert retrieved.total_pages == 2

        # Retrieve by document ID
        doc_results = ocr_service.get_results_for_document(result.document_id)
        assert len(doc_results) >= 1

    def test_audit_logged(self, ocr_service, digital_pdf_bytes):
        """OCR completion should be audit-logged."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="audit.pdf",
            document_type="DECISION",
            title="Audit OCR",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        ocr_service.process_bytes(result.document_id, digital_pdf_bytes, user_id="admin")

        events = recent_events(ocr_service.registry.repo.conn, entity_id=str(result.document_id))
        ocr_events = [e for e in events if e["event"] == "ocr.complete"]
        assert len(ocr_events) >= 1


# ======================================================================
# 5. Error Handling
# ======================================================================


class TestOcrErrorHandling:
    """Error conditions (tasks/003 #FailureHandling)."""

    def test_failure_transitions_to_failed(self, ocr_service):
        """OCR failure should transition to FAILED state."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=b"%PDF-1.4\n%%EOF",
            filename="bad.pdf",
            document_type="DECISION",
            title="Bad PDF",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        with pytest.raises(OcrEngineError):
            ocr_service.process_bytes(result.document_id, b"not a pdf", user_id="admin")

        assert ocr_service.registry.get_processing(result.document_id) == ProcessingState.FAILED

    def test_process_document_no_storage_ref_raises(self, ocr_service, digital_pdf_bytes):
        """process_document without storage_ref should raise a clear error."""
        svc = UploadService(registry=ocr_service.registry)
        result = svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="noref.pdf",
            document_type="DECISION",
            title="No Ref",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        ocr_service.registry.transition_processing(
            result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )

        with pytest.raises(ValueError, match="no storage_ref"):
            ocr_service.process_document(result.document_id, user_id="admin")

    def test_get_nonexistent_result(self, ocr_service):
        assert ocr_service.get_result(new_id()) is None

    def test_get_results_for_nonexistent_document(self, ocr_service):
        assert ocr_service.get_results_for_document(new_id()) == []


# ======================================================================
# 6. OCR Engine Replaceability
# ======================================================================


class TestEngineReplaceability:
    """OCR engine is replaceable (architecture.md)."""

    def test_custom_engine(self, digital_pdf_bytes):
        """A custom engine should work with the OcrService."""
        engine = PyMuPdfDigitalExtractor()
        svc = OcrService(ocr_engine=engine)
        assert svc.engine is engine

    def test_auto_engine_detects_digital(self, digital_pdf_bytes):
        """AutoOcrEngine should successfully extract from digital PDFs."""
        engine = AutoOcrEngine(digital_engine=PyMuPdfDigitalExtractor())
        result = engine.extract(
            content=digital_pdf_bytes,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert result.total_pages == 2
        assert result.ocr_mode == "digital"
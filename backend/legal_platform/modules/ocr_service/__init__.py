"""OCR Service (tasks/003-ocr-service.md, module Ingestion).

The OCR Service converts uploaded documents into machine-readable text while
preserving the original document as faithfully as possible.

Per the task, the OCR Service:
    - Detects whether OCR is required (digital PDF → extract embedded text;
      scanned PDF → run OCR engine).
    - Extracts text from scanned pages.
    - Preserves reading order, page boundaries, line boundaries.
    - Produces confidence scores.
    - Reports OCR failures.

The OCR Service does NOT:
    - Build Knowledge Trees, detect Articles/Clauses, correct legal wording,
      rewrite text, summarize, or translate.

Design notes (grounded in the specs):
    - Original files are never modified (BC-004).
    - OCR output remains traceable to the source document.
    - OCR output is immutable; later OCR versions create new OCR records.
    - OCR results are disposable per ADR-003 (can be regenerated).
    - The OCR engine is replaceable (architecture.md Replaceability).
"""

from legal_platform.modules.ocr_service.engine import (
    OcrEngine,
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

__all__ = [
    "OcrEngine",
    "OcrEngineError",
    "PyMuPdfDigitalExtractor",
    "OcrConfidence",
    "OcrLine",
    "OcrPage",
    "OcrResult",
    "OcrService",
]
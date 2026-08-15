"""OCR data models (tasks/003-ocr-service.md).

These models represent the output of the OCR pipeline: pages, lines, confidence
scores, and the complete OCR result. They are implementation-independent —
the OCR engine produces them, and the Parser (Task 004) consumes them.

Per the spec:
    - Each OCR result contains Page Number, Page Text, Line Information,
      Confidence Score.
    - OCR output must remain independent from the Knowledge Tree.
    - OCR output is immutable; later OCR versions create new OCR records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc


@dataclass
class OcrLine:
    """A single line of OCR-extracted text.

    Fields:
        text: the extracted text for this line.
        confidence: per-line confidence score (0.0–1.0), optional.
        bbox: bounding box [x0, y0, x1, y1] in page coordinates, optional.
    """

    text: str
    confidence: Optional[float] = None
    bbox: Optional[list[float]] = None


@dataclass
class OcrPage:
    """A single page of OCR output.

    Fields:
        page_number: 1-indexed page number.
        lines: list of extracted lines in reading order.
        text: concatenated page text (lines joined by newline).
        confidence: average confidence for this page (0.0–1.0), optional.
        width: page width in points, optional.
        height: page height in points, optional.
    """

    page_number: int
    lines: list[OcrLine] = field(default_factory=list)
    text: str = ""
    confidence: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class OcrConfidence:
    """Confidence metadata for an OCR result.

    Fields:
        page_average: average confidence across all pages (0.0–1.0).
        page_min: minimum page confidence (0.0–1.0).
        line_average: average line confidence (0.0–1.0), optional.
        engine: name of the OCR engine used.
    """

    page_average: float
    page_min: float
    line_average: Optional[float] = None
    engine: str = "unknown"


@dataclass
class OcrResult:
    """Complete output of an OCR operation.

    This is the canonical output consumed by the Parser (Task 004).
    It is immutable after creation; later OCR versions produce new records.

    Fields:
        ocr_id: unique identifier for this OCR result.
        document_id: the document that was OCR'd.
        version_id: the document version that was OCR'd.
        pages: list of OCR'd pages in document order.
        confidence: aggregate confidence metadata.
        ocr_mode: 'digital' for embedded text extraction, 'image' for
                  scanned-page OCR, 'hybrid' for mixed.
        engine: name of the OCR engine used.
        engine_version: version of the OCR engine.
        created_at: UTC timestamp of OCR completion.
        warnings: list of warnings generated during OCR.
        total_pages: total number of pages processed.
    """

    ocr_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    pages: list[OcrPage] = field(default_factory=list)
    confidence: OcrConfidence = field(default_factory=lambda: OcrConfidence(page_average=0.0, page_min=0.0))
    ocr_mode: str = "digital"
    engine: str = "unknown"
    engine_version: str = "0.0.0"
    created_at: datetime = field(default_factory=now_utc)
    warnings: list[str] = field(default_factory=list)
    total_pages: int = 0

    @property
    def full_text(self) -> str:
        """Concatenated text of all pages, separated by form feeds."""
        return "\f".join(page.text for page in self.pages)

    @property
    def page_count(self) -> int:
        """Number of pages in this result."""
        return len(self.pages)
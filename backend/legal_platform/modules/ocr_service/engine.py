"""OCR engine abstraction (tasks/003-ocr-service.md).

The OCR engine is replaceable (architecture.md Replaceability). The ``OcrEngine``
Protocol defines the interface; concrete implementations handle digital PDF
extraction and scanned-page image OCR.

Per the spec:
    - Digital Mode: Extract embedded text directly.
    - Image Mode: Run OCR engine.
    - Hybrid Mode: Automatically select the appropriate strategy.

Available implementations:
    - ``PyMuPdfDigitalExtractor``: extracts embedded text from digital PDFs
      using PyMuPDF (pymupdf). Works immediately.
    - ``Pdf2ImageTesseractEngine``: renders PDF pages to images via pdf2image
      and OCRs them via Tesseract. Requires tesseract-ocr binary installed.
    - ``AutoOcrEngine``: detects digital vs. scanned and routes accordingly.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional, Protocol
from uuid import UUID
from xml.etree import ElementTree

from legal_platform.modules.ocr_service.models import (
    OcrConfidence,
    OcrLine,
    OcrPage,
    OcrResult,
)


class OcrEngineError(RuntimeError):
    """Raised when an OCR operation fails."""


class DocxTextExtractor:
    """Extract paragraph text from a DOCX package without a heavyweight office runtime.

    DOCX is a ZIP/XML document, not a PDF, so sending it to PyMuPDF was both
    incorrect and guaranteed to fail.  The resulting single logical page has
    line-level provenance suitable for the existing deterministic parser.
    """

    ENGINE_NAME = "docx-xml"
    ENGINE_VERSION = "1.0"
    _WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def extract(self, *, content: bytes, document_id: UUID, version_id: UUID) -> OcrResult:
        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                xml = package.read("word/document.xml")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise OcrEngineError("Invalid DOCX file: missing Word document content") from exc
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError as exc:
            raise OcrEngineError("Invalid DOCX XML content") from exc

        paragraphs: list[str] = []
        for paragraph in root.iter(f"{self._WORD_NS}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{self._WORD_NS}t")).strip()
            if text:
                paragraphs.append(text)
        if not paragraphs:
            raise OcrEngineError("DOCX contains no extractable text")
        lines = [OcrLine(text=text, confidence=1.0) for text in paragraphs]
        page = OcrPage(page_number=1, lines=lines, text="\n".join(paragraphs), confidence=1.0)
        return OcrResult(
            document_id=document_id,
            version_id=version_id,
            pages=[page],
            confidence=OcrConfidence(page_average=1.0, page_min=1.0, line_average=1.0, engine=self.ENGINE_NAME),
            ocr_mode="digital",
            engine=self.ENGINE_NAME,
            engine_version=self.ENGINE_VERSION,
            total_pages=1,
            warnings=["DOCX page layout is not preserved; line-level source locations are used."],
        )


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class OcrEngine(Protocol):
    """Abstract OCR engine.

    All implementations must:
        - Accept PDF bytes (not file paths).
        - Preserve page boundaries.
        - Preserve reading order.
        - Preserve original wording (no rewriting, no summarization).
        - Produce confidence scores.
        - Raise ``OcrEngineError`` on failure (no silent data loss).
    """

    def extract(
        self,
        *,
        content: bytes,
        document_id: UUID,
        version_id: UUID,
    ) -> OcrResult:
        """Extract text from a PDF document.

        Args:
            content: raw PDF file bytes.
            document_id: the document being processed.
            version_id: the document version being processed.

        Returns:
            An ``OcrResult`` with pages, lines, and confidence metadata.

        Raises:
            OcrEngineError: if extraction fails or the content is not a valid PDF.
        """
        ...


# ---------------------------------------------------------------------------
# Digital PDF extractor (PyMuPDF)
# ---------------------------------------------------------------------------


class PyMuPdfDigitalExtractor:
    """Extracts embedded text from digital PDFs using PyMuPDF.

    This is the **Digital Mode** engine per the spec. It extracts text directly
    from the PDF's internal text objects without rendering pages to images.

    Limitations:
        - Only works for digital (text-based) PDFs.
        - Scanned PDFs will produce empty or garbled text.
        - Use ``AutoOcrEngine`` to detect and route appropriately.
    """

    ENGINE_NAME = "pymupdf"
    ENGINE_VERSION = "1.28"

    def extract(
        self,
        *,
        content: bytes,
        document_id: UUID,
        version_id: UUID,
    ) -> OcrResult:
        try:
            import pymupdf  # type: ignore[import-untyped]
        except ImportError as e:
            raise OcrEngineError("PyMuPDF is not installed") from e

        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception as e:
            raise OcrEngineError(f"Failed to open PDF: {e}") from e

        pages: list[OcrPage] = []
        total_confidence = 0.0
        min_confidence = 1.0
        total_lines = 0
        total_line_conf = 0.0
        warnings: list[str] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            rect = page.rect

            # Extract text blocks with position info
            blocks = page.get_text("dict")["blocks"]
            lines: list[OcrLine] = []

            for block in blocks:
                if block["type"] != 0:  # skip images
                    continue
                for line in block.get("lines", []):
                    line_text = "".join(
                        span["text"] for span in line.get("spans", [])
                    ).strip()
                    if not line_text:
                        continue
                    bbox = line["bbox"] if "bbox" in line else None
                    # PyMuPDF doesn't provide per-line confidence for digital PDFs
                    lines.append(OcrLine(text=line_text, bbox=bbox))
                    total_lines += 1
                    total_line_conf += 1.0  # digital text = high confidence

            page_text = "\n".join(l.text for l in lines)
            # Digital PDF confidence is high (1.0) since text is embedded
            page_confidence = 1.0 if lines else 0.0
            total_confidence += page_confidence
            min_confidence = min(min_confidence, page_confidence)

            if not lines and page_num < 5:
                # Only warn for early pages to avoid noise
                warnings.append(
                    f"Page {page_num + 1}: no text extracted "
                    "(may be a scanned image page)"
                )

            pages.append(
                OcrPage(
                    page_number=page_num + 1,
                    lines=lines,
                    text=page_text,
                    confidence=page_confidence,
                    width=rect.width,
                    height=rect.height,
                )
            )

        doc.close()

        page_count = len(pages)
        avg_confidence = total_confidence / page_count if page_count > 0 else 0.0
        avg_line_confidence = total_line_conf / total_lines if total_lines > 0 else None

        return OcrResult(
            document_id=document_id,
            version_id=version_id,
            pages=pages,
            confidence=OcrConfidence(
                page_average=round(avg_confidence, 4),
                page_min=round(min_confidence, 4),
                line_average=round(avg_line_confidence, 4) if avg_line_confidence else None,
                engine=self.ENGINE_NAME,
            ),
            ocr_mode="digital",
            engine=self.ENGINE_NAME,
            engine_version=self.ENGINE_VERSION,
            total_pages=page_count,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Scanned PDF OCR engine (pdf2image + Tesseract)
# ---------------------------------------------------------------------------


class Pdf2ImageTesseractEngine:
    """Renders PDF pages to images and OCRs them via Tesseract.

    This is the **Image Mode** engine per the spec. It:
        1. Renders each PDF page to a PIL image via pdf2image (poppler).
        2. OCRs each image via Tesseract (pytesseract).
        3. Preserves page boundaries and reading order.

    Requires:
        - tesseract-ocr binary installed on the system.
        - poppler-utils (for pdftotext/pdf2image).

    Raises ``OcrEngineError`` with a clear message if Tesseract is not found.
    """

    ENGINE_NAME = "tesseract"
    ENGINE_VERSION = "4.x+"

    def __init__(self, *, dpi: int = 300, lang: str = "vie+eng"):
        self.dpi = dpi
        self.lang = lang
        # Dependency is checked only when image OCR is needed.

    @staticmethod
    def _check_tesseract() -> None:
        """Verify that the tesseract binary is available."""
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise OcrEngineError(
                    "Tesseract OCR engine returned an error. "
                    "Install tesseract-ocr: sudo apt install tesseract-ocr"
                )
        except FileNotFoundError:
            raise OcrEngineError(
                "Tesseract OCR engine is not installed. "
                "Install tesseract-ocr: sudo apt install tesseract-ocr"
            )
        except subprocess.TimeoutExpired:
            raise OcrEngineError("Tesseract check timed out")

    def extract(
        self,
        *,
        content: bytes,
        document_id: UUID,
        version_id: UUID,
    ) -> OcrResult:
        try:
            import pytesseract
        except ImportError as e:
            raise OcrEngineError("pytesseract is not installed") from e

        import os
        import shutil
        import fitz
        from PIL import Image
        from legal_platform.paths import asset_root
        executable = os.environ.get('LEGAL_PLATFORM_TESSERACT') or shutil.which('tesseract')
        standard = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Tesseract-OCR/tesseract.exe'
        if not executable and standard.exists():
            executable = str(standard)
        bundled = asset_root() / 'ocr' / 'tesseract.exe'
        if not executable and bundled.exists():
            executable = str(bundled)
        if not executable:
            raise OcrEngineError('Scanned pages need Tesseract with Vietnamese language data. Ask the server administrator to enable OCR, then retry this document.')
        pytesseract.pytesseract.tesseract_cmd = executable
        pdf = fitz.open(stream=content, filetype='pdf')
        if len(pdf) > 500:
            pdf.close()
            raise OcrEngineError('PDF exceeds the 500-page processing limit.')
        def rendered_pages():
            try:
                for page in pdf:
                    if page.rect.width * page.rect.height * (self.dpi/72)**2 > 40000000:
                        raise OcrEngineError('Page dimensions exceed the OCR limit.')
                    pix = page.get_pixmap(matrix=fitz.Matrix(self.dpi/72, self.dpi/72), colorspace=fitz.csGRAY)
                    if pix.width * pix.height > 40000000:
                        raise OcrEngineError('Page dimensions exceed the OCR limit.')
                    yield Image.frombytes('L', (pix.width, pix.height), pix.samples)
            finally:
                pdf.close()
        images = rendered_pages()

        pages: list[OcrPage] = []
        total_confidence = 0.0
        min_confidence = 1.0
        total_lines = 0
        total_line_conf = 0.0
        warnings: list[str] = []

        for page_num, image in enumerate(images):
            try:
                # OCR with detailed output (per-line confidence)
                ocr_data = pytesseract.image_to_data(
                    image,
                    lang=self.lang,
                    output_type=pytesseract.Output.DICT,
                    timeout=60,
                )

                lines: list[OcrLine] = []
                page_text_parts: list[str] = []
                line_conf_sum = 0.0
                line_conf_count = 0

                n_boxes = len(ocr_data["text"])
                current_line = ""
                current_conf: list[float] = []

                for i in range(n_boxes):
                    text = ocr_data["text"][i].strip()
                    conf_str = ocr_data["conf"][i]
                    conf = float(conf_str) / 100.0 if conf_str != "-1" else 0.0
                    block_num = ocr_data["block_num"][i]
                    line_num = ocr_data["line_num"][i]
                    par_num = ocr_data["par_num"][i]

                    if not text:
                        # End of current line
                        if current_line:
                            avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0.0
                            lines.append(OcrLine(text=current_line, confidence=round(avg_conf, 4)))
                            page_text_parts.append(current_line)
                            line_conf_sum += avg_conf
                            line_conf_count += 1
                            current_line = ""
                            current_conf = []
                        continue

                    if current_line:
                        current_line += " " + text
                    else:
                        current_line = text
                    current_conf.append(conf)

                # Flush last line
                if current_line:
                    avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0.0
                    lines.append(OcrLine(text=current_line, confidence=round(avg_conf, 4)))
                    page_text_parts.append(current_line)
                    line_conf_sum += avg_conf
                    line_conf_count += 1

                page_text = "\n".join(page_text_parts)
                page_confidence = line_conf_sum / line_conf_count if line_conf_count > 0 else 0.0
                total_confidence += page_confidence
                min_confidence = min(min_confidence, page_confidence)
                total_lines += line_conf_count
                total_line_conf += line_conf_sum

                pages.append(
                    OcrPage(
                        page_number=page_num + 1,
                        lines=lines,
                        text=page_text,
                        confidence=round(page_confidence, 4),
                        width=float(image.width),
                        height=float(image.height),
                    )
                )

            except Exception as e:
                warnings.append(f"Page {page_num + 1} OCR failed: {e}")
                pages.append(
                    OcrPage(
                        page_number=page_num + 1,
                        lines=[],
                        text="",
                        confidence=0.0,
                    )
                )

        page_count = len(pages)
        avg_confidence = total_confidence / page_count if page_count > 0 else 0.0
        avg_line_confidence = total_line_conf / total_lines if total_lines > 0 else None

        return OcrResult(
            document_id=document_id,
            version_id=version_id,
            pages=pages,
            confidence=OcrConfidence(
                page_average=round(avg_confidence, 4),
                page_min=round(min_confidence, 4),
                line_average=round(avg_line_confidence, 4) if avg_line_confidence else None,
                engine=self.ENGINE_NAME,
            ),
            ocr_mode="image",
            engine=self.ENGINE_NAME,
            engine_version=self.ENGINE_VERSION,
            total_pages=page_count,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# Auto-detection engine
# ---------------------------------------------------------------------------


class AutoOcrEngine:
    """Automatically selects digital or image OCR mode.

    Strategy (per spec #OCRModes):
        1. Try digital extraction via PyMuPDF.
        2. If the digital result has very low text density (suggesting a scanned
           document), fall back to image OCR via Tesseract.
        3. If Tesseract is unavailable, report the failure clearly.

    This is the **Hybrid Mode** engine per the spec.
    """

    MIN_TEXT_CHARS_FOR_DIGITAL = 50  # minimum chars to consider a page "digital"

    def __init__(
        self,
        digital_engine: "OcrEngine | None" = None,
        image_engine: "OcrEngine | None" = None,
    ):
        self._digital = digital_engine or PyMuPdfDigitalExtractor()
        self._image = image_engine
        self._docx = DocxTextExtractor()

    def extract(
        self,
        *,
        content: bytes,
        document_id: UUID,
        version_id: UUID,
    ) -> OcrResult:
        if content.startswith(b"PK\x03\x04"):
            return self._docx.extract(
                content=content, document_id=document_id, version_id=version_id,
            )
        # Phase 1: try digital extraction
        digital_result = self._digital.extract(
            content=content,
            document_id=document_id,
            version_id=version_id,
        )

        if not digital_result.pages:
            raise OcrEngineError('The PDF has no readable pages.')
        low_text = {p.page_number for p in digital_result.pages if len(p.text.strip()) < self.MIN_TEXT_CHARS_FOR_DIGITAL}
        if not low_text:
            return digital_result
        if self._image is None:
            raise OcrEngineError('Some PDF pages have little or no embedded text. Configure image OCR or upload a text PDF; no pages have been silently omitted.')
        image_result = self._image.extract(content=content, document_id=document_id, version_id=version_id)
        by_page = {p.page_number: p for p in image_result.pages}
        combined = []
        for page in digital_result.pages:
            if page.page_number in low_text:
                replacement = by_page.get(page.page_number)
                if replacement is None or not replacement.text.strip():
                    raise OcrEngineError(f'Page {page.page_number} could not be read. Check whether it is blank or upload a clearer scan, then retry. The document has not been marked ready.')
                combined.append(replacement)
            else:
                combined.append(page)
        image_result.pages = combined
        image_result.total_pages = len(combined)
        image_result.ocr_mode = 'image' if len(low_text) == len(combined) else 'hybrid'
        image_result.warnings = [*digital_result.warnings, *image_result.warnings,
            'Scanned text was recognized automatically. Verify figures, dates and tables against the original.']
        return image_result

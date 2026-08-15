"""Parser engine — converts OCR text into structured Knowledge Tree candidates.

The parser is the only component allowed to construct a Knowledge Tree
(tasks/004-parser.md). It transforms OCR output into legal hierarchy while
preserving original content.

This module provides:
    - ``ParserEngine`` Protocol (replaceable per architecture.md)
    - ``LegalRegexParser`` — deterministic regex-based parser for Vietnamese
      legal documents (the primary MVP implementation)

Design notes:
    - The parser is deterministic: same input + same version = same output.
    - Original wording is never modified, summarized, or paraphrased (KT-002).
    - The parser does NOT infer legal meaning (KT-001).
    - Unknown structures are captured as ``UNKNOWN`` nodes (graceful handling).
    - Source locations (page, line) are preserved for traceability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol
from uuid import UUID

from legal_platform.contracts.common import new_id
from legal_platform.modules.ocr_service.models import OcrResult


class SectionType(str, Enum):
    """Types of structural elements the parser can detect."""

    DOCUMENT = "DOCUMENT"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    ARTICLE = "ARTICLE"
    CLAUSE = "CLAUSE"
    POINT = "POINT"
    PARAGRAPH = "PARAGRAPH"
    APPENDIX = "APPENDIX"
    TABLE = "TABLE"
    FIGURE = "FIGURE"
    UNKNOWN = "UNKNOWN"
    PREAMBLE = "PREAMBLE"  # introductory text before the first article


@dataclass
class ParserSection:
    """A detected structural section from the OCR text.

    This is the intermediate representation before it becomes a Knowledge Node.
    """

    section_type: SectionType
    title: str
    number: Optional[str] = None
    text: str = ""
    children: list["ParserSection"] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ParserOutput:
    """The complete output of the parser engine.

    This is consumed by the Knowledge Tree Builder (Task 005) to construct
    the validated Knowledge Tree Contract.
    """

    sections: list[ParserSection]
    document_id: UUID
    version_id: UUID
    parser_version: str
    warnings: list[str] = field(default_factory=list)
    total_lines: int = 0
    total_pages: int = 0


class ParserEngineError(RuntimeError):
    """Raised when parsing fails."""


class ParserEngine(Protocol):
    """Abstract parser engine.

    All implementations must:
        - Accept ``OcrResult`` (or raw text).
        - Preserve original wording.
        - Preserve document order.
        - Produce deterministic output for identical inputs.
        - Raise ``ParserEngineError`` on failure.
    """

    def parse(
        self,
        *,
        ocr_result: OcrResult,
        document_id: UUID,
        version_id: UUID,
    ) -> ParserOutput:
        ...


# ---------------------------------------------------------------------------
# Vietnamese legal document regex patterns
# ---------------------------------------------------------------------------

# Chapter: "Chương I", "Chương II", "Chương 1", etc.
RE_CHAPTER = re.compile(r"^Chương\s+([IVXLCDM\d]+)[\.\s:]*(.*)", re.IGNORECASE | re.UNICODE)

# Section: "Mục 1", "Mục I", etc.
RE_SECTION = re.compile(r"^Mục\s+([IVXLCDM\d]+)[\.\s:]*(.*)", re.IGNORECASE | re.UNICODE)

# Article: "Điều 1.", "Điều 15.", "Điều 1:", etc.
RE_ARTICLE = re.compile(r"^Điều\s+(\d+)[\.\s:]*(.*)", re.IGNORECASE | re.UNICODE)

# Clause: "1.", "2.", "3." (at start of line, after article)
RE_CLAUSE = re.compile(r"^(\d+)[\.\)]\s+(.*)")

# Point: "a)", "b)", "c)", "a.", "b.", etc.
RE_POINT = re.compile(r"^([a-zđáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ]+)[\.\)]\s+(.*)", re.IGNORECASE | re.UNICODE)

# Appendix: "Phụ lục I", "Phụ lục 1", "Phụ lục A"
RE_APPENDIX = re.compile(r"^Phụ\s*lục\s+([IVXLCDM\dA-Z]+)[\.\s:]*(.*)", re.IGNORECASE | re.UNICODE)

# Preamble / opening: "Căn cứ", "Theo đề nghị", etc.
RE_PREAMBLE = re.compile(r"^(Căn\s+cứ|Theo\s+đề\s+nghị|Quốc\s+hội|Chính\s+phủ|Bộ\s+trưởng)", re.IGNORECASE | re.UNICODE)


# ---------------------------------------------------------------------------
# LegalRegexParser
# ---------------------------------------------------------------------------


class LegalRegexParser:
    """Deterministic regex-based parser for Vietnamese legal documents.

    Strategy (per tasks/004 #ParsingStrategy):
        1. Split OCR text into lines.
        2. Classify each line by regex patterns (Chapter → Section → Article → Clause → Point).
        3. Build a hierarchy tree from the classified lines.
        4. Assign source locations (page, line).
        5. Collect preamble text before the first Article as PREAMBLE.

    Limitations:
        - Relies on predictable Vietnamese legal formatting.
        - May not handle all formatting variations; unknown structures become UNKNOWN nodes.
        - Table and figure detection is not implemented (future improvement).
    """

    PARSER_VERSION = "parser-1.0.0"

    def __init__(self):
        self._warnings: list[str] = []

    def parse(
        self,
        *,
        ocr_result: OcrResult,
        document_id: UUID,
        version_id: UUID,
    ) -> ParserOutput:
        self._warnings = []
        sections: list[ParserSection] = []

        # Track page and line numbers across the OCR result
        global_line = 0
        preamble_lines: list[str] = []
        preamble_page = 1
        preamble_line_start: Optional[int] = None

        for page in ocr_result.pages:
            for line_idx, ocr_line in enumerate(page.lines):
                global_line += 1
                text = ocr_line.text.strip()
                if not text:
                    continue

                # Try to classify the line
                section = self._classify_line(text, page.page_number, global_line)

                if section is not None:
                    # If we've been accumulating preamble and hit a real section, flush preamble
                    if preamble_lines and section.section_type in (
                        SectionType.CHAPTER, SectionType.ARTICLE, SectionType.APPENDIX
                    ):
                        preamble_text = "\n".join(preamble_lines)
                        sections.append(ParserSection(
                            section_type=SectionType.PREAMBLE,
                            title="Preamble",
                            text=preamble_text,
                            page_start=preamble_page,
                            page_end=page.page_number,
                            line_start=preamble_line_start,
                            line_end=global_line - 1,
                        ))
                        preamble_lines = []
                        preamble_line_start = None

                    sections.append(section)
                else:
                    # Check if this could be preamble (before first article)
                    has_article = any(s.section_type == SectionType.ARTICLE for s in sections)
                    if not has_article:
                        if not preamble_lines:
                            preamble_line_start = global_line
                            preamble_page = page.page_number
                        preamble_lines.append(text)
                    else:
                        # Append text to the last open section
                        if sections:
                            last = sections[-1]
                            # Only append if the line looks like continuation text
                            # (not a new structural element)
                            last.text = (last.text + "\n" + text).strip()

        # Flush remaining preamble
        if preamble_lines:
            sections.append(ParserSection(
                section_type=SectionType.PREAMBLE,
                title="Preamble",
                text="\n".join(preamble_lines),
                page_start=preamble_page,
                page_end=ocr_result.pages[-1].page_number if ocr_result.pages else 1,
                line_start=preamble_line_start,
                line_end=global_line,
            ))

        # Build hierarchy
        root = self._build_hierarchy(sections)

        return ParserOutput(
            sections=[root] if root else sections,
            document_id=document_id,
            version_id=version_id,
            parser_version=self.PARSER_VERSION,
            warnings=self._warnings,
            total_lines=global_line,
            total_pages=ocr_result.total_pages,
        )

    def _classify_line(
        self, text: str, page: int, line: int
    ) -> Optional[ParserSection]:
        """Classify a single line of text into a structural section.

        Returns None if the line is not a structural header (continuation text).
        """
        # Try each pattern in priority order
        m = RE_CHAPTER.match(text)
        if m:
            num, title = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.CHAPTER,
                title=title or f"Chương {num}",
                number=num,
                text=text,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        m = RE_SECTION.match(text)
        if m:
            num, title = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.SECTION,
                title=title or f"Mục {num}",
                number=num,
                text=text,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        m = RE_ARTICLE.match(text)
        if m:
            num, title = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.ARTICLE,
                title=title or f"Điều {num}",
                number=num,
                text=text,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        m = RE_APPENDIX.match(text)
        if m:
            num, title = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.APPENDIX,
                title=title or f"Phụ lục {num}",
                number=num,
                text=text,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        m = RE_CLAUSE.match(text)
        if m:
            num, content = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.CLAUSE,
                title=f"Khoản {num}",
                number=num,
                text=content,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        m = RE_POINT.match(text)
        if m:
            letter, content = m.group(1), m.group(2).strip()
            return ParserSection(
                section_type=SectionType.POINT,
                title=f"Điểm {letter}",
                number=letter,
                text=content,
                page_start=page,
                page_end=page,
                line_start=line,
                line_end=line,
            )

        return None

    def _build_hierarchy(self, sections: list[ParserSection]) -> ParserSection:
        """Build a hierarchical tree from a flat list of sections.

        The hierarchy follows Vietnamese legal document structure:
            Document
            ├── Preamble (optional)
            ├── Chapter
            │   ├── Section (optional)
            │   │   └── Article
            │   │       ├── Clause
            │   │       │   └── Point
            │   └── Article (if no Section)
            ├── Article (if no Chapter)
            └── Appendix
        """
        root = ParserSection(
            section_type=SectionType.DOCUMENT,
            title="Document",
            page_start=1,
            page_end=sections[-1].page_end if sections else 1,
        )

        stack: list[ParserSection] = [root]
        # Hierarchy depth mapping: which type nests under which
        parent_map = {
            SectionType.PREAMBLE: SectionType.DOCUMENT,
            SectionType.CHAPTER: SectionType.DOCUMENT,
            SectionType.SECTION: SectionType.CHAPTER,
            SectionType.ARTICLE: SectionType.DOCUMENT,  # may be under CHAPTER or DOCUMENT
            SectionType.CLAUSE: SectionType.ARTICLE,
            SectionType.POINT: SectionType.CLAUSE,
            SectionType.APPENDIX: SectionType.DOCUMENT,
            SectionType.PARAGRAPH: SectionType.CLAUSE,
            SectionType.UNKNOWN: SectionType.DOCUMENT,
        }

        for section in sections:
            expected_parent = parent_map.get(section.section_type, SectionType.DOCUMENT)

            # Find the right parent in the stack
            while stack and stack[-1].section_type != expected_parent:
                if stack[-1].section_type == SectionType.DOCUMENT:
                    break
                stack.pop()

            # If article and last stack is chapter, nest under chapter
            if section.section_type == SectionType.ARTICLE:
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i].section_type == SectionType.CHAPTER:
                        expected_parent = SectionType.CHAPTER
                        break
                    if stack[i].section_type == SectionType.DOCUMENT:
                        break

            # Find parent again after adjusting for articles under chapters
            if section.section_type == SectionType.ARTICLE and expected_parent == SectionType.CHAPTER:
                while stack and stack[-1].section_type not in (SectionType.CHAPTER, SectionType.DOCUMENT):
                    stack.pop()
            else:
                while stack and stack[-1].section_type != expected_parent:
                    if stack[-1].section_type == SectionType.DOCUMENT:
                        break
                    stack.pop()

            parent = stack[-1] if stack else root
            parent.children.append(section)
            stack.append(section)

        return root
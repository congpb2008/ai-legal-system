"""Parser (tasks/004-parser.md, module Ingestion).

The Parser converts OCR output into a structured Knowledge Tree. It is responsible
for understanding document structure — transforming unstructured text into legal
hierarchy while preserving the original content.

Per the task, the Parser:
    - Parses OCR output
    - Detects document hierarchy
    - Builds the Knowledge Tree
    - Preserves legal references, document order, original wording
    - Records source locations
    - Produces parser diagnostics

The Parser does NOT:
    - Perform OCR, rewrite text, summarize, chunk, embed, retrieve, or generate answers.

The Parser is the only component allowed to construct a Knowledge Tree
(tasks/004-parser.md). The Knowledge Tree Builder (Task 005) validates and
publishes the tree into the Knowledge Layer.
"""

from legal_platform.modules.parser.engine import (
    LegalRegexParser,
    ParserEngine,
    ParserEngineError,
    ParserOutput,
    ParserSection,
    SectionType,
)
from legal_platform.modules.parser.service import ParserService

__all__ = [
    "LegalRegexParser",
    "ParserEngine",
    "ParserEngineError",
    "ParserOutput",
    "ParserSection",
    "SectionType",
    "ParserService",
]
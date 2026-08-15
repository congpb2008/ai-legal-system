"""Citation Builder (tasks/012-citation-builder.md, module Citation).

The Citation Builder constructs, validates and attaches citations to generated
answers. Every factual statement must be traceable back to retrieved evidence.

Per the spec:
    - Builds citations
    - Validates citations
    - Resolves canonical references
    - Resolves page references
    - Resolves line references
    - Detects unsupported claims
    - Attaches citation metadata

The Citation Builder does NOT:
    - Retrieve evidence
    - Generate answers
    - Rewrite legal wording
    - Interpret legal meaning
"""

from legal_platform.modules.citation.citation_builder import (
    CitationBuilder,
    CitationBuilderConfig,
    Claim,
    ClaimType,
    CitationResolution,
    EvidenceMapping,
    ValidationReport,
)
from legal_platform.modules.citation.service import CitationBuilderService

__all__ = [
    "CitationBuilder",
    "CitationBuilderConfig",
    "CitationBuilderService",
    "Claim",
    "ClaimType",
    "CitationResolution",
    "EvidenceMapping",
    "ValidationReport",
]
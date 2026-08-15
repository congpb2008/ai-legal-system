"""Canonical contracts (02-contracts/).

These are the stable interfaces between modules. They are:
- authoritative (modules consume contracts, not each other's internals),
- backward compatible,
- independently versioned.

Modifying a contract requires the developer-guide flow:
    ADR -> Contract Update -> Examples Update -> Implementation Update.

Never invent fields, remove fields, or change field semantics without an ADR.
"""

from legal_platform.contracts.document import (  # noqa: F401
    Document,
    DocumentStatus,
    DocumentType,
    DocumentVersionReference,
    DocumentVersionStatus,
    Metadata,
    SourceFile,
    Visibility,
)
from legal_platform.contracts.knowledge_tree import (  # noqa: F401
    BoundingBox,
    KnowledgeTree,
    Node,
    NodeMetadata,
    NodeReference,
    NodeType,
    SourceLocation,
    TreeMetadata,
    TreeStatistics,
)
from legal_platform.contracts.retrieval import (  # noqa: F401
    Evidence,
    RetrievalMetadata,
    RetrievalReason,
    RetrievalResult,
    RetrievalStrategy,
    SourceAnchor,
)
from legal_platform.contracts.answer import (  # noqa: F401
    Answer,
    AnswerMetadata,
    AnswerStatus,
    Citation,
    Confidence,
    ConfidenceLevel,
    EvidenceReference,
    Limitation,
    Response,
)

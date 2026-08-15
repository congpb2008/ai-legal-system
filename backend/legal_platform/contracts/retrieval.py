"""Retrieval Contract (02-contracts/retrieval-contract.md).

The canonical output produced by the Retrieval Engine. It serves as the boundary
between Retrieval and Generation — the Generation pipeline must consume this
contract rather than interacting directly with vector databases, search engines
or storage systems.

The Retrieval Contract is transient (request-lifetime only), not a persistent
business object.

Invariants (per retrieval-contract.md):
    INV-001  Every Evidence item belongs to exactly one Knowledge Node.
    INV-002  Evidence text must match the original parsed content.
    INV-003  Evidence ranking is deterministic.
    INV-004  Evidence is immutable.
    INV-005  Retrieval never generates new knowledge.
    INV-006  Retrieval never modifies source wording.
    INV-007  Retrieval never performs legal interpretation.
    INV-008  An empty evidence list is a valid result.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from legal_platform.contracts.common import now_utc


class RetrievalStrategy(str, Enum):
    """Search strategy used (retrieval-contract.md)."""

    KEYWORD = "KEYWORD"
    SEMANTIC = "SEMANTIC"
    HYBRID = "HYBRID"


class SourceAnchor(BaseModel):
    """Source anchor for evidence (retrieval-contract.md #EvidenceContract)."""

    model_config = ConfigDict(extra="forbid")

    page: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    canonical_reference: Optional[str] = None


class RetrievalReason(BaseModel):
    """Informational reason why evidence was selected (retrieval-contract.md #RetrievalReason).

    This field is informational only. The Generation Pipeline must never rely on it.
    """

    model_config = ConfigDict(extra="forbid")

    method: str = "hybrid"  # keyword, semantic, hybrid, metadata
    keyword_score: Optional[float] = None
    semantic_score: Optional[float] = None
    rerank_score: Optional[float] = None


class Evidence(BaseModel):
    """A single piece of retrieved evidence (retrieval-contract.md #EvidenceContract).

    Every Evidence item:
        - originates from exactly one Knowledge Node (INV-001)
        - preserves original wording (INV-002)
        - includes source mapping
        - remains immutable (INV-004)
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    knowledge_node_id: UUID
    document_id: UUID
    document_version_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)
    text: str
    source_anchor: Optional[SourceAnchor] = None
    reason: Optional[RetrievalReason] = None


class RetrievalMetadata(BaseModel):
    """Metadata for the retrieval operation (retrieval-contract.md #Metadata).

    Intended for monitoring and debugging. Shall never influence business logic.
    """

    model_config = ConfigDict(extra="forbid")

    strategy: str = "HYBRID"
    latency_ms: Optional[float] = None
    candidate_count: int = 0
    returned_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    """The canonical Retrieval Contract (retrieval-contract.md #Contract).

    This is the boundary between Retrieval and Generation. Generation must
    consume this contract instead of touching vector databases, search engines,
    or storage directly.
    """

    model_config = ConfigDict(extra="forbid")

    query_id: UUID
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    generated_at: datetime = Field(default_factory=now_utc)
    query: str
    evidence: list[Evidence] = Field(default_factory=list)
    metadata: RetrievalMetadata = Field(default_factory=RetrievalMetadata)
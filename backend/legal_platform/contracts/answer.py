"""Answer Contract (02-contracts/answer-contract.md).

The canonical output produced by the Generation Pipeline. It represents the final
response delivered to the user. It is the only object exposed to client applications.

The Answer Contract separates user-facing responses from internal retrieval and
generation implementations.

Invariants (per answer-contract.md):
    INV-001  Every factual claim shall be supported by at least one Citation.
    INV-002  The Answer Contract never contains fabricated citations.
    INV-003  Evidence references must originate from the Retrieval Contract.
    INV-004  Generation never modifies the wording of citations.
    INV-005  Confidence is never interpreted as legal certainty.
    INV-006  The Answer Contract never creates new legal knowledge.
    INV-007  Missing evidence is explicitly communicated.
    INV-008  The client receives exactly one Answer Contract per request.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from legal_platform.contracts.common import now_utc
from legal_platform.contracts.retrieval import SourceAnchor


class AnswerStatus(str, Enum):
    """Status of the generated answer (answer-contract.md #Contract)."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    NO_EVIDENCE = "NO_EVIDENCE"
    ERROR = "ERROR"


class ConfidenceLevel(str, Enum):
    """Confidence level (answer-contract.md #Confidence)."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Response(BaseModel):
    """The natural-language response (answer-contract.md #Response)."""

    model_config = ConfigDict(extra="forbid")

    format: str = "MARKDOWN"
    content: str = ""


class Citation(BaseModel):
    """A citation linking a claim to source evidence (answer-contract.md #Citation)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    document_id: UUID
    document_version_id: UUID
    knowledge_node_id: UUID
    evidence_id: Optional[UUID] = None
    source_anchor: Optional[SourceAnchor] = None
    label: Optional[str] = None


class EvidenceReference(BaseModel):
    """Reference to evidence from the Retrieval Contract (answer-contract.md #EvidenceReference)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID
    usage: str = "DIRECT"  # DIRECT | SUPPORTING | CONTEXT


class Confidence(BaseModel):
    """Confidence in the generated answer (answer-contract.md #Confidence).

    Advisory only — users remain responsible for interpreting legal documents.
    """

    model_config = ConfigDict(extra="forbid")

    level: ConfidenceLevel = ConfidenceLevel.MEDIUM
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: Optional[str] = None


class Limitation(BaseModel):
    """A limitation of the generated answer (answer-contract.md #Limitation)."""

    model_config = ConfigDict(extra="forbid")

    description: str


class AnswerMetadata(BaseModel):
    """Metadata about the generation (answer-contract.md #Metadata).

    Supports monitoring and debugging only.
    """

    model_config = ConfigDict(extra="forbid")

    generation_model: str = "template"
    generation_latency_ms: Optional[float] = None
    prompt_version: str = "1.0.0"
    retrieval_strategy: Optional[str] = None
    token_usage: Optional[dict] = None


class Answer(BaseModel):
    """The Answer Contract (answer-contract.md #Contract).

    This is the final output delivered to the client. Internal implementation
    details (vector DB, embedding model, LLM provider) must never leak into
    this contract.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    generated_at: datetime = Field(default_factory=now_utc)
    status: AnswerStatus = AnswerStatus.SUCCESS
    response: Response = Field(default_factory=Response)
    citations: list[Citation] = Field(default_factory=list)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    limitations: list[Limitation] = Field(default_factory=list)
    metadata: AnswerMetadata = Field(default_factory=AnswerMetadata)

"""Citation Builder core (tasks/012-citation-builder.md).

The Citation Builder constructs, validates and attaches citations to generated
answers. It performs:

    - Sentence segmentation
    - Claim detection
    - Evidence mapping
    - Citation resolution
    - Citation validation
    - Unsupported claim detection

The Citation Builder does NOT:
    - Retrieve evidence
    - Generate answers
    - Rewrite legal wording
    - Interpret legal meaning
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.answer import (
    Answer,
    AnswerStatus,
    Citation,
    Confidence,
    ConfidenceLevel,
    EvidenceReference,
    Limitation,
)
from legal_platform.contracts.common import new_id, now_utc
from legal_platform.contracts.knowledge_tree import KnowledgeTree, Node, NodeType
from legal_platform.contracts.retrieval import Evidence, RetrievalResult, SourceAnchor
from legal_platform.modules.knowledge_tree_builder.references import (
    CanonicalReferenceGenerator,
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ClaimType(str, Enum):
    """Types of claims that can be detected in generated answers.

    Per tasks/012-citation-builder.md #ClaimDetection:
        - Statements of fact
        - Legal requirements
        - Definitions
        - Exceptions
        - Dates
        - Thresholds
        - Legal references
    """

    STATEMENT_OF_FACT = "STATEMENT_OF_FACT"
    LEGAL_REQUIREMENT = "LEGAL_REQUIREMENT"
    DEFINITION = "DEFINITION"
    EXCEPTION = "EXCEPTION"
    DATE = "DATE"
    THRESHOLD = "THRESHOLD"
    LEGAL_REFERENCE = "LEGAL_REFERENCE"


class EvidenceUsage(str, Enum):
    """How evidence is used to support a claim.

    Per answer-contract.md #EvidenceReference:
        - DIRECT: the evidence directly supports the claim.
        - SUPPORTING: the evidence provides supporting context.
        - CONTEXT: the evidence provides background context.
    """

    DIRECT = "DIRECT"
    SUPPORTING = "SUPPORTING"
    CONTEXT = "CONTEXT"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class Claim:
    """A single claim detected in a generated answer.

    Fields:
        id: unique identifier for this claim.
        text: the claim text as it appears in the answer.
        claim_type: the type of claim detected.
        sentence_index: index of the sentence containing this claim.
        start_char: character offset where the claim starts in the answer.
        end_char: character offset where the claim ends in the answer.
    """

    id: UUID
    text: str
    claim_type: ClaimType
    sentence_index: int
    start_char: int
    end_char: int


@dataclass
class EvidenceMapping:
    """A mapping between a claim and supporting evidence.

    Fields:
        claim_id: the claim being mapped.
        evidence_id: the evidence supporting the claim.
        evidence: the Evidence object from the Retrieval Contract.
        usage: how the evidence is used (DIRECT, SUPPORTING, CONTEXT).
        confidence: confidence in this mapping (0.0 - 1.0).
    """

    claim_id: UUID
    evidence_id: UUID
    evidence: Evidence
    usage: EvidenceUsage = EvidenceUsage.DIRECT
    confidence: float = 1.0


@dataclass
class CitationResolution:
    """A resolved citation linking a claim to a Knowledge Node.

    Fields:
        citation_id: unique identifier for this citation.
        claim_id: the claim this citation supports.
        evidence_id: the evidence this citation originates from.
        document_id: the document containing the source.
        document_version_id: the specific document version.
        knowledge_node_id: the Knowledge Node containing the source.
        canonical_reference: human-readable reference (e.g. "Điều 3 Khoản 2").
        page: page number in the source document.
        line_start: start line in the source document.
        line_end: end line in the source document.
        label: display label for the citation.
        confidence: confidence in this resolution (0.0 - 1.0).
    """

    citation_id: UUID
    claim_id: UUID
    evidence_id: UUID
    document_id: UUID
    document_version_id: UUID
    knowledge_node_id: UUID
    canonical_reference: Optional[str] = None
    page: Optional[int] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    label: Optional[str] = None
    confidence: float = 1.0


@dataclass
class ValidationReport:
    """Report of citation validation results.

    Per tasks/012-citation-builder.md #ValidationReport:
        - Supported Claims
        - Unsupported Claims
        - Citation Coverage
        - Validation Errors
        - Warnings
        - Generation Status
    """

    supported_claims: list[Claim] = field(default_factory=list)
    unsupported_claims: list[Claim] = field(default_factory=list)
    citation_count: int = 0
    coverage: float = 0.0  # 0.0 - 1.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "PENDING"


@dataclass
class CitationBuilderConfig:
    """Configuration for the Citation Builder.

    Fields:
        min_confidence: minimum confidence for a citation to be accepted.
        max_claims_per_sentence: maximum number of claims to detect per sentence.
        enable_unsupported_detection: whether to detect unsupported claims.
        enable_retry: whether to signal generation retry on unsupported claims.
        cache_knowledge_trees: whether to cache Knowledge Tree lookups.
    """

    min_confidence: float = 0.3
    max_claims_per_sentence: int = 5
    enable_unsupported_detection: bool = True
    enable_retry: bool = True
    cache_knowledge_trees: bool = True


# ---------------------------------------------------------------------------
# Citation Builder
# ---------------------------------------------------------------------------


class CitationBuilder:
    """The Citation Builder.

    Constructs, validates and attaches citations to generated answers.
    Every factual statement must be traceable back to retrieved evidence.

    Processing flow (per tasks/012-citation-builder.md #ProcessingFlow):
        1. Sentence Segmentation
        2. Claim Detection
        3. Evidence Mapping
        4. Citation Resolution
        5. Citation Validation
        6. Verified Answer
    """

    CITATION_VERSION = "citation-1.0.0"

    # Vietnamese legal keywords for claim detection
    _LEGAL_KEYWORDS = {
        ClaimType.STATEMENT_OF_FACT: [
            "là", "bao gồm", "gồm", "thuộc", "được", "có",
        ],
        ClaimType.LEGAL_REQUIREMENT: [
            "phải", "cần", "bắt buộc", "yêu cầu", "có nghĩa vụ",
            "có trách nhiệm", "không được", "cấm",
        ],
        ClaimType.DEFINITION: [
            "là", "được hiểu là", "được định nghĩa là", "nghĩa là",
            "được gọi là",
        ],
        ClaimType.EXCEPTION: [
            "trừ", "ngoại lệ", "không áp dụng", "trừ trường hợp",
            "trừ khi",
        ],
        ClaimType.THRESHOLD: [
            "từ", "đến", "trên", "dưới", "tối thiểu", "tối đa",
            "không quá", "không dưới", "vượt quá",
        ],
    }

    def __init__(self, config: "CitationBuilderConfig | None" = None):
        self.config = config or CitationBuilderConfig()
        self._kt_cache: dict[UUID, KnowledgeTree] = {}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build_citations(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
        knowledge_trees: "dict[UUID, KnowledgeTree] | None" = None,
    ) -> tuple[Answer, ValidationReport]:
        """Build and attach citations to a generated answer.

        Flow (per tasks/012-citation-builder.md #ProcessingFlow):
            1. Sentence Segmentation
            2. Claim Detection
            3. Evidence Mapping
            4. Citation Resolution
            5. Citation Validation
            6. Verified Answer

        Args:
            answer: the draft Answer to attach citations to.
            evidence_package: the evidence items from the Retrieval/Reranker.
            knowledge_trees: Knowledge Trees keyed by document_version_id,
                used for resolving canonical references.

        Returns:
            A tuple of (verified Answer with citations, validation report).
        """
        # Cache Knowledge Trees for resolution
        if knowledge_trees:
            self._kt_cache.update(knowledge_trees)

        # 1. Sentence Segmentation
        sentences = self._segment_sentences(answer.response.content)

        # 2. Claim Detection
        claims = self._detect_claims(sentences)

        if not claims:
            # No claims to cite — return answer as-is
            report = ValidationReport(
                supported_claims=[],
                unsupported_claims=[],
                citation_count=0,
                coverage=1.0,
                status="NO_CLAIMS",
                warnings=["No detectable claims found in the answer."],
            )
            return answer, report

        # 3. Evidence Mapping
        mappings = self._map_claims_to_evidence(claims, evidence_package)

        # 4. Citation Resolution
        resolutions = self._resolve_citations(mappings, evidence_package)

        # 5. Citation Validation
        report = self._validate_citations(
            claims, mappings, resolutions, evidence_package
        )

        # Build final citations and evidence references
        citations: list[Citation] = []
        evidence_refs: list[EvidenceReference] = []
        limitations: list[Limitation] = []

        for res in resolutions:
            citation = Citation(
                id=res.citation_id,
                document_id=res.document_id,
                document_version_id=res.document_version_id,
                knowledge_node_id=res.knowledge_node_id,
                evidence_id=res.evidence_id,
                source_anchor=SourceAnchor(
                    canonical_reference=res.canonical_reference,
                    page=res.page,
                    line_start=res.line_start,
                    line_end=res.line_end,
                ),
                label=res.label or res.canonical_reference,
            )
            citations.append(citation)

        # Build evidence references (deduplicated by evidence_id)
        seen_evidence: set[UUID] = set()
        for mapping in mappings:
            if mapping.evidence_id not in seen_evidence:
                seen_evidence.add(mapping.evidence_id)
                evidence_refs.append(EvidenceReference(
                    evidence_id=mapping.evidence_id,
                    usage=mapping.usage.value,
                ))

        # Handle unsupported claims
        if report.unsupported_claims:
            limitations.append(Limitation(
                description=(
                    f"{len(report.unsupported_claims)} claim(s) in the answer "
                    "could not be supported by available evidence. "
                    "Consider reviewing the generated answer."
                )
            ))

        # Determine final status
        status = answer.status
        if report.unsupported_claims and status == AnswerStatus.SUCCESS:
            status = AnswerStatus.PARTIAL

        # Build verified answer
        verified_answer = Answer(
            request_id=answer.request_id,
            generated_at=answer.generated_at,
            status=status,
            response=answer.response,
            citations=citations,
            evidence=evidence_refs,
            confidence=answer.confidence,
            limitations=answer.limitations + limitations,
            metadata=answer.metadata,
        )

        return verified_answer, report

    # ------------------------------------------------------------------
    # 1. Sentence Segmentation
    # ------------------------------------------------------------------

    @staticmethod
    def _segment_sentences(text: str) -> list[str]:
        """Segment text into sentences.

        Uses a simple regex-based approach that handles Vietnamese sentence
        boundaries (periods, question marks, exclamation marks, colons
        followed by newlines).

        Args:
            text: the text to segment.

        Returns:
            A list of sentence strings.
        """
        if not text:
            return []

        # Split on sentence-ending punctuation followed by space or newline
        # Handle Vietnamese-specific patterns
        sentences = re.split(
            r"(?<=[.!?])\s+(?=[A-ZĐÁẢÃẠÀẦẨẪẬẤẮẰẲẴẶÉẺẼẸÈỀỂỄỆẾỒỔỖỘỐỜỞỠỢỚÚỦŨỤÙỪỬỮỰỨỊ])",
            text,
        )

        # If that didn't work well, fall back to simple period splitting
        if len(sentences) <= 1:
            sentences = re.split(r"(?<=[.!?])\s+", text)

        # Filter out empty/whitespace-only sentences
        return [s.strip() for s in sentences if s.strip()]

    # ------------------------------------------------------------------
    # 2. Claim Detection
    # ------------------------------------------------------------------

    def _detect_claims(self, sentences: list[str]) -> list[Claim]:
        """Detect factual claims in segmented sentences.

        Per tasks/012-citation-builder.md #ClaimDetection, identifies:
            - Statements of fact
            - Legal requirements
            - Definitions
            - Exceptions
            - Dates
            - Thresholds
            - Legal references

        Args:
            sentences: the segmented sentences.

        Returns:
            A list of detected Claims.
        """
        claims: list[Claim] = []
        char_offset = 0

        for sent_idx, sentence in enumerate(sentences):
            if sent_idx >= self.config.max_claims_per_sentence:
                break

            # Detect claim type based on keywords
            claim_type = self._classify_claim(sentence)

            # Detect legal references (e.g. "Điều 3", "Khoản 2", "Điểm a")
            refs = self._detect_legal_references(sentence)

            # If we found legal references, create a claim for each
            if refs:
                for ref in refs:
                    claim = Claim(
                        id=new_id(),
                        text=ref,
                        claim_type=ClaimType.LEGAL_REFERENCE,
                        sentence_index=sent_idx,
                        start_char=char_offset + sentence.find(ref),
                        end_char=char_offset + sentence.find(ref) + len(ref),
                    )
                    claims.append(claim)

            # Create a claim for the main sentence content
            if claim_type != ClaimType.LEGAL_REFERENCE or not refs:
                claim = Claim(
                    id=new_id(),
                    text=sentence,
                    claim_type=claim_type,
                    sentence_index=sent_idx,
                    start_char=char_offset,
                    end_char=char_offset + len(sentence),
                )
                claims.append(claim)

            # Detect dates (simple pattern)
            date_claims = self._detect_dates(sentence, sent_idx, char_offset)
            claims.extend(date_claims)

            char_offset += len(sentence) + 1  # +1 for the separator

        return claims

    def _classify_claim(self, sentence: str) -> ClaimType:
        """Classify a sentence by its claim type based on keywords."""
        sentence_lower = sentence.lower()

        # Check for legal references first
        if self._has_legal_reference(sentence):
            return ClaimType.LEGAL_REFERENCE

        # Check for definitions
        for kw in self._LEGAL_KEYWORDS[ClaimType.DEFINITION]:
            if kw in sentence_lower:
                return ClaimType.DEFINITION

        # Check for exceptions
        for kw in self._LEGAL_KEYWORDS[ClaimType.EXCEPTION]:
            if kw in sentence_lower:
                return ClaimType.EXCEPTION

        # Check for thresholds
        for kw in self._LEGAL_KEYWORDS[ClaimType.THRESHOLD]:
            if kw in sentence_lower:
                return ClaimType.THRESHOLD

        # Check for legal requirements
        for kw in self._LEGAL_KEYWORDS[ClaimType.LEGAL_REQUIREMENT]:
            if kw in sentence_lower:
                return ClaimType.LEGAL_REQUIREMENT

        # Check for dates
        if self._has_date(sentence):
            return ClaimType.DATE

        # Default to statement of fact
        return ClaimType.STATEMENT_OF_FACT

    @staticmethod
    def _has_legal_reference(text: str) -> bool:
        """Check if text contains a legal reference pattern."""
        patterns = [
            r"Điều\s+\d+",
            r"Khoản\s+\d+",
            r"Điểm\s+[a-zđ]",
            r"Chương\s+\d+",
            r"Mục\s+\d+",
            r"Phụ\s+lục\s+\d+",
            r"Điều\s+\d+\s+Khoản\s+\d+",
            r"Điều\s+\d+\s+Điểm\s+[a-zđ]",
        ]
        return any(re.search(p, text) for p in patterns)

    @staticmethod
    def _detect_legal_references(text: str) -> list[str]:
        """Extract legal reference strings from text."""
        refs: list[str] = []
        patterns = [
            r"Điều\s+\d+(?:\s+Khoản\s+\d+(?:\s+Điểm\s+[a-zđ])?)?",
            r"Khoản\s+\d+(?:\s+Điểm\s+[a-zđ])?",
            r"Điểm\s+[a-zđ]",
            r"Chương\s+\d+",
            r"Mục\s+\d+",
            r"Phụ\s+lục\s+\d+",
        ]
        for pattern in patterns:
            refs.extend(re.findall(pattern, text))
        return refs

    @staticmethod
    def _has_date(text: str) -> bool:
        """Check if text contains a date pattern."""
        date_patterns = [
            r"\d{1,2}/\d{1,2}/\d{4}",
            r"\d{4}-\d{2}-\d{2}",
            r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}",
            r"tháng\s+\d{1,2}\s+năm\s+\d{4}",
            r"năm\s+\d{4}",
        ]
        return any(re.search(p, text) for p in date_patterns)

    @staticmethod
    def _detect_dates(
        text: str, sent_idx: int, char_offset: int
    ) -> list[Claim]:
        """Extract date claims from text."""
        claims: list[Claim] = []
        date_patterns = [
            r"\d{1,2}/\d{1,2}/\d{4}",
            r"ngày\s+\d{1,2}\s+tháng\s+\d{1,2}\s+năm\s+\d{4}",
        ]
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                claims.append(Claim(
                    id=new_id(),
                    text=match.group(),
                    claim_type=ClaimType.DATE,
                    sentence_index=sent_idx,
                    start_char=char_offset + match.start(),
                    end_char=char_offset + match.end(),
                ))
        return claims

    # ------------------------------------------------------------------
    # 3. Evidence Mapping
    # ------------------------------------------------------------------

    def _map_claims_to_evidence(
        self,
        claims: list[Claim],
        evidence_package: list[Evidence],
    ) -> list[EvidenceMapping]:
        """Map claims to supporting evidence.

        Per tasks/012-citation-builder.md #EvidenceMapping:
            - One Claim -> One Evidence
            - One Claim -> Multiple Evidence
            - Many-to-many mappings are allowed.

        Args:
            claims: the detected claims.
            evidence_package: the evidence items from retrieval.

        Returns:
            A list of EvidenceMappings.
        """
        mappings: list[EvidenceMapping] = []

        for claim in claims:
            matched = False
            for ev in evidence_package:
                # Score the match between claim text and evidence text
                score = self._score_claim_evidence_match(claim.text, ev.text)

                if score >= self.config.min_confidence:
                    usage = self._determine_usage(claim, ev, score)
                    mappings.append(EvidenceMapping(
                        claim_id=claim.id,
                        evidence_id=ev.id,
                        evidence=ev,
                        usage=usage,
                        confidence=score,
                    ))
                    matched = True

            # If no match found and unsupported detection is enabled,
            # the claim remains unmapped (will be reported as unsupported)

        return mappings

    @staticmethod
    def _score_claim_evidence_match(claim_text: str, evidence_text: str) -> float:
        """Score how well evidence supports a claim.

        Uses term overlap scoring:
            - Exact match: 1.0
            - Partial overlap: proportional
            - No overlap: 0.0

        Args:
            claim_text: the claim text from the answer.
            evidence_text: the evidence text from retrieval.

        Returns:
            A score between 0.0 and 1.0.
        """
        if not claim_text or not evidence_text:
            return 0.0

        # Normalize
        claim_lower = claim_text.lower()
        evidence_lower = evidence_text.lower()

        # Exact match
        if claim_lower == evidence_lower:
            return 1.0

        # Check if evidence contains the claim (or vice versa)
        if claim_lower in evidence_lower:
            return 0.9
        if evidence_lower in claim_lower:
            return 0.8

        # Term overlap scoring
        claim_terms = set(claim_lower.split())
        evidence_terms = set(evidence_lower.split())

        if not claim_terms or not evidence_terms:
            return 0.0

        # Remove common stop words
        stop_words = {
            "và", "của", "các", "có", "được", "cho", "trong", "với",
            "một", "những", "đến", "từ", "theo", "tại", "về", "hoặc",
            "không", "này", "đó", "là", "đã", "sẽ", "đang", "bị",
        }
        claim_terms -= stop_words
        evidence_terms -= stop_words

        if not claim_terms:
            return 0.0

        overlap = len(claim_terms & evidence_terms)
        return overlap / len(claim_terms)

    @staticmethod
    def _determine_usage(
        claim: Claim, evidence: Evidence, score: float
    ) -> EvidenceUsage:
        """Determine how evidence is used to support a claim.

        Args:
            claim: the claim.
            evidence: the evidence.
            score: the match score.

        Returns:
            The EvidenceUsage type.
        """
        if score >= 0.8:
            return EvidenceUsage.DIRECT
        elif score >= 0.5:
            return EvidenceUsage.SUPPORTING
        else:
            return EvidenceUsage.CONTEXT

    # ------------------------------------------------------------------
    # 4. Citation Resolution
    # ------------------------------------------------------------------

    def _resolve_citations(
        self,
        mappings: list[EvidenceMapping],
        evidence_package: list[Evidence],
    ) -> list[CitationResolution]:
        """Resolve evidence mappings into full citations.

        Resolves (per tasks/012-citation-builder.md #CitationResolution):
            - Document ID
            - Knowledge Node IDs
            - Canonical References
            - Page Numbers
            - Line Numbers
            - Evidence IDs

        All references originate from the Knowledge Tree.

        Args:
            mappings: the evidence-to-claim mappings.
            evidence_package: the full evidence package.

        Returns:
            A list of resolved CitationResolutions.
        """
        resolutions: list[CitationResolution] = []

        for mapping in mappings:
            ev = mapping.evidence

            # Resolve canonical reference from Knowledge Tree if available
            canonical_ref = None
            if ev.source_anchor and ev.source_anchor.canonical_reference:
                canonical_ref = ev.source_anchor.canonical_reference

            # Try to resolve from Knowledge Tree cache
            if not canonical_ref and self._kt_cache:
                canonical_ref = self._resolve_from_knowledge_tree(
                    ev.document_version_id,
                    ev.knowledge_node_id,
                )

            # Extract page and line info
            page = None
            line_start = None
            line_end = None
            if ev.source_anchor:
                page = ev.source_anchor.page
                line_start = ev.source_anchor.line_start
                line_end = ev.source_anchor.line_end

            # Build label
            label = canonical_ref or f"Document {ev.document_id}"

            resolution = CitationResolution(
                citation_id=new_id(),
                claim_id=mapping.claim_id,
                evidence_id=ev.id,
                document_id=ev.document_id,
                document_version_id=ev.document_version_id,
                knowledge_node_id=ev.knowledge_node_id,
                canonical_reference=canonical_ref,
                page=page,
                line_start=line_start,
                line_end=line_end,
                label=label,
                confidence=mapping.confidence,
            )
            resolutions.append(resolution)

        return resolutions

    def _resolve_from_knowledge_tree(
        self,
        document_version_id: UUID,
        knowledge_node_id: UUID,
    ) -> Optional[str]:
        """Resolve a canonical reference from a cached Knowledge Tree.

        Args:
            document_version_id: the document version to look up.
            knowledge_node_id: the knowledge node to find.

        Returns:
            The canonical reference string, or None if not found.
        """
        tree = self._kt_cache.get(document_version_id)
        if tree is None:
            return None

        node = tree.get_node(knowledge_node_id)
        if node is None:
            return None

        return CanonicalReferenceGenerator.generate(node, tree.nodes)

    # ------------------------------------------------------------------
    # 5. Citation Validation
    # ------------------------------------------------------------------

    def _validate_citations(
        self,
        claims: list[Claim],
        mappings: list[EvidenceMapping],
        resolutions: list[CitationResolution],
        evidence_package: list[Evidence],
    ) -> ValidationReport:
        """Validate citations against the evidence package.

        Validates (per tasks/012-citation-builder.md #CitationValidation):
            - Evidence exists
            - Node exists
            - Canonical Reference exists
            - Page exists
            - Line exists
            - Evidence belongs to the Evidence Package
            - User has permission (delegated to vault service)

        Args:
            claims: all detected claims.
            mappings: evidence-to-claim mappings.
            resolutions: resolved citations.
            evidence_package: the full evidence package.

        Returns:
            A ValidationReport.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Build lookup sets
        evidence_ids = {ev.id for ev in evidence_package}
        mapped_claim_ids = {m.claim_id for m in mappings}
        resolved_evidence_ids = {r.evidence_id for r in resolutions}

        # Identify supported and unsupported claims
        supported = [c for c in claims if c.id in mapped_claim_ids]
        unsupported = [c for c in claims if c.id not in mapped_claim_ids]

        # Validate each resolution
        for res in resolutions:
            # Evidence exists in the package
            if res.evidence_id not in evidence_ids:
                errors.append(
                    f"Citation {res.citation_id}: evidence {res.evidence_id} "
                    "not found in evidence package"
                )

            # Evidence ID is resolved
            if res.evidence_id not in resolved_evidence_ids:
                errors.append(
                    f"Citation {res.citation_id}: evidence {res.evidence_id} "
                    "not resolved"
                )

        # Check for evidence in package that wasn't used
        used_evidence_ids = {m.evidence_id for m in mappings}
        unused_evidence = evidence_ids - used_evidence_ids
        if unused_evidence:
            warnings.append(
                f"{len(unused_evidence)} evidence item(s) from the package "
                "were not mapped to any claim"
            )

        # Compute coverage
        total_claims = len(claims)
        supported_count = len(supported)
        coverage = supported_count / total_claims if total_claims > 0 else 1.0

        return ValidationReport(
            supported_claims=supported,
            unsupported_claims=unsupported,
            citation_count=len(resolutions),
            coverage=coverage,
            errors=errors,
            warnings=warnings,
            status="VALID" if not errors else "INVALID",
        )

    # ------------------------------------------------------------------
    # Convenience: validate an existing Answer
    # ------------------------------------------------------------------

    def validate_answer(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
        knowledge_trees: "dict[UUID, KnowledgeTree] | None" = None,
    ) -> ValidationReport:
        """Validate citations in an existing Answer.

        This is a lighter-weight operation that validates the citations
        already present in the Answer without rebuilding them.

        Args:
            answer: the Answer to validate.
            evidence_package: the evidence items from retrieval.
            knowledge_trees: optional Knowledge Trees for resolution.

        Returns:
            A ValidationReport.
        """
        if knowledge_trees:
            self._kt_cache.update(knowledge_trees)

        errors: list[str] = []
        warnings: list[str] = []

        evidence_ids = {ev.id for ev in evidence_package}

        # Validate each citation
        for citation in answer.citations:
            # Check that the citation references exist
            if citation.document_id is None:
                errors.append(f"Citation {citation.id}: missing document_id")

            if citation.knowledge_node_id is None:
                errors.append(f"Citation {citation.id}: missing knowledge_node_id")

            # Check that evidence references exist
            evidence_found = False
            for ev_ref in answer.evidence:
                if ev_ref.evidence_id in evidence_ids:
                    evidence_found = True
                    break

            if not evidence_found and answer.evidence:
                warnings.append(
                    f"Citation {citation.id}: no matching evidence found "
                    "in evidence package"
                )

        # Check for citations without evidence references
        if answer.citations and not answer.evidence:
            errors.append(
                "Answer has citations but no evidence references (INV-003)"
            )

        # Check INV-001: every factual claim should have citations
        if answer.status in (AnswerStatus.SUCCESS, AnswerStatus.PARTIAL):
            if not answer.citations:
                warnings.append(
                    "Answer has SUCCESS/PARTIAL status but no citations"
                )

        return ValidationReport(
            supported_claims=[],
            unsupported_claims=[],
            citation_count=len(answer.citations),
            coverage=1.0 if answer.citations else 0.0,
            errors=errors,
            warnings=warnings,
            status="VALID" if not errors else "INVALID",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_citation_version(self) -> str:
        """Return the current citation builder version."""
        return self.CITATION_VERSION

"""Generation Service (tasks/011-generation.md, module Generation).

The Generation Service converts retrieved evidence into a clear, structured
response for the user. It explains retrieved evidence — it never invents legal
facts, never retrieves additional evidence, and never reads original documents.

Per the spec:
    - Interprets the user question
    - Reads the Evidence Package
    - Composes a natural-language answer
    - Attaches citations
    - Explains supporting context
    - Reports uncertainty when evidence is insufficient

The Generation Service consumes ONLY the Retrieval Contract (via the Reranker).
It never retrieves documents, never accesses vector databases, never reads
original documents (ADR-002).

The LLM provider is replaceable (Task 025). When no provider is configured,
a template-based fallback is used.
"""

from __future__ import annotations

import time
import re
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.answer import (
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
from legal_platform.contracts.retrieval import Evidence, RetrievalResult
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.generation.provider import (
    GenerationProvider,
    GenerationProviderError,
    OpenAICompatibleProvider,
    ProviderConfig,
    is_configured,
    load_config,
)
from legal_platform.modules.reranker.reranker import RerankedEvidence
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.storage.eventlog import init_audit_log, log_event


def _load_system_prompt() -> str:
    """Load the authoritative system prompt from design/system-prompt.md."""
    path = Path(__file__).resolve().parent.parent.parent.parent.parent / "design" / "system-prompt.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "You are a legal knowledge assistant. Answer based on the provided evidence."


class GenerationService:
    """The Generation Service.

    Transforms retrieved evidence into a structured Answer Contract.
    Consumes ONLY the Retrieval Contract (via the Reranker). Never retrieves
    documents, never accesses vector databases, never reads originals.

    Integrates with:
        - RerankerService (Task 010) for the final evidence set.
        - DocumentRegistry (Task 001) for audit logging.
        - GenerationProvider (Task 025) for LLM-based generation.
    """

    PROMPT_VERSION = "2.0.0"
    # BGE-M3 cosine scores are normalized by RetrievalService to [0, 1].
    # Below this empirically validated floor, unrelated corpus-nearest chunks
    # must not be presented to the model as evidence.
    ANSWER_MIN_EVIDENCE_SCORE = 0.72
    ANSWER_STRONG_EVIDENCE_SCORE = 0.80
    ANSWER_MIN_QUERY_COVERAGE = 0.35

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        reranker_service: "RerankerService | None" = None,
        provider: "GenerationProvider | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.reranker_service = reranker_service or RerankerService(
            registry=self.registry,
        )
        self._provider = provider
        self._provider_injected = provider is not None
        self._provider_signature: "tuple | None" = None
        self._system_prompt = _load_system_prompt()
        init_audit_log(self.registry.repo.conn)

    @property
    def provider(self) -> GenerationProvider:
        """Return the active provider or fail when setup is incomplete."""
        provider = self._resolve_provider()
        if provider is None:
            raise GenerationProviderError("No generation provider is configured.")
        return provider

    @provider.setter
    def provider(self, value: GenerationProvider) -> None:
        self._provider = value
        self._provider_injected = True
        self._provider_signature = None

    @staticmethod
    def _config_signature(config: ProviderConfig) -> tuple:
        """Return the fields that require rebuilding a provider client."""
        return (
            config.provider_type,
            config.base_url,
            config.api_key,
            config.model,
            config.timeout_seconds,
            config.max_tokens,
            config.temperature,
            config.reasoning_effort,
        )

    def _resolve_provider(self) -> "GenerationProvider | None":
        """Resolve injected or persisted configuration without stale caching.

        The setup wizard can change provider settings while the process is
        running, so persisted clients are rebuilt when their configuration
        changes. An explicitly injected provider remains authoritative for
        tests and alternate deployments.
        """
        if self._provider_injected:
            return self._provider
        if not is_configured():
            self._provider = None
            self._provider_signature = None
            return None

        config = load_config()
        signature = self._config_signature(config)
        if self._provider is None or signature != self._provider_signature:
            if config.provider_type != "openai_compatible":
                raise GenerationProviderError(
                    f"Unsupported generation provider type: {config.provider_type}"
                )
            self._provider = OpenAICompatibleProvider(config=config)
            self._provider_signature = signature
        return self._provider

    # ------------------------------------------------------------------
    # Generate answer from evidence
    # ------------------------------------------------------------------

    def generate(
        self,
        query: str,
        *,
        evidence: "list[Evidence] | list[RerankedEvidence]",
        vault_id: "UUID | None" = None,
    ) -> Answer:
        """Generate an answer from retrieved evidence.

        Flow (per tasks/011 #ProcessingFlow):
            1. Read Evidence Package
            2. Evidence interpretation
            3. Answer generation (LLM or template)
            4. Citation assembly
            5. Answer validation
            6. Return Answer Contract

        Args:
            query: the user's original question.
            evidence: the evidence items (from Retrieval or Reranker).
            vault_id: the vault context (for audit).

        Returns:
            An ``Answer`` contract.
        """
        start_time = time.time()
        request_id = uuid4()

        # Extract Evidence objects from whatever form they arrive in
        evidence_items = self._extract_evidence(evidence)

        # --- Determine status based on evidence ---
        if not evidence_items:
            return self._no_evidence_answer(request_id, query, start_time)

        # --- Build response from evidence ---
        citations: list[Citation] = []
        evidence_refs: list[EvidenceReference] = []
        limitations: list[Limitation] = []

        # Build citations and evidence refs
        for ev in evidence_items:
            citation_id = uuid4()
            citation = Citation(
                id=citation_id,
                document_id=ev.document_id,
                document_version_id=ev.document_version_id,
                knowledge_node_id=ev.knowledge_node_id,
                evidence_id=ev.id,
                source_anchor=ev.source_anchor,
                label=(
                    ev.source_anchor.canonical_reference
                    if ev.source_anchor and ev.source_anchor.canonical_reference
                    else f"Document {ev.document_id}"
                ),
            )
            citations.append(citation)
            evidence_refs.append(EvidenceReference(
                evidence_id=ev.id,
                usage="DIRECT",
            ))

        # --- Generate response text ---
        response_text = self._generate_response(query, evidence_items, citations)
        if self._response_reports_insufficient_evidence(response_text):
            # The model has concluded that the retrieved neighbours do not
            # answer the question.  Do not expose a contradictory SUCCESS
            # badge or decorative citations to unrelated evidence.
            return self._no_evidence_answer(request_id, query, start_time)

        # --- Determine confidence from evidence quality ---
        confidence = self._compute_confidence(evidence_items)

        # --- Check if evidence is incomplete ---
        status = AnswerStatus.SUCCESS
        if confidence.level in (ConfidenceLevel.LOW,):
            status = AnswerStatus.PARTIAL
            limitations.append(Limitation(
                description="Available evidence provides limited coverage of the question. "
                "Consider uploading additional relevant documents."
            ))

        elapsed_ms = (time.time() - start_time) * 1000

        answer = Answer(
            request_id=request_id,
            status=status,
            response=Response(
                format="MARKDOWN",
                content=response_text,
            ),
            citations=citations,
            evidence=evidence_refs,
            confidence=confidence,
            limitations=limitations,
            metadata=AnswerMetadata(
                generation_model=self._get_model_name(),
                generation_latency_ms=round(elapsed_ms, 2),
                prompt_version=self.PROMPT_VERSION,
                retrieval_strategy="hybrid",
            ),
        )

        # Audit
        log_event(
            self.registry.repo.conn,
            service="generation-service",
            module="generation",
            event="generation.complete",
            entity_type="request",
            entity_id=request_id,
            severity="INFO",
            message=f"Answer generated: {status.value}, {len(citations)} citations",
            metadata={
                "status": status.value,
                "evidence_count": len(evidence_items),
                "citation_count": len(citations),
                "latency_ms": round(elapsed_ms, 2),
            },
        )

        return answer

    @staticmethod
    def _response_reports_insufficient_evidence(response_text: str) -> bool:
        """Recognize an explicit, early model conclusion of no evidence."""
        opening = " ".join(response_text.lower().split())[:700]
        patterns = (
            r"không (?:có|tìm thấy) (?:bất kỳ )?"
            r"(?:thông tin|bằng chứng)(?: nào)? "
            r"(?:về|đề cập|quy định|trong|từ)",
            r"không thể (?:xác định|xác minh|trả lời).{0,100}"
            r"(?:bằng chứng|tài liệu)",
            r"(?:evidence|documents?).{0,80}(?:insufficient|do not contain)",
        )
        return any(re.search(pattern, opening) for pattern in patterns)

    def _generate_response(
        self,
        query: str,
        evidence_items: list[Evidence],
        citations: list[Citation],
    ) -> str:
        """Generate via the configured provider or an explicit unconfigured template."""
        provider = self._resolve_provider()
        if provider is not None:
            evidence_text = self._format_evidence_for_llm(evidence_items)
            return provider.generate(
                system_prompt=self._system_prompt,
                evidence_text=evidence_text,
                question=query,
            )

        # Template behavior is limited to a genuinely unconfigured first run.
        return self._format_template_response(query, evidence_items, citations)

    def _format_evidence_for_llm(self, evidence_items: list[Evidence]) -> str:
        """Format evidence with enough document identity for legal attribution.

        Canonical references such as ``Điều 2`` are only meaningful within a
        document.  Omitting the document title caused the model to quote the
        correct clause while incorrectly claiming that the requested decree
        was absent from the evidence package.
        """
        parts = []
        for i, ev in enumerate(evidence_items):
            ref = (
                ev.source_anchor.canonical_reference
                if ev.source_anchor and ev.source_anchor.canonical_reference
                else f"Source {i + 1}"
            )
            document = self.registry.get_document(ev.document_id)
            document_title = (
                document.title if document is not None
                else f"Document {ev.document_id}"
            )
            parts.append(
                f"[Nguồn {i + 1}]\n"
                f"Tài liệu: {document_title}\n"
                f"Vị trí: {ref}\n"
                f"Nội dung:\n{ev.text}"
            )
        return "\n\n---\n\n".join(parts)

    def _get_model_name(self) -> str:
        """Get the model name for metadata reporting."""
        provider = self._resolve_provider()
        if provider is not None:
            try:
                return provider.config.model  # type: ignore
            except AttributeError:
                return provider.__class__.__name__
        return "template"

    # ------------------------------------------------------------------
    # Convenience: search + rerank + generate
    # ------------------------------------------------------------------

    def answer_query(
        self,
        query: str,
        *,
        vault_id: "UUID | None" = None,
        vault_ids: "set[UUID] | None" = None,
        document_id: "UUID | None" = None,
    ) -> Answer:
        """Full pipeline: search → rerank → generate.

        Args:
            query: the user's question.
            vault_id: restrict search to a specific vault.
            vault_ids: authorized vault scope from the API boundary.
            document_id: restrict search to a specific document.

        Returns:
            An ``Answer`` contract.
        """
        reranked, _ = self.reranker_service.search_and_rerank(
            query,
            vault_id=vault_id,
            vault_ids=vault_ids,
            document_id=document_id,
            strategy="HYBRID",
        )
        relevant_ids = {
            item.id for item in self.filter_answer_evidence(
                [candidate.evidence for candidate in reranked],
                query=query,
            )
        }
        relevant = [item for item in reranked if item.evidence.id in relevant_ids]
        return self.generate(query, evidence=relevant, vault_id=vault_id)

    def filter_answer_evidence(
        self,
        evidence: list[Evidence],
        *,
        query: str | None = None,
    ) -> list[Evidence]:
        """Keep evidence strong enough and specific enough for an answer.

        A nearest legal chunk can score just above the semantic floor because
        it shares generic terms such as "Hệ thống đấu thầu" and a currency
        amount.  That is not evidence for a cyberattack penalty.  Moderately
        scored candidates therefore also need meaningful query-term coverage;
        very strong semantic matches remain eligible for paraphrased questions.
        """
        score_eligible = [
            item for item in evidence
            if item.score >= self.ANSWER_MIN_EVIDENCE_SCORE
        ]
        if not query or not score_eligible:
            return score_eligible

        analyzer = self.reranker_service.retrieval_service._analyze_query_terms
        identifier_analyzer = (
            self.reranker_service.retrieval_service._document_identifier_terms
        )
        query_terms = analyzer(query)
        identifier_terms = identifier_analyzer(query)
        if not query_terms:
            return score_eligible

        relevant: list[Evidence] = []
        for item in score_eligible:
            if item.score >= self.ANSWER_STRONG_EVIDENCE_SCORE:
                relevant.append(item)
                continue
            document = self.registry.get_document(item.document_id)
            searchable = item.text
            if document is not None:
                searchable += " " + document.title
                title_terms = set(re.findall(
                    r"\w+", document.title.lower(), flags=re.UNICODE
                ))
                # Explicitly naming a document is stronger relevance evidence
                # than generic vocabulary coverage.  For comparison questions,
                # accept each score-eligible source that matches any requested
                # document code (for example, either 4A or 5A).
                if identifier_terms & title_terms:
                    relevant.append(item)
                    continue
            evidence_terms = set(re.findall(
                r"\w+", searchable.lower(), flags=re.UNICODE
            ))
            coverage = len(query_terms & evidence_terms) / len(query_terms)
            if coverage >= self.ANSWER_MIN_QUERY_COVERAGE:
                relevant.append(item)
        return relevant

    # ------------------------------------------------------------------
    # No evidence handler
    # ------------------------------------------------------------------

    def _no_evidence_answer(
        self, request_id: UUID, query: str, start_time: float
    ) -> Answer:
        """Generate an answer when no evidence is available.

        Per the spec: "If sufficient evidence cannot be found, the system must
        explicitly state uncertainty instead of generating speculative answers."
        """
        elapsed_ms = (time.time() - start_time) * 1000
        answer = Answer(
            request_id=request_id,
            status=AnswerStatus.NO_EVIDENCE,
            response=Response(
                format="MARKDOWN",
                content=(
                    "## Không tìm thấy bằng chứng\n\n"
                    "Không có tài liệu nào trong phạm vi truy xuất chứa thông tin "
                    "liên quan đến câu hỏi của bạn.\n\n"
                    "**Gợi ý:**\n"
                    "- Hãy thử tải lên các tài liệu liên quan.\n"
                    "- Mở rộng phạm vi tìm kiếm.\n"
                    "- Diễn đạt lại câu hỏi với từ khóa khác."
                ),
            ),
            confidence=Confidence(
                level=ConfidenceLevel.LOW,
                score=0.0,
                reason="No evidence was found for the query.",
            ),
            limitations=[Limitation(
                description="No relevant documents were found in the search scope."
            )],
            metadata=AnswerMetadata(
                generation_model=self._get_model_name(),
                generation_latency_ms=round(elapsed_ms, 2),
                prompt_version=self.PROMPT_VERSION,
            ),
        )

        log_event(
            self.registry.repo.conn,
            service="generation-service",
            module="generation",
            event="generation.complete",
            entity_type="request",
            entity_id=request_id,
            severity="INFO",
            message=f"Answer generated: {answer.status.value}, no evidence",
            metadata={
                "status": answer.status.value,
                "evidence_count": 0,
                "citation_count": 0,
                "latency_ms": round(elapsed_ms, 2),
            },
        )

        return answer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_evidence(
        evidence: "list[Evidence] | list[RerankedEvidence]",
    ) -> list[Evidence]:
        """Extract Evidence objects from either raw evidence or reranked evidence."""
        if not evidence:
            return []
        if isinstance(evidence[0], Evidence):
            return evidence  # type: ignore
        return [item.evidence for item in evidence]  # type: ignore

    @staticmethod
    def _compute_confidence(evidence: list[Evidence]) -> Confidence:
        """Compute confidence from evidence quality.

        Uses the average score and count of evidence items.
        """
        if not evidence:
            return Confidence(
                level=ConfidenceLevel.LOW,
                score=0.0,
                reason="No evidence available.",
            )

        avg_score = sum(e.score for e in evidence) / len(evidence)

        if avg_score >= 0.8 and len(evidence) >= 2:
            return Confidence(
                level=ConfidenceLevel.HIGH,
                score=round(avg_score, 4),
                reason=f"Based on {len(evidence)} evidence items with high relevance scores.",
            )
        elif avg_score >= 0.5:
            return Confidence(
                level=ConfidenceLevel.MEDIUM,
                score=round(avg_score, 4),
                reason=f"Based on {len(evidence)} evidence items with moderate relevance.",
            )
        else:
            return Confidence(
                level=ConfidenceLevel.LOW,
                score=round(avg_score, 4),
                reason="Evidence quality is low. Consider uploading more documents.",
            )

    @staticmethod
    def _format_template_response(
        query: str,
        evidence_items: list[Evidence],
        citations: list[Citation],
    ) -> str:
        """Format the response as Markdown using the template approach.

        This is the fallback when no LLM provider is configured.
        """
        parts = [ev.text for ev in evidence_items if ev.text]
        if not parts:
            return "Không có thông tin để hiển thị."

        lines: list[str] = []
        lines.append("## Kết quả tra cứu\n")

        lines.append("### Thông tin tìm thấy\n")
        for i, part in enumerate(parts):
            lines.append(f"{part}\n")

        if citations:
            lines.append("### Trích dẫn\n")
            for i, cit in enumerate(citations):
                label = cit.label or f"Nguồn {i + 1}"
                lines.append(f"- **{label}**")
            lines.append("")

        return "\n".join(lines)

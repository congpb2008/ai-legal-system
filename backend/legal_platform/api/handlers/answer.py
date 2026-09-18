"""Answer generation handler (tasks/014-api.md #QuestionAPIs)."""
from __future__ import annotations

import datetime
from typing import Any
from uuid import UUID

from legal_platform.api.handlers.search import SearchHandler
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory
from legal_platform.contracts.answer import Answer
from legal_platform.modules.citation.service import (
    CitationBuilderService,
    CitationTraceabilityError,
)
from legal_platform.modules.embedding.engine import EmbeddingEngineError
from legal_platform.modules.generation.provider import GenerationProviderError
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.vault.service import VaultService


class AnswerHandler:
    """Question answering endpoints (tasks/014-api.md #QuestionAPIs)."""

    def __init__(
        self,
        generation_service: "GenerationService | None" = None,
        citation_service: "CitationBuilderService | None" = None,
        vault_service: "VaultService | None" = None,
        ocr_service=None,
    ):
        self.ocr = ocr_service
        self.generation = generation_service or GenerationService()
        self.citation = citation_service or CitationBuilderService()
        self.vault = vault_service or VaultService(registry=self.generation.registry)

    def answer(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/answers"""
        query = (body.get("query") or "").strip()
        if not query:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="query is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        scope = SearchHandler(
            retrieval_service=self.generation.reranker_service.retrieval_service,
            reranker_service=self.generation.reranker_service,
            vault_service=self.vault,
        )
        vault_id, vault_ids, document_id, scope_error = scope._resolve_scope(body, user_id)
        if scope_error:
            return scope_error

        # Run the full pipeline while retaining the exact transient evidence
        # package for citation verification.
        try:
            reranked, _ = self.generation.reranker_service.search_and_rerank(
                query,
                vault_id=vault_id,
                vault_ids=vault_ids,
                document_id=document_id,
                strategy="HYBRID",
                as_of=body.get('as_of'),
            )
            evidence = self.generation.filter_answer_evidence(
                [item.evidence for item in reranked],
                query=query,
            )
            if self.ocr:
                from legal_platform.grounding import source_passages
                evidence = source_passages(evidence, self.ocr, self.citation.parser)
            answer = self.generation.generate(
                query,
                evidence=evidence,
                vault_id=vault_id,
            )
            answer, _ = self.citation.verify_evidence_traceability(answer, evidence)
        except EmbeddingEngineError:
            return SearchHandler._embedding_unavailable()
        except GenerationProviderError as exc:
            return ApiResponse.err_response(
                ApiError(
                    code="GENERATION_UNAVAILABLE",
                    message=f"Answer generation failed: {exc}",
                    category=ErrorCategory.DEPENDENCY,
                    retryable=True,
                ),
                status=503,
            )
        except CitationTraceabilityError:
            return ApiResponse.err_response(
                ApiError(
                    code="CITATION_TRACEABILITY_FAILED",
                    message=(
                        "The answer was withheld because its citations could "
                        "not be verified against the canonical source."
                    ),
                    category=ErrorCategory.INTERNAL,
                    retryable=False,
                ),
                status=500,
            )

        payload = self._answer_to_dict(answer)
        payload['answer_mode'] = 'verified_quotations'
        payload['as_of'] = body.get('as_of') or datetime.date.today().isoformat()
        payload['scope'] = {'vault_id': str(vault_id) if vault_id else None, 'document_id': str(document_id) if document_id else None}
        payload['confidence'] = None
        payload['evidence_status'] = 'no_evidence' if not answer.citations else 'source_quotations'
        from legal_platform.grounding import evidence_date_info
        for citation in payload['citations']:
            document = self.generation.registry.get_document(UUID(citation['document_id']))
            if document:
                citation.update(evidence_date_info(document))
        return ApiResponse.ok(data=payload)

    def _answer_to_dict(self, answer: Answer) -> dict[str, Any]:
        return {
            "request_id": str(answer.request_id),
            "generated_at": answer.generated_at.isoformat(),
            "status": answer.status.value if hasattr(answer.status, 'value') else answer.status,
            "response": {
                "format": answer.response.format,
                "content": answer.response.content,
            },
            "citations": [
                ({
                    "id": str(c.id),
                    "document_id": str(c.document_id),
                    "document_version_id": str(c.document_version_id),
                    "knowledge_node_id": str(c.knowledge_node_id),
                    "evidence_id": str(c.evidence_id) if c.evidence_id else None,
                    "source_anchor": c.source_anchor.model_dump() if c.source_anchor else None,
                    "label": c.label,
                    "document_title": (
                        self.generation.registry.get_document(c.document_id).title
                        if self.generation.registry.get_document(c.document_id)
                        else None
                    ),
                    "document_tags": (
                        self.generation.registry.get_document(c.document_id).metadata.tags
                        if self.generation.registry.get_document(c.document_id)
                        else []
                    ),
                    "source_url": (
                        f"/api/v1/documents/{c.document_id}/source"
                        f"?node_id={c.knowledge_node_id}"
                        + (f"&page={c.source_anchor.page}" if c.source_anchor and c.source_anchor.page else "")
                    ),
                })
                for c in answer.citations
            ],
            "evidence": [
                {
                    "evidence_id": str(e.evidence_id),
                    "usage": e.usage,
                }
                for e in answer.evidence
            ],
            "confidence": {
                "level": answer.confidence.level.value if hasattr(answer.confidence.level, 'value') else answer.confidence.level,
                "score": answer.confidence.score,
                "reason": answer.confidence.reason,
            },
            "limitations": [l.description for l in answer.limitations],
            "metadata": {
                "generation_model": answer.metadata.generation_model,
                "generation_latency_ms": answer.metadata.generation_latency_ms,
                "prompt_version": answer.metadata.prompt_version,
                "retrieval_strategy": answer.metadata.retrieval_strategy,
            },
        }

"""Search handler (tasks/014-api.md #SearchAPIs)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from legal_platform.api.handlers.vault import VaultHandler
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory
from legal_platform.contracts.retrieval import RetrievalResult
from legal_platform.modules.embedding.engine import EmbeddingEngineError
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vault.models import Permission
from legal_platform.modules.vault.service import VaultService


class SearchHandler:
    """Search endpoints (tasks/014-api.md #SearchAPIs)."""

    def __init__(
        self,
        retrieval_service: "RetrievalService | None" = None,
        reranker_service: "RerankerService | None" = None,
        vault_service: "VaultService | None" = None,
    ):
        self.retrieval = retrieval_service or RetrievalService()
        self.reranker = reranker_service or RerankerService()
        self.vault = vault_service or VaultService(registry=self.retrieval.registry)

    def search(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/search (hybrid search)"""
        query = (body.get("query") or "").strip()
        if not query:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="query is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        vault_id, vault_ids, document_id, scope_error = self._resolve_scope(body, user_id)
        if scope_error:
            return scope_error
        top_k = int(body.get("top_k", 20))

        try:
            result = self.retrieval.search(
                query,
                vault_id=vault_id,
                vault_ids=vault_ids,
                document_id=document_id,
                top_k=top_k,
                as_of=body.get('as_of'),
            )
        except EmbeddingEngineError:
            return self._embedding_unavailable()

        return ApiResponse.ok(data=self._result_to_dict(result))

    def search_semantic(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/search/semantic"""
        return self._search_with_strategy(body, "SEMANTIC", user_id)

    def search_keyword(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/search/keyword"""
        return self._search_with_strategy(body, "KEYWORD", user_id)

    def search_hybrid(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/search/hybrid"""
        return self._search_with_strategy(body, "HYBRID", user_id)

    def _search_with_strategy(self, body: dict[str, Any], strategy: str, user_id: str) -> ApiResponse:
        query = (body.get("query") or "").strip()
        if not query:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="query is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        vault_id, vault_ids, document_id, scope_error = self._resolve_scope(body, user_id)
        if scope_error:
            return scope_error
        top_k = int(body.get("top_k", 20))

        try:
            result = self.retrieval.search(
                query,
                vault_id=vault_id,
                vault_ids=vault_ids,
                document_id=document_id,
                top_k=top_k,
                as_of=body.get('as_of'),
                strategy=strategy,
            )
        except EmbeddingEngineError:
            return self._embedding_unavailable()

        return ApiResponse.ok(data=self._result_to_dict(result))

    def _resolve_scope(self, body: dict[str, Any], user_id: str):
        authorized = set(self.vault.authorized_vault_ids(user_id, permission=Permission.READ))
        try:
            vault_id = UUID(body["vault_id"]) if body.get("vault_id") else None
            document_id = UUID(body["document_id"]) if body.get("document_id") else None
        except ValueError:
            return None, authorized, None, ApiResponse.err_response(
                ApiError(
                    code="INVALID_SCOPE_ID",
                    message="vault_id and document_id must be valid UUIDs.",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )
        if vault_id is not None and vault_id not in authorized:
            return None, authorized, None, VaultHandler._forbidden(str(vault_id))
        if document_id is not None:
            document = self.retrieval.registry.get_document(document_id)
            if document is None:
                return None, authorized, None, ApiResponse.err_response(
                    ApiError(
                        code="DOCUMENT_NOT_FOUND",
                        message=f"Document {document_id} not found.",
                        category=ErrorCategory.NOT_FOUND,
                    ),
                    status=404,
                )
            if document.vault_id not in authorized:
                return None, authorized, None, ApiResponse.err_response(
                    ApiError(
                        code="DOCUMENT_FORBIDDEN",
                        message="You do not have permission to search this document.",
                        category=ErrorCategory.AUTHORIZATION,
                    ),
                    status=403,
                )
            if vault_id is not None and document.vault_id != vault_id:
                return None, authorized, None, ApiResponse.err_response(
                    ApiError(
                        code="SCOPE_CONFLICT",
                        message="The document does not belong to the requested vault.",
                        category=ErrorCategory.VALIDATION,
                    ),
                    status=400,
                )
        return vault_id, authorized, document_id, None

    @staticmethod
    def _embedding_unavailable() -> ApiResponse:
        return ApiResponse.err_response(
            ApiError(
                code="EMBEDDING_UNAVAILABLE",
                message=(
                    "Semantic search is unavailable because the configured "
                    "embedding backend or model could not be reached."
                ),
                category=ErrorCategory.DEPENDENCY,
                retryable=True,
            ),
            status=503,
        )

    def _result_to_dict(self, result: RetrievalResult) -> dict[str, Any]:
        return {
            "query_id": str(result.query_id),
            "strategy": result.strategy.value if hasattr(result.strategy, 'value') else result.strategy,
            "generated_at": result.generated_at.isoformat(),
            "query": result.query,
            "evidence": [
                ({
                    "id": str(e.id),
                    "knowledge_node_id": str(e.knowledge_node_id),
                    "document_id": str(e.document_id),
                    "document_version_id": str(e.document_version_id),
                    "document_title": (
                        self.retrieval.registry.get_document(e.document_id).title
                        if self.retrieval.registry.get_document(e.document_id)
                        else None
                    ),
                    "document_tags": (
                        self.retrieval.registry.get_document(e.document_id).metadata.tags
                        if self.retrieval.registry.get_document(e.document_id)
                        else []
                    ),
                    "score": e.score,
                    "rank": e.rank,
                    "text": e.text,
                    "source_anchor": {
                        "canonical_reference": e.source_anchor.canonical_reference if e.source_anchor else None,
                        "page": e.source_anchor.page if e.source_anchor else None,
                    } if e.source_anchor else None,
                    "source_url": (
                        f"/api/v1/documents/{e.document_id}/source"
                        f"?node_id={e.knowledge_node_id}"
                        + (f"&page={e.source_anchor.page}" if e.source_anchor and e.source_anchor.page else "")
                    ),
                })
                for e in result.evidence
            ],
            "metadata": {
                "strategy": result.metadata.strategy,
                "latency_ms": result.metadata.latency_ms,
                "candidate_count": result.metadata.candidate_count,
                "returned_count": result.metadata.returned_count,
            },
        }

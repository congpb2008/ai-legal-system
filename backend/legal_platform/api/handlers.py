"""API request handlers (tasks/014-api.md).

Each handler implements one API domain. Handlers are stateless and receive
the services they need via constructor injection. They return ``ApiResponse``
objects that the server serializes to JSON.

API Domains:
    - AuthHandler:     POST /v1/auth/login, POST /v1/auth/logout, GET /v1/auth/me
    - VaultHandler:    CRUD for vaults
    - DocumentHandler: CRUD for documents
    - UploadHandler:   File upload and status
    - SearchHandler:   Search endpoints
    - AnswerHandler:   Question answering
    - AdminHandler:    Administrative operations
    - HealthHandler:   Health check endpoints
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform import __version__

from legal_platform.api.models import (
    ApiError,
    ApiResponse,
    ErrorCategory,
    HealthStatus,
    PaginatedResponse,
)
from legal_platform.contracts.answer import Answer
from legal_platform.contracts.common import new_id
from legal_platform.contracts.document import Document, DocumentType, DocumentStatus, Visibility
from legal_platform.contracts.retrieval import RetrievalResult
from legal_platform.modules.chunking.service import ChunkingService
from legal_platform.modules.citation.service import (
    CitationBuilderService,
    CitationTraceabilityError,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import EmbeddingEngineError
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.generation.provider import GenerationProviderError
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.observability.jobs import JobMonitor, JobStatus
from legal_platform.modules.parser.service import ParserService
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.modules.vault.models import Permission, VaultType, VaultStatus
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vector_index.service import VectorIndexService


# ---------------------------------------------------------------------------
# Server start time (for uptime)
# ---------------------------------------------------------------------------

_START_TIME = time.time()


def _document_metadata_from_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize the mutable metadata fields exposed by the public API."""
    raw_metadata = body.get("metadata")
    if raw_metadata is not None and not isinstance(raw_metadata, dict):
        raise ValueError("metadata must be an object")
    metadata: dict[str, Any] = dict(raw_metadata or {})
    touched = raw_metadata is not None

    if "tags" in body:
        raw_tags = body.get("tags")
        if isinstance(raw_tags, str):
            stripped = raw_tags.strip()
            if stripped.startswith("["):
                try:
                    raw_tags = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError("tags must be a comma-separated list or JSON array") from exc
            else:
                raw_tags = [part.strip() for part in stripped.replace("\n", ",").split(",")]
        if raw_tags is None:
            raw_tags = []
        if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
            raise ValueError("tags must be a list of strings")
        tags: list[str] = []
        seen: set[str] = set()
        for raw_tag in raw_tags:
            tag = " ".join(raw_tag.strip().split())
            if not tag:
                continue
            if len(tag) > 64:
                raise ValueError("each tag must be at most 64 characters")
            if any(ord(char) < 32 for char in tag):
                raise ValueError("tags cannot contain control characters")
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                tags.append(tag)
        if len(tags) > 20:
            raise ValueError("a document can have at most 20 tags")
        metadata["tags"] = tags
        touched = True

    for field in ("issue_date", "effective_date", "expiration_date"):
        if field in body:
            value = body.get(field)
            if isinstance(value, str) and value and len(value) == 10:
                value = f"{value}T00:00:00Z"
            metadata[field] = value or None
            touched = True

    return metadata if touched else None


# ---------------------------------------------------------------------------
# Auth Handler
# ---------------------------------------------------------------------------


from legal_platform.accounts import AuthHandler


# ---------------------------------------------------------------------------
# Vault Handler
# ---------------------------------------------------------------------------


class VaultHandler:
    """Vault management endpoints (tasks/014-api.md #VaultAPIs)."""

    def __init__(self, vault_service: "VaultService | None" = None):
        self.vault = vault_service or VaultService()

    def list_vaults(self, params: dict[str, str], user_id: str) -> ApiResponse:
        """GET /v1/vaults"""
        vault_type = params.get("type")
        status = params.get("status")
        limit = int(params.get("limit", "100"))
        offset = int(params.get("offset", "0"))

        # Coerce string params to enums
        vt = VaultType(vault_type.upper()) if vault_type else None
        vs = VaultStatus(status.upper()) if status else None

        vaults = self.vault.list_vaults(
            vault_type=vt,
            status=vs,
            user_id=user_id,
            limit=None,
            offset=0,
        )
        total = len(vaults)

        return ApiResponse.ok(
            data=PaginatedResponse(
                items=[dict(self._vault_to_dict(v),
                            can_upload=v.has_permission(user_id, Permission.UPLOAD),
                            can_manage=v.has_permission(user_id, Permission.MANAGE))
                       for v in vaults[offset:offset + limit]],
                total=total,
                limit=limit,
                offset=offset,
            ),
        )

    def create_vault(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/vaults"""
        name = (body.get("name") or "").strip()
        if not name:
            return ApiResponse.err_response(
                ApiError(
                    code="VALIDATION_ERROR",
                    message="Vault name is required.",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        vault_type = body.get("vault_type", "COMMON")
        description = body.get("description")
        retention_policy = body.get("retention_policy")

        try:
            vault = self.vault.create_vault(
                name=name,
                vault_type=vault_type,
                owner=user_id,
                organization_id=UUID(body['organization_id']) if body.get('organization_id') else None,
                description=description,
                retention_policy=retention_policy,
            )
        except ValueError as e:
            return ApiResponse.err_response(
                ApiError(
                    code="VALIDATION_ERROR",
                    message=str(e),
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        return ApiResponse.ok(
            data=self._vault_to_dict(vault),
            status=201,
        )

    def get_vault(self, vault_id: str, user_id: str) -> ApiResponse:
        """GET /v1/vaults/{vaultId}"""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(
                    code="INVALID_ID",
                    message=f"Invalid vault ID: {vault_id}",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        vault = self.vault.get_vault(vid)
        if vault is None:
            return ApiResponse.err_response(
                ApiError(
                    code="VAULT_NOT_FOUND",
                    message=f"Vault {vault_id} not found.",
                    category=ErrorCategory.NOT_FOUND,
                ),
                status=404,
            )
        if not self.vault.check_permission(vid, user_id, Permission.READ):
            return self._forbidden(vault_id)

        return ApiResponse.ok(data=self._vault_to_dict(vault))

    def update_vault(self, vault_id: str, body: dict[str, Any], user_id: str) -> ApiResponse:
        """PATCH /v1/vaults/{vaultId}"""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid vault ID: {vault_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not self.vault.check_permission(vid, user_id, Permission.MANAGE):
            return self._forbidden(vault_id)

        try:
            vault = self.vault.update_vault(
                vid,
                name=body.get("name"),
                description=body.get("description"),
                retention_policy=body.get("retention_policy"),
            )
        except KeyError:
            return ApiResponse.err_response(
                ApiError(code="VAULT_NOT_FOUND", message=f"Vault {vault_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )

        return ApiResponse.ok(data=self._vault_to_dict(vault))

    def delete_vault(self, vault_id: str, user_id: str) -> ApiResponse:
        """DELETE /v1/vaults/{vaultId} — archives the vault."""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid vault ID: {vault_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not self.vault.check_permission(vid, user_id, Permission.MANAGE):
            return self._forbidden(vault_id)
        try:
            self.vault.archive_vault(vid)
        except KeyError:
            return ApiResponse.err_response(
                ApiError(code="VAULT_NOT_FOUND", message=f"Vault {vault_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        return ApiResponse.ok(data={"message": f"Vault {vault_id} archived."})

    @staticmethod
    def _forbidden(vault_id: str) -> ApiResponse:
        return ApiResponse.err_response(
            ApiError(
                code="VAULT_FORBIDDEN",
                message=f"You do not have permission to access vault {vault_id}.",
                category=ErrorCategory.AUTHORIZATION,
            ),
            status=403,
        )

    @staticmethod
    def _vault_to_dict(vault: Any) -> dict[str, Any]:
        return {
            "id": str(vault.id),
            "name": vault.name,
            "vault_type": vault.vault_type.value if hasattr(vault.vault_type, 'value') else vault.vault_type,
            "owner": vault.owner,
            "description": vault.description,
            "status": vault.status.value if hasattr(vault.status, 'value') else vault.status,
            "organization_id": str(vault.organization_id),
            "created_at": vault.created_at.isoformat() if hasattr(vault.created_at, 'isoformat') else str(vault.created_at),
            "updated_at": vault.updated_at.isoformat() if hasattr(vault.updated_at, 'isoformat') else str(vault.updated_at),
            "document_count": vault.document_count,
            "member_count": vault.member_count,
            "retention_policy": vault.retention_policy,
        }


# ---------------------------------------------------------------------------
# Document Handler
# ---------------------------------------------------------------------------


class DocumentHandler:
    """Document management endpoints (tasks/014-api.md #DocumentAPIs)."""

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        vault_service: "VaultService | None" = None,
        vector_index: "VectorIndexService | None" = None,
        file_storage: Any = None,
        ocr_service: "OcrService | None" = None,
        parser_service: "ParserService | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.vault = vault_service or VaultService(registry=self.registry)
        self.vector_index = vector_index or VectorIndexService(registry=self.registry)
        self.storage = file_storage
        self.ocr = ocr_service
        self.parser = parser_service

    def create_document(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/documents"""
        title = (body.get("title") or "").strip()
        if not title:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="Document title is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        try:
            vault_id = UUID(body["vault_id"]) if "vault_id" in body else new_id()
            vault = self.vault.get_vault(vault_id)
            if vault is None:
                raise ValueError(f"Vault {vault_id} does not exist")
            if not self.vault.check_permission(vault_id, user_id, Permission.UPLOAD):
                return VaultHandler._forbidden(str(vault_id))
            metadata = _document_metadata_from_body(body)
            doc = self.registry.register_document(
                user_id=user_id,
                document_type=body.get("document_type", "INTERNAL_REGULATION"),
                title=title,
                issuing_authority=body.get("issuing_authority", ""),
                vault_id=vault_id,
                organization_id=(
                    UUID(body["organization_id"])
                    if "organization_id" in body
                    else vault.organization_id
                ),
                document_number=body.get("document_number"),
                short_title=body.get("short_title"),
                description=body.get("description"),
                language=body.get("language", "vi"),
                visibility=body.get("visibility", "DEPARTMENT"),
                metadata=metadata,
            )
        except (ValueError, KeyError) as e:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message=str(e),
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        return ApiResponse.ok(data=self._doc_to_dict(doc), status=201)

    def update_document(self, doc_id: str, body: dict[str, Any], user_id: str) -> ApiResponse:
        """PATCH /v1/documents/{documentId} — mutable business metadata only."""
        try:
            did = UUID(doc_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        doc = self.registry.get_document(did)
        if doc is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        forbidden = self._require_document_permission(doc, user_id, Permission.UPDATE)
        if forbidden:
            return forbidden
        try:
            title = body.get("title")
            if title is not None:
                title = str(title).strip()
                if not title:
                    raise ValueError("Document title cannot be empty.")
            updated = self.registry.update_metadata(
                did,
                user_id=user_id,
                title=title,
                short_title=body.get("short_title") if "short_title" in body else None,
                description=body.get("description") if "description" in body else None,
                issuing_authority=body.get("issuing_authority") if "issuing_authority" in body else None,
                document_number=body.get("document_number") if "document_number" in body else None,
                language=body.get("language") if "language" in body else None,
                metadata=_document_metadata_from_body(body),
            )
        except (TypeError, ValueError) as exc:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message=str(exc),
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        return ApiResponse.ok(data=self._doc_to_dict(updated))

    def list_documents(self, params: dict[str, str], user_id: str) -> ApiResponse:
        """GET /v1/documents"""
        vault_id = params.get("vault_id")
        status = params.get("status")
        limit = int(params.get("limit", "100"))
        offset = int(params.get("offset", "0"))

        ds = DocumentStatus(status.upper()) if status else None

        requested_vault = UUID(vault_id) if vault_id else None
        if requested_vault and not self.vault.check_permission(
            requested_vault,
            user_id,
            Permission.READ,
        ):
            return VaultHandler._forbidden(str(requested_vault))
        authorized = set(self.vault.authorized_vault_ids(user_id))
        query = params.get('q', '').strip()
        processing = params.get('processing') or None
        if len(query) > 200 or processing not in (None, 'READY', 'FAILED', 'PROCESSING'):
            return ApiResponse.err_response(ApiError(code='INVALID_FILTER',
                message='Use a title or document number of up to 200 characters and a valid processing status.',
                category=ErrorCategory.VALIDATION), status=400)
        docs, total = self.registry.query_catalog(
            vault_ids=authorized & {requested_vault} if requested_vault else authorized,
            status=ds,
            query=query, processing=processing,
            limit=limit,
            offset=offset,
        )

        return ApiResponse.ok(
            data=PaginatedResponse(
                items=[dict(self._doc_to_dict(d), can_manage=self.vault.check_permission(
                    d.vault_id, user_id, Permission.MANAGE)) for d in docs],
                total=total,
                limit=limit,
                offset=offset,
            ),
        )

    def document_summary(self, user_id: str) -> ApiResponse:
        """Count the complete accessible catalog, without a pagination cap."""
        return ApiResponse.ok(data=self.registry.catalog_totals(self.vault.authorized_vault_ids(user_id)))

    def get_document(self, doc_id: str, user_id: str) -> ApiResponse:
        """GET /v1/documents/{documentId}"""
        try:
            did = UUID(doc_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        doc = self.registry.get_document(did)
        if doc is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        forbidden = self._require_document_permission(doc, user_id, Permission.READ)
        if forbidden:
            return forbidden
        payload = self._doc_to_dict(doc)
        payload['can_manage'] = self.vault.check_permission(doc.vault_id, user_id, Permission.MANAGE)
        payload['can_update'] = self.vault.check_permission(doc.vault_id, user_id, Permission.UPDATE)
        return ApiResponse.ok(data=payload)

    def delete_document(self, doc_id: str, user_id: str) -> ApiResponse:
        """DELETE /v1/documents/{documentId}"""
        try:
            did = UUID(doc_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        doc = self.registry.get_document(did)
        if doc is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        forbidden = self._require_document_permission(doc, user_id, Permission.DELETE)
        if forbidden:
            return forbidden
        self.registry.archive_document(did, user_id=user_id)
        self.vector_index.set_document_status(did, "ARCHIVED")
        return ApiResponse.ok(data={"message": f"Document {doc_id} archived."})

    def get_document_status(self, doc_id: str, user_id: str) -> ApiResponse:
        """GET /v1/documents/{documentId}/status"""
        try:
            did = UUID(doc_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        doc = self.registry.get_document(did)
        if doc is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        forbidden = self._require_document_permission(doc, user_id, Permission.READ)
        if forbidden:
            return forbidden
        processing = self.registry.get_processing(did)
        return ApiResponse.ok(data={
            "document_id": str(doc.id),
            "title": doc.title,
            "status": doc.status.value,
            "processing_state": processing.value if processing else None,
            "processing_error": self.registry.get_processing_failure_reason(did),
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        })

    def get_document_source(
        self,
        doc_id: str,
        params: dict[str, str],
        user_id: str,
    ) -> ApiResponse:
        """Return an authorized source view anchored to a node/page.

        Physical storage references never leave the API. Original bytes are
        returned only on an explicit request and remain protected by the same
        vault READ check as document metadata.
        """
        try:
            did = UUID(doc_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        document = self.registry.get_document(did)
        if document is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        forbidden = self._require_document_permission(document, user_id, Permission.READ)
        if forbidden:
            return forbidden

        requested_version = params.get('version_id') or params.get('document_version_id')
        if requested_version:
            version_id = UUID(requested_version)
        else:
            active = next((v for v in document.versions if v.status.value == 'ACTIVE'), document.versions[-1])
            version_id = active.version_id
        if not any(v.version_id == version_id for v in document.versions):
            return AuthHandler.error('Source version not found.', 404)
        source = self.registry.get_source_metadata(did, version_id=version_id)
        if source is None or self.storage is None:
            return ApiResponse.err_response(
                ApiError(code="SOURCE_NOT_FOUND", message="Original source is not available.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        storage_ref = source["storage_ref"]
        if not self.storage.exists(storage_ref):
            return ApiResponse.err_response(
                ApiError(code="SOURCE_FILE_MISSING",
                         message="The source record exists but its immutable file is missing.",
                         category=ErrorCategory.INTERNAL),
                status=410,
            )

        tree = self.parser.get_tree_for_version(version_id) if self.parser else None
        node = None
        node_id = params.get("node_id")
        if node_id:
            try:
                requested_node = UUID(node_id)
            except ValueError:
                return ApiResponse.err_response(
                    ApiError(code="INVALID_NODE_ID", message="node_id must be a UUID.",
                             category=ErrorCategory.VALIDATION),
                    status=400,
                )
            node = tree.get_node(requested_node) if tree else None
            if node is None:
                return ApiResponse.err_response(
                    ApiError(code="SOURCE_NODE_NOT_FOUND",
                             message="The requested citation node is not in this document version.",
                             category=ErrorCategory.NOT_FOUND),
                    status=404,
                )

        try:
            page_number = int(params["page"]) if params.get("page") else (
                node.source.page if node else 1
            )
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_PAGE", message="page must be a positive integer.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if page_number < 1:
            return ApiResponse.err_response(
                ApiError(code="INVALID_PAGE", message="page must be a positive integer.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        ocr_result = None
        if self.ocr:
            ocr_result = next(
                (
                    result for result in self.ocr.get_results_for_document(did)
                    if result.version_id == version_id
                ),
                None,
            )
        page = next(
            (item for item in ocr_result.pages if item.page_number == page_number),
            None,
        ) if ocr_result else None
        if ocr_result is not None and page is None:
            return ApiResponse.err_response(
                ApiError(code="SOURCE_PAGE_NOT_FOUND",
                         message=f"Page {page_number} is not available in this source.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )

        filename = source.get("filename") or Path(storage_ref).name
        mime_type = source.get("mime_type") or mimetypes.guess_type(filename)[0]
        payload: dict[str, Any] = {
            "document_id": str(document.id),
            "document_version_id": str(version_id),
            "title": document.title,
            "filename": filename,
            "mime_type": mime_type or "application/octet-stream",
            "size_bytes": source.get("size_bytes") or None,
            "checksum_sha256": source.get("checksum_sha256") or None,
            "page_count": ocr_result.total_pages if ocr_result else None,
            "extraction_warning": ' '.join(ocr_result.warnings) if ocr_result and ocr_result.engine.startswith('vision:') else "Word page layout is not preserved. These locations refer to extracted text." if ocr_result and ocr_result.engine == "docx-xml" else "For OCR sources, check recognition against the original file.",
            "page": ({
                "number": page.page_number,
                "text": page.text,
                "lines": [line.text for line in page.lines],
            } if page else None),
            "node": ({
                "id": str(node.id),
                "type": node.type.value,
                "title": node.title,
                "text": node.text,
                "page_start": node.page_start,
                "page_end": node.page_end,
                "line_start": node.source.line_start,
                "line_end": node.source.line_end,
            } if node else None),
        }

        if params.get("include_original", "").lower() in ("1", "true", "yes"):
            original = self.storage.retrieve(storage_ref)
            max_inline = 25 * 1024 * 1024
            if len(original) > max_inline:
                return ApiResponse.err_response(
                    ApiError(code="SOURCE_TOO_LARGE",
                             message="The original is too large for browser transfer.",
                             category=ErrorCategory.VALIDATION),
                    status=413,
                )
            payload["size_bytes"] = len(original)
            payload["checksum_sha256"] = hashlib.sha256(original).hexdigest()
            payload["content_base64"] = base64.b64encode(original).decode("ascii")

        return ApiResponse.ok(data=payload)

    def _require_document_permission(
        self,
        doc,
        user_id: str,
        permission: Permission,
    ) -> "ApiResponse | None":
        if self.vault.check_permission(doc.vault_id, user_id, permission):
            return None
        return ApiResponse.err_response(
            ApiError(
                code="DOCUMENT_FORBIDDEN",
                message="You do not have permission to access this document.",
                category=ErrorCategory.AUTHORIZATION,
            ),
            status=403,
        )

    def _doc_to_dict(self, doc: Any) -> dict[str, Any]:
        processing = self.registry.get_processing(doc.id)
        source = self.registry.get_source_metadata(doc.id) or {}
        metadata = doc.metadata.model_dump(mode="json") if hasattr(doc, "metadata") else {}
        return {
            "id": str(doc.id),
            "type": doc.type.value if hasattr(doc.type, 'value') else doc.type,
            "title": doc.title,
            "short_title": doc.short_title,
            "description": doc.description,
            "issuing_authority": doc.issuing_authority,
            "document_number": doc.document_number,
            "language": doc.language,
            "status": doc.status.value if hasattr(doc.status, 'value') else doc.status,
            "processing_state": processing.value if processing else None,
            "processing_error": self.registry.get_processing_failure_reason(doc.id),
            "visibility": doc.visibility.value if hasattr(doc.visibility, 'value') else doc.visibility,
            "vault_id": str(doc.vault_id),
            "organization_id": str(doc.organization_id),
            "created_at": doc.created_at.isoformat() if hasattr(doc.created_at, 'isoformat') else str(doc.created_at),
            "updated_at": doc.updated_at.isoformat() if hasattr(doc.updated_at, 'isoformat') else str(doc.updated_at),
            "version_count": len(doc.versions) if hasattr(doc, 'versions') else 0,
            "versions": [v.model_dump(mode='json') for v in doc.versions],
            "original_filename": source.get("filename"),
            "tags": metadata.get("tags", []),
            "keywords": metadata.get("keywords", []),
            "issue_date": str(metadata["issue_date"])[:10] if metadata.get("issue_date") else None,
            "effective_date": str(metadata["effective_date"])[:10] if metadata.get("effective_date") else None,
            "expiration_date": str(metadata["expiration_date"])[:10] if metadata.get("expiration_date") else None,
            "metadata": metadata,
        }


# ---------------------------------------------------------------------------
# Upload Handler
# ---------------------------------------------------------------------------


class UploadHandler:
    """Upload endpoints (tasks/014-api.md #UploadAPIs)."""

    def __init__(
        self,
        upload_service: "UploadService | None" = None,
        job_monitor: "JobMonitor | None" = None,
    ):
        self.upload = upload_service or UploadService()
        self.jobs = job_monitor or JobMonitor(conn=self.upload.registry.repo.conn)

    def upload_file(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/uploads

        Supports two methods:
        1. JSON body with base64 content (legacy)
        2. FormData with file object (preferred for folder upload)
        """
        # Check if file object is provided (FormData)
        if 'file' in body and isinstance(body['file'], bytes):
            file_content = body['file']
            # Browsers may include a webkitRelativePath in the multipart
            # filename during folder upload.  The UI sends File.name as the
            # explicit filename field, which is the authoritative provenance
            # basename and must win over the transport-level path.
            filename = ((body.get('filename') or body.get('__filename__') or '')).strip()
            title = (body.get('title') or '').strip()
            mime_type = body.get('mime_type') or 'application/octet-stream'

            if not filename or not title:
                return ApiResponse.err_response(
                    ApiError(code="VALIDATION_ERROR",
                             message="filename and title are required.",
                             category=ErrorCategory.VALIDATION),
                    status=400,
                )
        else:
            # Legacy JSON body with base64 content
            filename = (body.get("filename") or "").strip()
            content_b64 = (body.get("content_base64") or "").strip()
            title = (body.get("title") or "").strip()

            if not filename or not content_b64 or not title:
                return ApiResponse.err_response(
                    ApiError(code="VALIDATION_ERROR",
                             message="filename, content_base64, and title are required.",
                             category=ErrorCategory.VALIDATION),
                    status=400,
                )

            import base64
            try:
                content = base64.b64decode(content_b64)
            except Exception:
                return ApiResponse.err_response(
                    ApiError(code="INVALID_ENCODING",
                             message="content_base64 is not valid base64.",
                             category=ErrorCategory.VALIDATION),
                    status=400,
                )

            file_content = content
            mime_type = body.get("mime_type") or "application/octet-stream"

        # === Validate vault_id (required by Document Contract INV-001) ===
        raw_vault_id = body.get("vault_id", "").strip() if body.get("vault_id") else ""
        if not raw_vault_id:
            return ApiResponse.err_response(
                ApiError(code="MISSING_VAULT_ID",
                         message="vault_id is required. Please select a vault before uploading.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        try:
            vault_uuid = UUID(raw_vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_VAULT_ID",
                         message=f"vault_id is not a valid UUID: {raw_vault_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        # Verify vault exists (per Document Contract INV-001)
        if not self.upload.vault.vault_exists(vault_uuid):
            return ApiResponse.err_response(
                ApiError(code="VAULT_NOT_FOUND",
                         message=f"Vault {raw_vault_id} does not exist. Create a vault first.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not self.upload.vault.user_can_upload_to_vault(user_id, vault_uuid):
            return ApiResponse.err_response(
                ApiError(
                    code="VAULT_FORBIDDEN",
                    message="You do not have permission to upload to this vault.",
                    category=ErrorCategory.AUTHORIZATION,
                ),
                status=403,
            )

        # Pass validated UUID to upload service
        try:
            vault = self.upload.vault.get_vault(vault_uuid) if hasattr(
                self.upload.vault,
                "get_vault",
            ) else None
            metadata = _document_metadata_from_body(body)
            result = self.upload.upload(
                user_id=user_id,
                content=file_content,
                filename=filename,
                mime_type=mime_type,
                document_type=body.get("document_type", "INTERNAL_REGULATION"),
                title=title,
                issuing_authority=body.get("issuing_authority", ""),
                vault_id=vault_uuid,
                organization_id=(
                    UUID(body["organization_id"])
                    if body.get("organization_id")
                    else (vault.organization_id if vault is not None else new_id())
                ),
                document_number=body.get("document_number"),
                short_title=body.get("short_title"),
                description=body.get("description"),
                language=body.get("language", "vi"),
                visibility=body.get("visibility", "DEPARTMENT"),
                metadata=metadata,
            )
        except ValueError as e:
            err_msg = str(e)
            # Decode known causes into user-friendly messages
            if "Vault" in err_msg and ("does not exist" in err_msg or "not found" in err_msg.lower()):
                return ApiResponse.err_response(
                    ApiError(code="VAULT_NOT_FOUND", message=err_msg,
                             category=ErrorCategory.VALIDATION), status=400)
            if "invalid literal" in err_msg.lower() or "malformed" in err_msg.lower():
                return ApiResponse.err_response(
                    ApiError(code="INVALID_VAULT_ID", message=f"Invalid vault ID: {err_msg}",
                             category=ErrorCategory.VALIDATION), status=400)
            if "VaultResolver" in type(err_msg).__name__ or "vault" in err_msg.lower():
                return ApiResponse.err_response(
                    ApiError(code="VAULT_NOT_FOUND", message=err_msg,
                             category=ErrorCategory.VALIDATION), status=400)
            return ApiResponse.err_response(
                ApiError(code="UPLOAD_ERROR", message=f"{err_msg}",
                         category=ErrorCategory.VALIDATION), status=400)
        except Exception as e:
            import traceback
            err_trace = traceback.format_exc()
            print(f"  [upload_file] Unexpected error: {e}\n{err_trace}")
            return ApiResponse.err_response(
                ApiError(code="UPLOAD_ERROR", message="An unexpected error occurred during upload.",
                         category=ErrorCategory.INTERNAL), status=500)

        job = self.jobs.ensure_pending_job(
            "pipeline",
            str(result.document_id),
            metadata={"requested_by": user_id},
        )
        return ApiResponse.ok(data={
            "document_id": str(result.document_id),
            "job_id": job.job_id,
            "processing_status": job.status.value,
            "filename": result.filename,
            "size_bytes": result.size_bytes,
            "checksum_sha256": result.checksum_sha256,
            "status": result.status,
            "duplicate_candidates": [
                {"document_id": str(did), "version_id": str(vid)}
                for did, vid in result.duplicate_candidates
            ],
        }, status=201)

    def get_upload_status(self, doc_id: str, user_id: str) -> ApiResponse:
        """GET /v1/uploads/{jobId}"""
        job = self.jobs.get_job(doc_id)
        resolved_document_id = job.document_id if job is not None else doc_id
        try:
            did = UUID(resolved_document_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {doc_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        doc = self.upload.registry.get_document(did)
        can_read = (
            self.upload.vault.check_permission(
                doc.vault_id,
                user_id,
                Permission.READ,
            )
            if doc is not None and hasattr(self.upload.vault, "check_permission")
            else True
        )
        if doc is not None and not can_read:
            return ApiResponse.err_response(
                ApiError(
                    code="DOCUMENT_FORBIDDEN",
                    message="You do not have permission to access this upload.",
                    category=ErrorCategory.AUTHORIZATION,
                ),
                status=403,
            )
        status = self.upload.get_upload_status(did)
        if status is None:
            return ApiResponse.err_response(
                ApiError(code="DOCUMENT_NOT_FOUND", message=f"Document {doc_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        if job is None:
            jobs = self.jobs.list_jobs(
                job_type="pipeline",
                document_id=str(did),
                limit=1,
            )
            job = jobs[0] if jobs else None
        data = dict(status)
        if job is not None:
            data["job"] = {
                "job_id": job.job_id,
                "status": job.status.value,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "duration_ms": job.duration_ms,
                "error": job.error,
            }
        return ApiResponse.ok(data=data)


# ---------------------------------------------------------------------------
# Search Handler
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Answer Handler
# ---------------------------------------------------------------------------


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
        payload['as_of'] = body.get('as_of') or __import__('datetime').date.today().isoformat()
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


# ---------------------------------------------------------------------------
# Admin Handler
# ---------------------------------------------------------------------------


class AdminHandler:
    """Administrative endpoints (tasks/014-api.md #AdministrationAPIs)."""

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        upload_service: "UploadService | None" = None,
        ocr_service: "OcrService | None" = None,
        parser_service: "ParserService | None" = None,
        chunking_service: "ChunkingService | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        vector_index: "VectorIndexService | None" = None,
        pipeline: Any = None,
        vault_service: "VaultService | None" = None,
        job_monitor: "JobMonitor | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self._upload_service = upload_service or UploadService(registry=self.registry)
        self.ocr = ocr_service or OcrService(registry=self.registry)
        self.parser = parser_service or ParserService(registry=self.registry)
        self.chunking = chunking_service or ChunkingService(registry=self.registry)
        self.embedding = embedding_service or EmbeddingService(registry=self.registry)
        self.vector_index = vector_index or VectorIndexService(registry=self.registry)
        self.pipeline = pipeline
        self.vault = vault_service or VaultService(registry=self.registry)
        self.jobs = job_monitor or JobMonitor(conn=self.registry.repo.conn)

    def list_jobs(self, params: dict[str, str], user_id: str) -> ApiResponse:
        """GET /v1/jobs"""
        status = params.get("status")
        limit = int(params.get("limit", "100"))
        offset = int(params.get("offset", "0"))

        authorized = set(self.vault.authorized_vault_ids(user_id, permission=Permission.READ))
        try:
            job_status = JobStatus(status.upper()) if status else None
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_JOB_STATUS", message=f"Unknown job status: {status}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        records = self.jobs.list_jobs(status=job_status, limit=10000, offset=0)
        jobs = []
        for job in records:
            try:
                did = UUID(job.document_id)
            except ValueError:
                continue
            doc = self.registry.get_document(did)
            if doc is None or doc.vault_id not in authorized:
                continue
            processing = self.registry.get_processing(doc.id)
            jobs.append({
                "job_id": job.job_id,
                "job_type": job.job_type,
                "document_id": str(doc.id),
                "title": doc.title,
                "status": job.status.value,
                "document_status": doc.status.value,
                "processing_state": processing.value if processing else None,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "duration_ms": job.duration_ms,
                "error": job.error,
            })
        total = len(jobs)
        jobs = jobs[offset:offset + limit]

        return ApiResponse.ok(data={
            "jobs": jobs,
            "total": total,
            "limit": limit,
            "offset": offset,
        })

    def get_system_info(self, user_id: str) -> ApiResponse:
        """GET /v1/system"""
        index_stats = self.vector_index.stats() if hasattr(self.vector_index, 'stats') else {}
        authorized = set(self.vault.authorized_vault_ids(user_id, permission=Permission.READ))
        document_count = self.registry.catalog_totals(authorized)['total']
        return ApiResponse.ok(data={
            "version": __version__,
            "index": index_stats,
            "document_count": document_count,
        })

    def reindex(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/reindex"""
        return self._run_reprocessing("index", body, user_id)

    def reembed(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/reembed"""
        return self._run_reprocessing("embed", body, user_id)

    def reparse(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/reparse"""
        return self._run_reprocessing("parse", body, user_id)

    def reocr(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/reocr"""
        return self._run_reprocessing("ocr", body, user_id)

    def _run_reprocessing(self, stage: str, body: dict[str, Any], user_id: str) -> ApiResponse:
        """Run a real bounded rebuild and report persisted outcomes."""
        if self.pipeline is None:
            return ApiResponse.err_response(
                ApiError(
                    code="PROCESSING_COORDINATOR_UNAVAILABLE",
                    message="The document processing coordinator is unavailable.",
                    category=ErrorCategory.DEPENDENCY,
                    retryable=True,
                ),
                status=503,
            )

        document_id = body.get("document_id")
        if document_id:
            try:
                document_ids = [UUID(document_id)]
            except ValueError:
                return ApiResponse.err_response(
                    ApiError(
                        code="INVALID_ID",
                        message=f"Invalid document ID: {document_id}",
                        category=ErrorCategory.VALIDATION,
                    ),
                    status=400,
                )
            document = self.registry.get_document(document_ids[0])
            if document is not None and not self.vault.check_permission(
                document.vault_id,
                user_id,
                Permission.MANAGE,
            ):
                return ApiResponse.err_response(
                    ApiError(
                        code="DOCUMENT_FORBIDDEN",
                        message="You do not have permission to reprocess this document.",
                        category=ErrorCategory.AUTHORIZATION,
                    ),
                    status=403,
                )
        else:
            managed_vaults = set(self.vault.authorized_vault_ids(
                user_id,
                permission=Permission.MANAGE,
            ))
            documents, _ = self.registry.query_catalog(vault_ids=managed_vaults, limit=-1)
            document_ids = [doc.id for doc in documents]

        completed = []
        failures = []
        for did in document_ids:
            job = None
            claimed = False
            document = self.registry.get_document(did)
            if document is None:
                failures.append({"document_id": str(did), "error": "Document not found."})
                continue
            if not self.vault.check_permission(
                document.vault_id,
                user_id,
                Permission.MANAGE,
            ):
                failures.append({
                    "document_id": str(did),
                    "error": "You do not have permission to reprocess this document.",
                })
                continue
            try:
                job = self.jobs.ensure_pending_job(
                    f"reprocess-{stage}",
                    str(did),
                    metadata={"requested_by": user_id},
                )
                self.jobs.start_job(job.job_id)
                claimed = True
                count = self.pipeline.reprocess(
                    did,
                    from_stage=stage,
                    user_id=user_id,
                )
                completed.append({
                    "job_id": job.job_id,
                    "document_id": str(did),
                    "indexed_entries": count,
                    "processing_state": self.registry.get_processing(did).value,
                })
                self.jobs.complete_job(job.job_id)
            except (ValueError, KeyError) as exc:
                if claimed and job is not None:
                    current_job = self.jobs.get_job(job.job_id)
                    if current_job and current_job.status == JobStatus.RUNNING:
                        self.jobs.fail_job(job.job_id, "Reprocessing failed; review document status.")
                failures.append({
                    "document_id": str(did),
                    "error": str(exc),
                })
            except Exception:
                if claimed and job is not None:
                    current_job = self.jobs.get_job(job.job_id)
                    if current_job and current_job.status == JobStatus.RUNNING:
                        self.jobs.fail_job(job.job_id, "Reprocessing failed; review document status.")
                failures.append({
                    "document_id": str(did),
                    "error": "Processing failed; inspect document status for recovery details.",
                })

        data = {
            "stage": stage,
            "completed": completed,
            "failures": failures,
            "completed_count": len(completed),
            "failure_count": len(failures),
        }
        if failures:
            return ApiResponse.err_response(
                ApiError(
                    code="REPROCESSING_FAILED",
                    message=(
                        f"Reprocessing completed for {len(completed)} document(s) "
                        f"and failed for {len(failures)}."
                    ),
                    category=ErrorCategory.CONFLICT,
                    details=data,
                ),
                status=409,
            )
        return ApiResponse.ok(data=data)

    def process_document(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/process — run full pipeline on a single document.

        Handles recovery from stalled documents at any non-terminal state
        and re-queues FAILED documents for processing."""
        from legal_platform.modules.document_registry.processing import ProcessingState, InvalidTransition
        
        document_id = body.get("document_id")
        if not document_id:
            return ApiResponse.err_response(
                ApiError(code="MISSING_DOCUMENT_ID", message="document_id is required.",
                         category=ErrorCategory.VALIDATION), status=400)

        try:
            did = UUID(document_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid document ID: {document_id}",
                         category=ErrorCategory.VALIDATION), status=400)

        doc = self.registry.get_document(did)
        if not doc:
            return ApiResponse.err_response(
                ApiError(code="NOT_FOUND", message=f"Document {document_id} not found.",
                         category=ErrorCategory.NOT_FOUND), status=404)

        if not self.vault.check_permission(doc.vault_id, user_id, Permission.UPDATE):
            return ApiResponse.err_response(
                ApiError(
                    code="DOCUMENT_FORBIDDEN",
                    message="You do not have permission to process this document.",
                    category=ErrorCategory.AUTHORIZATION,
                ),
                status=403,
            )

        # The application runtime injects the authoritative coordinator.  Keep
        # legacy fallback code below only for isolated old handler tests.
        if self.pipeline is not None:
            job = None
            claimed = False
            try:
                job = self.jobs.ensure_pending_job(
                    "pipeline",
                    str(did),
                    metadata={"requested_by": user_id},
                )
                self.jobs.start_job(job.job_id)
                claimed = True
                count = self.pipeline.process(did, user_id=user_id)
            except ValueError as exc:
                if claimed and job is not None:
                    current_job = self.jobs.get_job(job.job_id)
                    if current_job and current_job.status == JobStatus.RUNNING:
                        self.jobs.fail_job(job.job_id, "Processing precondition failed.")
                return ApiResponse.err_response(
                    ApiError(code="PROCESSING_PRECONDITION", message=str(exc),
                             category=ErrorCategory.VALIDATION), status=409)
            except Exception:
                if claimed and job is not None:
                    current_job = self.jobs.get_job(job.job_id)
                    if current_job and current_job.status == JobStatus.RUNNING:
                        self.jobs.fail_job(job.job_id, "Processing failed; review document status.")
                return ApiResponse.err_response(
                    ApiError(code="PROCESSING_FAILED",
                             message="Document processing failed. Review its status and retry after resolving the source error.",
                             category=ErrorCategory.INTERNAL), status=500)
            self.jobs.complete_job(job.job_id)
            return ApiResponse.ok(data={
                "job_id": job.job_id,
                "document_id": document_id,
                "processing_state": self.registry.get_processing(did).value,
                "indexed_entries": count,
                "message": "Processing completed." if count else "Document is already ready.",
            })

        result_state = "unchanged"
        
        # Read current state (may change between reads due to concurrent workers)
        def get_current() -> ProcessingState:
            cs = self.registry.get_processing(did)
            return cs or ProcessingState.FAILED
        
        state = get_current()
        state_name = state.value
        
        # === READY — already indexed, nothing to do ===
        if state_name == "READY":
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": "already READY",
                "message": "Document is already indexed.",
            })
        
        # Helper: retrieve stored OCR result or re-run OCR as fallback.
        def _get_ocr_result() -> tuple["OcrResult | None", str | None]:
            """Return (ocr_result_obj, file_bytes_or_None).
            
            Tries to load stored OCR from DB first. If no stored result and storage ref exists,
            re-runs OCR directly using process_bytes (which sets state to OCR_PENDING -> RUNNING).
            """
            # 1) Try stored OCR result from DB (works for any state where OCR was already done)
            stored = self.ocr.get_results_for_document(did)
            if stored:
                return stored[0], None
            
            # 2) No stored result — fall back to re-running OCR from file
            storage_ref = self.registry.get_source_storage_ref(did)
            if not storage_ref:
                return None, None
            
            try:
                fs = self._upload_service.storage
                file_bytes = fs.retrieve(storage_ref)
                if not file_bytes or len(file_bytes) < 100:
                    return None, file_bytes
            except Exception as e:
                print(f"  [process_document] Storage retrieval error: {e}")
                return None, None
            
            # Re-run OCR via process_bytes (transitions through OCR_PENDING -> RUNNING)
            ocr_obj = self.ocr.process_bytes(did, file_bytes, user_id="system")
            if not ocr_obj:
                return None, file_bytes
            return ocr_obj, file_bytes
        
        # === Intermediate states (processing in progress elsewhere) — skip ===
        if state_name in ("OCR_RUNNING", "PARSING_PENDING", "PARSING_RUNNING"):
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": f"{state_name} (skipped -- processing in progress)",
                "message": "Document is currently being processed by another worker.",
            })
        
        # === FAILED — re-queue to OCR_PENDING ===
        if state_name == "FAILED":
            try:
                self.registry.transition_processing(did, ProcessingState.OCR_PENDING, user_id="system")
            except InvalidTransition:
                pass  # Another thread already re-queued it; just read the OCR result
            
            ocr_result_obj, file_bytes = _get_ocr_result()
            
            if not ocr_result_obj:
                try:
                    storage_ref = self.registry.get_source_storage_ref(did)
                    if storage_ref:
                        fs = self._upload_service.storage
                        stored_bytes = fs.retrieve(storage_ref)
                        if stored_bytes and len(stored_bytes) > 100:
                            ocr_result_obj = self.ocr.process_bytes(did, stored_bytes, user_id="system")
                except Exception as e:
                    print(f"  [process_document] Failed to re-run OCR from storage: {e}")
            
            if not ocr_result_obj:
                return ApiResponse.err_response(
                    ApiError(code="OCR_FAILED", message="Failed to run OCR during re-queue.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            total_chars = sum(len(p.text) for p in ocr_result_obj.pages) if hasattr(ocr_result_obj, 'pages') else 0
            
            if total_chars <= 10:
                return ApiResponse.err_response(
                    ApiError(code="NO_TEXT", message=f"OCR returned only {total_chars} chars.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            result_state = f"re-queued (from FAILED)"
            
        # === OCR_COMPLETED — use stored OCR result, skip OCR stage ===
        elif state_name == "OCR_COMPLETED":
            ocr_result_obj, file_bytes = _get_ocr_result()
            if not ocr_result_obj:
                return ApiResponse.err_response(
                    ApiError(code="NO_OCR_RESULT", message="No stored OCR result and no storage ref.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            total_chars = sum(len(p.text) for p in ocr_result_obj.pages) if hasattr(ocr_result_obj, 'pages') else 0
            if total_chars <= 10:
                return ApiResponse.err_response(
                    ApiError(code="NO_TEXT", message=f"OCR returned only {total_chars} chars.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            result_state = f"completed (from {state_name})"
        
        # === UPLOADED — run full pipeline from OCR ===
        elif state_name == "UPLOADED":
            try:
                self.registry.transition_processing(did, ProcessingState.OCR_PENDING, user_id="system")
            except InvalidTransition:
                pass  # Already transitioned by another path
            
            # Get file bytes from storage for OCR
            storage_ref = self.registry.get_source_storage_ref(did)
            if not storage_ref:
                return ApiResponse.err_response(
                    ApiError(code="NO_STORAGE_REF", message="No storage reference found.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            fs = self._upload_service.storage
            
            try:
                file_bytes = fs.retrieve(storage_ref)
                if not file_bytes or len(file_bytes) < 100:
                    return ApiResponse.err_response(
                        ApiError(code="STORAGE_ERROR", message=f"File too small for {document_id}",
                                 category=ErrorCategory.VALIDATION), status=400)
            except Exception as e:
                return ApiResponse.err_response(
                    ApiError(code="STORAGE_ERROR", message=f"Cannot retrieve file: {e}",
                             category=ErrorCategory.VALIDATION), status=400)
            
            ocr_result_obj = self.ocr.process_bytes(did, file_bytes, user_id="system")
            if not ocr_result_obj:
                return ApiResponse.err_response(
                    ApiError(code="OCR_FAILED", message="OCR returned no result.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            total_chars = sum(len(p.text) for p in ocr_result_obj.pages) if hasattr(ocr_result_obj, 'pages') else 0
            
            if total_chars <= 10:
                return ApiResponse.err_response(
                    ApiError(code="NO_TEXT", message=f"OCR returned only {total_chars} chars.",
                             category=ErrorCategory.VALIDATION), status=400)
            
            # Advance through remaining states per state machine (catch InvalidTransition for race conditions)
            try:
                self.registry.transition_processing(did, ProcessingState.OCR_COMPLETED, user_id="system")
            except InvalidTransition:
                pass
            try:
                self.registry.transition_processing(did, ProcessingState.PARSING_PENDING, user_id="system")
            except InvalidTransition:
                pass
            try:
                self.registry.transition_processing(did, ProcessingState.PARSING_RUNNING, user_id="system")
            except InvalidTransition:
                pass
            
            result_state = "indexed (from UPLOADED)"
        
        else:
            return ApiResponse.err_response(
                ApiError(code="UNEXPECTED_STATE", message=f"Document in state: {state_name}",
                         category=ErrorCategory.VALIDATION), status=400)
        
        # === Re-check state before common path (race condition guard) ===
        current = get_current()
        if current.value == "READY":
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": "already READY",
                "message": "Document is already indexed by another worker.",
            })
        
        # === Common path: parse -> chunk -> embed -> index ===
        # Parse the OCR result into a Knowledge Tree
        tree = self.parser.parse_ocr_result(ocr_result_obj, document_id=did, user_id="system")
        if not tree or len(tree.nodes) == 0:
            return ApiResponse.err_response(
                ApiError(code="PARSE_FAILED", message="Parsing returned no knowledge tree.",
                         category=ErrorCategory.VALIDATION), status=400)
        
        # Advance to READY (catch InvalidTransition for race conditions)
        try:
            self.registry.transition_processing(did, ProcessingState.READY, user_id="system")
        except InvalidTransition:
            # Another thread already advanced it; just verify parsing succeeded
            pass
        
        # Chunk
        chunks = self.chunking.chunk_document(did)
        
        # Embed
        embeddings = self.embedding.embed_collection(chunks)
        
        # Index -- use index_embeddings (the correct method on VectorIndexService)
        idx_entries = self.vector_index.index_embeddings(embeddings.embeddings)
        
        result_state = f"indexed ({len(idx_entries)} entries)"
        
        return ApiResponse.ok(data={
            "document_id": document_id,
            "processing_state": result_state,
            "message": f"Processing completed. State: {result_state}",
        })



class HealthHandler:
    """Health check endpoints (tasks/014-api.md #HealthAPIs)."""

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        *,
        storage: Any = None,
        vector_index: "VectorIndexService | None" = None,
        embedding_service: "EmbeddingService | None" = None,
        worker_alive: Any = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.storage = storage
        self.vector_index = vector_index
        self.embedding = embedding_service
        self.worker_alive = worker_alive

    def _checks(self) -> dict[str, str]:
        checks: dict[str, str] = {}
        try:
            row = self.registry.repo.conn.execute("SELECT 1").fetchone()
            checks["database"] = "healthy" if row else "unhealthy: query returned no row"
        except Exception as exc:
            checks["database"] = f"unhealthy: {type(exc).__name__}"

        if self.storage is None:
            checks["storage"] = "not_checked"
        else:
            root = getattr(self.storage, "base_path", None)
            if root is not None and Path(root).is_dir() and os.access(root, os.R_OK | os.W_OK):
                checks["storage"] = "healthy"
            else:
                checks["storage"] = "unhealthy: configured root is unavailable"

        if self.vector_index is None:
            checks["index"] = "not_checked"
        else:
            try:
                count = len(self.vector_index.entries_snapshot())
                checks["index"] = f"healthy ({count} entries)"
            except Exception as exc:
                checks["index"] = f"unhealthy: {type(exc).__name__}"

        if self.worker_alive is None:
            checks["worker"] = "not_checked"
        else:
            checks["worker"] = "healthy" if self.worker_alive() else "unhealthy: stopped"

        if self.embedding is None:
            checks["embedding"] = "not_checked"
        else:
            model = getattr(self.embedding.engine, "MODEL_NAME", None)
            checks["embedding"] = f"configured ({model})" if model else "unhealthy: no model"

        from legal_platform.modules.generation.provider import is_configured
        checks["generation"] = "configured" if is_configured() else "not_configured"
        return checks

    def health(self) -> ApiResponse:
        """GET /health — overall health check."""
        checks = self._checks()
        status = HealthStatus(
            status=("degraded" if any(v.startswith("unhealthy") for v in checks.values()) else "healthy"),
            version=__version__,
            uptime_seconds=time.time() - _START_TIME,
            checks=checks,
        )
        return ApiResponse.ok(data={
            "status": status.status,
            "version": status.version,
            "uptime_seconds": round(status.uptime_seconds, 2),
            "checks": status.checks,
        })

    def ready(self) -> ApiResponse:
        """GET /ready — readiness check."""
        checks = self._checks()
        failures = {key: value for key, value in checks.items() if value.startswith("unhealthy")}
        if failures:
            return ApiResponse.err_response(
                ApiError(
                    code="NOT_READY",
                    message="One or more required runtime components are unavailable.",
                    category=ErrorCategory.DEPENDENCY,
                    retryable=True,
                    details={"checks": failures},
                ),
                status=503,
            )
        return ApiResponse.ok(data={"status": "ready", "checks": checks})

    def live(self) -> ApiResponse:
        """GET /live — liveness check."""
        return ApiResponse.ok(data={"status": "alive"})


# ---------------------------------------------------------------------------
# Setup Handler (Task 026 — Setup & Configuration Wizard)
# ---------------------------------------------------------------------------


class SetupHandler:
    """Setup & configuration endpoints (tasks/026-setup-configuration-wizard).

    Provides the backend for the Setup Wizard Web UI:
        - GET  /v1/setup/status   — whether the app is configured / first run
        - GET  /v1/setup/config   — safe (non-secret) provider config
        - POST /v1/setup/config   — save provider config
        - POST /v1/setup/test     — test provider connectivity
        - POST /v1/setup/complete — mark setup as complete
    """

    def __init__(self, on_config_saved: Any = None) -> None:
        from legal_platform.modules.generation.provider import (
            OpenAICompatibleProvider,
            ProviderConfig,
            is_configured,
            is_first_run,
            load_config,
            mark_configured,
            save_config,
        )
        self._OpenAICompatibleProvider = OpenAICompatibleProvider
        self._ProviderConfig = ProviderConfig
        self._is_configured = is_configured
        self._is_first_run = is_first_run
        self._load_config = load_config
        self._mark_configured = mark_configured
        self._save_config = save_config
        self._on_config_saved = on_config_saved

    def status(self) -> ApiResponse:
        """GET /v1/setup/status — whether the app needs setup."""
        return ApiResponse.ok(data={
            "first_run": self._is_first_run(),
            "configured": self._is_configured(),
        })

    def is_configured(self) -> bool:
        """Expose configuration state to the router's authorization gate."""
        return self._is_configured()

    def is_first_run(self) -> bool:
        """Return whether setup has not yet been explicitly completed."""
        return self._is_first_run()

    def get_config(self) -> ApiResponse:
        """GET /v1/setup/config — safe (non-secret) provider config."""
        config = self._load_config()
        return ApiResponse.ok(data=config.to_safe_dict())

    def save_config(self, body: dict[str, Any]) -> ApiResponse:
        """POST /v1/setup/config — save provider config.

        Body: {
            "provider_type": "openai_compatible",
            "base_url": "...",
            "api_key": "...",     # optional
            "model": "...",
            "timeout_seconds": 60,
            "max_tokens": 4096,
            "temperature": 0.1,
            "reasoning_effort": "none"
        }
        """
        config = self._load_config()
        if "allow_lan" in body:
            if not isinstance(body["allow_lan"], bool):
                return AuthHandler.error("LAN access must be enabled or disabled.")
            config.allow_lan = body["allow_lan"]

        # Merge provided fields, preserving existing secrets if not re-supplied
        if "provider_type" in body:
            config.provider_type = str(body["provider_type"])
        if "base_url" in body:
            new_url = str(body['base_url']).strip().rstrip('/')
            if new_url != config.base_url.rstrip('/'):
                config.api_key = ''
            config.base_url = new_url
        if "api_key" in body:
            config.api_key = str(body["api_key"] or '').strip()
        if "model" in body:
            config.model = str(body["model"]).strip()
        if "timeout_seconds" in body:
            config.timeout_seconds = int(body["timeout_seconds"])
        if "max_tokens" in body:
            config.max_tokens = int(body["max_tokens"])
        if "temperature" in body:
            config.temperature = float(body["temperature"])
        if "reasoning_effort" in body:
            config.reasoning_effort = str(body["reasoning_effort"]).strip().lower()

        if 'embedding_model' in body:
            config.embedding_model = str(body['embedding_model']).strip()
            if not config.embedding_model or len(config.embedding_model) > 200:
                return AuthHandler.error('Enter an embedding model name.')
        # Validate required fields
        if not config.base_url:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="base_url is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not config.model:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="model is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        allowed_reasoning = {"", "none", "minimal", "low", "medium", "high"}
        if config.reasoning_effort not in allowed_reasoning:
            return ApiResponse.err_response(
                ApiError(
                    code="VALIDATION_ERROR",
                    message="reasoning_effort must be empty, none, minimal, low, medium, or high.",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        # Validate provider URL for SSRF safety
        from legal_platform.modules.generation.provider import validate_provider_url
        valid, reason = validate_provider_url(config.base_url, allow_lan=config.allow_lan)
        if not valid:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message=f"Invalid provider URL: {reason}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        if not 1 <= config.timeout_seconds <= 120 or not 256 <= config.max_tokens <= 8192 or not 0 <= config.temperature <= 1:
            return AuthHandler.error('Choose a timeout of 1–120 seconds, 256–8192 output tokens and temperature 0–1.')
        self._save_config(config)
        if self._on_config_saved is not None:
            self._on_config_saved(config)
        return ApiResponse.ok(data=config.to_safe_dict())

    def test_connection(self, body: dict[str, Any]) -> ApiResponse:
        """POST /v1/setup/test — test provider connectivity.

        Body: same shape as save_config (may be partial).
        """
        config = self._load_config()
        if "allow_lan" in body:
            if not isinstance(body["allow_lan"], bool):
                return AuthHandler.error("LAN access must be enabled or disabled.")
            config.allow_lan = body["allow_lan"]
        if "base_url" in body:
            new_url = str(body['base_url']).strip().rstrip('/')
            if new_url != config.base_url.rstrip('/'):
                config.api_key = ''
            config.base_url = new_url
        if "api_key" in body:
            config.api_key = str(body["api_key"] or '').strip()
        if "model" in body:
            config.model = str(body["model"]).strip()
        if "timeout_seconds" in body:
            config.timeout_seconds = int(body["timeout_seconds"])

        if not config.base_url:
            return ApiResponse.err_response(
                ApiError(code="VALIDATION_ERROR", message="base_url is required.",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )

        from legal_platform.modules.generation.provider import validate_provider_url
        valid, reason = validate_provider_url(config.base_url, allow_lan=config.allow_lan)
        if not valid:
            return AuthHandler.error(reason)
        config.timeout_seconds = min(15, max(1, config.timeout_seconds))
        provider = self._OpenAICompatibleProvider(config=config)
        ok, message = provider.check_connectivity()
        return ApiResponse.ok(data={
            "reachable": ok,
            "message": message or "Provider is reachable and usable.",
        })

    def complete(self) -> ApiResponse:
        """POST /v1/setup/complete — mark setup as complete."""
        self._mark_configured()
        if self._on_config_saved is not None:
            self._on_config_saved(self._load_config())
        return ApiResponse.ok(data={"message": "Setup complete.", "configured": True})

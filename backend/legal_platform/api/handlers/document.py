"""Document management handler (tasks/014-api.md #DocumentAPIs)."""
from __future__ import annotations

import base64
import hashlib
import mimetypes
from pathlib import Path
from typing import Any
from uuid import UUID

from legal_platform.accounts import AuthHandler
from legal_platform.api.handlers.common import _document_metadata_from_body
from legal_platform.api.handlers.vault import VaultHandler
from legal_platform.api.models import (
    ApiError,
    ApiResponse,
    ErrorCategory,
    PaginatedResponse,
)
from legal_platform.contracts.common import new_id
from legal_platform.contracts.document import DocumentStatus
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.parser.service import ParserService
from legal_platform.modules.vault.models import Permission
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vector_index.service import VectorIndexService


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

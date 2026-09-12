"""Upload management handler (tasks/014-api.md #UploadAPIs)."""
from __future__ import annotations

import base64
import traceback
from typing import Any
from uuid import UUID

from legal_platform.api.handlers.common import _document_metadata_from_body
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory
from legal_platform.contracts.common import new_id
from legal_platform.modules.observability.jobs import JobMonitor, JobStatus
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.modules.vault.models import Permission


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

        # Validate vault_id (required by Document Contract INV-001)
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

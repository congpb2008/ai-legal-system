"""Administrative operations handler (tasks/014-api.md #AdministrationAPIs)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from legal_platform import __version__
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory
from legal_platform.modules.chunking.service import ChunkingService
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.observability.jobs import JobMonitor, JobStatus
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.parser.service import ParserService
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.modules.vault.models import Permission
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vector_index.service import VectorIndexService


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
        """POST /v1/process — run full pipeline on a single document."""
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

        def get_current() -> ProcessingState:
            cs = self.registry.get_processing(did)
            return cs or ProcessingState.FAILED
        
        state = get_current()
        state_name = state.value
        
        if state_name == "READY":
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": "already READY",
                "message": "Document is already indexed.",
            })
        
        def _get_ocr_result() -> tuple[Any, str | None]:
            stored = self.ocr.get_results_for_document(did)
            if stored:
                return stored[0], None
            
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
            
            ocr_obj = self.ocr.process_bytes(did, file_bytes, user_id="system")
            if not ocr_obj:
                return None, file_bytes
            return ocr_obj, file_bytes
        
        if state_name in ("OCR_RUNNING", "PARSING_PENDING", "PARSING_RUNNING"):
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": f"{state_name} (skipped -- processing in progress)",
                "message": "Document is currently being processed by another worker.",
            })
        
        if state_name == "FAILED":
            try:
                self.registry.transition_processing(did, ProcessingState.OCR_PENDING, user_id="system")
            except InvalidTransition:
                pass
            
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
            
            result_state = "re-queued (from FAILED)"
            
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
        
        elif state_name == "UPLOADED":
            try:
                self.registry.transition_processing(did, ProcessingState.OCR_PENDING, user_id="system")
            except InvalidTransition:
                pass
            
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
        
        current = get_current()
        if current.value == "READY":
            return ApiResponse.ok(data={
                "document_id": document_id,
                "processing_state": "already READY",
                "message": "Document is already indexed by another worker.",
            })
        
        tree = self.parser.parse_ocr_result(ocr_result_obj, document_id=did, user_id="system")
        if not tree or len(tree.nodes) == 0:
            return ApiResponse.err_response(
                ApiError(code="PARSE_FAILED", message="Parsing returned no knowledge tree.",
                         category=ErrorCategory.VALIDATION), status=400)
        
        try:
            self.registry.transition_processing(did, ProcessingState.READY, user_id="system")
        except InvalidTransition:
            pass
        
        chunks = self.chunking.chunk_document(did)
        embeddings = self.embedding.embed_collection(chunks)
        idx_entries = self.vector_index.index_embeddings(embeddings.embeddings)
        
        result_state = f"indexed ({len(idx_entries)} entries)"
        
        return ApiResponse.ok(data={
            "document_id": document_id,
            "processing_state": result_state,
            "message": f"Processing completed. State: {result_state}",
        })

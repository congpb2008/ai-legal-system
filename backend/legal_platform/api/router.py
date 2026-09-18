"""Clean, explicit API router and dispatcher (tasks/014-api.md)."""
from __future__ import annotations

from typing import Any, Optional

from legal_platform.api.handlers import (
    AdminHandler,
    AnswerHandler,
    AuthHandler,
    DocumentHandler,
    HealthHandler,
    SearchHandler,
    SetupHandler,
    UploadHandler,
    VaultHandler,
)
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory


class ApiRouter:
    """Explicit router that maps HTTP paths and methods to domain handler methods."""

    def __init__(
        self,
        auth_handler: Optional[AuthHandler] = None,
        vault_handler: Optional[VaultHandler] = None,
        document_handler: Optional[DocumentHandler] = None,
        upload_handler: Optional[UploadHandler] = None,
        search_handler: Optional[SearchHandler] = None,
        answer_handler: Optional[AnswerHandler] = None,
        admin_handler: Optional[AdminHandler] = None,
        health_handler: Optional[HealthHandler] = None,
        setup_handler: Optional[SetupHandler] = None,
    ):
        self.auth_handler = auth_handler or AuthHandler()
        self.vault_handler = vault_handler or VaultHandler()
        self.document_handler = document_handler or DocumentHandler()
        self.upload_handler = upload_handler or UploadHandler()
        self.search_handler = search_handler or SearchHandler()
        self.answer_handler = answer_handler or AnswerHandler()
        self.admin_handler = admin_handler or AdminHandler()
        self.health_handler = health_handler or HealthHandler()
        self.setup_handler = setup_handler or SetupHandler()

    def dispatch(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        body: dict[str, Any],
        token: Optional[str],
        user_id: Optional[str] = None,
    ) -> ApiResponse:
        """Dispatch a request to the appropriate handler method."""
        # --- Health (no auth required) ---
        if path in ("/health",):
            return self.health_handler.health()
        if path in ("/ready",):
            return self.health_handler.ready()
        if path in ("/live",):
            return self.health_handler.live()

        # --- Auth (no auth required) ---
        if path == "/v1/auth/login" and method == "POST":
            return self.auth_handler.login(body)
        if path == "/v1/auth/logout" and method == "POST":
            return self.auth_handler.logout(token)
        if path == "/v1/auth/me" and method == "GET":
            return self.auth_handler.me(token)

        # --- Setup (status is public; configuration is public only on first run) ---
        if path == "/v1/setup/status" and method == "GET":
            return self.setup_handler.status()

        if path.startswith("/v1/setup/"):
            actor = user_id or self.auth_handler.resolve_user(token)
            if actor is None:
                return self.auth_handler.error("Please sign in.", 401, "NOT_AUTHENTICATED")
            if not self.auth_handler.is_admin(actor):
                return self.auth_handler.error("Only an administrator can change server settings.", 403)

        if path == "/v1/setup/config" and method == "GET":
            return self.setup_handler.get_config()
        if path == "/v1/setup/config" and method == "POST":
            return self.setup_handler.save_config(body)
        if path == "/v1/setup/test" and method == "POST":
            return self.setup_handler.test_connection(body)
        if path == "/v1/setup/complete" and method == "POST":
            return self.setup_handler.complete()

        # All remaining endpoints require authentication
        uid = user_id or self.auth_handler.resolve_user(token)
        if uid is None:
            return ApiResponse.err_response(
                ApiError(
                    code="NOT_AUTHENTICATED",
                    message="Authentication required. Provide a Bearer token.",
                    category=ErrorCategory.AUTHENTICATION,
                ),
                status=401,
            )

        # --- Vaults ---
        if path == "/v1/vaults" and method == "GET":
            return self.vault_handler.list_vaults(params, uid)
        if path == "/v1/vaults" and method == "POST":
            return self.vault_handler.create_vault(body, uid)
        if path.startswith("/v1/vaults/") and method == "GET":
            vault_id = path[len("/v1/vaults/"):]
            return self.vault_handler.get_vault(vault_id, uid)
        if path.startswith("/v1/vaults/") and method == "PATCH":
            vault_id = path[len("/v1/vaults/"):]
            return self.vault_handler.update_vault(vault_id, body, uid)
        if path.startswith("/v1/vaults/") and method == "DELETE":
            vault_id = path[len("/v1/vaults/"):]
            return self.vault_handler.delete_vault(vault_id, uid)

        # --- Documents ---
        if path == "/v1/documents/summary" and method == "GET":
            return self.document_handler.document_summary(uid)
        if path == "/v1/documents" and method == "POST":
            return self.document_handler.create_document(body, uid)
        if path == "/v1/documents" and method == "GET":
            return self.document_handler.list_documents(params, uid)
        if path.startswith("/v1/documents/") and path.endswith("/status") and method == "GET":
            doc_id = path[len("/v1/documents/"):-len("/status")]
            return self.document_handler.get_document_status(doc_id, uid)
        if path.startswith("/v1/documents/") and path.endswith("/source") and method == "GET":
            doc_id = path[len("/v1/documents/"):-len("/source")]
            return self.document_handler.get_document_source(doc_id, params, uid)
        if path.startswith("/v1/documents/") and method == "GET":
            doc_id = path[len("/v1/documents/"):]
            return self.document_handler.get_document(doc_id, uid)
        if path.startswith("/v1/documents/") and method == "PATCH":
            doc_id = path[len("/v1/documents/"):]
            return self.document_handler.update_document(doc_id, body, uid)
        if path.startswith("/v1/documents/") and method == "DELETE":
            doc_id = path[len("/v1/documents/"):]
            return self.document_handler.delete_document(doc_id, uid)

        # --- Uploads ---
        if path == "/v1/uploads" and method == "POST":
            return self.upload_handler.upload_file(body, uid)
        if path.startswith("/v1/uploads/") and method == "GET":
            doc_id = path[len("/v1/uploads/"):]
            return self.upload_handler.get_upload_status(doc_id, uid)

        # --- Search ---
        if path == "/v1/search" and method == "POST":
            return self.search_handler.search(body, uid)
        if path == "/v1/search/semantic" and method == "POST":
            return self.search_handler.search_semantic(body, uid)
        if path == "/v1/search/keyword" and method == "POST":
            return self.search_handler.search_keyword(body, uid)
        if path == "/v1/search/hybrid" and method == "POST":
            return self.search_handler.search_hybrid(body, uid)

        # --- Answers ---
        if path == "/v1/answers" and method == "POST":
            return self.answer_handler.answer(body, uid)

        # --- Admin ---
        if path == "/v1/jobs" and method == "GET":
            return self.admin_handler.list_jobs(params, uid)
        if path == "/v1/system" and method == "GET":
            if not self.auth_handler.is_admin(uid):
                return self.auth_handler.error("Administrator access required.", 403)
            return self.admin_handler.get_system_info(uid)
        if path == "/v1/reindex" and method == "POST":
            return self.admin_handler.reindex(body, uid)
        if path == "/v1/reembed" and method == "POST":
            return self.admin_handler.reembed(body, uid)
        if path == "/v1/reparse" and method == "POST":
            return self.admin_handler.reparse(body, uid)
        if path == "/v1/reocr" and method == "POST":
            return self.admin_handler.reocr(body, uid)
        if path == "/v1/process" and method == "POST":
            return self.admin_handler.process_document(body, uid)

        # --- 404 ---
        return ApiResponse.err_response(
            ApiError(
                code="NOT_FOUND",
                message=f"Unknown endpoint: {method} {path}",
                category=ErrorCategory.NOT_FOUND,
            ),
            status=404,
        )

"""Tests for the Platform API (Task 014).

Covers:
    - API response model (ApiResponse, ApiError, PaginatedResponse, HealthStatus)
    - Auth handler (login, logout, me, token resolution)
    - Vault handler (CRUD, list, archive)
    - Document handler (CRUD, status)
    - Upload handler (upload file, status)
    - Search handler (search, semantic, keyword, hybrid)
    - Answer handler (question answering)
    - Admin handler (jobs, system, reindex, reembed, reparse)
    - Health handler (health, ready, live)
    - Server routing (dispatch, 404, auth enforcement)

The authoritative source is the Platform API specification
(tasks/014-api.md).
"""

import json
import time
from uuid import UUID

import pytest

from legal_platform.api.handlers import (
    AdminHandler,
    AnswerHandler,
    AuthHandler,
    DocumentHandler,
    HealthHandler,
    SearchHandler,
    UploadHandler,
    VaultHandler,
)
from legal_platform.api.models import (
    ApiError,
    ApiResponse,
    ErrorCategory,
    HealthStatus,
    PaginatedResponse,
)
from legal_platform.api.server import PlatformAPI, create_app
from legal_platform.contracts.common import new_id
from legal_platform.contracts.retrieval import (
    Evidence,
    RetrievalMetadata,
    RetrievalResult,
    RetrievalStrategy,
    SourceAnchor,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.generation.provider import GenerationProviderError
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vault.models import VaultType
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vector_index.service import VectorIndexService


def _test_retrieval_service() -> RetrievalService:
    """Build isolated deterministic wiring; production defaults use Ollama."""
    registry = DocumentRegistry()
    embedding = EmbeddingService(
        registry=registry,
        engine=PlaceholderEmbedder(),
    )
    vector_index = VectorIndexService(registry=registry)
    return RetrievalService(
        registry=registry,
        embedding_service=embedding,
        vector_index=vector_index,
    )


def _test_search_handler() -> SearchHandler:
    retrieval = _test_retrieval_service()
    reranker = RerankerService(
        registry=retrieval.registry,
        retrieval_service=retrieval,
    )
    return SearchHandler(
        retrieval_service=retrieval,
        reranker_service=reranker,
    )


def _test_answer_handler() -> AnswerHandler:
    retrieval = _test_retrieval_service()
    reranker = RerankerService(
        registry=retrieval.registry,
        retrieval_service=retrieval,
    )
    generation = GenerationService(
        registry=retrieval.registry,
        reranker_service=reranker,
    )
    return AnswerHandler(generation_service=generation)


def _test_document_handler():
    registry = DocumentRegistry()
    vault_service = VaultService(registry=registry, conn=registry.repo.conn)
    registry.vault = vault_service
    vector_index = VectorIndexService(registry=registry)
    handler = DocumentHandler(
        registry=registry,
        vault_service=vault_service,
        vector_index=vector_index,
    )
    vault = vault_service.create_vault(
        name="Document Handler Test",
        vault_type=VaultType.PERSONAL,
        owner="admin",
    )
    return handler, vault.id


# ======================================================================
# 1. API Response Models
# ======================================================================


class TestApiResponse:
    """API response model (tasks/014-api.md #ResponseFormat)."""

    def test_ok_response(self):
        resp = ApiResponse.ok(data={"key": "value"})
        assert resp.success is True
        assert resp.data == {"key": "value"}
        assert resp.err is None
        assert resp.status == 200

    def test_ok_response_with_metadata(self):
        resp = ApiResponse.ok(data="test", metadata={"version": "1.0"})
        assert resp.metadata == {"version": "1.0"}

    def test_error_response(self):
        err = ApiError(code="TEST_ERROR", message="Something went wrong.",
                       category=ErrorCategory.VALIDATION)
        resp = ApiResponse.err_response(err, status=400)
        assert resp.success is False
        assert resp.err is not None
        assert resp.err.code == "TEST_ERROR"
        assert resp.status == 400

    def test_error_category_maps_to_status(self):
        err = ApiError(code="NOT_FOUND", message="Not found.",
                       category=ErrorCategory.NOT_FOUND)
        resp = ApiResponse.err_response(err)
        assert resp.status == 404

    def test_to_dict_success(self):
        resp = ApiResponse.ok(data={"msg": "hello"})
        d = resp.to_dict()
        assert d["success"] is True
        assert d["data"] == {"msg": "hello"}
        assert "error" not in d

    def test_to_dict_error(self):
        err = ApiError(code="ERR", message="fail", category=ErrorCategory.VALIDATION)
        resp = ApiResponse.err_response(err, status=400)
        d = resp.to_dict()
        assert d["success"] is False
        assert d["error"]["code"] == "ERR"
        assert d["error"]["category"] == "VALIDATION"


class TestPaginatedResponse:
    """Paginated response model."""

    def test_pagination(self):
        pr = PaginatedResponse(items=[1, 2, 3], total=10, limit=3, offset=0)
        assert pr.has_more is True
        assert len(pr.items) == 3

    def test_no_more_pages(self):
        pr = PaginatedResponse(items=[1, 2], total=2, limit=100, offset=0)
        assert pr.has_more is False


class TestHealthStatus:
    """Health status model."""

    def test_defaults(self):
        hs = HealthStatus()
        assert hs.status == "healthy"
        assert hs.version == "0.1.0"


# ======================================================================
# 2. Auth Handler
# ======================================================================


class TestAuthHandler:
    """Authentication endpoints (tasks/014-api.md #AuthenticationAPIs)."""

    def test_login_success(self):
        handler = AuthHandler()
        resp = handler.login({"user_id": "admin", "password": "secret"})
        assert resp.success is True
        assert resp.data["user_id"] == "admin"
        assert "token" in resp.data

    def test_login_missing_credentials(self):
        handler = AuthHandler()
        resp = handler.login({})
        assert resp.success is False
        assert resp.status == 400

    def test_login_empty_credentials(self):
        handler = AuthHandler()
        resp = handler.login({"user_id": "", "password": ""})
        assert resp.success is False
        assert resp.status == 400

    def test_logout(self):
        handler = AuthHandler()
        login_resp = handler.login({"user_id": "admin", "password": "x"})
        token = login_resp.data["token"]
        resp = handler.logout(token)
        assert resp.success is True

    def test_me_authenticated(self):
        handler = AuthHandler()
        login_resp = handler.login({"user_id": "admin", "password": "x"})
        token = login_resp.data["token"]
        resp = handler.me(token)
        assert resp.success is True
        assert resp.data["user_id"] == "admin"

    def test_me_unauthenticated(self):
        handler = AuthHandler()
        resp = handler.me("invalid-token")
        assert resp.success is False
        assert resp.status == 401

    def test_me_no_token(self):
        handler = AuthHandler()
        resp = handler.me(None)
        assert resp.success is False
        assert resp.status == 401

    def test_resolve_user(self):
        handler = AuthHandler()
        login_resp = handler.login({"user_id": "admin", "password": "x"})
        token = login_resp.data["token"]
        assert handler.resolve_user(token) == "admin"
        assert handler.resolve_user("bad") is None
        assert handler.resolve_user(None) is None


# ======================================================================
# 3. Vault Handler
# ======================================================================


class TestVaultHandler:
    """Vault management endpoints (tasks/014-api.md #VaultAPIs)."""

    def test_list_vaults(self):
        handler = VaultHandler()
        # Create a vault first
        handler.vault.create_vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        resp = handler.list_vaults({}, "admin")
        assert resp.success is True
        assert len(resp.data.items) >= 1

    def test_create_vault(self):
        handler = VaultHandler()
        resp = handler.create_vault({"name": "New Vault"}, "admin")
        assert resp.success is True
        assert resp.status == 201
        assert resp.data["name"] == "New Vault"

    def test_create_vault_missing_name(self):
        handler = VaultHandler()
        resp = handler.create_vault({}, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_get_vault(self):
        handler = VaultHandler()
        vault = handler.vault.create_vault(name="Get Test", vault_type=VaultType.COMMON, owner="admin")
        resp = handler.get_vault(str(vault.id), "admin")
        assert resp.success is True
        assert resp.data["name"] == "Get Test"

    def test_get_vault_not_found(self):
        handler = VaultHandler()
        resp = handler.get_vault(str(new_id()), "admin")
        assert resp.success is False
        assert resp.status == 404

    def test_get_vault_invalid_id(self):
        handler = VaultHandler()
        resp = handler.get_vault("not-a-uuid", "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_update_vault(self):
        handler = VaultHandler()
        vault = handler.vault.create_vault(name="Original", vault_type=VaultType.COMMON, owner="admin")
        resp = handler.update_vault(str(vault.id), {"name": "Updated"}, "admin")
        assert resp.success is True
        assert resp.data["name"] == "Updated"

    def test_delete_vault(self):
        handler = VaultHandler()
        vault = handler.vault.create_vault(name="To Delete", vault_type=VaultType.COMMON, owner="admin")
        resp = handler.delete_vault(str(vault.id), "admin")
        assert resp.success is True
        # Verify archived
        fetched = handler.vault.get_vault(vault.id)
        assert fetched.status.value == "ARCHIVED"


# ======================================================================
# 4. Document Handler
# ======================================================================


class TestDocumentHandler:
    """Document management endpoints (tasks/014-api.md #DocumentAPIs)."""

    def test_create_document(self):
        handler, vault_id = _test_document_handler()
        resp = handler.create_document({
            "title": "Test Document",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT Dept",
            "vault_id": str(vault_id),
        }, "admin")
        assert resp.success is True
        assert resp.status == 201
        assert resp.data["title"] == "Test Document"

    def test_document_tags_are_created_serialized_and_mutable(self):
        handler, vault_id = _test_document_handler()
        created = handler.create_document({
            "title": "Tagged Document",
            "document_type": "CIRCULAR",
            "issuing_authority": "Bộ Tài chính",
            "vault_id": str(vault_id),
            "description": "Mô tả nguồn.",
            "tags": ["Thông tư", "Đấu thầu", "thông tư"],
            "issue_date": "2025-08-04",
        }, "admin")

        assert created.success is True
        assert created.data["tags"] == ["Thông tư", "Đấu thầu"]
        assert created.data["issue_date"].startswith("2025-08-04")

        updated = handler.update_document(created.data["id"], {
            "title": "Tagged Document Updated",
            "description": "Mô tả đã cập nhật.",
            "tags": "Biểu mẫu, E-HSMT, Biểu mẫu",
        }, "admin")
        assert updated.success is True
        assert updated.data["title"] == "Tagged Document Updated"
        assert updated.data["description"] == "Mô tả đã cập nhật."
        assert updated.data["tags"] == ["Biểu mẫu", "E-HSMT"]

    def test_document_tag_validation_rejects_non_string_values(self):
        handler, vault_id = _test_document_handler()
        response = handler.create_document({
            "title": "Bad tags",
            "document_type": "CIRCULAR",
            "issuing_authority": "Authority",
            "vault_id": str(vault_id),
            "tags": ["valid", 42],
        }, "admin")
        assert response.success is False
        assert response.status == 400

    def test_create_document_missing_title(self):
        handler, _ = _test_document_handler()
        resp = handler.create_document({}, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_list_documents(self):
        handler, vault_id = _test_document_handler()
        created = handler.create_document({
            "title": "Listed document",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "Test authority",
            "vault_id": str(vault_id),
        }, "admin")
        assert created.success is True
        resp = handler.list_documents({}, "admin")
        assert resp.success is True
        assert isinstance(resp.data.items, list)
        assert "processing_state" in resp.data.items[0]

    def test_get_document(self):
        handler, vault_id = _test_document_handler()
        create_resp = handler.create_document({
            "title": "Get Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        doc_id = create_resp.data["id"]
        resp = handler.get_document(doc_id, "admin")
        assert resp.success is True
        assert resp.data["title"] == "Get Test"

    def test_get_document_not_found(self):
        handler, _ = _test_document_handler()
        resp = handler.get_document(str(new_id()), "admin")
        assert resp.success is False
        assert resp.status == 404

    def test_get_document_status(self):
        handler, vault_id = _test_document_handler()
        create_resp = handler.create_document({
            "title": "Status Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        doc_id = create_resp.data["id"]
        resp = handler.get_document_status(doc_id, "admin")
        assert resp.success is True
        assert resp.data["document_id"] == doc_id

    def test_delete_document(self):
        handler, vault_id = _test_document_handler()
        create_resp = handler.create_document({
            "title": "Delete Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        doc_id = create_resp.data["id"]
        resp = handler.delete_document(doc_id, "admin")
        assert resp.success is True


# ======================================================================
# 5. Upload Handler
# ======================================================================


class TestUploadHandler:
    """Upload endpoints (tasks/014-api.md #UploadAPIs)."""

    def test_upload_file(self):
        handler = UploadHandler()
        import base64
        content = base64.b64encode(b"%PDF-1.4 test content").decode()
        vault_id = new_id()
        resp = handler.upload_file({
            "filename": "test.pdf",
            "content_base64": content,
            "title": "Upload Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        assert resp.success is True
        assert resp.status == 201
        assert "document_id" in resp.data

    def test_upload_persists_tags_issue_date_and_original_filename(self):
        handler = UploadHandler()
        import base64
        content = base64.b64encode(b"%PDF-1.4 tagged content").decode()
        response = handler.upload_file({
            "filename": "source-law.pdf",
            "content_base64": content,
            "title": "Tagged upload",
            "document_type": "LAW",
            "issuing_authority": "Quốc hội",
            "vault_id": str(new_id()),
            "tags": '["Luật", "Đấu thầu"]',
            "issue_date": "2025-06-25",
            "description": "Nguồn luật thử nghiệm.",
        }, "admin")
        assert response.success is True
        doc = handler.upload.registry.get_document(UUID(response.data["document_id"]))
        assert doc.metadata.tags == ["Luật", "Đấu thầu"]
        assert doc.metadata.issue_date.date().isoformat() == "2025-06-25"
        source = handler.upload.registry.get_source_metadata(doc.id)
        assert source["filename"] == "source-law.pdf"

    def test_upload_missing_fields(self):
        handler = UploadHandler()
        resp = handler.upload_file({}, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_upload_invalid_base64(self):
        handler = UploadHandler()
        vault_id = new_id()
        resp = handler.upload_file({
            "filename": "test.pdf",
            "content_base64": "not-valid-base64!!!",
            "title": "Bad Upload",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_get_upload_status(self):
        handler = UploadHandler()
        import base64
        content = base64.b64encode(b"%PDF-1.4 test").decode()
        vault_id = new_id()
        upload_resp = handler.upload_file({
            "filename": "test.pdf",
            "content_base64": content,
            "title": "Status Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(vault_id),
        }, "admin")
        doc_id = upload_resp.data["document_id"]
        resp = handler.get_upload_status(doc_id, "admin")
        assert resp.success is True

    def test_get_upload_status_not_found(self):
        handler = UploadHandler()
        resp = handler.get_upload_status(str(new_id()), "admin")
        assert resp.success is False
        assert resp.status == 404

    def test_folder_upload_prefers_explicit_basename_over_relative_transport_name(self):
        import io
        import zipfile

        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types/>")
            archive.writestr(
                "word/document.xml",
                "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                "<w:body><w:p><w:r><w:t>Mau ho so dau thau hop le</w:t></w:r></w:p></w:body>"
                "</w:document>",
            )
        handler = UploadHandler()
        vault_id = new_id()
        response = handler.upload_file({
            "file": package.getvalue(),
            "__filename__": "temporary-folder/4. Mau so 4A.docx",
            "filename": "4. Mau so 4A.docx",
            "title": "Mau so 4A",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "Bo Tai chinh",
            "vault_id": str(vault_id),
        }, "admin")

        assert response.success is True, response.err.message if response.err else response
        source = handler.upload.registry.get_source_metadata(
            UUID(response.data["document_id"])
        )
        assert source["filename"] == "4. Mau so 4A.docx"


# ======================================================================
# 6. Search Handler
# ======================================================================


class TestSearchHandler:
    """Search endpoints (tasks/014-api.md #SearchAPIs)."""

    def test_search(self):
        handler = _test_search_handler()
        resp = handler.search({"query": "mua sắm máy chủ"}, "admin")
        assert resp.success is True
        assert "query_id" in resp.data

    def test_search_missing_query(self):
        handler = SearchHandler()
        resp = handler.search({}, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_search_semantic(self):
        handler = _test_search_handler()
        resp = handler.search_semantic({"query": "test query"}, "admin")
        assert resp.success is True

    def test_search_keyword(self):
        handler = _test_search_handler()
        resp = handler.search_keyword({"query": "test query"}, "admin")
        assert resp.success is True

    def test_search_hybrid(self):
        handler = _test_search_handler()
        resp = handler.search_hybrid({"query": "test query"}, "admin")
        assert resp.success is True

    def test_search_evidence_includes_document_identity_and_source_link(self):
        handler = _test_search_handler()
        document = handler.retrieval.registry.register_document(
            user_id="admin",
            document_type="LAW",
            title="Luật số 90/2025/QH15",
            issuing_authority="Quốc hội",
            vault_id=new_id(),
            organization_id=new_id(),
        )
        node_id = new_id()
        result = RetrievalResult(
            query_id=new_id(),
            strategy=RetrievalStrategy.HYBRID,
            query="hiệu lực luật 90",
            evidence=[Evidence(
                id=new_id(),
                knowledge_node_id=node_id,
                document_id=document.id,
                document_version_id=document.versions[0].version_id,
                score=0.91,
                rank=1,
                text="Luật này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2025.",
                source_anchor=SourceAnchor(
                    page=12,
                    canonical_reference="Điều 8",
                ),
            )],
            metadata=RetrievalMetadata(
                strategy="HYBRID",
                candidate_count=1,
                returned_count=1,
            ),
        )

        item = handler._result_to_dict(result)["evidence"][0]

        assert item["document_title"] == "Luật số 90/2025/QH15"
        assert item["source_url"] == (
            f"/api/v1/documents/{document.id}/source"
            f"?node_id={node_id}&page=12"
        )


# ======================================================================
# 7. Answer Handler
# ======================================================================


class TestAnswerHandler:
    """Question answering endpoints (tasks/014-api.md #QuestionAPIs)."""

    def test_answer(self):
        handler = _test_answer_handler()
        resp = handler.answer({"query": "mua sắm máy chủ"}, "admin")
        assert resp.success is True
        assert "request_id" in resp.data
        assert "response" in resp.data

    def test_answer_missing_query(self):
        handler = AnswerHandler()
        resp = handler.answer({}, "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_answer_handler_uses_hybrid_retrieval(self):
        handler = _test_answer_handler()
        calls = []
        original = handler.generation.reranker_service.search_and_rerank

        def capture(*args, **kwargs):
            calls.append(kwargs)
            return original(*args, **kwargs)

        handler.generation.reranker_service.search_and_rerank = capture
        response = handler.answer({"query": "mua sắm máy chủ"}, "admin")

        assert response.success is True
        assert calls[0]["strategy"] == "HYBRID"

    def test_answer_reports_configured_provider_failure(self, monkeypatch):
        handler = _test_answer_handler()

        def fail(*args, **kwargs):
            raise GenerationProviderError("provider unavailable")

        monkeypatch.setattr(handler.generation, "generate", fail)
        resp = handler.answer({"query": "mua sắm máy chủ"}, "admin")

        assert resp.success is False
        assert resp.status == 503
        assert resp.err.code == "GENERATION_UNAVAILABLE"
        assert resp.err.retryable is True


# ======================================================================
# 8. Admin Handler
# ======================================================================


class TestAdminHandler:
    """Administrative endpoints (tasks/014-api.md #AdministrationAPIs)."""

    def test_list_jobs(self):
        handler = AdminHandler()
        resp = handler.list_jobs({}, "admin")
        assert resp.success is True
        assert "jobs" in resp.data

    def test_get_system_info(self):
        handler = AdminHandler()
        resp = handler.get_system_info("admin")
        assert resp.success is True
        assert "version" in resp.data

    def test_reindex_all(self):
        handler = AdminHandler()
        resp = handler.reindex({}, "admin")
        assert resp.success is False
        assert resp.status == 503

    def test_reindex_document(self):
        handler = AdminHandler()
        resp = handler.reindex({"document_id": str(new_id())}, "admin")
        assert resp.success is False
        assert resp.status == 503

    def test_reembed(self):
        handler = AdminHandler()
        resp = handler.reembed({}, "admin")
        assert resp.success is False
        assert resp.status == 503

    def test_reparse(self):
        handler = AdminHandler()
        resp = handler.reparse({}, "admin")
        assert resp.success is False
        assert resp.status == 503


# ======================================================================
# 9. Health Handler
# ======================================================================


class TestHealthHandler:
    """Health check endpoints (tasks/014-api.md #HealthAPIs)."""

    def test_health(self):
        handler = HealthHandler()
        resp = handler.health()
        assert resp.success is True
        assert resp.data["status"] == "healthy"
        assert "uptime_seconds" in resp.data
        assert resp.data["checks"]["database"] == "healthy"

    def test_ready(self):
        handler = HealthHandler()
        resp = handler.ready()
        assert resp.success is True
        assert resp.data["status"] == "ready"

    def test_live(self):
        handler = HealthHandler()
        resp = handler.live()
        assert resp.success is True
        assert resp.data["status"] == "alive"


# ======================================================================
# 10. Server Routing
# ======================================================================


class TestServerRouting:
    """Server routing and dispatch (tasks/014-api.md)."""

    def test_create_app(self):
        """create_app should return a handler class."""
        handler_cls = create_app()
        assert handler_cls is not None

    def test_platform_api_create(self):
        """PlatformAPI should initialize."""
        api = PlatformAPI(host="127.0.0.1", port=0)
        assert api.host == "127.0.0.1"
        assert api.port == 0


# ======================================================================
# 11. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_api_error_defaults(self):
        err = ApiError(code="TEST", message="test")
        assert err.category == ErrorCategory.INTERNAL
        assert err.retryable is False
        assert err.details is None

    def test_api_response_ok_defaults(self):
        resp = ApiResponse.ok()
        assert resp.success is True
        assert resp.status == 200
        assert resp.data is None
        assert resp.warnings == []

    def test_health_status_custom(self):
        hs = HealthStatus(status="degraded", checks={"db": "down"})
        assert hs.status == "degraded"
        assert hs.checks["db"] == "down"

    def test_paginated_response_empty(self):
        pr = PaginatedResponse(items=[], total=0, limit=100, offset=0)
        assert pr.has_more is False
        assert pr.items == []

    def test_auth_handler_token_uniqueness(self):
        """Each login should generate a unique token."""
        handler = AuthHandler()
        r1 = handler.login({"user_id": "user1", "password": "x"})
        r2 = handler.login({"user_id": "user2", "password": "x"})
        assert r1.data["token"] != r2.data["token"]

    def test_vault_handler_list_with_filters(self):
        handler = VaultHandler()
        handler.vault.create_vault(name="Common", vault_type=VaultType.COMMON, owner="admin")
        handler.vault.create_vault(name="Personal", vault_type=VaultType.PERSONAL, owner="user-1")

        resp = handler.list_vaults({"type": "COMMON"}, "admin")
        assert resp.success is True
        for item in resp.data.items:
            assert item["vault_type"] == "COMMON"

    def test_document_handler_invalid_id(self):
        handler, _ = _test_document_handler()
        resp = handler.get_document("not-a-uuid", "admin")
        assert resp.success is False
        assert resp.status == 400

    def test_upload_handler_invalid_vault(self):
        handler = UploadHandler()
        import base64
        content = base64.b64encode(b"%PDF-1.4 test content").decode()
        resp = handler.upload_file({
            "filename": "test.pdf",
            "content_base64": content,
            "title": "Test",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "IT",
            "vault_id": str(new_id()),
        }, "admin")
        # With AllowAllVaults stub, any vault_id is accepted
        assert resp.success is True


class TestAuthorizationIsolation:
    """Personal vaults are enforced before document access and retrieval."""

    def test_two_users_cannot_cross_personal_vault_boundaries(self):
        registry = DocumentRegistry()
        vaults = VaultService(registry=registry, conn=registry.repo.conn)
        registry.vault = vaults
        index = VectorIndexService(registry=registry)
        documents = DocumentHandler(
            registry=registry,
            vault_service=vaults,
            vector_index=index,
        )
        embedding = EmbeddingService(
            registry=registry,
            engine=PlaceholderEmbedder(),
        )
        retrieval = RetrievalService(
            registry=registry,
            embedding_service=embedding,
            vector_index=index,
        )
        search = SearchHandler(
            retrieval_service=retrieval,
            vault_service=vaults,
        )
        vault_a = vaults.create_vault(
            name="A private",
            vault_type=VaultType.PERSONAL,
            owner="user-a",
        )
        vaults.create_vault(
            name="B private",
            vault_type=VaultType.PERSONAL,
            owner="user-b",
        )
        created = documents.create_document({
            "title": "A private legal source",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "A",
            "vault_id": str(vault_a.id),
        }, "user-a")
        document_id = created.data["id"]

        assert documents.list_documents({}, "user-b").data.total == 0
        assert documents.get_document(document_id, "user-b").status == 403
        assert search.search_keyword({
            "query": "private",
            "vault_id": str(vault_a.id),
        }, "user-b").status == 403
        assert documents.create_document({
            "title": "Cross-vault write",
            "document_type": "INTERNAL_REGULATION",
            "issuing_authority": "B",
            "vault_id": str(vault_a.id),
        }, "user-b").status == 403
        assert documents.get_document(document_id, "user-a").status == 200


# ======================================================================
# Regression: PaginatedResponse serialization (Task 023)
# ======================================================================


class TestPaginatedResponseSerialization:
    """PaginatedResponse must serialize correctly via ApiResponse.to_dict()."""

    def test_paginated_response_to_dict(self):
        from legal_platform.api.models import PaginatedResponse
        pr = PaginatedResponse(items=[{"id": "1"}, {"id": "2"}], total=2, limit=10, offset=0)
        d = pr.to_dict()
        assert isinstance(d, dict)
        assert d["items"] == [{"id": "1"}, {"id": "2"}]
        assert d["total"] == 2
        assert d["has_more"] is False

    def test_api_response_serializes_paginated_response(self):
        from legal_platform.api.models import ApiResponse, PaginatedResponse
        pr = PaginatedResponse(items=[{"id": "1"}], total=1, limit=10, offset=0)
        resp = ApiResponse.ok(data=pr)
        d = resp.to_dict()
        assert isinstance(d["data"], dict)
        assert d["data"]["items"] == [{"id": "1"}]
        assert d["data"]["total"] == 1
        assert d["data"]["has_more"] is False

    def test_api_response_serializes_regular_dict(self):
        from legal_platform.api.models import ApiResponse
        resp = ApiResponse.ok(data={"key": "value"})
        d = resp.to_dict()
        assert d["data"] == {"key": "value"}


# ======================================================================
# Regression: Handler state sharing (Task 023)
# ======================================================================


class TestHandlerStateSharing:
    """Handlers created via PlatformAPI must share the same DocumentRegistry."""

    def test_upload_and_list_share_state(self):
        from legal_platform.api.server import PlatformAPI
        import socket, threading, time, json, urllib.request

        # Start server on ephemeral port
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        api = PlatformAPI(host="127.0.0.1", port=port)
        t = threading.Thread(target=api.start, daemon=True)
        t.start()

        try:
            # Wait for server
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/health", timeout=1
                    ) as resp:
                        json.loads(resp.read().decode("utf-8"))
                        break
                except Exception:
                    time.sleep(0.1)

            base = f"http://127.0.0.1:{port}"

            # Login
            req = urllib.request.Request(
                f"{base}/api/v1/auth/login",
                data=json.dumps({"user_id": "admin", "password": "admin"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                token = json.loads(resp.read().decode("utf-8"))["data"]["token"]

            # Create vault
            req = urllib.request.Request(
                f"{base}/api/v1/vaults",
                data=json.dumps({"name": "Shared State Test", "vault_type": "DEPARTMENT"}).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req) as resp:
                vault_id = json.loads(resp.read().decode("utf-8"))["data"]["id"]

            # Upload a document
            content_b64 = "JVBERi0xLg=="  # minimal PDF-like base64
            req = urllib.request.Request(
                f"{base}/api/v1/uploads",
                data=json.dumps({
                    "filename": "test.pdf",
                    "content_base64": content_b64,
                    "title": "Shared State Doc",
                    "document_type": "INTERNAL_REGULATION",
                    "issuing_authority": "QA",
                    "vault_id": vault_id,
                }).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req) as resp:
                upload_data = json.loads(resp.read().decode("utf-8"))
                assert upload_data["success"] is True
                doc_id = upload_data["data"]["document_id"]

            # List documents — must include the uploaded doc
            req = urllib.request.Request(
                f"{base}/api/v1/documents",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(req) as resp:
                list_data = json.loads(resp.read().decode("utf-8"))
                assert list_data["success"] is True
                items = list_data["data"]["items"]
                assert len(items) >= 1, (
                    f"Expected at least 1 document, got {len(items)}. "
                    "Handlers may not share the same DocumentRegistry."
                )
                found = any(item["id"] == doc_id for item in items)
                assert found, f"Uploaded document {doc_id} not found in document list"

        finally:
            api.stop()
            t.join(timeout=2)

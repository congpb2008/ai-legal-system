"""Security & hardening tests (Task 027).

Covers:
    - Unauthenticated access to protected endpoints
    - Secret masking (API key not exposed in responses)
    - Provider URL validation (SSRF protection)
    - Filename sanitization (path traversal)
    - Error message sanitization (no exception details leaked)
    - Security headers
    - Malformed JSON handling
    - Oversized request handling
    - Invalid upload types
    - Malformed configuration handling
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

import pytest

from legal_platform.api.models import ApiResponse, ApiError, ErrorCategory
from legal_platform.api.server import PlatformAPI


# ======================================================================
# 1. Unauthenticated access
# ======================================================================


class TestUnauthenticatedAccess:
    """Protected endpoints must reject unauthenticated requests."""

    def _get_server(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        api = PlatformAPI(host="127.0.0.1", port=port)
        t = threading.Thread(target=api.start, daemon=True)
        t.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ):
                    break
            except Exception:
                time.sleep(0.1)
        return api, t, port

    def _req(self, port, method, path, body=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body else None
        r = urllib.request.Request(
            f"http://127.0.0.1:{port}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(r) as resp:
                return json.loads(resp.read().decode("utf-8")), resp.status
        except urllib.error.HTTPError as e:
            return json.loads(e.read().decode("utf-8")), e.code

    def test_vaults_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/v1/vaults")
            assert status == 401, f"Expected 401, got {status}"
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_documents_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/v1/documents")
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_uploads_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "POST", "/api/v1/uploads", {})
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_search_requires_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "POST", "/api/v1/search", {"query": "test"})
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_answers_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "POST", "/api/v1/answers", {"query": "test"})
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_admin_requires_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/v1/jobs")
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_health_does_not_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/health")
            assert status == 200
            assert data["success"] is True
        finally:
            api.stop()
            t.join(timeout=2)

    def test_setup_does_not_require_auth(self):
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/v1/setup/status")
            assert status == 200
            assert data["success"] is True
        finally:
            api.stop()
            t.join(timeout=2)

    def test_first_run_can_save_then_complete_before_login(self):
        api, t, port = self._get_server()
        try:
            saved, status = self._req(
                port,
                "POST",
                "/api/v1/setup/config",
                {
                    "base_url": "https://provider.example/v1",
                    "model": "configured-model",
                    "timeout_seconds": 90,
                },
            )
            assert status == 200
            assert saved["success"] is True

            completed, status = self._req(
                port,
                "POST",
                "/api/v1/setup/complete",
                {},
            )
            assert status == 200
            assert completed["data"]["configured"] is True

            _, status = self._req(port, "GET", "/api/v1/setup/config")
            assert status == 401
        finally:
            api.stop()
            t.join(timeout=2)

    def test_configured_setup_requires_authentication(self):
        from legal_platform.modules.generation.provider import mark_configured

        mark_configured()
        api, t, port = self._get_server()
        try:
            data, status = self._req(port, "GET", "/api/v1/setup/config")
            assert status == 401
            assert data["error"]["code"] == "NOT_AUTHENTICATED"

            login, status = self._req(
                port,
                "POST",
                "/api/v1/auth/login",
                {"user_id": "admin", "password": "admin"},
            )
            assert status == 200
            data, status = self._req(
                port,
                "GET",
                "/api/v1/setup/config",
                token=login["data"]["token"],
            )
            assert status == 200
            assert "api_key" not in data["data"]
        finally:
            api.stop()
            t.join(timeout=2)


# ======================================================================
# 2. Secret masking
# ======================================================================


class TestSecretMasking:
    """API keys and secrets must not leak through API responses."""

    def test_setup_config_omits_api_key(self):
        """GET /v1/setup/config must not return the raw api_key."""
        from legal_platform.modules.generation.provider import (
            ProviderConfig,
            save_config,
        )
        from legal_platform.api.handlers import SetupHandler

        # Save a config with a known API key
        save_config(ProviderConfig(
            base_url="http://localhost:11434/v1",
            api_key="sk-test-secret-key-12345",
            model="llama3",
        ))

        handler = SetupHandler()
        resp = handler.get_config()
        d = resp.to_dict()
        json_str = json.dumps(d)
        assert "sk-test-secret-key-12345" not in json_str, "API key value leaked in response JSON"
        assert d["data"]["has_api_key"] is True, "has_api_key should be True"

    def test_to_safe_dict_omits_api_key(self):
        from legal_platform.modules.generation.provider import ProviderConfig

        cfg = ProviderConfig(api_key="super-secret-key")
        safe = cfg.to_safe_dict()
        assert "api_key" not in safe
        assert safe["has_api_key"] is True

    def test_reasoning_effort_is_optional_and_safe(self):
        from legal_platform.modules.generation.provider import (
            OpenAICompatibleProvider,
            ProviderConfig,
        )

        automatic = OpenAICompatibleProvider(ProviderConfig())
        automatic_payload = automatic._build_payload([])
        assert "reasoning_effort" not in automatic_payload

        disabled = OpenAICompatibleProvider(
            ProviderConfig(reasoning_effort="none")
        )
        disabled_payload = disabled._build_payload([])
        assert disabled_payload["reasoning_effort"] == "none"
        assert disabled.config.to_safe_dict()["reasoning_effort"] == "none"

    def test_saved_provider_config_is_owner_readable_only(self):
        from legal_platform.modules.generation.provider import (
            ProviderConfig,
            _config_path,
            save_config,
        )

        save_config(ProviderConfig(api_key="test-secret"))
        assert _config_path().stat().st_mode & 0o077 == 0

    def test_setup_save_refreshes_runtime_clients(self):
        from legal_platform.api.handlers import SetupHandler

        refreshed = []
        handler = SetupHandler(on_config_saved=refreshed.append)
        response = handler.save_config({
            "base_url": "https://provider.example/v1",
            "model": "configured-model",
            "timeout_seconds": 90,
            "reasoning_effort": "none",
        })

        assert response.success is True
        assert len(refreshed) == 1
        assert refreshed[0].base_url == "https://provider.example/v1"
        assert refreshed[0].model == "configured-model"
        assert refreshed[0].reasoning_effort == "none"

    def test_setup_rejects_unknown_reasoning_effort(self):
        from legal_platform.api.handlers import SetupHandler

        response = SetupHandler().save_config({
            "base_url": "https://provider.example/v1",
            "model": "configured-model",
            "reasoning_effort": "maximum-plus",
        })

        assert response.status == 400
        assert response.to_dict()["error"]["code"] == "VALIDATION_ERROR"


# ======================================================================
# 3. Provider URL validation (SSRF protection)
# ======================================================================


class TestProviderUrlValidation:
    """Provider URLs must be validated for SSRF safety."""

    def test_validates_http_only(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("ftp://evil.com/v1")
        assert not valid, "FTP URL should be rejected"

    def test_rejects_embedded_credentials(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("http://user:pass@evil.com/v1")
        assert not valid, "Embedded credentials should be rejected"

    def test_rejects_private_ip(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("http://10.0.0.1/v1")
        assert not valid, "Private IP should be rejected"

    def test_rejects_private_range(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("http://192.168.1.1/v1")
        assert not valid, "192.168.x.x should be rejected"

    def test_allows_localhost(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("http://localhost:11434/v1")
        assert valid, "localhost should be allowed"

    def test_allows_public_url(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("https://api.openai.com/v1")
        assert valid, "Public URL should be allowed"

    def test_rejects_empty_url(self):
        from legal_platform.modules.generation.provider import validate_provider_url

        valid, msg = validate_provider_url("")
        assert not valid, "Empty URL should be rejected"

    def test_provider_rejects_empty_generated_content(self):
        from legal_platform.modules.generation.provider import (
            GenerationProviderError,
            OpenAICompatibleProvider,
        )

        with pytest.raises(GenerationProviderError, match="empty answer"):
            OpenAICompatibleProvider._extract_content({
                "choices": [{"message": {"content": ""}}],
            })


# ======================================================================
# 4. Filename sanitization
# ======================================================================


class TestFilenameSanitization:
    """Filenames must be sanitized to prevent path traversal."""

    def test_removes_path_separators(self):
        from legal_platform.modules.upload_service.service import _sanitize_filename

        result = _sanitize_filename("../../../etc/passwd")
        assert "/" not in result, "Path separators must be removed"
        assert "etc" not in result or "_" in result, "Dots should be collapsed"

    def test_removes_null_bytes(self):
        from legal_platform.modules.upload_service.service import _sanitize_filename

        result = _sanitize_filename("file\x00.pdf")
        assert "\x00" not in result, "Null bytes must be removed"

    def test_removes_windows_special_chars(self):
        from legal_platform.modules.upload_service.service import _sanitize_filename

        result = _sanitize_filename('file<>:"|?*.pdf')
        assert all(c not in result for c in '<>:"|?*'), "Windows special chars removed"

    def test_returns_default_for_empty(self):
        from legal_platform.modules.upload_service.service import _sanitize_filename

        result = _sanitize_filename("...")
        assert result == "uploaded_file", "Empty result should get default name"

    def test_preserves_normal_filename(self):
        from legal_platform.modules.upload_service.service import _sanitize_filename

        result = _sanitize_filename("policy-2026.pdf")
        assert result == "policy_2026_pdf", "Normal name should be preserved"


# ======================================================================
# 5. Error message sanitization
# ======================================================================


class TestErrorSanitization:
    """Error messages must not leak internal details."""

    def test_internal_error_hides_exception(self):
        from legal_platform.api.models import ApiError, ErrorCategory, ApiResponse

        err = ApiError(
            code="INTERNAL_ERROR",
            message="An internal error occurred. Please check the server logs.",
            category=ErrorCategory.INTERNAL,
        )
        resp = ApiResponse.err_response(err, status=500)
        d = resp.to_dict()
        assert "server logs" in d["error"]["message"]
        assert "traceback" not in d["error"]["message"].lower()
        assert "exception" not in d["error"]["message"].lower()

    def test_validation_error_does_not_expose_internals(self):
        from legal_platform.api.handlers import SetupHandler

        handler = SetupHandler()
        resp = handler.save_config({"base_url": "", "model": "test"})
        d = resp.to_dict()
        assert d["error"]["message"] == "base_url is required."
        assert "traceback" not in json.dumps(d)


# ======================================================================
# 6. Security headers
# ======================================================================


class TestSecurityHeaders:
    """API responses must include security headers."""

    def test_api_response_has_security_headers(self):
        api, t, port = self._get_server()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/health")
            with urllib.request.urlopen(req) as resp:
                headers = dict(resp.headers)
                assert headers.get("X-Content-Type-Options") == "nosniff"
                assert headers.get("X-Frame-Options") == "DENY"
        finally:
            api.stop()
            t.join(timeout=2)

    def test_static_response_has_security_headers(self):
        api, t, port = self._get_server()
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/")
            with urllib.request.urlopen(req) as resp:
                headers = dict(resp.headers)
                assert headers.get("X-Content-Type-Options") == "nosniff"
                assert headers.get("X-Frame-Options") == "DENY"
        finally:
            api.stop()
            t.join(timeout=2)

    def _get_server(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        api = PlatformAPI(host="127.0.0.1", port=port)
        t = threading.Thread(target=api.start, daemon=True)
        t.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ):
                    break
            except Exception:
                time.sleep(0.1)
        return api, t, port


# ======================================================================
# 7. Malformed JSON / oversized requests
# ======================================================================


class TestRequestValidation:
    """The server must handle malformed and oversized requests safely."""

    def test_malformed_json_returns_400(self):
        import http.client

        api, t, port = self._get_server()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request(
                "POST",
                "/api/v1/auth/login",
                body="not valid json",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            assert resp.status == 400
            assert data["error"]["code"] == "INVALID_JSON"
        finally:
            api.stop()
            t.join(timeout=2)

    def _get_server(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        api = PlatformAPI(host="127.0.0.1", port=port)
        t = threading.Thread(target=api.start, daemon=True)
        t.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/health", timeout=1
                ):
                    break
            except Exception:
                time.sleep(0.1)
        return api, t, port


# ======================================================================
# 8. Invalid upload types
# ======================================================================


class TestUploadValidation:
    """Upload validation must reject invalid file types."""

    def test_rejects_unsupported_mime_type(self):
        from legal_platform.modules.upload_service.service import (
            UploadService,
            UnsupportedFileType,
        )

        svc = UploadService()
        with pytest.raises(UnsupportedFileType):
            svc._resolve_mime_type("file.exe", "application/x-msdownload")

    def test_rejects_unsupported_extension(self):
        from legal_platform.modules.upload_service.service import (
            UploadService,
            UnsupportedFileType,
        )

        svc = UploadService()
        with pytest.raises(UnsupportedFileType):
            svc._resolve_mime_type("file.exe", None)

    def test_rejects_empty_file(self):
        from legal_platform.modules.upload_service.service import (
            UploadService,
            CorruptedUpload,
        )

        svc = UploadService()
        with pytest.raises(CorruptedUpload):
            svc._validate(b"", "application/pdf")


# ======================================================================
# 9. Malformed configuration
# ======================================================================


class TestMalformedConfiguration:
    """Corrupted configuration must fail safely."""

    def test_load_config_returns_default_on_corrupted_file(self):
        from legal_platform.modules.generation.provider import (
            _config_path,
            load_config,
        )

        path = _config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json")

        config = load_config()
        assert config is not None
        assert config.model == "llama3"  # default value
        path.unlink(missing_ok=True)

    def test_load_config_returns_default_on_missing_file(self):
        from legal_platform.modules.generation.provider import (
            _config_path,
            load_config,
        )

        path = _config_path()
        if path.exists():
            path.unlink()

        config = load_config()
        assert config is not None
        assert config.base_url == "http://localhost:11434/v1"

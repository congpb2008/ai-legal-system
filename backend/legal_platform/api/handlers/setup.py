"""Setup & configuration handler (tasks/026-setup-configuration-wizard)."""
from __future__ import annotations

from typing import Any

from legal_platform.accounts import AuthHandler
from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory


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
        """POST /v1/setup/config — save provider config."""
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
        """POST /v1/setup/test — test provider connectivity."""
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

"""AI Provider abstraction for the Generation Service.

Defines the replaceable provider interface that the Generation Service
depends on, and provides an OpenAI-compatible remote implementation.

Architecture principle (ADR-002):
    Generation consumes only the Retrieval Contract. The LLM is a replaceable
    component — replacement must not require Contract changes.
"""

from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import dataclass, field
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any, Optional, Protocol
from urllib import request as urllib_request
from urllib.error import URLError
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


# Loopback / link-local / private networks that must never be reached by
# outbound provider requests (SSRF protection). The default Ollama endpoint
# (localhost) is allowed only when explicitly configured via the setup wizard.
_PRIVATE_NETWORKS = [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",   # link-local
    "::1/128",
    "fc00::/7",          # unique local
    "fe80::/10",         # link-local IPv6
]


def _is_loopback_or_private(host: str) -> bool:
    """Return True if a host resolves to a loopback/private address."""
    try:
        addr = ip_address(host)
    except ValueError:
        return False
    return any(addr in ip_network(net) for net in _PRIVATE_NETWORKS)


def validate_provider_url(url: str) -> tuple[bool, str]:
    """Validate a provider base URL for safety (SSRF mitigation).

    Returns (True, "") if the URL is acceptable, or (False, reason) otherwise.

    Rules:
        - Must be http/https.
        - Must not contain a username/password (credential leakage).
        - Must not resolve to a loopback/private address unless the host is
          explicitly localhost (the default Ollama endpoint is permitted).
    """
    if not url:
        return False, "URL is required."
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "Invalid URL."
    if parsed.scheme not in ("http", "https"):
        return False, "Provider URL must use http or https."
    if parsed.username or parsed.password:
        return False, "Provider URL must not contain embedded credentials."
    if not parsed.hostname:
        return False, "Provider URL must include a host."
    # Allow explicit localhost (Ollama default); block other loopback/private hosts
    host = parsed.hostname.lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        return True, ""
    if _is_loopback_or_private(host):
        return False, "Provider URL must not point to a private/loopback address."
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except OSError:
        addresses = set()
    for address in addresses:
        if _is_loopback_or_private(address):
            return False, "Provider hostname resolves to a private/loopback address."
    return True, ""


@dataclass
class ProviderConfig:
    """Configuration for an AI provider.

    Stores the provider endpoint, authentication, and model selection.
    Secret values (api_key) are never serialized in normal status responses.
    """

    provider_type: str = "openai_compatible"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = ""
    model: str = "llama3"
    timeout_seconds: int = 60
    max_tokens: int = 4096
    temperature: float = 0.1
    reasoning_effort: str = ""

    def to_safe_dict(self) -> dict[str, Any]:
        """Return a dict suitable for status/UI display — no secrets."""
        return {
            "provider_type": self.provider_type,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            "has_api_key": bool(self.api_key),
        }


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


class GenerationProviderError(RuntimeError):
    """Raised when the provider fails to generate a response."""


class GenerationProvider(Protocol):
    """A replaceable AI provider for the Generation Service.

    The provider receives a system prompt, retrieved evidence, and the user's
    question, and returns a generated text response.
    """

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_text: str,
        question: str,
    ) -> str:
        """Generate a response from the provider.

        Args:
            system_prompt: The system-level instruction (from system-prompt.md).
            evidence_text: Concatenated retrieved evidence text.
            question: The user's original question.

        Returns:
            The generated text response.

        Raises:
            GenerationProviderError: if generation fails.
        """
        ...

    def check_connectivity(self) -> tuple[bool, str]:
        """Test whether the provider is reachable and usable.

        Returns:
            (True, "") on success, or (False, error_message) on failure.
        """
        ...


# ---------------------------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider:
    """Provider implementation for OpenAI-compatible APIs.

    Works with any endpoint that implements the OpenAI Chat Completions API
    format, including:
        - OpenAI API
        - Azure OpenAI
        - Ollama (localhost:11434/v1)
        - LocalAI
        - vLLM
        - FPT Cloud AI (if OpenAI-compatible)
        - Any self-hosted model serving an OpenAI-compatible endpoint

    API credentials are read from the config and never hardcoded.
    """

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self.config = config or ProviderConfig()

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        *,
        system_prompt: str,
        evidence_text: str,
        question: str,
    ) -> str:
        """Generate a response via the OpenAI Chat Completions API."""
        messages = self._build_messages(system_prompt, evidence_text, question)
        payload = self._build_payload(messages)
        data = self._post(payload)
        return self._extract_content(data)

    def _build_messages(
        self,
        system_prompt: str,
        evidence_text: str,
        question: str,
    ) -> list[dict[str, str]]:
        """Build the messages array for the Chat Completions API."""
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Dưới đây là các bằng chứng từ tài liệu pháp lý:\n\n"
                    f"{evidence_text}\n\n"
                    "Câu hỏi:\n"
                    f"{question}\n\n"
                    "Trả lời dựa trên các bằng chứng trên. "
                    "Nếu bằng chứng không đủ, hãy nói rõ."
                ),
            },
        ]

    def _build_payload(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Build the request payload for the Chat Completions API."""
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,
        }
        # Reasoning models can otherwise spend the entire visible completion
        # budget on hidden reasoning and return no answer.  Keep this optional
        # because not every OpenAI-compatible provider supports the field.
        if self.config.reasoning_effort:
            payload["reasoning_effort"] = self.config.reasoning_effort
        return payload

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a POST request to the provider's chat completions endpoint."""
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        # Validate the URL for SSRF safety before making the request
        valid, reason = validate_provider_url(self.config.base_url)
        if not valid:
            raise GenerationProviderError(f"Invalid provider URL: {reason}")

        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib_request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except URLError as e:
            raise GenerationProviderError(
                f"Provider connection failed: {e.reason}"
            ) from e
        except json.JSONDecodeError as e:
            raise GenerationProviderError(
                f"Provider returned invalid JSON: {e}"
            ) from e
        except TimeoutError as e:
            raise GenerationProviderError(
                f"Provider timed out after {self.config.timeout_seconds}s"
            ) from e

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        """Extract the generated text from the API response."""
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise GenerationProviderError(
                f"Unexpected provider response format: {e}"
            ) from e
        if not isinstance(content, str) or not content.strip():
            raise GenerationProviderError(
                "Provider returned an empty answer. Increase the generation "
                "token budget or verify the configured model."
            )
        return content.strip()

    # ------------------------------------------------------------------
    # Connectivity check
    # ------------------------------------------------------------------

    def check_connectivity(self) -> tuple[bool, str]:
        """Check whether the provider is reachable by listing models."""
        # Validate the URL for SSRF safety before making the request
        valid, reason = validate_provider_url(self.config.base_url)
        if not valid:
            return False, f"Invalid provider URL: {reason}"

        url = f"{self.config.base_url.rstrip('/')}/models"
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            req = urllib_request.Request(url, headers=headers)
            with urllib_request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except URLError as e:
            return False, f"Connection failed: {e.reason}"
        except json.JSONDecodeError:
            return False, "Provider returned invalid JSON"
        except TimeoutError:
            return False, f"Connection timed out after {self.config.timeout_seconds}s"
        except Exception as e:
            return False, f"Connection error: {e}"

        # Verify the configured model is available
        models = data.get("data", [])
        model_ids = [m.get("id", "") for m in models]
        if self.config.model not in model_ids:
            available = ", ".join(model_ids[:10])
            return False, (
                f"Model '{self.config.model}' not found. "
                f"Available models: {available}"
            )

        return True, ""


# ---------------------------------------------------------------------------
# Configuration persistence
# ---------------------------------------------------------------------------


def _data_dir() -> Path:
    """Return the same durable data root used by the production server."""
    configured = os.environ.get("LEGAL_PLATFORM_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    project_root = Path(__file__).resolve().parents[4]
    return (project_root / "storage").resolve()


def _config_path() -> Path:
    """Return the provider config path inside the durable application root."""
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "provider_config.json"


def load_config() -> ProviderConfig:
    """Load the provider configuration from disk, falling back to environment."""
    path = _config_path()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, TypeError, KeyError):
            data = {}

    # Environment variables supply defaults when not explicitly saved in JSON
    env_base = os.environ.get("LEGAL_PLATFORM_GENERATION_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
    if env_base and "base_url" not in data:
        base = env_base.strip().rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        data["base_url"] = base

    env_key = os.environ.get("LEGAL_PLATFORM_GENERATION_API_KEY") or os.environ.get("OLLAMA_API_KEY")
    if env_key is not None and "api_key" not in data:
        data["api_key"] = env_key.strip()

    env_model = os.environ.get("LEGAL_PLATFORM_GENERATION_MODEL") or os.environ.get("GENERATION_MODEL")
    if env_model and "model" not in data:
        data["model"] = env_model.strip()

    env_timeout = os.environ.get("LEGAL_PLATFORM_GENERATION_TIMEOUT")
    if env_timeout and "timeout_seconds" not in data:
        try:
            data["timeout_seconds"] = int(env_timeout)
        except ValueError:
            pass

    env_reasoning = os.environ.get("LEGAL_PLATFORM_GENERATION_REASONING_EFFORT")
    if env_reasoning and "reasoning_effort" not in data:
        data["reasoning_effort"] = env_reasoning.strip().lower()

    return ProviderConfig(**data) if data else ProviderConfig()


def save_config(config: ProviderConfig) -> None:
    """Save the provider configuration to disk."""
    path = _config_path()
    path.write_text(json.dumps({
        "provider_type": config.provider_type,
        "base_url": config.base_url,
        "api_key": config.api_key,
        "model": config.model,
        "timeout_seconds": config.timeout_seconds,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "reasoning_effort": config.reasoning_effort,
    }, indent=2))
    path.chmod(0o600)


def is_configured() -> bool:
    """Check whether the application has been configured with a provider."""
    # Check the sentinel file first (set by mark_configured / setup complete)
    data_dir = _data_dir()
    if (data_dir / ".configured").exists():
        return True
    path = _config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            # Consider configured if base_url is non-empty and not the default
            return bool(data.get("base_url")) and data.get("base_url") != "http://localhost:11434/v1"
        except (json.JSONDecodeError, TypeError):
            pass
    # Also check if configured via environment variables
    env_base = os.environ.get("LEGAL_PLATFORM_GENERATION_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")
    if env_base and env_base.strip() not in ("", "http://localhost:11434", "http://localhost:11434/v1"):
        return True
    return False


def mark_configured() -> None:
    """Mark the application as configured (creates a sentinel file)."""
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    sentinel = data_dir / ".configured"
    sentinel.touch()
    sentinel.chmod(0o600)


def is_first_run() -> bool:
    """Check whether this is the first run (no configuration exists)."""
    data_dir = _data_dir()
    return not (data_dir / ".configured").exists()

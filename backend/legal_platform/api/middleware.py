"""WSGI security, rate limiting, and request body parsing middleware."""
from __future__ import annotations

import io
import json
import os
import threading
import time
from collections import deque
from email.parser import BytesParser
from email.policy import default
from ipaddress import ip_address, ip_network
from typing import Any, Optional
from urllib.parse import urlsplit


class SecurityHeaders:
    """Standard security response headers for the web boundary."""

    @staticmethod
    def headers() -> list[tuple[str, str]]:
        return [
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Referrer-Policy", "no-referrer"),
            ("Permissions-Policy", "camera=(), microphone=(), geolocation=()"),
            (
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'none'; form-action 'self'",
            ),
        ]


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_keys: int = 10000, cleanup_age_seconds: float = 3600.0):
        self._rates: dict[Any, deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys
        self._cleanup_age = cleanup_age_seconds

    def is_limited(self, key: Any, count: int, period: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._rates) > self._max_keys:
                self._rates = {
                    k: v for k, v in self._rates.items() if v and v[-1] > now - self._cleanup_age
                }
                if len(self._rates) > self._max_keys:
                    return True
            queue = self._rates.setdefault(key, deque())
            while queue and queue[0] < now - period:
                queue.popleft()
            if len(queue) >= count:
                return True
            queue.append(now)
            return False


class OriginValidator:
    """Origin, host, and proxy validation for secure LAN/hosted deployments."""

    def __init__(self, public_origin: str = "", trusted_proxies: Optional[list[Any]] = None):
        self.public_origin = public_origin.strip().rstrip("/")
        self.public_host = ""
        if self.public_origin:
            origin = urlsplit(self.public_origin)
            if (
                origin.scheme != "https"
                or not origin.hostname
                or origin.username
                or origin.password
                or origin.path
                or origin.query
                or origin.fragment
            ):
                raise ValueError(
                    "LEGAL_PLATFORM_PUBLIC_ORIGIN must be an HTTPS origin, "
                    "such as https://library.example.com, without a path or credentials."
                )
            origin.port
            self.public_origin = "https://" + origin.netloc.lower()
            self.public_host = origin.netloc.lower()

        self.trusted_proxies = trusted_proxies or []

    @classmethod
    def from_environ(cls) -> "OriginValidator":
        public_origin = os.environ.get("LEGAL_PLATFORM_PUBLIC_ORIGIN", "")
        trusted_proxies_str = os.environ.get("LEGAL_PLATFORM_TRUSTED_PROXIES", "")
        trusted = [
            ip_network(v.strip(), strict=False)
            for v in trusted_proxies_str.split(",")
            if v.strip()
        ]
        return cls(public_origin=public_origin, trusted_proxies=trusted)

    def apply_forwarded_peer(self, env: dict[str, Any]) -> None:
        """Trust forwarding only from explicitly configured network peers."""
        try:
            peer = ip_address(env.get("REMOTE_ADDR", ""))
            if any(peer in network for network in self.trusted_proxies):
                forwarded = env.get("HTTP_X_FORWARDED_FOR", "").strip()
                env["REMOTE_ADDR"] = str(ip_address(forwarded))
        except ValueError:
            pass

    def is_misdirected(self, host: str, api_path: str) -> bool:
        if not self.public_origin:
            return False
        if api_path in ("/health", "/ready", "/live"):
            return False
        return host.lower() != self.public_host


class BodyReader:
    """Safe bounded request body streaming and multipart/JSON parser."""

    @staticmethod
    def read_body(env: dict[str, Any], path: str) -> dict[str, Any]:
        size = int(env.get("CONTENT_LENGTH") or 0)
        maximum = 35 * 1024 * 1024 if path == "/v1/uploads" else 128 * 1024
        if size < 0 or size > maximum:
            remaining = size if 0 < size <= 40 * 1024 * 1024 else 0
            while remaining:
                chunk = env["wsgi.input"].read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise OverflowError("The file is too large. Upload files of at most 25 MB.")

        raw = env["wsgi.input"].read(size)
        content_type = env.get("CONTENT_TYPE", "")
        if content_type.startswith("multipart/form-data") and path == "/v1/uploads":
            message = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw
            )
            result: dict[str, Any] = {}
            for part in message.iter_parts():
                name = part.get_param("name", header="content-disposition")
                value = part.get_payload(decode=True) or b""
                if part.get_filename():
                    if len(value) > 25 * 1024 * 1024:
                        raise OverflowError("Upload files of at most 25 MB.")
                    result["file"] = value
                    result["__filename__"] = part.get_filename()
                    result["mime_type"] = part.get_content_type()
                elif name and len(value) < 16000:
                    result[name] = value.decode("utf-8")
            return result

        if raw and not content_type.startswith("application/json"):
            raise ValueError("Use JSON or a file upload.")
        body = json.loads(raw) if raw else {}
        if not isinstance(body, dict):
            raise ValueError("JSON object required")
        return body

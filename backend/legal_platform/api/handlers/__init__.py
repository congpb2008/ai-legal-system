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
    - SetupHandler:    Configuration and wizard endpoints
"""
from __future__ import annotations

from legal_platform.accounts import AuthHandler
from legal_platform.api.handlers.common import _START_TIME, _document_metadata_from_body
from legal_platform.api.handlers.vault import VaultHandler
from legal_platform.api.handlers.document import DocumentHandler
from legal_platform.api.handlers.upload import UploadHandler
from legal_platform.api.handlers.search import SearchHandler
from legal_platform.api.handlers.answer import AnswerHandler
from legal_platform.api.handlers.admin import AdminHandler
from legal_platform.api.handlers.health import HealthHandler
from legal_platform.api.handlers.setup import SetupHandler

__all__ = [
    "AuthHandler",
    "VaultHandler",
    "DocumentHandler",
    "UploadHandler",
    "SearchHandler",
    "AnswerHandler",
    "AdminHandler",
    "HealthHandler",
    "SetupHandler",
    "_START_TIME",
    "_document_metadata_from_body",
]

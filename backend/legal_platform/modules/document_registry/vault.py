"""Vault resolver protocol — the seam between Registry and Vault Service.

The Registry needs to know whether a vault exists and whether a user can upload to it.
Per architecture.md dependency rules, lower layers never depend on higher layers; the
Registry (Ingestion layer) defines a ``VaultResolver`` Protocol that Task 013 (Vault
Service, Presentation layer) will implement. The Registry never calls Vault internals.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class VaultResolver(Protocol):
    """Validates vault existence and user authorization.

    The Registry calls this before registering a document. The concrete implementation
    is provided by Task 013 (Vault Service). For now, a simple ``AllowAllVaults`` stub
    accepts every vault ID, which is sufficient for the MVP document pipeline.
    """

    def vault_exists(self, vault_id: UUID) -> bool:
        """True if the vault is known to the platform."""
        ...

    def user_can_upload_to_vault(self, user_id: str, vault_id: UUID) -> bool:
        """True if the user is authorized to upload into the given vault."""
        ...


class AllowAllVaults:
    """Stub that accepts every vault ID and every user.

    Replaced by a real VaultResolver from Task 013.
    """

    def vault_exists(self, vault_id: UUID) -> bool:
        return True

    def user_can_upload_to_vault(self, user_id: str, vault_id: UUID) -> bool:
        return True
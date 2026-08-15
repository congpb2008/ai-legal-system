"""VaultServiceResolver — bridges the Vault Service into the DocumentRegistry.

The Registry (Ingestion layer) defines a ``VaultResolver`` Protocol that the
Vault Service (Presentation layer) implements. This resolver replaces the
``AllowAllVaults`` stub used during earlier tasks.

Per architecture.md dependency rules:
    - Lower layers never depend on higher layers.
    - The Registry defines the protocol; the Vault Service implements it.
    - The Registry calls the protocol; it never calls Vault internals.
"""

from __future__ import annotations

from uuid import UUID

from legal_platform.modules.vault.models import Permission
from legal_platform.modules.vault.service import VaultService


class VaultServiceResolver:
    """Concrete ``VaultResolver`` backed by the Vault Service.

    Replaces ``AllowAllVaults`` in the Document Registry when the Vault
    Service is available.
    """

    def __init__(self, vault_service: "VaultService | None" = None):
        self._vault_service = vault_service or VaultService()

    def vault_exists(self, vault_id: UUID) -> bool:
        """True if the vault is known to the platform."""
        return self._vault_service.vault_exists(vault_id)

    def user_can_upload_to_vault(self, user_id: str, vault_id: UUID) -> bool:
        """True if the user is authorized to upload into the given vault."""
        return self._vault_service.check_permission(
            vault_id, user_id, Permission.UPLOAD
        )
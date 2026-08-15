"""Vault Service (tasks/013-vault-service.md, module Vault).

The Vault Service manages logical knowledge boundaries, document ownership and
access control. A Vault represents an isolated knowledge domain.

The Vault Service is the primary authorization layer for document access.

Per the spec:
    - Creates, updates, archives, and manages Vaults
    - Assigns documents to vaults
    - Assigns users to vaults with roles
    - Resolves permissions
    - Provides vault metadata

The Vault Service does NOT:
    - Store documents
    - Perform retrieval
    - Generate embeddings
    - Generate answers
"""

from legal_platform.modules.vault.models import (
    Vault,
    VaultType,
    VaultStatus,
    VaultMember,
    VaultRole,
    Permission,
)
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vault.resolver import VaultServiceResolver

__all__ = [
    "Vault",
    "VaultType",
    "VaultStatus",
    "VaultMember",
    "VaultRole",
    "Permission",
    "VaultService",
    "VaultServiceResolver",
]
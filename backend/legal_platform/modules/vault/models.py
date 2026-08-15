"""Vault domain models (tasks/013-vault-service.md).

Defines the Vault entity, its types, statuses, membership, and the permission
model. These are the Vault Service's own domain concepts (not part of the
Document Contract, though they relate to it).

Per tasks/013-vault-service.md:
    - Vault Types: Common, Department, Project, Personal
    - Vault Metadata: Vault ID, Name, Type, Owner, Description, Status,
      Creation Time, Last Updated, Document Count, Member Count,
      Retention Policy
    - Permission Model: Read, Upload, Update, Delete, Share, Manage
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from legal_platform.contracts.common import new_id, now_utc


class VaultType(str, Enum):
    """Type of a Vault (tasks/013 #VaultTypes).

    - COMMON: shared knowledge (laws, regulations, national standards, circulars).
    - DEPARTMENT: department-specific knowledge (IT, HR, Finance, Procurement, Compliance).
    - PROJECT: project-specific documents (access may expire with project lifecycle).
    - PERSONAL: user-owned documents (only owner or delegates).
    """

    COMMON = "COMMON"
    DEPARTMENT = "DEPARTMENT"
    PROJECT = "PROJECT"
    PERSONAL = "PERSONAL"


class VaultStatus(str, Enum):
    """Lifecycle status of a Vault (tasks/013 #Lifecycle).

    - ACTIVE: vault is usable.
    - ARCHIVED: vault is archived (read-only / historical).
    """

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class VaultRole(str, Enum):
    """Role of a user within a Vault.

    Roles grant progressively broader permissions:
        - VIEWER: read access.
        - CONTRIBUTOR: read + upload + update.
        - MANAGER: contributor + delete + share + manage.
        - OWNER: full control (including member management).
    """

    VIEWER = "VIEWER"
    CONTRIBUTOR = "CONTRIBUTOR"
    MANAGER = "MANAGER"
    OWNER = "OWNER"


class Permission(str, Enum):
    """Permission kinds (tasks/013 #PermissionModel).

    - READ: view documents and their content.
    - UPLOAD: add new documents to the vault.
    - UPDATE: modify document metadata.
    - DELETE: remove documents (subject to retention policy).
    - SHARE: share documents / invite members.
    - MANAGE: administer the vault (membership, settings).
    """

    READ = "READ"
    UPLOAD = "UPLOAD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    SHARE = "SHARE"
    MANAGE = "MANAGE"


# Role -> granted permissions
_ROLE_PERMISSIONS: dict[VaultRole, frozenset[Permission]] = {
    VaultRole.VIEWER: frozenset({Permission.READ}),
    VaultRole.CONTRIBUTOR: frozenset(
        {Permission.READ, Permission.UPLOAD, Permission.UPDATE}
    ),
    VaultRole.MANAGER: frozenset(
        {
            Permission.READ,
            Permission.UPLOAD,
            Permission.UPDATE,
            Permission.DELETE,
            Permission.SHARE,
            Permission.MANAGE,
        }
    ),
    VaultRole.OWNER: frozenset(
        {
            Permission.READ,
            Permission.UPLOAD,
            Permission.UPDATE,
            Permission.DELETE,
            Permission.SHARE,
            Permission.MANAGE,
        }
    ),
}


def role_permissions(role: VaultRole) -> frozenset[Permission]:
    """Return the set of permissions granted by a role."""
    return _ROLE_PERMISSIONS[role]


class VaultMember(BaseModel):
    """A user's membership in a Vault.

    Fields:
        user_id: the platform user identifier.
        role: the role granting permissions within the vault.
        joined_at: when the membership was created.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: VaultRole = VaultRole.VIEWER
    joined_at: datetime = Field(default_factory=now_utc)


class Vault(BaseModel):
    """A Vault — an isolated knowledge domain.

    Per tasks/013 #VaultMetadata, each Vault contains:
        Vault ID, Vault Name, Vault Type, Owner, Description, Status,
        Creation Time, Last Updated, Document Count, Member Count,
        Retention Policy.

    The Vault is the primary authorization boundary. Every Document belongs
    to exactly one primary Vault (document-contract.md INV-001).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID = Field(default_factory=new_id)
    name: str = Field(min_length=1, max_length=256)
    vault_type: VaultType = VaultType.COMMON
    owner: str  # user_id of the vault owner
    description: Optional[str] = Field(default=None, max_length=1024)
    status: VaultStatus = VaultStatus.ACTIVE
    organization_id: UUID = Field(default_factory=new_id)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    # Counts are maintained by the Vault Service (denormalized for metadata).
    document_count: int = Field(default=0, ge=0)
    member_count: int = Field(default=0, ge=0)

    # Retention policy (free-form; e.g. "keep forever", "archive after 5 years").
    retention_policy: Optional[str] = None

    # Members of the vault (user_id -> role). The owner is implicitly a member
    # with OWNER role.
    members: dict[str, VaultMember] = Field(default_factory=dict)

    def touch(self, *, now: datetime | None = None) -> None:
        """Mark the vault as updated."""
        self.updated_at = now or now_utc()

    def has_member(self, user_id: str) -> bool:
        """True if the user is a member of the vault."""
        return user_id in self.members or user_id == self.owner

    def member_role(self, user_id: str) -> Optional[VaultRole]:
        """Return the user's role in the vault, or None if not a member."""
        if user_id == self.owner:
            return VaultRole.OWNER
        member = self.members.get(user_id)
        return member.role if member else None

    def has_permission(self, user_id: str, permission: Permission) -> bool:
        """True if the user has the given permission in this vault.

        The owner always has all permissions. Otherwise, the user's role
        determines the granted permission set.
        """
        if self.status != VaultStatus.ACTIVE:
            return False
        role = self.member_role(user_id)
        if role is None:
            return False
        return permission in role_permissions(role)

    def authorize(self, user_id: str, permission: Permission) -> bool:
        """Alias for ``has_permission`` (permission check before retrieval)."""
        return self.has_permission(user_id, permission)
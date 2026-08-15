"""Vault Service (tasks/013-vault-service.md).

The Vault Service manages logical knowledge boundaries, document ownership and
access control. It is the primary authorization layer for document access.

Per the spec:
    - Create Vaults
    - Update Vaults
    - Archive Vaults
    - Assign documents
    - Assign users
    - Resolve permissions
    - Provide vault metadata

The Vault Service does NOT:
    - Store documents
    - Perform retrieval
    - Generate embeddings
    - Generate answers
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import new_id, now_utc, utc_iso
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.vault.models import (
    Vault,
    VaultMember,
    VaultRole,
    VaultStatus,
    VaultType,
    Permission,
    role_permissions,
)
from legal_platform.storage.db import in_memory
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_VAULT_SCHEMA = """
CREATE TABLE IF NOT EXISTS vault (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    vault_type          TEXT NOT NULL,
    owner               TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'ACTIVE',
    organization_id     TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    document_count      INTEGER NOT NULL DEFAULT 0,
    member_count        INTEGER NOT NULL DEFAULT 0,
    retention_policy    TEXT,
    members_json        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_vault_type    ON vault(vault_type);
CREATE INDEX IF NOT EXISTS idx_vault_status  ON vault(status);
CREATE INDEX IF NOT EXISTS idx_vault_owner   ON vault(owner);

-- Tracks which documents belong to which vault (for count maintenance).
CREATE TABLE IF NOT EXISTS vault_document (
    vault_id     TEXT NOT NULL REFERENCES vault(id) ON DELETE CASCADE,
    document_id  TEXT NOT NULL,
    assigned_at  TEXT NOT NULL,
    PRIMARY KEY (vault_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_vault_doc_vault ON vault_document(vault_id);
CREATE INDEX IF NOT EXISTS idx_vault_doc_doc   ON vault_document(document_id);
"""


# ---------------------------------------------------------------------------
# Vault Service
# ---------------------------------------------------------------------------


class VaultService:
    """The Vault Service.

    Manages logical knowledge boundaries, document ownership and access control.
    This is the primary authorization layer for document access.

    Integrates with:
        - DocumentRegistry (Task 001) for document lookups and audit logging.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        conn: "sqlite3.Connection | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self._conn = conn or in_memory()
        self._conn.executescript(_VAULT_SCHEMA)
        self._conn.commit()
        init_audit_log(self.registry.repo.conn)

    @property
    def conn(self) -> sqlite3.Connection:
        """The underlying database connection (for cross-cutting access)."""
        return self._conn

    # ------------------------------------------------------------------
    # Create Vault
    # ------------------------------------------------------------------

    def create_vault(
        self,
        *,
        name: str,
        vault_type: "str | VaultType" = VaultType.COMMON,
        owner: str,
        description: "str | None" = None,
        organization_id: "UUID | None" = None,
        retention_policy: "str | None" = None,
    ) -> Vault:
        """Create a new Vault.

        Args:
            name: the vault name.
            vault_type: the vault type (COMMON, DEPARTMENT, PROJECT, PERSONAL).
            owner: the user_id of the vault owner.
            description: optional description.
            organization_id: the organization this vault belongs to.
            retention_policy: optional retention policy.

        Returns:
            The created Vault.
        """
        if isinstance(vault_type, str):
            vault_type = VaultType(vault_type.upper())

        vault = Vault(
            name=name,
            vault_type=vault_type,
            owner=owner,
            description=description,
            organization_id=organization_id or new_id(),
            retention_policy=retention_policy,
        )

        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.create",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"Vault '{vault.name}' created (type={vault.vault_type.value})",
            metadata={
                "name": vault.name,
                "vault_type": vault.vault_type.value,
                "owner": vault.owner,
            },
        )

        return vault

    # ------------------------------------------------------------------
    # Read Vault
    # ------------------------------------------------------------------

    def get_vault(self, vault_id: UUID) -> Optional[Vault]:
        """Retrieve a Vault by its ID."""
        row = self._conn.execute(
            "SELECT * FROM vault WHERE id = ?", (str(vault_id),)
        ).fetchone()
        return self._vault_from_row(row) if row else None

    def list_vaults(
        self,
        *,
        vault_type: "VaultType | None" = None,
        status: "VaultStatus | None" = None,
        user_id: "str | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Vault]:
        """List Vaults with optional filtering.

        Args:
            vault_type: filter by vault type.
            status: filter by vault status.
            user_id: filter to vaults where the user is a member.
            limit: maximum number of results.
            offset: pagination offset.

        Returns:
            A list of Vaults.
        """
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if vault_type is not None:
            clauses.append("vault_type = :vault_type")
            params["vault_type"] = vault_type.value
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status.value
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        if user_id is None:
            rows = self._conn.execute(
                f"SELECT * FROM vault{where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
                params,
            )
            return [self._vault_from_row(r) for r in rows]

        # Membership lives in JSON for the MVP. Filter parsed identities rather
        # than SQL LIKE, which lets identifiers such as `user-1` match `user-10`.
        rows = self._conn.execute(
            f"SELECT * FROM vault{where} ORDER BY created_at DESC",
            {key: value for key, value in params.items() if key not in {"limit", "offset"}},
        )
        authorized = [
            vault for vault in (self._vault_from_row(row) for row in rows)
            if vault.has_member(user_id)
        ]
        return authorized[offset:offset + limit]

    # ------------------------------------------------------------------
    # Update Vault
    # ------------------------------------------------------------------

    def update_vault(
        self,
        vault_id: UUID,
        *,
        name: "str | None" = None,
        description: "str | None" = None,
        retention_policy: "str | None" = None,
    ) -> Vault:
        """Update mutable Vault metadata.

        Does NOT change vault_type, owner, status, or organization_id
        (those require dedicated operations).

        Args:
            vault_id: the vault to update.
            name: new name.
            description: new description.
            retention_policy: new retention policy.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")

        changed = False
        if name is not None and name != vault.name:
            vault.name = name
            changed = True
        if description is not None:
            vault.description = description
            changed = True
        if retention_policy is not None:
            vault.retention_policy = retention_policy
            changed = True

        if changed:
            vault.touch()
            self._persist_vault(vault)
            log_event(
                self.registry.repo.conn,
                service="vault-service",
                module="vault",
                event="vault.update",
                entity_type="vault",
                entity_id=vault.id,
                severity="INFO",
                message=f"Vault '{vault.name}' updated",
            )

        return vault

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def archive_vault(self, vault_id: UUID) -> Vault:
        """Archive a Vault.

        Archived vaults are read-only / historical. Documents in an archived
        vault remain accessible for historical reference but new documents
        cannot be added.

        Args:
            vault_id: the vault to archive.

        Returns:
            The archived Vault.

        Raises:
            KeyError: if the vault is not found.
            ValueError: if the vault is already archived.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")
        if vault.status == VaultStatus.ARCHIVED:
            raise ValueError(f"Vault {vault_id} is already archived")

        vault.status = VaultStatus.ARCHIVED
        vault.touch()
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.archive",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"Vault '{vault.name}' archived",
        )
        return vault

    def restore_vault(self, vault_id: UUID) -> Vault:
        """Restore an archived Vault back to ACTIVE status.

        Args:
            vault_id: the vault to restore.

        Returns:
            The restored Vault.

        Raises:
            KeyError: if the vault is not found.
            ValueError: if the vault is not archived.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")
        if vault.status != VaultStatus.ARCHIVED:
            raise ValueError(f"Vault {vault_id} is not archived")

        vault.status = VaultStatus.ACTIVE
        vault.touch()
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.restore",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"Vault '{vault.name}' restored",
        )
        return vault

    # ------------------------------------------------------------------
    # Member Management
    # ------------------------------------------------------------------

    def add_member(
        self,
        vault_id: UUID,
        user_id: str,
        *,
        role: "str | VaultRole" = VaultRole.VIEWER,
    ) -> Vault:
        """Add a member to a Vault.

        Args:
            vault_id: the vault.
            user_id: the user to add.
            role: the role to assign.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
            ValueError: if the user is already a member.
        """
        if isinstance(role, str):
            role = VaultRole(role.upper())

        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")
        if vault.has_member(user_id):
            raise ValueError(f"User {user_id} is already a member of vault {vault_id}")

        member = VaultMember(user_id=user_id, role=role)
        vault.members[user_id] = member
        vault.member_count = len(vault.members)
        vault.touch()
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.member_add",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"User {user_id} added to vault '{vault.name}' as {role.value}",
            metadata={"user_id": user_id, "role": role.value},
        )
        return vault

    def remove_member(self, vault_id: UUID, user_id: str) -> Vault:
        """Remove a member from a Vault.

        Args:
            vault_id: the vault.
            user_id: the user to remove.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
            ValueError: if the user is not a member or is the owner.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")
        if user_id == vault.owner:
            raise ValueError("Cannot remove the vault owner")
        if user_id not in vault.members:
            raise ValueError(f"User {user_id} is not a member of vault {vault_id}")

        del vault.members[user_id]
        vault.member_count = len(vault.members)
        vault.touch()
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.member_remove",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"User {user_id} removed from vault '{vault.name}'",
            metadata={"user_id": user_id},
        )
        return vault

    def update_member_role(
        self,
        vault_id: UUID,
        user_id: str,
        role: "str | VaultRole",
    ) -> Vault:
        """Update a member's role within a Vault.

        Args:
            vault_id: the vault.
            user_id: the user whose role to update.
            role: the new role.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
            ValueError: if the user is not a member or is the owner.
        """
        if isinstance(role, str):
            role = VaultRole(role.upper())

        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")
        if user_id == vault.owner:
            raise ValueError("Cannot change the vault owner's role")
        if user_id not in vault.members:
            raise ValueError(f"User {user_id} is not a member of vault {vault_id}")

        vault.members[user_id].role = role
        vault.touch()
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.member_role_update",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"User {user_id} role updated to {role.value} in vault '{vault.name}'",
            metadata={"user_id": user_id, "role": role.value},
        )
        return vault

    # ------------------------------------------------------------------
    # Document Assignment
    # ------------------------------------------------------------------

    def assign_document(self, vault_id: UUID, document_id: UUID) -> Vault:
        """Assign a document to a Vault.

        Every document belongs to exactly one primary Vault
        (document-contract.md INV-001).

        Args:
            vault_id: the vault to assign the document to.
            document_id: the document to assign.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")

        now = utc_iso(now_utc())
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO vault_document (vault_id, document_id, assigned_at) "
                "VALUES (?, ?, ?)",
                (str(vault_id), str(document_id), now),
            )

        # Update document count
        vault.document_count = self._document_count(vault_id)
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.document_assign",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"Document {document_id} assigned to vault '{vault.name}'",
            metadata={"document_id": str(document_id)},
        )
        return vault

    def unassign_document(self, vault_id: UUID, document_id: UUID) -> Vault:
        """Remove a document from a Vault.

        Args:
            vault_id: the vault.
            document_id: the document to remove.

        Returns:
            The updated Vault.

        Raises:
            KeyError: if the vault is not found.
        """
        vault = self.get_vault(vault_id)
        if vault is None:
            raise KeyError(f"Vault {vault_id} not found")

        with self._conn:
            self._conn.execute(
                "DELETE FROM vault_document WHERE vault_id = ? AND document_id = ?",
                (str(vault_id), str(document_id)),
            )

        vault.document_count = self._document_count(vault_id)
        self._persist_vault(vault)

        log_event(
            self.registry.repo.conn,
            service="vault-service",
            module="vault",
            event="vault.document_unassign",
            entity_type="vault",
            entity_id=vault.id,
            severity="INFO",
            message=f"Document {document_id} unassigned from vault '{vault.name}'",
            metadata={"document_id": str(document_id)},
        )
        return vault

    def list_document_ids(self, vault_id: UUID) -> list[UUID]:
        """List all document IDs assigned to a Vault.

        Args:
            vault_id: the vault.

        Returns:
            A list of document UUIDs.
        """
        rows = self._conn.execute(
            "SELECT document_id FROM vault_document WHERE vault_id = ?",
            (str(vault_id),),
        )
        return [UUID(r["document_id"]) for r in rows]

    # ------------------------------------------------------------------
    # Permission Resolution
    # ------------------------------------------------------------------

    def check_permission(
        self,
        vault_id: UUID,
        user_id: str,
        permission: "str | Permission",
    ) -> bool:
        """Check if a user has a specific permission in a Vault.

        Permissions are evaluated before retrieval begins
        (tasks/013 #PermissionModel).

        Args:
            vault_id: the vault to check.
            user_id: the user to check.
            permission: the required permission.

        Returns:
            True if the user has the permission.
        """
        if isinstance(permission, str):
            permission = Permission(permission.upper())

        vault = self.get_vault(vault_id)
        if vault is None:
            return False
        return vault.has_permission(user_id, permission)

    def authorized_vault_ids(
        self,
        user_id: str,
        *,
        permission: "str | Permission" = Permission.READ,
    ) -> list[UUID]:
        """Return all vault IDs the user has a given permission in.

        This is used by the Retrieval Service to scope search to
        authorized vaults.

        Args:
            user_id: the user to check.
            permission: the required permission (default READ).

        Returns:
            A list of vault UUIDs.
        """
        if isinstance(permission, str):
            permission = Permission(permission.upper())

        vaults = self.list_vaults(user_id=user_id, status=VaultStatus.ACTIVE)
        return [
            v.id for v in vaults
            if v.has_permission(user_id, permission)
        ]

    def vault_exists(self, vault_id: UUID) -> bool:
        """Check if a Vault exists (for the VaultResolver protocol)."""
        return self.get_vault(vault_id) is not None

    def user_can_upload_to_vault(self, user_id: str, vault_id: UUID) -> bool:
        """Check if a user can upload documents to a Vault.

        Requires UPLOAD permission (or higher). The vault must be ACTIVE.
        """
        return self.check_permission(vault_id, user_id, Permission.UPLOAD)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_vault(self, vault: Vault) -> None:
        """Persist a vault to the database."""
        members_json = json.dumps(
            {
                uid: m.model_dump(mode="json")
                for uid, m in vault.members.items()
            },
            ensure_ascii=False,
        )
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO vault
                    (id, name, vault_type, owner, description, status,
                     organization_id, created_at, updated_at, document_count,
                     member_count, retention_policy, members_json)
                VALUES
                    (:id, :name, :vault_type, :owner, :description, :status,
                     :organization_id, :created_at, :updated_at, :document_count,
                     :member_count, :retention_policy, :members_json)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, vault_type=excluded.vault_type,
                    owner=excluded.owner, description=excluded.description,
                    status=excluded.status, organization_id=excluded.organization_id,
                    updated_at=excluded.updated_at, document_count=excluded.document_count,
                    member_count=excluded.member_count,
                    retention_policy=excluded.retention_policy,
                    members_json=excluded.members_json
                """,
                {
                    "id": str(vault.id),
                    "name": vault.name,
                    "vault_type": vault.vault_type.value,
                    "owner": vault.owner,
                    "description": vault.description,
                    "status": vault.status.value,
                    "organization_id": str(vault.organization_id),
                    "created_at": utc_iso(vault.created_at),
                    "updated_at": utc_iso(vault.updated_at),
                    "document_count": vault.document_count,
                    "member_count": vault.member_count,
                    "retention_policy": vault.retention_policy,
                    "members_json": members_json,
                },
            )

    def _vault_from_row(self, row: sqlite3.Row) -> Vault:
        """Reconstruct a Vault from a DB row."""
        members_raw = json.loads(row["members_json"] or "{}")
        members = {
            uid: VaultMember(**m)
            for uid, m in members_raw.items()
        }
        return Vault(
            id=UUID(row["id"]),
            name=row["name"],
            vault_type=VaultType(row["vault_type"]),
            owner=row["owner"],
            description=row["description"],
            status=VaultStatus(row["status"]),
            organization_id=UUID(row["organization_id"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            document_count=row["document_count"],
            member_count=row["member_count"],
            retention_policy=row["retention_policy"],
            members=members,
        )

    def _document_count(self, vault_id: UUID) -> int:
        """Count documents assigned to a vault."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM vault_document WHERE vault_id = ?",
            (str(vault_id),),
        ).fetchone()
        return row["cnt"] if row else 0

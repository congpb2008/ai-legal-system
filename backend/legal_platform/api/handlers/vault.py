"""Vault management handler (tasks/014-api.md #VaultAPIs)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from legal_platform.api.models import (
    ApiError,
    ApiResponse,
    ErrorCategory,
    PaginatedResponse,
)
from legal_platform.modules.vault.models import Permission, VaultType, VaultStatus
from legal_platform.modules.vault.service import VaultService


class VaultHandler:
    """Vault management endpoints (tasks/014-api.md #VaultAPIs)."""

    def __init__(self, vault_service: "VaultService | None" = None):
        self.vault = vault_service or VaultService()

    def list_vaults(self, params: dict[str, str], user_id: str) -> ApiResponse:
        """GET /v1/vaults"""
        vault_type = params.get("type")
        status = params.get("status")
        limit = int(params.get("limit", "100"))
        offset = int(params.get("offset", "0"))

        # Coerce string params to enums
        vt = VaultType(vault_type.upper()) if vault_type else None
        vs = VaultStatus(status.upper()) if status else None

        vaults = self.vault.list_vaults(
            vault_type=vt,
            status=vs,
            user_id=user_id,
            limit=None,
            offset=0,
        )
        total = len(vaults)

        return ApiResponse.ok(
            data=PaginatedResponse(
                items=[dict(self._vault_to_dict(v),
                            can_upload=v.has_permission(user_id, Permission.UPLOAD),
                            can_manage=v.has_permission(user_id, Permission.MANAGE))
                       for v in vaults[offset:offset + limit]],
                total=total,
                limit=limit,
                offset=offset,
            ),
        )

    def create_vault(self, body: dict[str, Any], user_id: str) -> ApiResponse:
        """POST /v1/vaults"""
        name = (body.get("name") or "").strip()
        if not name:
            return ApiResponse.err_response(
                ApiError(
                    code="VALIDATION_ERROR",
                    message="Vault name is required.",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        vault_type = body.get("vault_type", "COMMON")
        description = body.get("description")
        retention_policy = body.get("retention_policy")

        try:
            vault = self.vault.create_vault(
                name=name,
                vault_type=vault_type,
                owner=user_id,
                organization_id=UUID(body['organization_id']) if body.get('organization_id') else None,
                description=description,
                retention_policy=retention_policy,
            )
        except ValueError as e:
            return ApiResponse.err_response(
                ApiError(
                    code="VALIDATION_ERROR",
                    message=str(e),
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        return ApiResponse.ok(
            data=self._vault_to_dict(vault),
            status=201,
        )

    def get_vault(self, vault_id: str, user_id: str) -> ApiResponse:
        """GET /v1/vaults/{vaultId}"""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(
                    code="INVALID_ID",
                    message=f"Invalid vault ID: {vault_id}",
                    category=ErrorCategory.VALIDATION,
                ),
                status=400,
            )

        vault = self.vault.get_vault(vid)
        if vault is None:
            return ApiResponse.err_response(
                ApiError(
                    code="VAULT_NOT_FOUND",
                    message=f"Vault {vault_id} not found.",
                    category=ErrorCategory.NOT_FOUND,
                ),
                status=404,
            )
        if not self.vault.check_permission(vid, user_id, Permission.READ):
            return self._forbidden(vault_id)

        return ApiResponse.ok(data=self._vault_to_dict(vault))

    def update_vault(self, vault_id: str, body: dict[str, Any], user_id: str) -> ApiResponse:
        """PATCH /v1/vaults/{vaultId}"""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid vault ID: {vault_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not self.vault.check_permission(vid, user_id, Permission.MANAGE):
            return self._forbidden(vault_id)

        try:
            vault = self.vault.update_vault(
                vid,
                name=body.get("name"),
                description=body.get("description"),
                retention_policy=body.get("retention_policy"),
            )
        except KeyError:
            return ApiResponse.err_response(
                ApiError(code="VAULT_NOT_FOUND", message=f"Vault {vault_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )

        return ApiResponse.ok(data=self._vault_to_dict(vault))

    def delete_vault(self, vault_id: str, user_id: str) -> ApiResponse:
        """DELETE /v1/vaults/{vaultId} — archives the vault."""
        try:
            vid = UUID(vault_id)
        except ValueError:
            return ApiResponse.err_response(
                ApiError(code="INVALID_ID", message=f"Invalid vault ID: {vault_id}",
                         category=ErrorCategory.VALIDATION),
                status=400,
            )
        if not self.vault.check_permission(vid, user_id, Permission.MANAGE):
            return self._forbidden(vault_id)
        try:
            self.vault.archive_vault(vid)
        except KeyError:
            return ApiResponse.err_response(
                ApiError(code="VAULT_NOT_FOUND", message=f"Vault {vault_id} not found.",
                         category=ErrorCategory.NOT_FOUND),
                status=404,
            )
        return ApiResponse.ok(data={"message": f"Vault {vault_id} archived."})

    @staticmethod
    def _forbidden(vault_id: str) -> ApiResponse:
        return ApiResponse.err_response(
            ApiError(
                code="VAULT_FORBIDDEN",
                message=f"You do not have permission to access vault {vault_id}.",
                category=ErrorCategory.AUTHORIZATION,
            ),
            status=403,
        )

    @staticmethod
    def _vault_to_dict(vault: Any) -> dict[str, Any]:
        return {
            "id": str(vault.id),
            "name": vault.name,
            "vault_type": vault.vault_type.value if hasattr(vault.vault_type, 'value') else vault.vault_type,
            "owner": vault.owner,
            "description": vault.description,
            "status": vault.status.value if hasattr(vault.status, 'value') else vault.status,
            "organization_id": str(vault.organization_id),
            "created_at": vault.created_at.isoformat() if hasattr(vault.created_at, 'isoformat') else str(vault.created_at),
            "updated_at": vault.updated_at.isoformat() if hasattr(vault.updated_at, 'isoformat') else str(vault.updated_at),
            "document_count": vault.document_count,
            "member_count": vault.member_count,
            "retention_policy": vault.retention_policy,
        }

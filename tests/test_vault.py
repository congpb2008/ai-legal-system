"""Tests for the Vault Service (Task 013).

Covers:
    - Vault model invariants (types, statuses, permissions, roles)
    - Vault CRUD (create, get, list, update)
    - Vault lifecycle (archive, restore)
    - Member management (add, remove, update role)
    - Document assignment (assign, unassign, list)
    - Permission resolution (check_permission, authorized_vault_ids)
    - VaultResolver protocol (vault_exists, user_can_upload_to_vault)
    - Vault isolation (Personal, Common, Department, Project)
    - Audit logging
    - Error handling

The authoritative source is the Vault Service specification
(tasks/013-vault-service.md) and the Document Contract
(02-contracts/document-contract.md).
"""

from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.modules.vault.models import (
    Vault,
    VaultMember,
    VaultRole,
    VaultStatus,
    VaultType,
    Permission,
    role_permissions,
)
from legal_platform.modules.vault.service import VaultService
from legal_platform.modules.vault.resolver import VaultServiceResolver
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def vault_service():
    return VaultService()


@pytest.fixture
def common_vault(vault_service) -> Vault:
    return vault_service.create_vault(
        name="Common Knowledge",
        vault_type=VaultType.COMMON,
        owner="admin",
        description="Shared laws and regulations.",
    )


@pytest.fixture
def department_vault(vault_service) -> Vault:
    return vault_service.create_vault(
        name="IT Department",
        vault_type=VaultType.DEPARTMENT,
        owner="it-manager",
        description="IT department documents.",
    )


@pytest.fixture
def personal_vault(vault_service) -> Vault:
    return vault_service.create_vault(
        name="Personal Documents",
        vault_type=VaultType.PERSONAL,
        owner="user-1",
        description="User's personal documents.",
    )


@pytest.fixture
def project_vault(vault_service) -> Vault:
    return vault_service.create_vault(
        name="Migration Project",
        vault_type=VaultType.PROJECT,
        owner="pm-1",
        description="System migration project documents.",
    )


# ======================================================================
# 1. Vault Model
# ======================================================================


class TestVaultModel:
    """Vault model invariants."""

    def test_vault_has_id(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        assert vault.id is not None

    def test_vault_default_status(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        assert vault.status == VaultStatus.ACTIVE

    def test_vault_default_type(self):
        vault = Vault(name="Test", owner="admin")
        assert vault.vault_type == VaultType.COMMON

    def test_vault_owner_is_implicit_member(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        assert vault.has_member("admin")
        assert vault.member_role("admin") == VaultRole.OWNER

    def test_vault_owner_has_all_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        for perm in Permission:
            assert vault.has_permission("admin", perm)

    def test_vault_archived_denies_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        vault.status = VaultStatus.ARCHIVED
        assert not vault.has_permission("admin", Permission.READ)

    def test_vault_non_member_has_no_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        assert not vault.has_permission("stranger", Permission.READ)

    def test_viewer_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        vault.members["viewer"] = VaultMember(user_id="viewer", role=VaultRole.VIEWER)
        assert vault.has_permission("viewer", Permission.READ)
        assert not vault.has_permission("viewer", Permission.UPLOAD)
        assert not vault.has_permission("viewer", Permission.DELETE)
        assert not vault.has_permission("viewer", Permission.MANAGE)

    def test_contributor_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        vault.members["contrib"] = VaultMember(user_id="contrib", role=VaultRole.CONTRIBUTOR)
        assert vault.has_permission("contrib", Permission.READ)
        assert vault.has_permission("contrib", Permission.UPLOAD)
        assert vault.has_permission("contrib", Permission.UPDATE)
        assert not vault.has_permission("contrib", Permission.DELETE)
        assert not vault.has_permission("contrib", Permission.MANAGE)

    def test_manager_permissions(self):
        vault = Vault(name="Test", vault_type=VaultType.COMMON, owner="admin")
        vault.members["mgr"] = VaultMember(user_id="mgr", role=VaultRole.MANAGER)
        assert vault.has_permission("mgr", Permission.READ)
        assert vault.has_permission("mgr", Permission.UPLOAD)
        assert vault.has_permission("mgr", Permission.UPDATE)
        assert vault.has_permission("mgr", Permission.DELETE)
        assert vault.has_permission("mgr", Permission.SHARE)
        assert vault.has_permission("mgr", Permission.MANAGE)

    def test_role_permissions_mapping(self):
        """Each role should grant the correct set of permissions."""
        assert Permission.READ in role_permissions(VaultRole.VIEWER)
        assert Permission.UPLOAD not in role_permissions(VaultRole.VIEWER)

        assert Permission.READ in role_permissions(VaultRole.CONTRIBUTOR)
        assert Permission.UPLOAD in role_permissions(VaultRole.CONTRIBUTOR)
        assert Permission.DELETE not in role_permissions(VaultRole.CONTRIBUTOR)


# ======================================================================
# 2. Vault CRUD
# ======================================================================


class TestVaultCRUD:
    """Create, read, update, list vaults."""

    def test_create_common_vault(self, vault_service):
        vault = vault_service.create_vault(
            name="Common Knowledge",
            vault_type=VaultType.COMMON,
            owner="admin",
        )
        assert vault.id is not None
        assert vault.name == "Common Knowledge"
        assert vault.vault_type == VaultType.COMMON
        assert vault.owner == "admin"
        assert vault.status == VaultStatus.ACTIVE

    def test_create_department_vault(self, vault_service):
        vault = vault_service.create_vault(
            name="IT Department",
            vault_type=VaultType.DEPARTMENT,
            owner="it-manager",
        )
        assert vault.vault_type == VaultType.DEPARTMENT

    def test_create_personal_vault(self, vault_service):
        vault = vault_service.create_vault(
            name="Personal",
            vault_type=VaultType.PERSONAL,
            owner="user-1",
        )
        assert vault.vault_type == VaultType.PERSONAL

    def test_create_project_vault(self, vault_service):
        vault = vault_service.create_vault(
            name="Project X",
            vault_type=VaultType.PROJECT,
            owner="pm-1",
        )
        assert vault.vault_type == VaultType.PROJECT

    def test_get_vault(self, vault_service, common_vault):
        fetched = vault_service.get_vault(common_vault.id)
        assert fetched is not None
        assert fetched.id == common_vault.id
        assert fetched.name == common_vault.name

    def test_get_nonexistent_vault(self, vault_service):
        fetched = vault_service.get_vault(new_id())
        assert fetched is None

    def test_list_vaults(self, vault_service, common_vault, department_vault):
        vaults = vault_service.list_vaults()
        assert len(vaults) >= 2

    def test_list_vaults_by_type(self, vault_service, common_vault, department_vault):
        commons = vault_service.list_vaults(vault_type=VaultType.COMMON)
        assert all(v.vault_type == VaultType.COMMON for v in commons)

    def test_list_vaults_by_status(self, vault_service, common_vault):
        actives = vault_service.list_vaults(status=VaultStatus.ACTIVE)
        assert all(v.status == VaultStatus.ACTIVE for v in actives)

    def test_list_vaults_by_user(self, vault_service, common_vault, personal_vault):
        user_vaults = vault_service.list_vaults(user_id="user-1")
        assert any(v.id == personal_vault.id for v in user_vaults)

    def test_update_vault_name(self, vault_service, common_vault):
        updated = vault_service.update_vault(
            common_vault.id,
            name="Updated Name",
        )
        assert updated.name == "Updated Name"

    def test_update_vault_description(self, vault_service, common_vault):
        updated = vault_service.update_vault(
            common_vault.id,
            description="Updated description.",
        )
        assert updated.description == "Updated description."

    def test_update_nonexistent_vault(self, vault_service):
        with pytest.raises(KeyError):
            vault_service.update_vault(new_id(), name="New Name")


# ======================================================================
# 3. Vault Lifecycle
# ======================================================================


class TestVaultLifecycle:
    """Vault archive, restore."""

    def test_archive_vault(self, vault_service, common_vault):
        archived = vault_service.archive_vault(common_vault.id)
        assert archived.status == VaultStatus.ARCHIVED

    def test_archive_already_archived(self, vault_service, common_vault):
        vault_service.archive_vault(common_vault.id)
        with pytest.raises(ValueError, match="already archived"):
            vault_service.archive_vault(common_vault.id)

    def test_archive_nonexistent(self, vault_service):
        with pytest.raises(KeyError):
            vault_service.archive_vault(new_id())

    def test_restore_vault(self, vault_service, common_vault):
        vault_service.archive_vault(common_vault.id)
        restored = vault_service.restore_vault(common_vault.id)
        assert restored.status == VaultStatus.ACTIVE

    def test_restore_active_vault(self, vault_service, common_vault):
        with pytest.raises(ValueError, match="not archived"):
            vault_service.restore_vault(common_vault.id)

    def test_archived_vault_denies_permissions(self, vault_service, common_vault):
        vault_service.archive_vault(common_vault.id)
        assert not vault_service.check_permission(
            common_vault.id, "admin", Permission.READ
        )


# ======================================================================
# 4. Member Management
# ======================================================================


class TestMemberManagement:
    """Add, remove, update members."""

    def test_add_member(self, vault_service, common_vault):
        updated = vault_service.add_member(
            common_vault.id, "user-2", role=VaultRole.VIEWER
        )
        assert updated.has_member("user-2")
        assert updated.member_role("user-2") == VaultRole.VIEWER

    def test_add_member_default_role(self, vault_service, common_vault):
        updated = vault_service.add_member(common_vault.id, "user-2")
        assert updated.member_role("user-2") == VaultRole.VIEWER

    def test_add_duplicate_member(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "user-2")
        with pytest.raises(ValueError, match="already a member"):
            vault_service.add_member(common_vault.id, "user-2")

    def test_remove_member(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "user-2")
        updated = vault_service.remove_member(common_vault.id, "user-2")
        assert not updated.has_member("user-2")

    def test_remove_owner_forbidden(self, vault_service, common_vault):
        with pytest.raises(ValueError, match="Cannot remove the vault owner"):
            vault_service.remove_member(common_vault.id, "admin")

    def test_remove_nonexistent_member(self, vault_service, common_vault):
        with pytest.raises(ValueError, match="not a member"):
            vault_service.remove_member(common_vault.id, "stranger")

    def test_update_member_role(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "user-2", role=VaultRole.VIEWER)
        updated = vault_service.update_member_role(
            common_vault.id, "user-2", VaultRole.CONTRIBUTOR
        )
        assert updated.member_role("user-2") == VaultRole.CONTRIBUTOR

    def test_update_owner_role_forbidden(self, vault_service, common_vault):
        with pytest.raises(ValueError, match="Cannot change the vault owner"):
            vault_service.update_member_role(common_vault.id, "admin", VaultRole.VIEWER)

    def test_member_count_tracking(self, vault_service, common_vault):
        assert common_vault.member_count == 0  # owner not counted in members dict
        vault_service.add_member(common_vault.id, "user-2")
        vault_service.add_member(common_vault.id, "user-3")
        fetched = vault_service.get_vault(common_vault.id)
        assert fetched.member_count == 2


# ======================================================================
# 5. Document Assignment
# ======================================================================


class TestDocumentAssignment:
    """Assign, unassign, list documents."""

    def test_assign_document(self, vault_service, common_vault):
        doc_id = new_id()
        updated = vault_service.assign_document(common_vault.id, doc_id)
        assert updated.document_count >= 1

    def test_unassign_document(self, vault_service, common_vault):
        doc_id = new_id()
        vault_service.assign_document(common_vault.id, doc_id)
        updated = vault_service.unassign_document(common_vault.id, doc_id)
        assert updated.document_count == 0

    def test_list_document_ids(self, vault_service, common_vault):
        doc_id_1 = new_id()
        doc_id_2 = new_id()
        vault_service.assign_document(common_vault.id, doc_id_1)
        vault_service.assign_document(common_vault.id, doc_id_2)
        ids = vault_service.list_document_ids(common_vault.id)
        assert doc_id_1 in ids
        assert doc_id_2 in ids

    def test_assign_nonexistent_vault(self, vault_service):
        with pytest.raises(KeyError):
            vault_service.assign_document(new_id(), new_id())


# ======================================================================
# 6. Permission Resolution
# ======================================================================


class TestPermissionResolution:
    """Permission checks and authorized vault IDs."""

    def test_check_permission_owner(self, vault_service, common_vault):
        assert vault_service.check_permission(
            common_vault.id, "admin", Permission.READ
        )
        assert vault_service.check_permission(
            common_vault.id, "admin", Permission.UPLOAD
        )
        assert vault_service.check_permission(
            common_vault.id, "admin", Permission.MANAGE
        )

    def test_check_permission_viewer(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "viewer", role=VaultRole.VIEWER)
        assert vault_service.check_permission(
            common_vault.id, "viewer", Permission.READ
        )
        assert not vault_service.check_permission(
            common_vault.id, "viewer", Permission.UPLOAD
        )

    def test_check_permission_non_member(self, vault_service, common_vault):
        assert not vault_service.check_permission(
            common_vault.id, "stranger", Permission.READ
        )

    def test_check_permission_nonexistent_vault(self, vault_service):
        assert not vault_service.check_permission(
            new_id(), "admin", Permission.READ
        )

    def test_authorized_vault_ids(self, vault_service, common_vault, department_vault):
        vault_service.add_member(common_vault.id, "user-2", role=VaultRole.VIEWER)
        vault_service.add_member(department_vault.id, "user-2", role=VaultRole.CONTRIBUTOR)

        authorized = vault_service.authorized_vault_ids("user-2", permission=Permission.READ)
        assert common_vault.id in authorized
        assert department_vault.id in authorized

    def test_authorized_vault_ids_upload(self, vault_service, common_vault, department_vault):
        vault_service.add_member(common_vault.id, "user-2", role=VaultRole.VIEWER)
        vault_service.add_member(department_vault.id, "user-2", role=VaultRole.CONTRIBUTOR)

        # VIEWER can't upload, CONTRIBUTOR can
        authorized = vault_service.authorized_vault_ids("user-2", permission=Permission.UPLOAD)
        assert common_vault.id not in authorized
        assert department_vault.id in authorized

    def test_authorized_vault_ids_owner(self, vault_service, common_vault):
        authorized = vault_service.authorized_vault_ids("admin", permission=Permission.READ)
        assert common_vault.id in authorized

    def test_vault_exists(self, vault_service, common_vault):
        assert vault_service.vault_exists(common_vault.id)
        assert not vault_service.vault_exists(new_id())

    def test_user_can_upload_to_vault(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "contrib", role=VaultRole.CONTRIBUTOR)
        assert vault_service.user_can_upload_to_vault("admin", common_vault.id)
        assert vault_service.user_can_upload_to_vault("contrib", common_vault.id)
        assert not vault_service.user_can_upload_to_vault("viewer", common_vault.id)


# ======================================================================
# 7. VaultResolver Protocol
# ======================================================================


class TestVaultResolver:
    """VaultServiceResolver replaces AllowAllVaults."""

    def test_resolver_vault_exists(self, vault_service, common_vault):
        resolver = VaultServiceResolver(vault_service)
        assert resolver.vault_exists(common_vault.id)
        assert not resolver.vault_exists(new_id())

    def test_resolver_user_can_upload(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "contrib", role=VaultRole.CONTRIBUTOR)
        resolver = VaultServiceResolver(vault_service)
        assert resolver.user_can_upload_to_vault("admin", common_vault.id)
        assert resolver.user_can_upload_to_vault("contrib", common_vault.id)
        assert not resolver.user_can_upload_to_vault("viewer", common_vault.id)

    def test_resolver_default_constructor(self):
        """VaultServiceResolver() should work without arguments."""
        resolver = VaultServiceResolver()
        # No vaults exist yet, so this should return False
        assert not resolver.vault_exists(new_id())


# ======================================================================
# 8. Vault Isolation
# ======================================================================


class TestVaultIsolation:
    """Vault isolation principles (tasks/013 #VaultIsolation)."""

    def test_personal_vault_owner_only(self, vault_service):
        vault = vault_service.create_vault(
            name="Personal",
            vault_type=VaultType.PERSONAL,
            owner="user-1",
        )
        assert vault.has_permission("user-1", Permission.READ)
        assert not vault.has_permission("user-2", Permission.READ)

    def test_common_vault_accessible(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "any-user", role=VaultRole.VIEWER)
        assert vault_service.check_permission(
            common_vault.id, "any-user", Permission.READ
        )

    def test_department_vault_restricted(self, vault_service, department_vault):
        assert not vault_service.check_permission(
            department_vault.id, "outsider", Permission.READ
        )
        vault_service.add_member(department_vault.id, "dept-member", role=VaultRole.VIEWER)
        assert vault_service.check_permission(
            department_vault.id, "dept-member", Permission.READ
        )

    def test_project_vault_lifecycle(self, vault_service):
        vault = vault_service.create_vault(
            name="Project Alpha",
            vault_type=VaultType.PROJECT,
            owner="pm-1",
        )
        vault_service.add_member(vault.id, "team-member", role=VaultRole.CONTRIBUTOR)
        assert vault_service.check_permission(
            vault.id, "team-member", Permission.READ
        )
        vault_service.archive_vault(vault.id)
        assert not vault_service.check_permission(
            vault.id, "team-member", Permission.READ
        )

    def test_documents_isolated_by_vault(self, vault_service):
        """Documents in different vaults should be isolated."""
        vault_a = vault_service.create_vault(
            name="Vault A", vault_type=VaultType.DEPARTMENT, owner="mgr-a"
        )
        vault_b = vault_service.create_vault(
            name="Vault B", vault_type=VaultType.DEPARTMENT, owner="mgr-b"
        )
        doc_a = new_id()
        doc_b = new_id()
        vault_service.assign_document(vault_a.id, doc_a)
        vault_service.assign_document(vault_b.id, doc_b)

        docs_in_a = vault_service.list_document_ids(vault_a.id)
        docs_in_b = vault_service.list_document_ids(vault_b.id)

        assert doc_a in docs_in_a
        assert doc_b in docs_in_b
        assert doc_a not in docs_in_b
        assert doc_b not in docs_in_a


# ======================================================================
# 9. Audit Logging
# ======================================================================


class TestAuditLogging:
    """Vault audit logging."""

    def test_create_logs_event(self, vault_service):
        vault = vault_service.create_vault(
            name="Audit Test",
            vault_type=VaultType.COMMON,
            owner="admin",
        )
        events = recent_events(
            vault_service.registry.repo.conn,
            entity_id=str(vault.id),
        )
        create_events = [e for e in events if e["event"] == "vault.create"]
        assert len(create_events) >= 1

    def test_archive_logs_event(self, vault_service, common_vault):
        vault_service.archive_vault(common_vault.id)
        events = recent_events(
            vault_service.registry.repo.conn,
            entity_id=str(common_vault.id),
        )
        archive_events = [e for e in events if e["event"] == "vault.archive"]
        assert len(archive_events) >= 1

    def test_member_add_logs_event(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "user-x", role=VaultRole.VIEWER)
        events = recent_events(
            vault_service.registry.repo.conn,
            entity_id=str(common_vault.id),
        )
        member_events = [e for e in events if e["event"] == "vault.member_add"]
        assert len(member_events) >= 1

    def test_document_assign_logs_event(self, vault_service, common_vault):
        doc_id = new_id()
        vault_service.assign_document(common_vault.id, doc_id)
        events = recent_events(
            vault_service.registry.repo.conn,
            entity_id=str(common_vault.id),
        )
        assign_events = [e for e in events if e["event"] == "vault.document_assign"]
        assert len(assign_events) >= 1


# ======================================================================
# 10. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_create_vault_with_string_type(self, vault_service):
        vault = vault_service.create_vault(
            name="String Type",
            vault_type="COMMON",
            owner="admin",
        )
        assert vault.vault_type == VaultType.COMMON

    def test_create_vault_with_retention_policy(self, vault_service):
        vault = vault_service.create_vault(
            name="Retention",
            vault_type=VaultType.COMMON,
            owner="admin",
            retention_policy="keep forever",
        )
        assert vault.retention_policy == "keep forever"

    def test_list_vaults_pagination(self, vault_service):
        for i in range(5):
            vault_service.create_vault(
                name=f"Vault {i}",
                vault_type=VaultType.COMMON,
                owner="admin",
            )
        vaults = vault_service.list_vaults(limit=3)
        assert len(vaults) <= 3

    def test_add_member_with_string_role(self, vault_service, common_vault):
        updated = vault_service.add_member(common_vault.id, "user-x", role="CONTRIBUTOR")
        assert updated.member_role("user-x") == VaultRole.CONTRIBUTOR

    def test_update_member_role_with_string(self, vault_service, common_vault):
        vault_service.add_member(common_vault.id, "user-x", role=VaultRole.VIEWER)
        updated = vault_service.update_member_role(common_vault.id, "user-x", "MANAGER")
        assert updated.member_role("user-x") == VaultRole.MANAGER

    def test_check_permission_with_string(self, vault_service, common_vault):
        assert vault_service.check_permission(common_vault.id, "admin", "READ")
        assert not vault_service.check_permission(common_vault.id, "stranger", "READ")

    def test_authorized_vault_ids_with_string(self, vault_service, common_vault):
        authorized = vault_service.authorized_vault_ids("admin", permission="READ")
        assert common_vault.id in authorized
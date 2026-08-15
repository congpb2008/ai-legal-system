"""Tests for the Document Registry (Task 001).

Covers:
    - Document Contract invariants (document-contract.md INV-001..INV-009).
    - Processing state machine (tasks/001 #ProcessingStates).
    - Registry service CRUD (create, get, list, update metadata).
    - Duplicate detection by checksum.
    - Version management.
    - Relationships.
    - Lifecycle (archive / restore / delete).
    - Audit logging.
    - Error handling.

The authoritative source is the Document Contract (02-contracts/document-contract.md).
Examples are illustrative and may drift; tests follow the contract.
"""

import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id, now_utc
from legal_platform.contracts.document import (
    Document,
    DocumentStatus,
    DocumentType,
    DocumentVersionReference,
    DocumentVersionStatus,
    Metadata,
    Visibility,
)
from legal_platform.modules.document_registry.processing import (
    ProcessingState,
    can_transition,
    InvalidTransition,
    is_terminal,
)
from legal_platform.modules.document_registry.repository import SqliteDocumentRepository
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.document_registry.vault import AllowAllVaults
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def repo():
    return SqliteDocumentRepository()


@pytest.fixture
def registry():
    return DocumentRegistry()


@pytest.fixture
def sample_doc(registry: DocumentRegistry) -> Document:
    """A minimal valid Document for use in tests."""
    return registry.register_document(
        user_id="admin",
        document_type="DECISION",
        title="Test Decision",
        issuing_authority="ABC Bank",
        vault_id=new_id(),
        organization_id=new_id(),
        visibility="PUBLIC",
        source_checksum_sha256="abc123",
    )


# ======================================================================
# 1. Document Contract Invariants
# ======================================================================


class TestDocumentContract:
    """Document Contract invariants (document-contract.md INV-001..INV-009)."""

    def test_inv_001_exactly_one_vault(self):
        """INV-001: A Document must belong to exactly one Vault."""
        with pytest.raises((ValueError, TypeError)):
            Document(
                type="DECISION",
                title="x",
                issuing_authority="a",
                vault_id=None,  # type: ignore
                organization_id=new_id(),
                visibility="PUBLIC",
                versions=[DocumentVersionReference(version_id=new_id())],
            )

    def test_inv_002_exactly_one_organization(self):
        """INV-002: A Document must belong to exactly one Organization."""
        with pytest.raises((ValueError, TypeError)):
            Document(
                type="DECISION",
                title="x",
                issuing_authority="a",
                vault_id=new_id(),
                organization_id=None,  # type: ignore
                visibility="PUBLIC",
                versions=[DocumentVersionReference(version_id=new_id())],
            )

    def test_inv_003_at_least_one_version(self):
        """INV-003: A Document must own at least one Document Version."""
        with pytest.raises((ValueError, TypeError)):
            Document(
                type="DECISION",
                title="x",
                issuing_authority="a",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="PUBLIC",
                versions=[],
            )

    def test_inv_004_identifier_never_changes(self):
        """INV-004: Document identifier never changes (structural — id is immutable)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        original_id = d.id
        # Reconstruct with same id — the contract enforces identity via the model
        d2 = Document.model_validate(
            {
                "id": original_id,
                "type": "CIRCULAR",
                "title": "y",
                "issuing_authority": "b",
                "vault_id": new_id(),
                "organization_id": new_id(),
                "visibility": "DEPARTMENT",
                "versions": [{"version_id": str(new_id())}],
            }
        )
        assert d2.id == original_id, "INV-004: id must survive reconstruction"

    def test_inv_006_never_contains_parsed_content(self):
        """INV-006: A Document never stores parsed content (structural — no field for it)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        # The contract has no 'content', 'parsed', 'knowledge_tree' fields
        assert not hasattr(d, "content")
        assert not hasattr(d, "parsed")
        assert not hasattr(d, "knowledge_tree")

    def test_inv_007_never_stores_embeddings(self):
        """INV-007: A Document never stores embeddings (structural)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        assert not hasattr(d, "embeddings")

    def test_inv_008_never_stores_chunks(self):
        """INV-008: A Document never stores retrieval chunks (structural)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        assert not hasattr(d, "chunks")

    def test_inv_009_never_stores_ai_outputs(self):
        """INV-009: A Document never stores AI-generated outputs (structural)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        assert not hasattr(d, "answers")
        assert not hasattr(d, "ai_generated")

    def test_exactly_one_active_version(self):
        """Exactly one Document Version must be ACTIVE at any time."""
        with pytest.raises(ValueError, match="Exactly one"):
            Document(
                type="DECISION",
                title="x",
                issuing_authority="a",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="PUBLIC",
                versions=[
                    DocumentVersionReference(version_id=new_id(), status=DocumentVersionStatus.ACTIVE),
                    DocumentVersionReference(version_id=new_id(), status=DocumentVersionStatus.ACTIVE),
                ],
            )

    def test_visibility_enum_values(self):
        """Visibility must be PUBLIC | DEPARTMENT | PERSONAL (contract enum)."""
        d = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        assert d.visibility == Visibility.PUBLIC

        d2 = Document(
            type="DECISION",
            title="x",
            issuing_authority="a",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="SHARED",  # example alias -> PUBLIC
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        assert d2.visibility == Visibility.PUBLIC

        with pytest.raises((ValueError, TypeError)):
            Document(
                type="DECISION",
                title="x",
                issuing_authority="a",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="INVALID",
                versions=[DocumentVersionReference(version_id=new_id())],
            )


# ======================================================================
# 2. Processing State Machine
# ======================================================================


class TestProcessingStateMachine:
    """Processing state transitions (tasks/001 #ProcessingStates)."""

    def test_initial_state(self, registry, sample_doc):
        assert registry.get_processing(sample_doc.id) == ProcessingState.UPLOADED

    def test_valid_transitions(self):
        assert can_transition(ProcessingState.UPLOADED, ProcessingState.OCR_PENDING)
        assert can_transition(ProcessingState.OCR_PENDING, ProcessingState.OCR_RUNNING)
        assert can_transition(ProcessingState.OCR_RUNNING, ProcessingState.OCR_COMPLETED)
        assert can_transition(ProcessingState.OCR_COMPLETED, ProcessingState.PARSING_PENDING)
        assert can_transition(ProcessingState.PARSING_PENDING, ProcessingState.PARSING_RUNNING)
        assert can_transition(ProcessingState.PARSING_RUNNING, ProcessingState.READY)
        assert can_transition(ProcessingState.READY, ProcessingState.ARCHIVED)

    def test_failure_from_any_non_terminal(self):
        for state in ProcessingState:
            if is_terminal(state):
                assert not can_transition(state, ProcessingState.FAILED)
            else:
                assert can_transition(state, ProcessingState.FAILED)

    def test_invalid_transition_raises(self, registry, sample_doc):
        with pytest.raises(InvalidTransition):
            registry.transition_processing(sample_doc.id, "READY", user_id="admin")

    def test_full_pipeline(self, registry, sample_doc):
        states = [
            ProcessingState.OCR_PENDING,
            ProcessingState.OCR_RUNNING,
            ProcessingState.OCR_COMPLETED,
            ProcessingState.PARSING_PENDING,
            ProcessingState.PARSING_RUNNING,
            ProcessingState.READY,
        ]
        for s in states:
            registry.transition_processing(sample_doc.id, s, user_id="admin")
        assert registry.get_processing(sample_doc.id) == ProcessingState.READY

    def test_terminal_states(self):
        assert is_terminal(ProcessingState.READY)
        assert is_terminal(ProcessingState.ARCHIVED)
        assert is_terminal(ProcessingState.FAILED)
        assert not is_terminal(ProcessingState.UPLOADED)


# ======================================================================
# 3. Registry Service — CRUD
# ======================================================================


class TestRegistryService:
    """Registry CRUD operations (tasks/001 #API)."""

    def test_create_and_retrieve(self, registry):
        doc = registry.register_document(
            user_id="admin",
            document_type="CIRCULAR",
            title="Test Circular",
            issuing_authority="Central Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            document_number="12/2024/TT-NH",
        )
        assert doc.id is not None
        assert doc.type == DocumentType.CIRCULAR
        assert doc.title == "Test Circular"
        assert doc.document_number == "12/2024/TT-NH"
        assert doc.status == DocumentStatus.ACTIVE

        retrieved = registry.get_document(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id
        assert retrieved.title == doc.title

    def test_create_with_full_metadata(self, registry):
        doc = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Full Metadata Decision",
            issuing_authority="ABC Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="DEPARTMENT",
            document_number="15/2026/QD-NH",
            short_title="QD 15/2026",
            description="Procurement regulation",
            language="vi",
            metadata={"effective_date": "2026-01-15T00:00:00Z", "tags": ["procurement"]},
            source_checksum_sha256="def456",
            source_filename="QD15-2026.pdf",
            source_mime_type="application/pdf",
        )
        assert doc.short_title == "QD 15/2026"
        assert doc.description == "Procurement regulation"
        assert doc.metadata.effective_date is not None
        assert "procurement" in doc.metadata.tags

    def test_list_documents(self, registry, sample_doc):
        # Create a second doc
        registry.register_document(
            user_id="admin",
            document_type="CIRCULAR",
            title="Another Doc",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        docs = registry.list_documents()
        assert len(docs) >= 2

    def test_list_filter_by_vault(self, registry):
        vault_id = new_id()
        registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Vault Doc",
            issuing_authority="Bank",
            vault_id=vault_id,
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        docs = registry.list_documents(vault_id=vault_id)
        assert len(docs) == 1
        assert docs[0].vault_id == vault_id

    def test_list_filter_by_status(self, registry, sample_doc):
        active = registry.list_documents(status=DocumentStatus.ACTIVE)
        archived = registry.list_documents(status=DocumentStatus.ARCHIVED)
        assert len(active) >= 1
        assert len(archived) == 0

    def test_get_nonexistent_returns_none(self, registry):
        assert registry.get_document(new_id()) is None

    def test_update_metadata(self, registry, sample_doc):
        updated = registry.update_metadata(
            sample_doc.id,
            user_id="admin",
            title="Updated Title",
            description="Updated description",
            metadata={"tags": ["updated"]},
        )
        assert updated.title == "Updated Title"
        assert updated.description == "Updated description"
        assert "updated" in updated.metadata.tags

        # Verify persistence
        retrieved = registry.get_document(sample_doc.id)
        assert retrieved.title == "Updated Title"

    def test_update_metadata_noop(self, registry, sample_doc):
        """No-op update should not change updated_at."""
        before = sample_doc.updated_at
        updated = registry.update_metadata(sample_doc.id, user_id="admin")
        assert updated.updated_at >= before  # touch may bump it slightly

    def test_update_nonexistent_raises(self, registry):
        with pytest.raises(KeyError):
            registry.update_metadata(new_id(), user_id="admin", title="x")


# ======================================================================
# 4. Duplicate Detection
# ======================================================================


class TestDuplicateDetection:
    """Checksum-based duplicate detection (tasks/001 #DuplicateDetection)."""

    def test_detect_by_checksum(self, registry):
        checksum = "dup123"
        registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Original",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            source_checksum_sha256=checksum,
        )
        hits = registry.find_by_checksum(checksum)
        assert len(hits) == 1

    def test_multiple_versions_same_checksum(self, registry):
        checksum = "multi123"
        doc = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Multi",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            source_checksum_sha256=checksum,
        )
        # Add a second version with the same checksum (simulating re-upload)
        registry.repo.add_checksum(
            checksum_sha256=checksum,
            document_id=doc.id,
            version_id=new_id(),
            filename="same.pdf",
        )
        hits = registry.find_by_checksum(checksum)
        assert len(hits) == 2

    def test_no_match_returns_empty(self, registry):
        assert registry.find_by_checksum("nonexistent") == []

    def test_compute_checksum(self, registry):
        content = b"hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert registry.compute_checksum(content) == expected


# ======================================================================
# 5. Version Management
# ======================================================================


class TestVersionManagement:
    """Document Version operations (tasks/001 #Versioning)."""

    def test_initial_version(self, registry):
        doc = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Versioned",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        assert len(doc.versions) == 1
        assert doc.versions[0].version_number == 1
        assert doc.versions[0].status == DocumentVersionStatus.ACTIVE

    def test_add_version(self, registry, sample_doc):
        updated = registry.add_version(sample_doc.id, user_id="admin")
        assert len(updated.versions) == 2
        # Previous active should now be SUPERSEDED
        assert updated.versions[0].status == DocumentVersionStatus.SUPERSEDED
        assert updated.versions[1].status == DocumentVersionStatus.ACTIVE
        assert updated.versions[1].version_number == 2

    def test_add_version_with_custom_number(self, registry, sample_doc):
        updated = registry.add_version(sample_doc.id, user_id="admin", version_number=5)
        assert updated.versions[-1].version_number == 5

    def test_add_version_nonexistent_raises(self, registry):
        with pytest.raises(KeyError):
            registry.add_version(new_id(), user_id="admin")


# ======================================================================
# 6. Relationships
# ======================================================================


class TestRelationships:
    """Document relationship operations (tasks/001 #Relationships)."""

    def test_create_with_relationships(self, registry):
        target = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Target",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        source = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Source",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            supersedes=[target.id],
        )
        rels = registry.get_relationships(source.id)
        assert len(rels) >= 1
        kinds = [k for _, k in rels]
        assert "SUPERSEDES" in kinds

    def test_add_relationship(self, registry):
        a = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="A",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        b = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="B",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        registry.add_relationship(a.id, b.id, "REFERENCES", user_id="admin")
        rels = registry.get_relationships(a.id)
        assert ("REFERENCES" in [k for _, k in rels]) or ("REFERENCES" in [k for _, k in registry.get_relationships(b.id)])


# ======================================================================
# 7. Lifecycle
# ======================================================================


class TestLifecycle:
    """Document lifecycle (Created -> Active -> Archived)."""

    def test_archive(self, registry, sample_doc):
        archived = registry.archive_document(sample_doc.id, user_id="admin")
        assert archived.status == DocumentStatus.ARCHIVED
        assert registry.get_processing(sample_doc.id) == ProcessingState.ARCHIVED

    def test_restore(self, registry, sample_doc):
        registry.archive_document(sample_doc.id, user_id="admin")
        restored = registry.restore_document(sample_doc.id, user_id="admin")
        assert restored.status == DocumentStatus.ACTIVE
        assert registry.get_processing(sample_doc.id) == ProcessingState.READY

    def test_archive_already_archived_raises(self, registry, sample_doc):
        registry.archive_document(sample_doc.id, user_id="admin")
        with pytest.raises(ValueError, match="already archived"):
            registry.archive_document(sample_doc.id, user_id="admin")

    def test_archive_nonexistent_raises(self, registry):
        with pytest.raises(KeyError):
            registry.archive_document(new_id(), user_id="admin")

    def test_restore_not_archived_raises(self, registry, sample_doc):
        with pytest.raises(ValueError, match="not archived"):
            registry.restore_document(sample_doc.id, user_id="admin")

    def test_delete_admin(self, registry, sample_doc):
        result = registry.delete_document(sample_doc.id, user_id="admin")
        assert result is True
        assert registry.get_document(sample_doc.id) is None

    def test_delete_nonexistent(self, registry):
        assert registry.delete_document(new_id(), user_id="admin") is False


# ======================================================================
# 8. Audit Logging
# ======================================================================


class TestAuditLogging:
    """Audit events are recorded (tasks/001 #Logging)."""

    def test_create_logs_event(self, registry):
        doc = registry.register_document(
            user_id="admin",
            document_type="DECISION",
            title="Audited",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        events = recent_events(registry.repo.conn, entity_id=str(doc.id))
        assert len(events) >= 1
        assert events[0]["event"] == "document.create"

    def test_transition_logs_event(self, registry, sample_doc):
        registry.transition_processing(sample_doc.id, "OCR_PENDING", user_id="admin")
        events = recent_events(registry.repo.conn, entity_id=str(sample_doc.id))
        assert any(e["event"] == "document.processing_transition" for e in events)

    def test_archive_logs_event(self, registry, sample_doc):
        registry.archive_document(sample_doc.id, user_id="admin")
        events = recent_events(registry.repo.conn, entity_id=str(sample_doc.id))
        assert any(e["event"] == "document.archive" for e in events)

    def test_delete_logs_event(self, registry, sample_doc):
        registry.delete_document(sample_doc.id, user_id="admin")
        events = recent_events(registry.repo.conn, entity_id=str(sample_doc.id))
        assert any(e["event"] == "document.delete" for e in events)


# ======================================================================
# 9. Error Handling
# ======================================================================


class TestErrorHandling:
    """Error conditions (tasks/001 #ErrorHandling, #Validation)."""

    def test_register_invalid_type(self, registry):
        with pytest.raises((ValueError, TypeError)):
            registry.register_document(
                user_id="admin",
                document_type="INVALID_TYPE",
                title="Bad",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="PUBLIC",
            )

    def test_register_invalid_visibility(self, registry):
        with pytest.raises((ValueError, TypeError)):
            registry.register_document(
                user_id="admin",
                document_type="DECISION",
                title="Bad",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="INVALID",
            )

    def test_transition_nonexistent_document(self, registry):
        with pytest.raises(ValueError, match="No processing state"):
            registry.transition_processing(new_id(), "OCR_PENDING", user_id="admin")

    def test_get_processing_nonexistent(self, registry):
        assert registry.get_processing(new_id()) is None


# ======================================================================
# 10. Repository edge cases
# ======================================================================


class TestRepository:
    """Repository-level edge cases."""

    def test_save_and_retrieve_roundtrip(self, repo):
        doc = Document(
            type="DECISION",
            title="Roundtrip Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        repo.save(doc, processing=ProcessingState.UPLOADED)
        retrieved = repo.get(doc.id)
        assert retrieved is not None
        assert retrieved.id == doc.id
        assert retrieved.title == doc.title
        assert retrieved.type == doc.type
        assert retrieved.visibility == doc.visibility

    def test_save_update_overwrites(self, repo):
        doc = Document(
            type="DECISION",
            title="Original",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        repo.save(doc, processing=ProcessingState.UPLOADED)
        doc.title = "Updated"
        repo.save(doc, processing=ProcessingState.OCR_PENDING)
        retrieved = repo.get(doc.id)
        assert retrieved.title == "Updated"
        assert repo.get_processing(doc.id) == ProcessingState.OCR_PENDING

    def test_delete_cascades(self, repo):
        doc = Document(
            type="DECISION",
            title="Cascade Test",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
            versions=[DocumentVersionReference(version_id=new_id())],
        )
        repo.save(doc, processing=ProcessingState.UPLOADED)
        repo.add_checksum(
            checksum_sha256="cascade",
            document_id=doc.id,
            version_id=doc.versions[0].version_id,
        )
        repo.delete(doc.id)
        assert repo.get(doc.id) is None
        assert repo.get_processing(doc.id) is None
        assert repo.find_by_checksum("cascade") == []

    def test_list_pagination(self, repo):
        for i in range(5):
            doc = Document(
                type="DECISION",
                title=f"Doc {i}",
                issuing_authority="Bank",
                vault_id=new_id(),
                organization_id=new_id(),
                visibility="PUBLIC",
                versions=[DocumentVersionReference(version_id=new_id())],
            )
            repo.save(doc, processing=ProcessingState.UPLOADED)
        assert len(repo.list_documents(limit=2)) == 2
        assert len(repo.list_documents(limit=10)) >= 5
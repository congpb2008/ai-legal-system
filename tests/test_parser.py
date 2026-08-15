"""Tests for the Parser (Task 004).

Covers:
    - Knowledge Tree Contract invariants
    - Vietnamese legal document parsing (Chapters, Articles, Clauses, Points)
    - Parser engine hierarchy detection
    - Full parsing pipeline (OCR → Parser → Knowledge Tree)
    - State machine transitions (OCR_COMPLETED → PARSING_PENDING → PARSING_RUNNING → READY)
    - Source location preservation
    - Error handling
    - Knowledge Tree persistence and retrieval

The authoritative source is the Knowledge Tree Contract (02-contracts/knowledge-tree-contract.md)
and the Parser specification (tasks/004-parser.md).
"""

import io
from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.contracts.knowledge_tree import (
    KnowledgeTree,
    Node,
    NodeType,
)
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.ocr_service.models import (
    OcrConfidence,
    OcrLine,
    OcrPage,
    OcrResult,
)
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.parser.engine import (
    LegalRegexParser,
    ParserEngineError,
    ParserSection,
    SectionType,
)
from legal_platform.modules.parser.service import ParserService
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def parser_service():
    return ParserService()


@pytest.fixture
def registered_document(parser_service):
    """Register a document in the Registry and put it in OCR_COMPLETED state."""
    from legal_platform.contracts.common import new_id as _nid
    svc = UploadService(registry=parser_service.registry)
    result = svc.upload(
        user_id="admin",
        content=b"%PDF-1.4\n%%EOF",
        filename="doc.pdf",
        document_type="DECISION",
        title="Test Document",
        issuing_authority="ABC Bank",
        vault_id=_nid(),
        organization_id=_nid(),
        visibility="PUBLIC",
    )
    # Transition to OCR_COMPLETED
    parser_service.registry.transition_processing(
        result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
    )
    parser_service.registry.transition_processing(
        result.document_id, ProcessingState.OCR_RUNNING, user_id="admin",
    )
    parser_service.registry.transition_processing(
        result.document_id, ProcessingState.OCR_COMPLETED, user_id="admin",
    )
    return result.document_id, result.storage_ref


@pytest.fixture
def simple_legal_text() -> OcrResult:
    """A simple Vietnamese legal document OCR result."""
    lines = [
        OcrLine(text="Căn cứ Luật Ngân hàng Nhà nước số 46/2010/QH12;"),
        OcrLine(text="Theo đề nghị của Thống đốc Ngân hàng Nhà nước;"),
        OcrLine(text=""),
        OcrLine(text="Chương I"),
        OcrLine(text="QUY ĐỊNH CHUNG"),
        OcrLine(text=""),
        OcrLine(text="Điều 1. Phạm vi điều chỉnh"),
        OcrLine(text="Quy chế này quy định việc mua sắm máy chủ phục vụ hạ tầng công nghệ thông tin."),
        OcrLine(text=""),
        OcrLine(text="Điều 2. Đối tượng áp dụng"),
        OcrLine(text="1. Áp dụng đối với toàn bộ đơn vị trực thuộc Khối Công nghệ Thông tin."),
        OcrLine(text="2. Không áp dụng đối với các thiết bị văn phòng thông thường."),
        OcrLine(text=""),
        OcrLine(text="Chương II"),
        OcrLine(text="QUY ĐỊNH CỤ THỂ"),
        OcrLine(text=""),
        OcrLine(text="Điều 3. Yêu cầu về cấu hình máy chủ"),
        OcrLine(text="a) Bộ vi xử lý từ 16 nhân trở lên."),
        OcrLine(text="b) RAM tối thiểu 64GB."),
        OcrLine(text="c) Ổ cứng SSD dung lượng tối thiểu 2TB."),
        OcrLine(text=""),
        OcrLine(text="Phụ lục I"),
        OcrLine(text="DANH MỤC CẤU HÌNH MÁY CHỦ"),
    ]
    return OcrResult(
        document_id=new_id(),
        version_id=new_id(),
        pages=[
            OcrPage(page_number=1, lines=lines, text="\n".join(l.text for l in lines)),
        ],
        confidence=OcrConfidence(page_average=0.98, page_min=0.95, engine="test"),
        total_pages=1,
    )


@pytest.fixture
def digital_pdf_bytes() -> bytes:
    """A minimal digital PDF with legal text (ASCII-safe for PyMuPDF extraction)."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Article 1. Scope of regulation", fontsize=12)
    page.insert_text((50, 80), "This regulation governs server procurement.", fontsize=12)
    page.insert_text((50, 120), "Article 2. Subjects of application", fontsize=12)
    page.insert_text((50, 150), "1. Applies to all IT department units.", fontsize=12)
    page.insert_text((50, 180), "2. Does not apply to standard office equipment.", fontsize=12)
    data = doc.write()
    doc.close()
    return data


# ======================================================================
# 1. Knowledge Tree Contract Invariants
# ======================================================================


class TestKnowledgeTreeContract:
    """Knowledge Tree Contract invariants (knowledge-tree-contract.md)."""

    def test_inv_001_exactly_one_root(self):
        """INV-001: Exactly one Root Node exists."""
        root_id = new_id()
        tree = KnowledgeTree(
            document_version_id=new_id(),
            parser_version="test",
            root={"node_id": root_id},
            nodes=[
                Node(id=root_id, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1),
                Node(id=new_id(), type=NodeType.ARTICLE, parent={"node_id": root_id}, source={"page": 1}, page_start=1, page_end=1),
            ],
        )
        assert tree is not None

    def test_inv_002_every_node_has_parent_except_root(self):
        """INV-002: Every node has exactly one parent except the Root Node."""
        root_id = new_id()
        with pytest.raises((ValueError, TypeError)):
            KnowledgeTree(
                document_version_id=new_id(),
                parser_version="test",
                root={"node_id": root_id},
                nodes=[
                    Node(id=root_id, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1),
                    Node(id=new_id(), type=NodeType.ARTICLE, parent=None, source={"page": 1}, page_start=1, page_end=1),
                ],
            )

    def test_inv_003_globally_unique_ids(self):
        """INV-003: Node identifiers are globally unique."""
        dup_id = new_id()
        with pytest.raises((ValueError, TypeError)):
            KnowledgeTree(
                document_version_id=new_id(),
                parser_version="test",
                root={"node_id": dup_id},
                nodes=[
                    Node(id=dup_id, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1),
                    Node(id=dup_id, type=NodeType.ARTICLE, parent={"node_id": dup_id}, source={"page": 1}, page_start=1, page_end=1),
                ],
            )

    def test_inv_008_no_chunks(self):
        """INV-008: Knowledge Trees never contain chunks (structural)."""
        rid = new_id()
        tree = KnowledgeTree(
            document_version_id=new_id(),
            parser_version="test",
            root={"node_id": rid},
            nodes=[Node(id=rid, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1)],
        )
        assert not hasattr(tree, "chunks")

    def test_inv_009_no_embeddings(self):
        """INV-009: Knowledge Trees never contain embeddings (structural)."""
        rid = new_id()
        tree = KnowledgeTree(
            document_version_id=new_id(),
            parser_version="test",
            root={"node_id": rid},
            nodes=[Node(id=rid, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1)],
        )
        assert not hasattr(tree, "embeddings")

    def test_inv_010_no_ai_text(self):
        """INV-010: Knowledge Trees never contain AI-generated text (structural)."""
        rid = new_id()
        tree = KnowledgeTree(
            document_version_id=new_id(),
            parser_version="test",
            root={"node_id": rid},
            nodes=[Node(id=rid, type=NodeType.DOCUMENT, source={"page": 1}, page_start=1, page_end=1)],
        )
        assert not hasattr(tree, "ai_generated")


# ======================================================================
# 2. Parser Engine — Hierarchy Detection
# ======================================================================


class TestParserEngine:
    """Parser engine hierarchy detection (tasks/004 #HierarchyDetection)."""

    def test_detects_chapter(self):
        parser = LegalRegexParser()
        section = parser._classify_line("Chương I. QUY ĐỊNH CHUNG", 1, 1)
        assert section is not None
        assert section.section_type == SectionType.CHAPTER
        assert section.number == "I"

    def test_detects_article(self):
        parser = LegalRegexParser()
        section = parser._classify_line("Điều 1. Phạm vi điều chỉnh", 1, 1)
        assert section is not None
        assert section.section_type == SectionType.ARTICLE
        assert section.number == "1"

    def test_detects_clause(self):
        parser = LegalRegexParser()
        section = parser._classify_line("1. Áp dụng đối với toàn bộ đơn vị.", 1, 1)
        assert section is not None
        assert section.section_type == SectionType.CLAUSE
        assert section.number == "1"

    def test_detects_point(self):
        parser = LegalRegexParser()
        section = parser._classify_line("a) Bộ vi xử lý từ 16 nhân trở lên.", 1, 1)
        assert section is not None
        assert section.section_type == SectionType.POINT
        assert section.number == "a"

    def test_detects_appendix(self):
        parser = LegalRegexParser()
        section = parser._classify_line("Phụ lục I. DANH MỤC CẤU HÌNH", 1, 1)
        assert section is not None
        assert section.section_type == SectionType.APPENDIX
        assert section.number == "I"

    def test_continuation_text_returns_none(self):
        parser = LegalRegexParser()
        section = parser._classify_line("Đây là văn bản tiếp tục không phải tiêu đề.", 1, 1)
        assert section is None

    def test_builds_hierarchy(self, simple_legal_text):
        parser = LegalRegexParser()
        output = parser.parse(
            ocr_result=simple_legal_text,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert len(output.sections) >= 1
        root = output.sections[0]
        assert root.section_type == SectionType.DOCUMENT
        assert len(root.children) >= 2  # preamble + chapters + appendix

    def test_preserves_original_wording(self, simple_legal_text):
        parser = LegalRegexParser()
        output = parser.parse(
            ocr_result=simple_legal_text,
            document_id=new_id(),
            version_id=new_id(),
        )
        # The preamble text should be captured somewhere in the output
        all_text = ""
        for section in output.sections:
            all_text += section.text + " "
            for child in section.children:
                all_text += child.text + " "
        assert "Căn cứ Luật" in all_text


# ======================================================================
# 3. Full Parsing Pipeline
# ======================================================================


class TestParsingPipeline:
    """Full parsing pipeline (OCR → Parser → Knowledge Tree)."""

    def test_parse_ocr_result_creates_tree(self, parser_service, registered_document, simple_legal_text):
        """Parsing an OCR result should produce a valid Knowledge Tree."""
        doc_id, _ = registered_document
        tree = parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        assert tree is not None
        assert tree.statistics.node_count > 0
        assert tree.parser_version == "parser-1.0.0"

    def test_tree_has_correct_structure(self, parser_service, registered_document, simple_legal_text):
        """The Knowledge Tree should reflect the document hierarchy."""
        doc_id, _ = registered_document
        tree = parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        # Should have articles
        articles = [n for n in tree.nodes if n.type == NodeType.ARTICLE]
        assert len(articles) >= 2

        # Should have clauses
        clauses = [n for n in tree.nodes if n.type == NodeType.CLAUSE]
        assert len(clauses) >= 2

        # Should have points
        points = [n for n in tree.nodes if n.type == NodeType.POINT]
        assert len(points) >= 3

    def test_tree_preserves_source_locations(self, parser_service, registered_document, simple_legal_text):
        """Every node should have source location information."""
        doc_id, _ = registered_document
        tree = parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        for node in tree.nodes:
            assert node.source is not None
            assert node.source.page >= 1

    def test_tree_preserves_original_text(self, parser_service, registered_document, simple_legal_text):
        """Original wording should be preserved in the tree."""
        doc_id, _ = registered_document
        tree = parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        # Find Article 1
        articles = [n for n in tree.nodes if n.type == NodeType.ARTICLE]
        assert len(articles) >= 1
        # Article 1 should have its title
        assert any("Phạm vi" in (a.title or "") for a in articles)

    def test_tree_persistence(self, parser_service, registered_document, simple_legal_text):
        """Knowledge Trees should be storable and retrievable."""
        doc_id, _ = registered_document
        tree = parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        retrieved = parser_service.get_tree(tree.id)
        assert retrieved is not None
        assert retrieved.id == tree.id
        assert retrieved.statistics.node_count == tree.statistics.node_count

    def test_audit_logged(self, parser_service, registered_document, simple_legal_text):
        """Parsing completion should be audit-logged."""
        doc_id, _ = registered_document
        parser_service.parse_ocr_result(
            simple_legal_text,
            document_id=doc_id,
            version_id=simple_legal_text.version_id,
        )
        events = recent_events(parser_service.registry.repo.conn, entity_id=str(doc_id))
        parser_events = [e for e in events if e["event"] == "parser.complete"]
        assert len(parser_events) >= 1


# ======================================================================
# 4. End-to-end: Upload → OCR → Parse
# ======================================================================


class TestEndToEnd:
    """End-to-end pipeline: Upload → OCR → Parse."""

    def test_full_pipeline(self, parser_service, digital_pdf_bytes):
        """Upload a PDF, OCR it, parse it — should produce a valid Knowledge Tree."""
        # Upload
        upload_svc = UploadService(registry=parser_service.registry)
        upload_result = upload_svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="regulation.pdf",
            document_type="DECISION",
            title="Test Regulation",
            issuing_authority="ABC Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )

        # OCR
        ocr_svc = OcrService(registry=parser_service.registry)
        ocr_svc.registry.transition_processing(
            upload_result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )
        ocr_result = ocr_svc.process_bytes(
            upload_result.document_id, digital_pdf_bytes, user_id="admin",
        )

        # Parse
        tree = parser_service.parse_ocr_result(
            ocr_result,
            document_id=upload_result.document_id,
            version_id=ocr_result.version_id,
        )

        # Verify
        assert tree is not None
        assert tree.statistics.node_count > 0
        assert tree.parser_version == "parser-1.0.0"

        # The parser detects Vietnamese patterns; English text is captured as preamble
        # Verify nodes exist and source locations are preserved
        assert len(tree.nodes) >= 1
        for node in tree.nodes:
            assert node.source is not None
            assert node.source.page >= 1

        # Verify state transition
        state = parser_service.registry.get_processing(upload_result.document_id)
        assert state == ProcessingState.PARSING_RUNNING

    def test_tree_retrievable_by_version(self, parser_service, digital_pdf_bytes):
        """Knowledge Tree should be retrievable by document version ID."""
        upload_svc = UploadService(registry=parser_service.registry)
        upload_result = upload_svc.upload(
            user_id="admin",
            content=digital_pdf_bytes,
            filename="retrievable.pdf",
            document_type="DECISION",
            title="Retrievable",
            issuing_authority="Bank",
            vault_id=new_id(),
            organization_id=new_id(),
            visibility="PUBLIC",
        )
        ocr_svc = OcrService(registry=parser_service.registry)
        ocr_svc.registry.transition_processing(
            upload_result.document_id, ProcessingState.OCR_PENDING, user_id="admin",
        )
        ocr_result = ocr_svc.process_bytes(
            upload_result.document_id, digital_pdf_bytes, user_id="admin",
        )
        tree = parser_service.parse_ocr_result(
            ocr_result,
            document_id=upload_result.document_id,
            version_id=ocr_result.version_id,
        )

        retrieved = parser_service.get_tree_for_version(ocr_result.version_id)
        assert retrieved is not None
        assert retrieved.id == tree.id


# ======================================================================
# 5. Error Handling
# ======================================================================


class TestParserErrorHandling:
    """Error conditions (tasks/004 #ErrorHandling)."""

    def test_parse_nonexistent_document_raises(self, parser_service, simple_legal_text):
        with pytest.raises(ValueError, match="not found"):
            parser_service.parse_ocr_result(
                simple_legal_text,
                document_id=new_id(),
                version_id=new_id(),
            )

    def test_get_nonexistent_tree(self, parser_service):
        assert parser_service.get_tree(new_id()) is None

    def test_get_tree_for_nonexistent_version(self, parser_service):
        assert parser_service.get_tree_for_version(new_id()) is None


# ======================================================================
# 6. Parser Engine Edge Cases
# ======================================================================


class TestParserEdgeCases:
    """Parser edge cases and robustness."""

    def test_empty_ocr_result(self):
        parser = LegalRegexParser()
        ocr_result = OcrResult(
            document_id=new_id(),
            version_id=new_id(),
            pages=[],
            confidence=OcrConfidence(page_average=0, page_min=0, engine="test"),
            total_pages=0,
        )
        output = parser.parse(
            ocr_result=ocr_result,
            document_id=new_id(),
            version_id=new_id(),
        )
        assert len(output.sections) == 1  # just the document root
        assert output.sections[0].section_type == SectionType.DOCUMENT

    def test_unknown_structure_becomes_unknown(self):
        parser = LegalRegexParser()
        ocr_result = OcrResult(
            document_id=new_id(),
            version_id=new_id(),
            pages=[
                OcrPage(
                    page_number=1,
                    lines=[OcrLine(text="Some random unstructured text")],
                    text="Some random unstructured text",
                ),
            ],
            confidence=OcrConfidence(page_average=0, page_min=0, engine="test"),
            total_pages=1,
        )
        output = parser.parse(
            ocr_result=ocr_result,
            document_id=new_id(),
            version_id=new_id(),
        )
        # The text should be captured as preamble or in the document root
        all_text = ""
        for section in output.sections:
            all_text += section.text + " "
            for child in section.children:
                all_text += child.text + " "
        assert "random unstructured" in all_text

    def test_deterministic_output(self, simple_legal_text):
        """Same input should produce identical output."""
        parser = LegalRegexParser()
        output1 = parser.parse(
            ocr_result=simple_legal_text,
            document_id=new_id(),
            version_id=new_id(),
        )
        output2 = parser.parse(
            ocr_result=simple_legal_text,
            document_id=new_id(),
            version_id=new_id(),
        )
        # Section types should be the same
        types1 = [s.section_type for s in output1.sections]
        types2 = [s.section_type for s in output2.sections]
        assert types1 == types2

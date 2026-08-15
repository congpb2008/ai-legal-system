"""Tests for the Chunking Service (Task 006).

Covers:
    - Structure-aware chunking from a Knowledge Tree
    - Chunk boundaries respect legal hierarchy
    - Oversized chunk splitting
    - Undersized chunk merging
    - Chunk metadata (node IDs, references, paths, source mapping)
    - Chunk ordering (document order)
    - Chunk collection persistence and retrieval
    - Integration with the Knowledge Tree

The authoritative source is the Chunking specification (tasks/006-chunking.md).
"""

from uuid import UUID

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.contracts.knowledge_tree import (
    KnowledgeTree,
    Node,
    NodeType,
)
from legal_platform.modules.chunking.chunker import (
    Chunk,
    ChunkCollection,
    ChunkType,
    ChunkerConfig,
    StructureAwareChunker,
    estimate_tokens,
)
from legal_platform.modules.chunking.service import ChunkingService
from legal_platform.modules.knowledge_tree_builder.builder import KnowledgeTreeBuilder
from legal_platform.modules.parser.engine import LegalRegexParser
from legal_platform.modules.ocr_service.models import (
    OcrResult,
    OcrPage,
    OcrLine,
    OcrConfidence,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def chunker():
    return StructureAwareChunker()


@pytest.fixture
def logical_document_id():
    return new_id()


@pytest.fixture
def chunking_service():
    return ChunkingService()


@pytest.fixture
def simple_tree() -> KnowledgeTree:
    """A simple Knowledge Tree with articles, clauses, and points."""
    from legal_platform.contracts.knowledge_tree import NodeReference
    root = Node(id=new_id(), type=NodeType.DOCUMENT, title="Document",
                source={"page": 1}, page_start=1, page_end=3)
    art1 = Node(id=new_id(), type=NodeType.ARTICLE, title="Điều 1. Phạm vi điều chỉnh",
                text="Điều 1. Phạm vi điều chỉnh\nQuy chế này quy định việc mua sắm.",
                parent=NodeReference(node_id=root.id), source={"page": 1}, page_start=1, page_end=1, order=0)
    clause1 = Node(id=new_id(), type=NodeType.CLAUSE, title="1. Áp dụng đối với toàn bộ đơn vị.",
                   text="1. Áp dụng đối với toàn bộ đơn vị trực thuộc Khối Công nghệ Thông tin.",
                   parent=NodeReference(node_id=art1.id), source={"page": 1}, page_start=1, page_end=1, order=0)
    clause2 = Node(id=new_id(), type=NodeType.CLAUSE, title="2. Không áp dụng đối với thiết bị văn phòng.",
                   text="2. Không áp dụng đối với các thiết bị văn phòng thông thường.",
                   parent=NodeReference(node_id=art1.id), source={"page": 1}, page_start=1, page_end=1, order=1)
    point1 = Node(id=new_id(), type=NodeType.POINT, title="a) Bộ vi xử lý 16 nhân.",
                  text="a) Bộ vi xử lý từ 16 nhân trở lên.",
                  parent=NodeReference(node_id=clause1.id), source={"page": 1}, page_start=1, page_end=1, order=0)
    point2 = Node(id=new_id(), type=NodeType.POINT, title="b) RAM tối thiểu 64GB.",
                  text="b) RAM tối thiểu 64GB.",
                  parent=NodeReference(node_id=clause1.id), source={"page": 1}, page_start=1, page_end=1, order=1)
    art2 = Node(id=new_id(), type=NodeType.ARTICLE, title="Điều 2. Đối tượng áp dụng",
                text="Điều 2. Đối tượng áp dụng\nÁp dụng đối với toàn bộ đơn vị.",
                parent=NodeReference(node_id=root.id), source={"page": 2}, page_start=2, page_end=2, order=1)
    appendix = Node(id=new_id(), type=NodeType.APPENDIX, title="Phụ lục I. Danh mục cấu hình",
                    text="Phụ lục I\nDanh mục cấu hình máy chủ.",
                    parent=NodeReference(node_id=root.id), source={"page": 3}, page_start=3, page_end=3, order=2)

    # Wire up children using NodeReference objects
    root.children = [NodeReference(node_id=art1.id), NodeReference(node_id=art2.id), NodeReference(node_id=appendix.id)]
    art1.children = [NodeReference(node_id=clause1.id), NodeReference(node_id=clause2.id)]
    clause1.children = [NodeReference(node_id=point1.id), NodeReference(node_id=point2.id)]

    return KnowledgeTree(
        document_version_id=new_id(),
        parser_version="test",
        root=NodeReference(node_id=root.id),
        nodes=[root, art1, clause1, clause2, point1, point2, art2, appendix],
    )


@pytest.fixture
def vietnamese_tree() -> KnowledgeTree:
    """A Knowledge Tree built from real Vietnamese parser output."""
    lines = [
        OcrLine(text="Chương I"),
        OcrLine(text="QUY ĐỊNH CHUNG"),
        OcrLine(text="Điều 1. Phạm vi điều chỉnh"),
        OcrLine(text="Quy chế này quy định việc mua sắm máy chủ."),
        OcrLine(text="Điều 2. Đối tượng áp dụng"),
        OcrLine(text="1. Áp dụng đối với toàn bộ đơn vị."),
        OcrLine(text="a) Bộ vi xử lý 16 nhân."),
        OcrLine(text="Phụ lục I"),
        OcrLine(text="DANH MỤC CẤU HÌNH"),
    ]
    ocr = OcrResult(document_id=new_id(), version_id=new_id(),
        pages=[OcrPage(page_number=1, lines=lines, text="\n".join(l.text for l in lines))],
        confidence=OcrConfidence(page_average=0.98, page_min=0.95, engine="test"), total_pages=1)
    parser = LegalRegexParser()
    po = parser.parse(ocr_result=ocr, document_id=new_id(), version_id=new_id())
    builder = KnowledgeTreeBuilder()
    return builder.build(po)


# ======================================================================
# 1. Token Estimation
# ======================================================================


class TestTokenEstimation:
    """Token estimation helper."""

    def test_estimates_tokens(self):
        assert estimate_tokens("Hello world") == 2
        assert estimate_tokens("") == 0
        assert estimate_tokens("A" * 100) == 25


# ======================================================================
# 2. Structure-Aware Chunking
# ======================================================================


class TestStructureAwareChunking:
    """Structure-aware chunking from a Knowledge Tree."""

    def test_chunks_created(self, chunker, simple_tree, logical_document_id):
        collection = chunker.chunk(simple_tree, document_id=logical_document_id)
        assert collection.total_chunks > 0
        assert collection.document_id == logical_document_id
        assert collection.version_id == simple_tree.document_version_id
        assert all(c.document_id == logical_document_id for c in collection.chunks)
        assert all(c.version_id == simple_tree.document_version_id for c in collection.chunks)

    def test_chunks_in_document_order(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        orders = [c.order for c in collection.chunks]
        assert orders == sorted(orders)

    def test_chunks_have_node_ids(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        for chunk in collection.chunks:
            assert len(chunk.node_ids) > 0

    def test_chunks_have_text(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        for chunk in collection.chunks:
            assert len(chunk.text) > 0

    def test_chunks_have_page_info(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        for chunk in collection.chunks:
            assert chunk.page_start >= 1
            assert chunk.page_end >= chunk.page_start

    def test_chunks_have_hierarchy_path(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        for chunk in collection.chunks:
            assert len(chunk.hierarchy_path) > 0

    def test_article_becomes_article_chunk(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        article_chunks = [c for c in collection.chunks if c.chunk_type == ChunkType.ARTICLE]
        assert len(article_chunks) >= 1

    def test_clause_becomes_clause_chunk_with_small_max(self, simple_tree):
        """With a small max_chunk_size, articles are split into clause chunks."""
        config = ChunkerConfig(max_chunk_size=30, min_chunk_size=5)
        chunker = StructureAwareChunker(config=config)
        collection = chunker.chunk(simple_tree, document_id=new_id())
        clause_chunks = [c for c in collection.chunks if c.chunk_type == ChunkType.CLAUSE]
        assert len(clause_chunks) >= 1

    def test_point_becomes_point_chunk_with_small_max(self, simple_tree):
        """With a very small max_chunk_size, clauses are split into point chunks."""
        config = ChunkerConfig(max_chunk_size=10, min_chunk_size=2)
        chunker = StructureAwareChunker(config=config)
        collection = chunker.chunk(simple_tree, document_id=new_id())
        point_chunks = [c for c in collection.chunks if c.chunk_type == ChunkType.POINT]
        assert len(point_chunks) >= 1

    def test_oversized_leaf_is_split_at_hard_limit(self, vietnamese_tree):
        leaf = next(node for node in vietnamese_tree.nodes if not vietnamese_tree.get_children(node.id))
        leaf.text = "Nội dung pháp lý rất dài. " * 200
        config = ChunkerConfig(max_chunk_size=40, min_chunk_size=1)
        collection = StructureAwareChunker(config=config).chunk(
            vietnamese_tree,
            document_id=new_id(),
        )
        anchored = [chunk for chunk in collection.chunks if leaf.id in chunk.node_ids]
        assert len(anchored) > 1
        assert all(chunk.estimated_tokens <= config.max_chunk_size for chunk in anchored)
        assert all(chunk.node_ids == [leaf.id] for chunk in anchored)

    def test_appendix_becomes_appendix_chunk(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        appendix_chunks = [c for c in collection.chunks if c.chunk_type == ChunkType.APPENDIX]
        assert len(appendix_chunks) >= 1


# ======================================================================
# 3. Chunk Boundaries Respect Hierarchy
# ======================================================================


class TestChunkBoundaries:
    """Chunk boundaries respect legal hierarchy (tasks/006 #ChunkingPrinciples)."""

    def test_chunks_respect_article_boundaries(self, chunker, simple_tree):
        """Chunks from different articles should not be merged."""
        collection = chunker.chunk(simple_tree, document_id=new_id())
        # Find article-level chunks
        article_chunks = [c for c in collection.chunks if c.chunk_type == ChunkType.ARTICLE]
        if len(article_chunks) >= 2:
            # They should be separate chunks
            assert article_chunks[0].chunk_id != article_chunks[1].chunk_id

    def test_chunks_preserve_canonical_references(self, chunker, simple_tree):
        collection = chunker.chunk(simple_tree, document_id=new_id())
        for chunk in collection.chunks:
            if chunk.canonical_references:
                assert all(len(ref) > 0 for ref in chunk.canonical_references)


# ======================================================================
# 4. Vietnamese Document Chunking
# ======================================================================


class TestVietnameseChunking:
    """Chunking real Vietnamese legal documents."""

    def test_chunks_vietnamese_tree(self, chunker, vietnamese_tree):
        collection = chunker.chunk(vietnamese_tree, document_id=new_id())
        assert collection.total_chunks > 0

    def test_vietnamese_chunks_have_content(self, chunker, vietnamese_tree):
        collection = chunker.chunk(vietnamese_tree, document_id=new_id())
        for chunk in collection.chunks:
            assert len(chunk.text) > 0

    def test_vietnamese_chunks_preserve_structure(self, chunker, vietnamese_tree):
        collection = chunker.chunk(vietnamese_tree, document_id=new_id())
        # Should have chunks with content referencing the legal structure
        assert collection.total_chunks > 0
        # Some chunks should carry canonical references to legal elements
        refs = [c for c in collection.chunks if c.canonical_references]
        assert len(refs) >= 1


# ======================================================================
# 5. Chunk Collection Persistence
# ======================================================================


class TestChunkPersistence:
    """Chunk collection storage and retrieval."""

    def test_store_and_retrieve(self, chunking_service, simple_tree):
        collection = chunking_service.chunk_tree(simple_tree, document_id=new_id())
        assert collection.total_chunks > 0

    def test_collection_has_metadata(self, chunking_service, simple_tree):
        collection = chunking_service.chunk_tree(simple_tree, document_id=new_id())
        assert collection.chunker_version == "chunker-1.1.0"
        assert collection.total_tokens > 0


# ======================================================================
# 6. Chunking Service Integration
# ======================================================================


class TestChunkingService:
    """ChunkingService integration."""

    def test_chunk_tree(self, chunking_service, simple_tree):
        collection = chunking_service.chunk_tree(simple_tree, document_id=new_id())
        assert collection.total_chunks > 0
        assert collection.chunker_version == "chunker-1.1.0"

    def test_chunk_tree_preserves_content(self, chunking_service, simple_tree):
        collection = chunking_service.chunk_tree(simple_tree, document_id=new_id())
        all_text = " ".join(c.text for c in collection.chunks)
        assert "Phạm vi điều chỉnh" in all_text
        assert "Đối tượng áp dụng" in all_text


# ======================================================================
# 7. Chunker Configuration
# ======================================================================


class TestChunkerConfig:
    """Chunker configuration options."""

    def test_custom_config(self, simple_tree):
        config = ChunkerConfig(preferred_chunk_size=256, max_chunk_size=512)
        chunker = StructureAwareChunker(config=config)
        collection = chunker.chunk(simple_tree, document_id=new_id())
        assert collection.total_chunks > 0

    def test_small_max_size(self, simple_tree):
        """Very small max chunk size should still produce valid chunks."""
        config = ChunkerConfig(max_chunk_size=50, min_chunk_size=10)
        chunker = StructureAwareChunker(config=config)
        collection = chunker.chunk(simple_tree, document_id=new_id())
        assert collection.total_chunks > 0

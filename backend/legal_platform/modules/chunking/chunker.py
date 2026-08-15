"""Structure-aware chunker for legal documents (tasks/006-chunking.md).

The chunker converts a validated Knowledge Tree into retrieval-ready chunks.
Knowledge Tree boundaries always take priority over token limits.

Chunking principles (per spec):
    1. Knowledge Tree boundaries
    2. Legal meaning
    3. Token size

Token limits never override legal hierarchy unless absolutely necessary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc
from legal_platform.contracts.knowledge_tree import KnowledgeTree, Node, NodeType


class ChunkType(str, Enum):
    """Type of chunk (tasks/006 #ChunkTypes)."""

    ARTICLE = "ARTICLE"
    CLAUSE = "CLAUSE"
    POINT = "POINT"
    APPENDIX = "APPENDIX"
    COMPOSITE = "COMPOSITE"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    PARAGRAPH = "PARAGRAPH"
    PREAMBLE = "PREAMBLE"


@dataclass
class Chunk:
    """A single retrieval chunk derived from the Knowledge Tree."""

    chunk_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    chunk_type: ChunkType = ChunkType.PARAGRAPH
    node_ids: list[UUID] = field(default_factory=list)
    canonical_references: list[str] = field(default_factory=list)
    text: str = ""
    estimated_tokens: int = 0
    hierarchy_path: str = ""
    page_start: int = 1
    page_end: int = 1
    order: int = 0
    source_mapping: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class ChunkCollection:
    """A collection of chunks for one document version.

    Fields:
        chunks: ordered list of chunks in document order.
        document_id: the document.
        version_id: the document version.
        chunker_version: version of the chunker that produced this.
        created_at: when the collection was created.
        statistics: summary statistics.
    """

    chunks: list[Chunk] = field(default_factory=list)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    chunker_version: str = "chunker-1.1.0"
    created_at: datetime = field(default_factory=now_utc)

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)

    @property
    def total_tokens(self) -> int:
        return sum(c.estimated_tokens for c in self.chunks)


@dataclass
class ChunkerConfig:
    """Configuration for the chunker.

    Fields:
        preferred_chunk_size: target token count per chunk.
        max_chunk_size: hard maximum token count.
        min_chunk_size: minimum token count (merge below this).
        max_overlap: maximum overlap tokens between chunks.
        merge_threshold: token count below which siblings are merged.
    """

    preferred_chunk_size: int = 512
    max_chunk_size: int = 1024
    min_chunk_size: int = 50
    max_overlap: int = 0
    merge_threshold: int = 100


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a simple heuristic: ~4 characters per token for Vietnamese/English.
    This is a rough estimate; a proper tokenizer can be swapped in later.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Structure-Aware Chunker
# ---------------------------------------------------------------------------


class StructureAwareChunker:
    """Structure-aware chunker that respects Knowledge Tree boundaries.

    Strategy (per tasks/006 #ChunkingPrinciples):
        1. Traverse the Knowledge Tree depth-first.
        2. Create chunks at preferred boundaries (Article > Clause > Point).
        3. If a chunk exceeds max_chunk_size, split at the next level down.
        4. If a chunk is below min_chunk_size, merge with adjacent siblings.
        5. Never merge chunks from different Articles.
    """

    CHUNKER_VERSION = "chunker-1.1.0"

    # Node types that are preferred chunk boundaries, in priority order
    _PREFERRED_BOUNDARIES: dict[NodeType, ChunkType] = {
        NodeType.ARTICLE: ChunkType.ARTICLE,
        NodeType.CLAUSE: ChunkType.CLAUSE,
        NodeType.POINT: ChunkType.POINT,
        NodeType.APPENDIX: ChunkType.APPENDIX,
        NodeType.CHAPTER: ChunkType.CHAPTER,
        NodeType.SECTION: ChunkType.SECTION,
        NodeType.PARAGRAPH: ChunkType.PARAGRAPH,
    }

    def __init__(self, config: "ChunkerConfig | None" = None):
        self.config = config or ChunkerConfig()

    def chunk(
        self,
        tree: KnowledgeTree,
        *,
        document_id: UUID,
    ) -> ChunkCollection:
        """Convert a Knowledge Tree into a chunk collection.

        Args:
            tree: the validated Knowledge Tree to chunk.
            document_id: the logical document that owns the version represented
                by ``tree``.  A Knowledge Tree intentionally contains only its
                version ID, so callers must provide the distinct document ID.

        Returns:
            A ``ChunkCollection`` with chunks in document order.
        """
        chunks: list[Chunk] = []
        order = 0

        # Traverse the tree depth-first, starting from root's children
        root = tree.get_node(tree.root.node_id)
        if root is None:
            return ChunkCollection(
                document_id=document_id,
                version_id=tree.document_version_id,
                chunker_version=self.CHUNKER_VERSION,
            )

        for child in tree.get_children(root.id):
            child_chunks = self._chunk_node(
                child,
                tree,
                order,
                document_id=document_id,
            )
            chunks.extend(child_chunks)
            order += len(child_chunks)

        # Merge undersized chunks
        chunks = self._merge_undersized(chunks, tree)

        return ChunkCollection(
            chunks=chunks,
            document_id=document_id,
            version_id=tree.document_version_id,
            chunker_version=self.CHUNKER_VERSION,
        )

    def _chunk_node(
        self,
        node: Node,
        tree: KnowledgeTree,
        start_order: int,
        *,
        document_id: UUID,
    ) -> list[Chunk]:
        """Convert a single node into chunks.

        If the node is a preferred boundary type, it becomes a chunk.
        If it's too large, it's split by children.
        If it has no children, it becomes a single chunk.
        """
        chunk_type = self._node_to_chunk_type(node.type)
        node_text = self._build_node_text(node, tree)
        token_count = estimate_tokens(node_text)
        children = tree.get_children(node.id)

        # Build canonical reference
        from legal_platform.modules.knowledge_tree_builder.references import (
            CanonicalReferenceGenerator,
            PathGenerator,
        )
        ref = CanonicalReferenceGenerator.generate(node, tree.nodes)
        path = PathGenerator.generate(node, tree.nodes)

        # If the node fits within max size, create a single chunk.
        if token_count <= self.config.max_chunk_size:
            chunk = Chunk(
                document_id=document_id,
                version_id=tree.document_version_id,
                chunk_type=chunk_type,
                node_ids=[node.id],
                canonical_references=[ref] if ref else [],
                text=node_text,
                estimated_tokens=token_count,
                hierarchy_path=path,
                page_start=node.page_start,
                page_end=node.page_end,
                order=start_order,
            )
            return [chunk]

        # A parser leaf can still contain a large unstructured paragraph (for
        # example, extracted PDF text).  The configured maximum is a hard
        # embedding contract, so split oversized leaves on a nearby textual
        # boundary while retaining the same canonical source anchor.
        if not children:
            parts = self._split_oversized_text(node_text)
            return [
                Chunk(
                    document_id=document_id,
                    version_id=tree.document_version_id,
                    chunk_type=chunk_type,
                    node_ids=[node.id],
                    canonical_references=[ref] if ref else [],
                    text=part,
                    estimated_tokens=estimate_tokens(part),
                    hierarchy_path=path,
                    page_start=node.page_start,
                    page_end=node.page_end,
                    order=start_order + index,
                )
                for index, part in enumerate(parts)
            ]

        # Node is too large and has children — split by children
        chunks: list[Chunk] = []
        order = start_order
        for child in children:
            child_chunks = self._chunk_node(
                child,
                tree,
                order,
                document_id=document_id,
            )
            chunks.extend(child_chunks)
            order += len(child_chunks)

        return chunks

    def _split_oversized_text(self, text: str) -> list[str]:
        """Split unstructured leaf text without exceeding max_chunk_size.

        The token estimator defines the chunking contract, so four characters
        per configured token is the corresponding hard character ceiling.
        Prefer paragraph, line, sentence, clause, then word boundaries; only a
        single overlong token is hard-sliced.
        """
        max_chars = max(1, self.config.max_chunk_size * 4)
        remaining = text.strip()
        parts: list[str] = []
        while len(remaining) > max_chars:
            window = remaining[:max_chars]
            minimum = max_chars // 2
            cut = 0
            for boundary in ("\n\n", "\n", ". ", "; ", ", ", " "):
                candidate = window.rfind(boundary, minimum)
                if candidate >= minimum:
                    cut = candidate + len(boundary.rstrip())
                    break
            if cut <= 0:
                cut = max_chars
            part = remaining[:cut].strip()
            if part:
                parts.append(part)
            remaining = remaining[cut:].lstrip()
        if remaining:
            parts.append(remaining)
        return parts

    def _build_node_text(self, node: Node, tree: KnowledgeTree) -> str:
        """Build the text content for a chunk from a node.

        Includes the node's title and text, plus the text of all descendants
        (for composite chunks that preserve context).
        """
        parts: list[str] = []
        if node.title:
            parts.append(node.title)
        if node.text and node.text != node.title:
            parts.append(node.text)

        # For leaf nodes, include only their own content
        children = tree.get_children(node.id)
        if not children:
            return "\n".join(parts)

        # For parent nodes, include children's content
        for child in children:
            child_text = self._build_node_text(child, tree)
            if child_text:
                parts.append(child_text)

        return "\n".join(parts)

    def _merge_undersized(
        self, chunks: list[Chunk], tree: KnowledgeTree
    ) -> list[Chunk]:
        """Merge undersized chunks with adjacent siblings.

        Rules (per tasks/006 #UndersizedChunks):
            - Same Parent (same article/chapter context)
            - Same Legal Context
            - Within Token Budget

        Chunks from different Articles shall never be merged.
        Only merge non-structural chunks (PARAGRAPH, PREAMBLE, COMPOSITE).
        ARTICLE, CLAUSE, POINT, CHAPTER, SECTION, APPENDIX chunks are
        never merged — they represent meaningful legal boundaries.
        """
        if len(chunks) <= 1:
            return chunks

        # Structural chunk types that should never be merged
        structural = {ChunkType.ARTICLE, ChunkType.CLAUSE, ChunkType.POINT,
                      ChunkType.CHAPTER, ChunkType.SECTION, ChunkType.APPENDIX}

        merged: list[Chunk] = []
        i = 0
        while i < len(chunks):
            current = chunks[i]

            # Never merge structural chunks
            if current.chunk_type in structural:
                merged.append(current)
                i += 1
                continue

            # Try to merge with next chunk if current is undersized
            if (
                current.estimated_tokens < self.config.merge_threshold
                and i + 1 < len(chunks)
            ):
                next_chunk = chunks[i + 1]

                # Only merge if they share the same parent context
                if self._same_parent_context(current, next_chunk):
                    combined_tokens = current.estimated_tokens + next_chunk.estimated_tokens
                    if combined_tokens <= self.config.max_chunk_size:
                        merged_chunk = self._merge_two(current, next_chunk)
                        merged.append(merged_chunk)
                        i += 2
                        continue

            merged.append(current)
            i += 1

        return merged

    @staticmethod
    def _same_parent_context(a: Chunk, b: Chunk) -> bool:
        """Check if two chunks share the same parent context.

        They share context if their hierarchy paths have the same prefix
        (same parent path).
        """
        a_parts = a.hierarchy_path.split(".")
        b_parts = b.hierarchy_path.split(".")
        # Same parent = same path except the last segment
        return a_parts[:-1] == b_parts[:-1]

    @staticmethod
    def _merge_two(a: Chunk, b: Chunk) -> Chunk:
        """Merge two adjacent chunks into one."""
        return Chunk(
            chunk_id=uuid4(),
            document_id=a.document_id,
            version_id=a.version_id,
            chunk_type=ChunkType.COMPOSITE,
            node_ids=a.node_ids + b.node_ids,
            canonical_references=a.canonical_references + b.canonical_references,
            text=a.text + "\n" + b.text if a.text and b.text else (a.text or b.text),
            estimated_tokens=a.estimated_tokens + b.estimated_tokens,
            hierarchy_path=a.hierarchy_path,
            page_start=min(a.page_start, b.page_start),
            page_end=max(a.page_end, b.page_end),
            order=a.order,
        )

    @staticmethod
    def _node_to_chunk_type(node_type: NodeType) -> ChunkType:
        """Map a Knowledge Node type to a Chunk type."""
        mapping = {
            NodeType.DOCUMENT: ChunkType.COMPOSITE,
            NodeType.CHAPTER: ChunkType.CHAPTER,
            NodeType.SECTION: ChunkType.SECTION,
            NodeType.ARTICLE: ChunkType.ARTICLE,
            NodeType.CLAUSE: ChunkType.CLAUSE,
            NodeType.POINT: ChunkType.POINT,
            NodeType.PARAGRAPH: ChunkType.PARAGRAPH,
            NodeType.APPENDIX: ChunkType.APPENDIX,
            NodeType.TABLE: ChunkType.COMPOSITE,
            NodeType.FIGURE: ChunkType.COMPOSITE,
            NodeType.UNKNOWN: ChunkType.PARAGRAPH,
        }
        return mapping.get(node_type, ChunkType.PARAGRAPH)

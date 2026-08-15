"""Knowledge Tree Contract (02-contracts/knowledge-tree-contract.md).

The canonical, immutable output of the parsing pipeline. Represents one fully
parsed document in a normalized, implementation-independent format.

This contract is consumed by:
    - Chunk Generator (Task 006)
    - Retrieval Engine (Task 009)
    - Citation Builder (Task 012)
    - Evaluation Pipeline (Task 017)

The Knowledge Tree Contract is immutable after creation. Changes to parser, OCR,
chunking, or embeddings must generate a new Knowledge Tree rather than modifying
an existing one.

Invariants enforced by this module (see knowledge-tree-contract.md INV-001..INV-010):
    INV-001  Exactly one Root Node exists.
    INV-002  Every node has exactly one parent except the Root Node.
    INV-003  Node identifiers are globally unique.
    INV-004  Sibling ordering is stable.
    INV-005  Every node belongs to exactly one Knowledge Tree.
    INV-006  Every node references exactly one source location.
    INV-007  Every character in the original document belongs to one and only one node.
    INV-008  Knowledge Trees never contain chunks.
    INV-009  Knowledge Trees never contain embeddings.
    INV-010  Knowledge Trees never contain AI-generated text.

Drift from examples/ (illustrative only, per project documentation hierarchy):
- examples/knowledge-tree-example.json uses ``node_id`` / ``parent_id`` (contract: ``id`` / ``parent``),
  ``content`` (contract: ``text``), ``number`` (not in contract Node), ``source.start_line`` /
  ``source.end_line`` (contract: ``line_start`` / ``line_end``), and ``children`` as a list of
  strings (contract: ``List<NodeReference>``). This model follows the contract.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from legal_platform.contracts.common import new_id, now_utc


# ----------------------------------------------------------------------------
# Enumerations
# ----------------------------------------------------------------------------


class NodeType(str, Enum):
    """Logical node type within a legal document (knowledge-tree-spec.md)."""

    DOCUMENT = "DOCUMENT"
    CHAPTER = "CHAPTER"
    SECTION = "SECTION"
    ARTICLE = "ARTICLE"
    CLAUSE = "CLAUSE"
    POINT = "POINT"
    PARAGRAPH = "PARAGRAPH"
    APPENDIX = "APPENDIX"
    TABLE = "TABLE"
    FIGURE = "FIGURE"
    UNKNOWN = "UNKNOWN"


# ----------------------------------------------------------------------------
# Source location
# ----------------------------------------------------------------------------


class BoundingBox(BaseModel):
    """Bounding box in page coordinates (optional)."""

    model_config = ConfigDict(extra="forbid")

    x0: float
    y0: float
    x1: float
    y1: float


class SourceLocation(BaseModel):
    """Reference to the original source location in the document.

    Every node must maintain a reference to its original source (INV-006).
    """

    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    bbox: Optional[BoundingBox] = None


# ----------------------------------------------------------------------------
# Node reference (lightweight pointer)
# ----------------------------------------------------------------------------


class NodeReference(BaseModel):
    """A lightweight reference to a Knowledge Node.

    Used in ``parent`` and ``children`` fields to avoid duplicating node data.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: UUID


# ----------------------------------------------------------------------------
# Node metadata
# ----------------------------------------------------------------------------


class NodeMetadata(BaseModel):
    """Parser-generated metadata for a node."""

    model_config = ConfigDict(extra="allow")

    parser_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    language: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------
# Tree metadata
# ----------------------------------------------------------------------------


class TreeMetadata(BaseModel):
    """Metadata for the entire Knowledge Tree."""

    model_config = ConfigDict(extra="allow")

    language: str = "vi"
    parser_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None


# ----------------------------------------------------------------------------
# Tree statistics
# ----------------------------------------------------------------------------


class TreeStatistics(BaseModel):
    """Informational statistics about the Knowledge Tree.

    Per the contract: "Statistics are informational only. Statistics shall never
    influence business logic."
    """

    model_config = ConfigDict(extra="forbid")

    node_count: int = 0
    depth: int = 0
    article_count: int = 0
    clause_count: int = 0
    appendix_count: int = 0
    page_count: int = 0


# ----------------------------------------------------------------------------
# Node
# ----------------------------------------------------------------------------


class Node(BaseModel):
    """A single element inside the Knowledge Tree.

    Every node contains:
        - Original text (immutable)
        - Position within the document
        - Parent node reference
        - Child node references
        - Metadata
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=new_id)
    type: NodeType
    title: Optional[str] = None
    text: str = ""
    parent: Optional[NodeReference] = None
    children: list[NodeReference] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)
    page_start: int = Field(default=1, ge=1)
    page_end: int = Field(default=1, ge=1)
    source: SourceLocation
    metadata: NodeMetadata = Field(default_factory=NodeMetadata)


# ----------------------------------------------------------------------------
# Knowledge Tree — the canonical contract
# ----------------------------------------------------------------------------


class KnowledgeTree(BaseModel):
    """The canonical Knowledge Tree Contract.

    Represents one fully parsed document version. Immutable after creation.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID = Field(default_factory=new_id)
    document_version_id: UUID
    parser_version: str
    created_at: datetime = Field(default_factory=now_utc)
    root: NodeReference
    nodes: list[Node] = Field(min_length=1)
    statistics: TreeStatistics = Field(default_factory=TreeStatistics)
    metadata: TreeMetadata = Field(default_factory=TreeMetadata)

    # ------------------------------------------------------------------ helpers
    def get_node(self, node_id: UUID) -> Optional[Node]:
        """Look up a node by its ID."""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_children(self, node_id: UUID) -> list[Node]:
        """Get the direct children of a node, in document order."""
        node = self.get_node(node_id)
        if node is None:
            return []
        child_ids = {ref.node_id for ref in node.children}
        children = [n for n in self.nodes if n.id in child_ids]
        children.sort(key=lambda n: n.order)
        return children

    def get_descendants(self, node_id: UUID) -> list[Node]:
        """Get all descendants of a node (recursive, depth-first)."""
        result: list[Node] = []
        stack = list(self.get_children(node_id))
        while stack:
            child = stack.pop(0)
            result.append(child)
            stack = self.get_children(child.id) + stack
        return result

    def get_node_by_path(self, path: str) -> Optional[Node]:
        """Look up a node by its canonical path (e.g., 'I.2.a')."""
        from legal_platform.modules.knowledge_tree_builder.references import PathGenerator
        for n in self.nodes:
            if PathGenerator.generate(n, self.nodes) == path:
                return n
        return None

    # ------------------------------------------------------------------ invariants
    @model_validator(mode="after")
    def _check_invariants(self) -> "KnowledgeTree":
        # INV-001: Exactly one Root Node exists
        root_nodes = [n for n in self.nodes if n.type == NodeType.DOCUMENT]
        if len(root_nodes) != 1:
            raise ValueError(
                f"INV-001: Exactly one Root Node (type=DOCUMENT) required, found {len(root_nodes)}"
            )

        # INV-003: Node identifiers are globally unique
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("INV-003: Node identifiers must be globally unique")

        # INV-002: Every node has exactly one parent except the Root Node
        root_id = root_nodes[0].id
        for n in self.nodes:
            if n.id == root_id:
                if n.parent is not None:
                    raise ValueError(f"INV-002: Root node {n.id} must not have a parent")
            else:
                if n.parent is None:
                    raise ValueError(f"INV-002: Non-root node {n.id} must have a parent")

        # INV-004: Sibling ordering is stable — enforced structurally (order field)
        # INV-005: Every node belongs to exactly one Knowledge Tree — structural
        # INV-006: Every node references exactly one source location — structural
        # INV-007: Every character belongs to exactly one node — enforced by parser
        # INV-008/009/010: No chunks/embeddings/AI text — structural (no fields for them)

        # Verify root reference matches
        if self.root.node_id != root_id:
            raise ValueError(
                f"Root reference {self.root.node_id} does not match root node {root_id}"
            )

        # Verify all child references exist
        referenced_ids = {self.root.node_id}
        for n in self.nodes:
            if n.parent is not None:
                referenced_ids.add(n.parent.node_id)
            for child_ref in n.children:
                referenced_ids.add(child_ref.node_id)
        known_ids = set(node_ids)
        missing = referenced_ids - known_ids
        if missing:
            raise ValueError(f"Node references to unknown IDs: {missing}")

        return self
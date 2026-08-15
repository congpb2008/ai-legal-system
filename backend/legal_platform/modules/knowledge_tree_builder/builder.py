"""Knowledge Tree Builder (tasks/005-knowledge-tree-builder.md).

The Knowledge Tree Builder transforms parsed structural elements into a validated
Knowledge Tree Contract. It:

    - Builds Knowledge Nodes
    - Constructs parent-child relationships
    - Generates Node IDs
    - Generates canonical references
    - Generates node paths
    - Generates node depth
    - Preserves ordering
    - Validates tree integrity

The Builder does NOT:
    - Perform OCR, parse raw text, rewrite content, generate embeddings,
      chunk documents, retrieve documents, or generate answers.

This module is the bridge between the Parser (Task 004) and the Knowledge Layer.
It consumes ``ParserOutput`` and produces a validated ``KnowledgeTree``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from legal_platform.contracts.common import new_id, now_utc
from legal_platform.contracts.knowledge_tree import (
    KnowledgeTree,
    Node,
    NodeMetadata,
    NodeReference,
    NodeType,
    SourceLocation,
    TreeMetadata,
    TreeStatistics,
)
from legal_platform.modules.knowledge_tree_builder.references import (
    CanonicalReferenceGenerator,
    PathGenerator,
)
from legal_platform.modules.parser.engine import (
    ParserOutput,
    ParserSection,
    SectionType,
)


class TreeValidationError(ValueError):
    """Raised when a Knowledge Tree fails validation."""

    def __init__(self, message: str, report: "ValidationReport | None" = None):
        self.report = report
        super().__init__(message)


@dataclass
class ValidationReport:
    """Report of tree validation results (tasks/005 #TreeValidation)."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class BuilderMetadata:
    """Metadata about the build operation (tasks/005 #Metadata)."""

    builder_version: str
    created_at: datetime
    document_id: UUID
    version_id: UUID
    node_count: int
    max_depth: int


class KnowledgeTreeBuilder:
    """The Knowledge Tree Builder.

    Consumes ``ParserOutput`` (from Task 004) and produces a validated,
    canonical ``KnowledgeTree`` (per the Knowledge Tree Contract).
    """

    BUILDER_VERSION = "builder-1.0.0"

    def __init__(self):
        self._node_counter = 0
        self._warnings: list[str] = []

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def build(self, parser_output: ParserOutput) -> KnowledgeTree:
        """Build a validated Knowledge Tree from parser output.

        Args:
            parser_output: the parser output (Task 004) to transform.

        Returns:
            A validated, canonical ``KnowledgeTree``.

        Raises:
            TreeValidationError: if the resulting tree fails validation.
        """
        self._node_counter = 0
        self._warnings = []

        # Build nodes
        nodes: list[Node] = []
        root_section = parser_output.sections[0] if parser_output.sections else None
        if root_section is None:
            raise TreeValidationError("Parser produced no sections")

        # If the first section is not a DOCUMENT, wrap it
        if root_section.section_type != SectionType.DOCUMENT:
            root_section = ParserSection(
                section_type=SectionType.DOCUMENT,
                title="Document",
                page_start=1,
                page_end=root_section.page_end,
                children=[root_section],
            )

        root_id = self._build_node_recursive(
            section=root_section,
            parent_id=None,
            order=0,
            depth=0,
            nodes=nodes,
        )

        # Compute statistics
        stats = self._compute_statistics(nodes, root_id)

        # Build tree
        tree = KnowledgeTree(
            document_version_id=parser_output.version_id,
            parser_version=parser_output.parser_version,
            root=NodeReference(node_id=root_id),
            nodes=nodes,
            statistics=stats,
            metadata=TreeMetadata(
                language="vi",
                parser_confidence=0.95,
                warnings=self._warnings,
            ),
        )

        # Validate tree integrity
        report = self.validate(tree)
        if not report.valid:
            raise TreeValidationError(
                "Knowledge Tree failed validation: " + "; ".join(report.errors),
                report=report,
            )

        return tree

    # ------------------------------------------------------------------
    # Node construction
    # ------------------------------------------------------------------

    def _build_node_recursive(
        self,
        *,
        section: ParserSection,
        parent_id: Optional[UUID],
        order: int,
        depth: int,
        nodes: list[Node],
    ) -> UUID:
        """Recursively build a node and its children from a parser section."""
        node_id = new_id()
        self._node_counter += 1

        node_type = self._section_to_node_type(section.section_type)

        node = Node(
            id=node_id,
            type=node_type,
            title=section.title,
            text=section.text,
            parent=NodeReference(node_id=parent_id) if parent_id else None,
            order=order,
            page_start=section.page_start,
            page_end=section.page_end,
            source=SourceLocation(
                page=section.page_start,
                line_start=section.line_start,
                line_end=section.line_end,
            ),
            metadata=NodeMetadata(
                parser_confidence=0.95,
                language="vi",
            ),
        )
        nodes.append(node)

        # Build children
        child_order = 0
        for child in section.children:
            child_id = self._build_node_recursive(
                section=child,
                parent_id=node_id,
                order=child_order,
                depth=depth + 1,
                nodes=nodes,
            )
            node.children.append(NodeReference(node_id=child_id))
            child_order += 1

        return node_id

    @staticmethod
    def _section_to_node_type(section_type: SectionType) -> NodeType:
        """Map a ParserSection type to a Knowledge Node type."""
        mapping = {
            SectionType.DOCUMENT: NodeType.DOCUMENT,
            SectionType.CHAPTER: NodeType.CHAPTER,
            SectionType.SECTION: NodeType.SECTION,
            SectionType.ARTICLE: NodeType.ARTICLE,
            SectionType.CLAUSE: NodeType.CLAUSE,
            SectionType.POINT: NodeType.POINT,
            SectionType.PARAGRAPH: NodeType.PARAGRAPH,
            SectionType.APPENDIX: NodeType.APPENDIX,
            SectionType.TABLE: NodeType.TABLE,
            SectionType.FIGURE: NodeType.FIGURE,
            SectionType.PREAMBLE: NodeType.PARAGRAPH,
            SectionType.UNKNOWN: NodeType.UNKNOWN,
        }
        return mapping.get(section_type, NodeType.UNKNOWN)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def _compute_statistics(self, nodes: list[Node], root_id: UUID) -> TreeStatistics:
        """Compute informational statistics for the tree."""
        depth_map: dict[UUID, int] = {}
        for node in nodes:
            if node.id == root_id:
                depth_map[node.id] = 0
            elif node.parent:
                depth_map[node.id] = depth_map.get(node.parent.node_id, 0) + 1

        return TreeStatistics(
            node_count=len(nodes),
            depth=max(depth_map.values(), default=0),
            article_count=sum(1 for n in nodes if n.type == NodeType.ARTICLE),
            clause_count=sum(1 for n in nodes if n.type == NodeType.CLAUSE),
            appendix_count=sum(1 for n in nodes if n.type == NodeType.APPENDIX),
            page_count=max((n.page_end for n in nodes), default=1),
        )

    # ------------------------------------------------------------------
    # Canonical references & paths
    # ------------------------------------------------------------------

    def get_canonical_reference(self, tree: KnowledgeTree, node_id: UUID) -> str:
        """Get the canonical reference for a node in a built tree."""
        node = tree.get_node(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found in tree")
        return CanonicalReferenceGenerator.generate(node, tree.nodes)

    def get_path(self, tree: KnowledgeTree, node_id: UUID) -> str:
        """Get the deterministic path for a node in a built tree."""
        node = tree.get_node(node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found in tree")
        return PathGenerator.generate(node, tree.nodes)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, tree: KnowledgeTree) -> ValidationReport:
        """Validate the integrity of a Knowledge Tree.

        Checks (per tasks/005 #TreeValidation):
            - One root node
            - No cycles
            - No orphan nodes
            - Unique Node IDs
            - Unique paths
            - Valid parent references
            - Valid canonical references
            - Nodes ordered correctly

        Returns a ``ValidationReport``. Note: the KnowledgeTree model already
        enforces some invariants (INV-001..010) at construction; this adds
        deeper structural checks.
        """
        errors: list[str] = []
        warnings: list[str] = []

        node_map = {n.id: n for n in tree.nodes}

        # 1. Exactly one root (type=DOCUMENT, no parent)
        roots = [n for n in tree.nodes if n.type == NodeType.DOCUMENT]
        if len(roots) != 1:
            errors.append(f"Expected exactly 1 root (DOCUMENT), found {len(roots)}")
        else:
            root = roots[0]
            if root.parent is not None:
                errors.append("Root node must not have a parent")

        # 2. No cycles (walk from root, track visited)
        if roots:
            visited: set[UUID] = set()
            stack = [roots[0].id]
            while stack:
                current = stack.pop()
                if current in visited:
                    errors.append(f"Cycle detected at node {current}")
                    break
                visited.add(current)
                node = node_map.get(current)
                if node:
                    for child_ref in node.children:
                        stack.append(child_ref.node_id)

            # 3. No orphan nodes (every node reachable from root)
            orphans = [n.id for n in tree.nodes if n.id not in visited]
            if orphans:
                errors.append(f"Orphan nodes (not reachable from root): {orphans}")

        # 4. Unique Node IDs (also enforced by contract, double-check)
        ids = [n.id for n in tree.nodes]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate node IDs detected")

        # 5. Valid parent references
        for n in tree.nodes:
            if n.parent is not None and n.parent.node_id not in node_map:
                errors.append(f"Node {n.id} has invalid parent reference {n.parent.node_id}")

        # 6. Valid child references
        for n in tree.nodes:
            for child_ref in n.children:
                if child_ref.node_id not in node_map:
                    errors.append(f"Node {n.id} has invalid child reference {child_ref.node_id}")

        # 7. Unique canonical references (within document)
        refs_seen: dict[str, UUID] = {}
        for n in tree.nodes:
            ref = CanonicalReferenceGenerator.generate(n, tree.nodes)
            if ref and ref in refs_seen:
                warnings.append(
                    f"Duplicate canonical reference '{ref}' for nodes {refs_seen[ref]} and {n.id}"
                )
            elif ref:
                refs_seen[ref] = n.id

        # 8. Unique paths
        paths_seen: dict[str, UUID] = {}
        for n in tree.nodes:
            path = PathGenerator.generate(n, tree.nodes)
            if path in paths_seen:
                warnings.append(f"Duplicate path '{path}' for nodes {paths_seen[path]} and {n.id}")
            else:
                paths_seen[path] = n.id

        # 9. Node ordering (children ordered by 'order' field)
        for n in tree.nodes:
            if n.children:
                child_ids = [c.node_id for c in n.children]
                child_orders = [node_map[c].order for c in child_ids if c in node_map]
                if child_orders != sorted(child_orders):
                    warnings.append(f"Children of node {n.id} are not in ascending order")

        return ValidationReport(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Builder metadata
    # ------------------------------------------------------------------

    def get_metadata(
        self,
        *,
        document_id: UUID,
        version_id: UUID,
        tree: KnowledgeTree,
    ) -> BuilderMetadata:
        """Return metadata about the build operation."""
        return BuilderMetadata(
            builder_version=self.BUILDER_VERSION,
            created_at=now_utc(),
            document_id=document_id,
            version_id=version_id,
            node_count=tree.statistics.node_count,
            max_depth=tree.statistics.depth,
        )
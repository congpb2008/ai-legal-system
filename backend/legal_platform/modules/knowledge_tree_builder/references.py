"""Canonical reference and path generation (tasks/005 #CanonicalReferences, #PathGeneration).

The Knowledge Tree Builder generates:
    - Canonical references: human-readable legal references like "Điều 3 Khoản 2 Điểm a"
    - Paths: deterministic numeric paths like "I.2.a" or "1.2.3"

These are generated from the node's type, number, and position in the hierarchy.
They must remain stable across rebuilds when the source document is unchanged.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from legal_platform.contracts.knowledge_tree import Node, NodeType


# ---------------------------------------------------------------------------
# Canonical reference generation
# ---------------------------------------------------------------------------


class CanonicalReferenceGenerator:
    """Generates human-readable legal references for Knowledge Nodes.

    Examples (per tasks/005):
        - Article 3
        - Article 3 Clause 2
        - Article 3 Clause 2 Point a

    The generator walks up the tree from a node to build the full reference.
    """

    # Vietnamese legal label mapping
    _LABELS: dict[NodeType, str] = {
        NodeType.CHAPTER: "Chương",
        NodeType.SECTION: "Mục",
        NodeType.ARTICLE: "Điều",
        NodeType.CLAUSE: "Khoản",
        NodeType.POINT: "Điểm",
        NodeType.APPENDIX: "Phụ lục",
        NodeType.PARAGRAPH: "Khoản",
    }

    @classmethod
    def generate(cls, node: Node, nodes: list[Node]) -> str:
        """Generate the canonical reference for a node.

        Walks up from the node to the root, collecting type+number pairs,
        then returns them in document order (root → leaf).

        Args:
            node: the node to generate a reference for.
            nodes: the full list of nodes in the tree (for parent lookup).

        Returns:
            A human-readable reference string, e.g. "Điều 3 Khoản 2 Điểm a".
        """
        parts: list[str] = []
        current: Optional[Node] = node
        node_map = {n.id: n for n in nodes}

        while current is not None:
            label = cls._LABELS.get(current.type)
            number = cls._extract_number(current)
            if label and number:
                parts.insert(0, f"{label} {number}")
            elif label:
                parts.insert(0, label)

            if current.parent is not None:
                current = node_map.get(current.parent.node_id)
            else:
                current = None

        return " ".join(parts)

    @classmethod
    def generate_short(cls, node: Node) -> str:
        """Generate a short reference for a node (self only, no hierarchy).

        Examples:
            - Article 3
            - Clause 2
            - Point a
        """
        label = cls._LABELS.get(node.type)
        number = cls._extract_number(node)
        if label and number:
            return f"{label} {number}"
        if label:
            return label
        return node.title or ""

    @staticmethod
    def _extract_number(node: Node) -> Optional[str]:
        """Extract the numbering from a node's title or text.

        Tries to find a number/letter identifier in the title first,
        then falls back to the text content.
        """
        title = node.title or ""
        text = node.text or ""

        # Try to extract from title patterns like "Điều 1", "Article 1", "Chương I"
        import re
        for field in [title, text]:
            # Match patterns like "1.", "I.", "a)", "1)", "I)"
            m = re.match(r"^([\dIVXLCDM]+|[a-zđ])\s*[\.\)\s]", field)
            if m:
                return m.group(1)
            # Match patterns like "Điều 1", "Chương I", "Khoản 2"
            m = re.match(r"^(?:Điều|Chương|Mục|Khoản|Điểm|Article|Chapter|Section|Clause|Point)\s+([\dIVXLCDM]+|[a-z])", field, re.IGNORECASE)
            if m:
                return m.group(1)

        return None


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------


class PathGenerator:
    """Generates deterministic paths for Knowledge Nodes.

    Examples (per tasks/005):
        - 1
        - 1.2
        - 1.2.3
        - 1.2.3.a

    Paths are built from node numbers at each level of the hierarchy,
    separated by dots. They must remain stable across rebuilds.
    """

    @classmethod
    def generate(cls, node: Node, nodes: list[Node]) -> str:
        """Generate the deterministic path for a node.

        Walks up from the node to the root, collecting numbers at each level,
        then returns them in document order (root → leaf).

        Uses the node's explicit number when available; falls back to the
        node's ``order`` field (guaranteed unique within its parent).

        Args:
            node: the node to generate a path for.
            nodes: the full list of nodes in the tree (for parent lookup).

        Returns:
            A dot-separated path string, e.g. "1.2.3.a".
        """
        parts: list[str] = []
        current: Optional[Node] = node
        node_map = {n.id: n for n in nodes}

        while current is not None:
            number = cls._extract_number(current)
            if number:
                parts.insert(0, number)
            else:
                # Use the node's order field (guaranteed unique within parent)
                parts.insert(0, str(current.order + 1))

            if current.parent is not None:
                current = node_map.get(current.parent.node_id)
            else:
                current = None

        return ".".join(parts)

    @staticmethod
    def _extract_number(node: Node) -> Optional[str]:
        """Extract the numbering from a node for path purposes."""
        title = node.title or ""
        text = node.text or ""

        import re
        for field in [title, text]:
            m = re.match(r"^([\dIVXLCDM]+|[a-zđ])\s*[\.\)\s]", field)
            if m:
                return m.group(1)
            m = re.match(r"^(?:Điều|Chương|Mục|Khoản|Điểm|Article|Chapter|Section|Clause|Point)\s+([\dIVXLCDM]+|[a-z])", field, re.IGNORECASE)
            if m:
                return m.group(1)

        return None
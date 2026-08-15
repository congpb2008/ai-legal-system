"""Knowledge Tree Builder (tasks/005-knowledge-tree-builder.md, module Knowledge).

The Knowledge Tree Builder transforms parsed structural elements into a validated
Knowledge Tree Contract. It is responsible for constructing the final hierarchical
representation of a legal document.

Per the task:
    - The Builder does NOT perform parsing (consumes parser output only).
    - It builds Knowledge Nodes, constructs parent-child relationships, generates
      Node IDs, canonical references, node paths, and node depth.
    - It preserves ordering and validates tree integrity.
    - Validation failures prevent publication.

The Builder is the bridge between the Parser (Task 004) and the Knowledge Layer.
It produces the canonical, immutable Knowledge Tree Contract consumed by Chunking
(Task 006), Retrieval (Task 009), Citation (Task 012), and Evaluation (Task 017).
"""

from legal_platform.modules.knowledge_tree_builder.builder import (
    KnowledgeTreeBuilder,
    BuilderMetadata,
    TreeValidationError,
    ValidationReport,
)
from legal_platform.modules.knowledge_tree_builder.references import (
    CanonicalReferenceGenerator,
    PathGenerator,
)

__all__ = [
    "KnowledgeTreeBuilder",
    "BuilderMetadata",
    "TreeValidationError",
    "ValidationReport",
    "CanonicalReferenceGenerator",
    "PathGenerator",
]
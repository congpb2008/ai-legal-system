"""Parser Service (tasks/004-parser.md).

The Parser Service orchestrates the parsing pipeline:
    1. Receives an OCR result (from the OCR Service, Task 003).
    2. Runs the parser engine to detect document structure.
    3. Builds the Knowledge Tree Contract (canonical, immutable).
    4. Stores the Knowledge Tree.
    5. Transitions the document's processing state.
    6. Returns the Knowledge Tree.

Per the spec:
    - The Parser is the only component allowed to construct a Knowledge Tree.
    - The Parser never reads files directly; it consumes OCR output only.
    - Original wording is preserved (no rewriting, summarizing, or paraphrasing).
    - The Parser does NOT infer legal meaning.
    - Parser output is deterministic.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import new_id, now_utc, utc_iso
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
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.ocr_service.models import OcrResult
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.parser.engine import (
    LegalRegexParser,
    ParserEngine,
    ParserEngineError,
    ParserOutput,
    ParserSection,
    SectionType,
)
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# Knowledge Tree storage (canonical, immutable per ADR-001)
# ---------------------------------------------------------------------------

_KT_DDL = """
CREATE TABLE IF NOT EXISTS knowledge_tree (
    id                  TEXT PRIMARY KEY,
    document_version_id TEXT NOT NULL,
    parser_version      TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    root_node_id        TEXT NOT NULL,
    tree_json           TEXT NOT NULL   -- full KnowledgeTree as JSON (immutable)
);

CREATE INDEX IF NOT EXISTS idx_kt_document_version ON knowledge_tree(document_version_id);
"""


# ---------------------------------------------------------------------------
# Parser Service
# ---------------------------------------------------------------------------


class ParserService:
    """The Parser Service.

    Orchestrates parsing of OCR output into a canonical Knowledge Tree.
    Integrates with:
        - OcrService (Task 003) for retrieving OCR results.
        - DocumentRegistry (Task 001) for state transitions and audit logging.
        - ParserEngine (replaceable) for the actual structure detection.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        ocr_service: "OcrService | None" = None,
        parser_engine: "ParserEngine | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.ocr_service = ocr_service or OcrService(registry=self.registry)
        self.engine = parser_engine or LegalRegexParser()
        # Ensure KT table + audit table exist
        init_audit_log(self.registry.repo.conn)
        self.registry.repo.conn.executescript(_KT_DDL)
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Parse from OCR result
    # ------------------------------------------------------------------

    def parse_ocr_result(
        self,
        ocr_result: OcrResult,
        *,
        document_id: UUID,
        version_id: "UUID | None" = None,
        user_id: str = "system",
        mark_ready: bool = False,
    ) -> KnowledgeTree:
        """Parse an OCR result into a Knowledge Tree.

        The document must be in OCR_COMPLETED state (or later).

        Args:
            ocr_result: the OCR result to parse.
            document_id: the document being parsed.
            version_id: the document version (defaults to the first version).
            user_id: for audit logging.

        Returns:
            The canonical Knowledge Tree.

        Raises:
            ValueError: if the document is not found or not in the right state.
            ParserEngineError: if parsing fails.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        vid = version_id or doc.versions[0].version_id

        # --- run parser engine ---
        try:
            parser_output = self.engine.parse(
                ocr_result=ocr_result,
                document_id=document_id,
                version_id=vid,
            )
        except ParserEngineError:
            self.registry.transition_processing(
                document_id, ProcessingState.FAILED,
                user_id=user_id,
                failure_reason="Parsing failed",
            )
            raise

        # --- build Knowledge Tree Contract ---
        tree = self._build_knowledge_tree(parser_output, vid)

        # --- store Knowledge Tree ---
        self._store_tree(tree)

        # Parsing is not sufficient for READY: chunking, embeddings, and an
        # active index are downstream prerequisites. ``mark_ready`` remains
        # only for isolated legacy callers; the production coordinator always
        # leaves the state at PARSING_RUNNING until it proves those artifacts.
        current = self.registry.get_processing(document_id)
        if current == ProcessingState.OCR_COMPLETED:
            self.registry.transition_processing(
                document_id, ProcessingState.PARSING_PENDING, user_id=user_id,
            )
            self.registry.transition_processing(
                document_id, ProcessingState.PARSING_RUNNING, user_id=user_id,
            )
            if mark_ready:
                self.registry.transition_processing(
                    document_id, ProcessingState.READY, user_id=user_id,
                )

        # --- audit ---
        log_event(
            self.registry.repo.conn,
            service="parser-service",
            module="parser",
            event="parser.complete",
            entity_type="document",
            entity_id=document_id,
            severity="INFO",
            message=f"Parsing completed for document {document_id}",
            metadata={
                "tree_id": str(tree.id),
                "node_count": tree.statistics.node_count,
                "parser_version": tree.parser_version,
                "warnings": parser_output.warnings,
            },
        )

        return tree

    # ------------------------------------------------------------------
    # Parse from OCR service (lookup by document)
    # ------------------------------------------------------------------

    def parse_document(
        self,
        document_id: UUID,
        *,
        user_id: str = "system",
    ) -> KnowledgeTree:
        """Parse a document using its most recent OCR result.

        Looks up the latest OCR result for the document and parses it.

        Args:
            document_id: the document to parse.
            user_id: for audit logging.

        Returns:
            The canonical Knowledge Tree.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        ocr_results = self.ocr_service.get_results_for_document(document_id)
        if not ocr_results:
            raise ValueError(
                f"No OCR result found for document {document_id}. "
                "Run OCR first (Task 003)."
            )

        # Use the most recent OCR result
        latest = ocr_results[0]
        return self.parse_ocr_result(
            latest,
            document_id=document_id,
            version_id=latest.version_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Knowledge Tree construction
    # ------------------------------------------------------------------

    def _build_knowledge_tree(
        self, parser_output: ParserOutput, version_id: UUID
    ) -> KnowledgeTree:
        """Convert parser output into a validated Knowledge Tree Contract.

        This is the core transformation: ParserSection tree → Node tree.
        """
        # Build nodes recursively
        nodes: list[Node] = []
        node_counter = [0]

        def build_node(
            section: ParserSection,
            parent_id: Optional[UUID],
            order: int,
            depth: int,
        ) -> UUID:
            node_id = new_id()
            node_counter[0] += 1

            # Convert section type to node type
            node_type = self._section_to_node_type(section.section_type)

            # Build source location
            source = SourceLocation(
                page=section.page_start,
                line_start=section.line_start,
                line_end=section.line_end,
            )

            # Build node
            node = Node(
                id=node_id,
                type=node_type,
                title=section.title,
                text=section.text,
                parent=NodeReference(node_id=parent_id) if parent_id else None,
                order=order,
                page_start=section.page_start,
                page_end=section.page_end,
                source=source,
                metadata=NodeMetadata(
                    parser_confidence=0.95,
                    language="vi",
                ),
            )
            nodes.append(node)

            # Build children
            child_order = 0
            for child in section.children:
                child_id = build_node(child, node_id, child_order, depth + 1)
                node.children.append(NodeReference(node_id=child_id))
                child_order += 1

            return node_id

        # Build root (Document node)
        root_section = parser_output.sections[0] if parser_output.sections else None
        if root_section is None:
            raise ParserEngineError("Parser produced no sections")

        # If the first section is not a DOCUMENT, wrap it
        if root_section.section_type != SectionType.DOCUMENT:
            root_section = ParserSection(
                section_type=SectionType.DOCUMENT,
                title="Document",
                page_start=1,
                page_end=root_section.page_end,
                children=[root_section],
            )

        root_id = build_node(root_section, None, 0, 0)

        # Compute statistics
        stats = TreeStatistics(
            node_count=len(nodes),
            depth=self._compute_depth(nodes, root_id),
            article_count=sum(1 for n in nodes if n.type == NodeType.ARTICLE),
            clause_count=sum(1 for n in nodes if n.type == NodeType.CLAUSE),
            appendix_count=sum(1 for n in nodes if n.type == NodeType.APPENDIX),
            page_count=max((n.page_end for n in nodes), default=1),
        )

        # Build tree
        tree = KnowledgeTree(
            document_version_id=version_id,
            parser_version=parser_output.parser_version,
            root=NodeReference(node_id=root_id),
            nodes=nodes,
            statistics=stats,
            metadata=TreeMetadata(
                language="vi",
                parser_confidence=0.95,
                warnings=parser_output.warnings,
            ),
        )

        return tree

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

    @staticmethod
    def _compute_depth(nodes: list[Node], root_id: UUID) -> int:
        """Compute the maximum depth of the node tree."""
        depth_map: dict[UUID, int] = {}
        for node in nodes:
            if node.id == root_id:
                depth_map[node.id] = 0
            elif node.parent:
                depth_map[node.id] = depth_map.get(node.parent.node_id, 0) + 1
        return max(depth_map.values(), default=0)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store_tree(self, tree: KnowledgeTree) -> None:
        """Persist a Knowledge Tree (canonical, immutable per ADR-001)."""
        self.registry.repo.conn.execute(
            """
            INSERT OR REPLACE INTO knowledge_tree
                (id, document_version_id, parser_version, created_at, root_node_id, tree_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(tree.id),
                str(tree.document_version_id),
                tree.parser_version,
                utc_iso(tree.created_at),
                str(tree.root.node_id),
                tree.model_dump_json(),
            ),
        )
        self.registry.repo.conn.commit()

    def get_tree(self, tree_id: UUID) -> Optional[KnowledgeTree]:
        """Retrieve a Knowledge Tree by its ID."""
        row = self.registry.repo.conn.execute(
            "SELECT tree_json FROM knowledge_tree WHERE id = ?",
            (str(tree_id),),
        ).fetchone()
        if row is None:
            return None
        return KnowledgeTree.model_validate_json(row["tree_json"])

    def get_tree_for_version(self, version_id: UUID) -> Optional[KnowledgeTree]:
        """Retrieve the Knowledge Tree for a document version."""
        row = self.registry.repo.conn.execute(
            "SELECT tree_json FROM knowledge_tree WHERE document_version_id = ? ORDER BY created_at DESC LIMIT 1",
            (str(version_id),),
        ).fetchone()
        if row is None:
            return None
        return KnowledgeTree.model_validate_json(row["tree_json"])

"""Citation Builder Service (tasks/012-citation-builder.md).

The Citation Builder Service orchestrates the citation pipeline:
    1. Receives a draft Answer (from the Generation Service, Task 011).
    2. Receives the Evidence Package (from the Reranker, Task 010).
    3. Runs the Citation Builder to detect claims, map evidence, and resolve
       citations.
    4. Returns the verified Answer with attached citations.

Per the spec:
    - Every factual statement must be traceable back to retrieved evidence.
    - The Citation Builder does NOT generate answers.
    - It validates them.
"""

from __future__ import annotations

import time
from typing import Optional
from uuid import UUID

from legal_platform.contracts.answer import (
    Answer,
    AnswerStatus,
    Citation,
    Limitation,
)
from legal_platform.contracts.knowledge_tree import KnowledgeTree
from legal_platform.contracts.retrieval import Evidence, SourceAnchor
from legal_platform.modules.citation.citation_builder import (
    CitationBuilder,
    CitationBuilderConfig,
    ValidationReport,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.knowledge_tree_builder.references import (
    CanonicalReferenceGenerator,
)
from legal_platform.modules.parser.service import ParserService
from legal_platform.storage.eventlog import init_audit_log, log_event


class CitationTraceabilityError(RuntimeError):
    """Raised when generated evidence cannot be traced to canonical artifacts."""


class CitationBuilderService:
    """The Citation Builder Service.

    Orchestrates the construction, validation and attachment of citations
    to generated answers.

    Integrates with:
        - GenerationService (Task 011) for draft answers.
        - DocumentRegistry (Task 001) for audit logging and Knowledge Tree
          lookups.
        - CitationBuilder (replaceable) for the actual citation logic.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        citation_builder: "CitationBuilder | None" = None,
        parser_service: "ParserService | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.citation_builder = citation_builder or CitationBuilder()
        self.parser = parser_service or ParserService(registry=self.registry)
        init_audit_log(self.registry.repo.conn)

    def verify_evidence_traceability(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
    ) -> tuple[Answer, ValidationReport]:
        """Validate and enrich citations against Document and Knowledge Tree.

        Unlike the optional lexical claim mapper, this release gate follows
        the exact evidence IDs produced by retrieval. Every returned citation
        must resolve to the same logical document, version, and immutable node.
        Page/line anchors are then taken from that canonical node.
        """
        if not evidence_package:
            if answer.citations:
                raise CitationTraceabilityError(
                    "Answer contains citations without retrieved evidence"
                )
            return answer, ValidationReport(
                citation_count=0,
                coverage=1.0,
                status="NO_EVIDENCE",
            )

        evidence_by_id = {item.id: item for item in evidence_package}
        verified: list[Citation] = []
        errors: list[str] = []

        for citation in answer.citations:
            evidence = (
                evidence_by_id.get(citation.evidence_id)
                if citation.evidence_id is not None
                else None
            )
            if evidence is None:
                errors.append(f"citation {citation.id} has no matching evidence")
                continue
            if (
                citation.document_id != evidence.document_id
                or citation.document_version_id != evidence.document_version_id
                or citation.knowledge_node_id != evidence.knowledge_node_id
            ):
                errors.append(f"citation {citation.id} disagrees with its evidence")
                continue

            document = self.registry.get_document(evidence.document_id)
            if document is None:
                errors.append(f"citation {citation.id} document is missing")
                continue
            if not any(
                version.version_id == evidence.document_version_id
                for version in document.versions
            ):
                errors.append(f"citation {citation.id} version is missing")
                continue

            tree = self.parser.get_tree_for_version(evidence.document_version_id)
            node = tree.get_node(evidence.knowledge_node_id) if tree else None
            if tree is None or node is None:
                errors.append(f"citation {citation.id} node is missing")
                continue

            reference = None
            if evidence.source_anchor:
                reference = evidence.source_anchor.canonical_reference
            if not reference:
                reference = CanonicalReferenceGenerator.generate(node, tree.nodes)
            if not reference:
                reference = node.title or f"Trang {node.source.page}"

            verified.append(Citation(
                id=citation.id,
                document_id=evidence.document_id,
                document_version_id=evidence.document_version_id,
                knowledge_node_id=evidence.knowledge_node_id,
                evidence_id=evidence.id,
                source_anchor=SourceAnchor(
                    canonical_reference=reference,
                    page=node.source.page,
                    line_start=node.source.line_start,
                    line_end=node.source.line_end,
                ),
                label=reference,
            ))

        if errors or len(verified) != len(answer.citations):
            log_event(
                self.registry.repo.conn,
                service="citation-service",
                module="citation",
                event="citation.traceability_failed",
                entity_type="request",
                entity_id=answer.request_id,
                severity="ERROR",
                message="Citation traceability validation failed",
                metadata={"error_count": len(errors)},
            )
            raise CitationTraceabilityError("; ".join(errors))

        verified_answer = answer.model_copy(update={"citations": verified})
        report = ValidationReport(
            citation_count=len(verified),
            coverage=1.0,
            status="VALID",
        )
        log_event(
            self.registry.repo.conn,
            service="citation-service",
            module="citation",
            event="citation.traceability_verified",
            entity_type="request",
            entity_id=answer.request_id,
            severity="INFO",
            message=f"Verified {len(verified)} citation source paths",
            metadata={"citation_count": len(verified), "coverage": 1.0},
        )
        return verified_answer, report

    # ------------------------------------------------------------------
    # Build citations for a generated answer
    # ------------------------------------------------------------------

    def build_citations(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
        *,
        knowledge_trees: "dict[UUID, KnowledgeTree] | None" = None,
    ) -> tuple[Answer, ValidationReport]:
        """Build and attach citations to a generated answer.

        Args:
            answer: the draft Answer from the Generation Service.
            evidence_package: the evidence items from the Reranker.
            knowledge_trees: optional Knowledge Trees for canonical reference
                resolution (keyed by document_version_id).

        Returns:
            A tuple of (verified Answer with citations, validation report).
        """
        start_time = time.time()

        verified_answer, report = self.citation_builder.build_citations(
            answer=answer,
            evidence_package=evidence_package,
            knowledge_trees=knowledge_trees,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Audit
        log_event(
            self.registry.repo.conn,
            service="citation-service",
            module="citation",
            event="citation.build",
            entity_type="request",
            entity_id=answer.request_id,
            severity="INFO",
            message=(
                f"Citations built: {report.citation_count} citations, "
                f"{len(report.supported_claims)} supported, "
                f"{len(report.unsupported_claims)} unsupported"
            ),
            metadata={
                "citation_count": report.citation_count,
                "supported_claims": len(report.supported_claims),
                "unsupported_claims": len(report.unsupported_claims),
                "coverage": report.coverage,
                "status": report.status,
                "latency_ms": round(elapsed_ms, 2),
                "citation_version": self.citation_builder.get_citation_version(),
            },
        )

        return verified_answer, report

    # ------------------------------------------------------------------
    # Validate citations in an existing answer
    # ------------------------------------------------------------------

    def validate_citations(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
        *,
        knowledge_trees: "dict[UUID, KnowledgeTree] | None" = None,
    ) -> ValidationReport:
        """Validate citations in an existing Answer.

        This is a lighter-weight operation that validates citations without
        rebuilding them.

        Args:
            answer: the Answer to validate.
            evidence_package: the evidence items from retrieval.
            knowledge_trees: optional Knowledge Trees for resolution.

        Returns:
            A ValidationReport.
        """
        start_time = time.time()

        report = self.citation_builder.validate_answer(
            answer=answer,
            evidence_package=evidence_package,
            knowledge_trees=knowledge_trees,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        # Audit
        log_event(
            self.registry.repo.conn,
            service="citation-service",
            module="citation",
            event="citation.validate",
            entity_type="request",
            entity_id=answer.request_id,
            severity="INFO",
            message=(
                f"Citations validated: {report.citation_count} citations, "
                f"status={report.status}"
            ),
            metadata={
                "citation_count": report.citation_count,
                "status": report.status,
                "errors": len(report.errors),
                "warnings": len(report.warnings),
                "latency_ms": round(elapsed_ms, 2),
            },
        )

        return report

    # ------------------------------------------------------------------
    # Convenience: generate + cite
    # ------------------------------------------------------------------

    def generate_and_cite(
        self,
        answer: Answer,
        evidence_package: list[Evidence],
        *,
        knowledge_trees: "dict[UUID, KnowledgeTree] | None" = None,
    ) -> Answer:
        """Convenience: build citations and return the verified answer.

        Args:
            answer: the draft Answer from the Generation Service.
            evidence_package: the evidence items from the Reranker.
            knowledge_trees: optional Knowledge Trees for resolution.

        Returns:
            The verified Answer with citations attached.
        """
        verified_answer, _ = self.build_citations(
            answer=answer,
            evidence_package=evidence_package,
            knowledge_trees=knowledge_trees,
        )
        return verified_answer

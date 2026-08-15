"""Retrieval Service (tasks/009-retrieval.md).

The Retrieval Service discovers the most relevant legal evidence for a user query.
It returns evidence — it does NOT generate answers, summarize, or interpret legal
meaning.

Per the spec:
    - Understands search intent
    - Builds retrieval queries
    - Performs hybrid retrieval (semantic + keyword)
    - Ranks candidate evidence
    - Removes duplicates
    - Expands legal context
    - Returns the Retrieval Contract

The Retrieval Service bridges user intent and indexed legal knowledge.
Generation depends entirely on retrieval quality.
"""

from __future__ import annotations

import re
import time
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import new_id
from legal_platform.contracts.retrieval import (
    Evidence,
    RetrievalMetadata,
    RetrievalReason,
    RetrievalResult,
    RetrievalStrategy,
    SourceAnchor,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.vector_index.index import SearchResult
from legal_platform.modules.vector_index.service import VectorIndexService
from legal_platform.storage.eventlog import init_audit_log, log_event


class RetrievalService:
    """The Retrieval Service.

    Discovers relevant legal evidence for a user query using hybrid search
    (semantic + keyword). Returns the Retrieval Contract consumed by the
    Generation Service (Task 011).

    Integrates with:
        - VectorIndexService (Task 008) for semantic search.
        - EmbeddingService (Task 007) for query embedding.
        - DocumentRegistry (Task 001) for document metadata.
    """

    _QUERY_STOPWORDS = {
        "ai", "bằng", "các", "cách", "cho", "chứng", "có", "của",
        "định", "được", "gì", "hiểu", "không", "kho", "là", "một",
        "mẫu", "nào", "năm", "ngày", "này", "quy", "số", "theo",
        "thế", "tài", "liệu", "trong", "từ", "và", "về",
        "what", "when", "where", "which", "who", "the", "is", "are",
    }

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        vector_index: "VectorIndexService | None" = None,
        embedding_service: "EmbeddingService | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.vector_index = vector_index or VectorIndexService(registry=self.registry)
        self.embedding_service = embedding_service or EmbeddingService(
            registry=self.registry,
        )
        init_audit_log(self.registry.repo.conn)

    # ------------------------------------------------------------------
    # Main search entry point
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        vault_id: "UUID | None" = None,
        vault_ids: "set[UUID] | None" = None,
        document_id: "UUID | None" = None,
        document_status: "str | None" = "ACTIVE",
        top_k: int = 10,
        strategy: "str | RetrievalStrategy" = RetrievalStrategy.HYBRID,
        threshold: "float | None" = None,
    ) -> RetrievalResult:
        """Execute a retrieval query.

        Flow (per tasks/009 #ProcessingFlow):
            1. Query analysis (intent, keywords, references)
            2. Query embedding (for semantic search)
            3. Hybrid search (semantic + keyword)
            4. Candidate collection
            5. Re-ranking
            6. Context expansion
            7. Deduplication
            8. Return Retrieval Contract

        Args:
            query: the user's natural language query.
            vault_id: restrict search to a specific vault.
            vault_ids: authorized vault scope supplied by the API boundary.
            document_id: restrict search to a specific document.
            document_status: filter by document status (default ACTIVE).
            top_k: maximum number of evidence items to return.
            strategy: search strategy (KEYWORD, SEMANTIC, HYBRID).
            threshold: minimum similarity score.

        Returns:
            A ``RetrievalResult`` containing ranked evidence.
        """
        start_time = time.time()
        query_id = new_id()

        # Normalize strategy
        if isinstance(strategy, str):
            strategy = RetrievalStrategy(strategy.upper())

        # --- Query embedding (for semantic search) ---
        query_vector: Optional[list[float]] = None
        if query.strip() and strategy in (
            RetrievalStrategy.SEMANTIC,
            RetrievalStrategy.HYBRID,
        ):
            # Provider/configuration failures are intentionally observable.  A
            # silent downgrade made the UI claim hybrid semantics while doing
            # keyword-only search.
            query_vector = self.embedding_service.engine.embed(query)

        # --- Semantic search ---
        semantic_results: list[SearchResult] = []
        if query_vector is not None:
            semantic_results = self.vector_index.search(
                query_vector,
                # Retrieval prioritizes recall.  Legal definitions can be
                # lexically exact but only moderately close in embedding
                # space, so keep a broader semantic pool for hybrid fusion.
                top_k=max(top_k * 10, 100),
                threshold=threshold,
                vault_id=vault_id,
                vault_ids=vault_ids,
                document_id=document_id,
                document_status=document_status,
                model=self.embedding_service.engine.MODEL_NAME,
                model_version=self.embedding_service.engine.MODEL_VERSION,
            )

        # --- Keyword search ---
        keyword_results: list[Evidence] = []
        if strategy in (RetrievalStrategy.KEYWORD, RetrievalStrategy.HYBRID):
            keyword_results = self._keyword_search(
                query,
                vault_id=vault_id,
                vault_ids=vault_ids,
                document_id=document_id,
                document_status=document_status,
            )

        # --- Merge and rank ---
        evidence = self._merge_results(
            semantic_results=semantic_results,
            keyword_results=keyword_results,
            query=query,
            top_k=top_k,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        result = RetrievalResult(
            query_id=query_id,
            strategy=strategy,
            query=query,
            evidence=evidence,
            metadata=RetrievalMetadata(
                strategy=strategy.value,
                latency_ms=round(elapsed_ms, 2),
                candidate_count=len(semantic_results) + len(keyword_results),
                returned_count=len(evidence),
            ),
        )

        # Audit
        log_event(
            self.registry.repo.conn,
            service="retrieval-service",
            module="retrieval",
            event="retrieval.search",
            entity_type="query",
            entity_id=query_id,
            severity="INFO",
            message=f"Retrieval completed: {len(evidence)} results",
            metadata={
                "strategy": strategy.value,
                "query_length": len(query),
                "results": len(evidence),
                "latency_ms": round(elapsed_ms, 2),
            },
        )

        return result

    # ------------------------------------------------------------------
    # Keyword search (basic text matching)
    # ------------------------------------------------------------------

    @classmethod
    def _analyze_query_terms(cls, query: str) -> set[str]:
        """Extract useful lexical terms and expand common time paraphrases."""
        normalized = query.lower()
        terms = {
            term
            for term in re.findall(r"\w+", normalized, flags=re.UNICODE)
            if term not in cls._QUERY_STOPWORDS and len(term) > 1
        }
        # Vietnamese users naturally say "múi giờ" while source forms often
        # contain only the canonical notation "GMT+7".  Likewise, "ngày theo
        # lịch" is commonly defined by enumerating weekends and holidays.
        if "múi giờ" in normalized:
            terms.difference_update({"múi", "giờ"})
            terms.add("gmt")
        if "ngày theo lịch" in normalized:
            terms.update({"dương", "nghỉ", "lễ", "tết"})
        return terms

    @staticmethod
    def _document_identifier_terms(query: str) -> set[str]:
        """Return document-code tokens without mistaking dates/timezones for IDs."""
        tokens = re.findall(r"\w+", query.lower(), flags=re.UNICODE)
        return {
            term
            for term in tokens
            if (
                any(character.isdigit() for character in term)
                and (
                    any(character.isalpha() for character in term)
                    or (term.isdigit() and len(term) >= 3)
                )
            )
        }

    @staticmethod
    def _document_identifier_match_ratio(
        identifier_terms: set[str], title_terms: set[str]
    ) -> float:
        """Return the share of named document codes present in one title.

        A comparison query can name several documents (for example, 4A and
        5A).  Each candidate document is relevant when its own title matches
        one of those identifiers; requiring every identifier in one title
        makes a legitimate cross-document question impossible to answer.
        """
        if not identifier_terms:
            return 0.0
        return len(identifier_terms & title_terms) / len(identifier_terms)

    def _keyword_search(
        self,
        query: str,
        *,
        vault_id: "UUID | None" = None,
        vault_ids: "set[UUID] | None" = None,
        document_id: "UUID | None" = None,
        document_status: "str | None" = "ACTIVE",
    ) -> list[Evidence]:
        """Simple keyword search over indexed entries.

        This is a basic implementation that matches query terms against
        the canonical_references and chunk text of indexed entries.
        A production implementation would use a proper search engine
        (e.g., Elasticsearch, SQLite FTS5).
        """
        query_terms = self._analyze_query_terms(query)

        if not query_terms:
            return []

        results: list[Evidence] = []
        rank = 0
        document_titles: dict[UUID, str] = {}

        for entry in self.vector_index.entries_snapshot():
            if entry.status != "ACTIVE":
                continue
            if vault_id is not None and entry.vault_id != vault_id:
                continue
            if vault_ids is not None and entry.vault_id not in vault_ids:
                continue
            if document_id is not None and entry.document_id != document_id:
                continue
            if document_status is not None and entry.document_status != document_status:
                continue

            # Score by term overlap
            ref_text = " ".join(entry.canonical_references).lower()
            if entry.document_id not in document_titles:
                document = self.registry.get_document(entry.document_id)
                document_titles[entry.document_id] = (
                    document.title.lower() if document is not None else ""
                )
            content_terms = set(re.findall(
                r"\w+",
                ref_text + " " + entry.chunk_text.lower(),
                flags=re.UNICODE,
            ))
            title_terms = set(re.findall(
                r"\w+",
                document_titles[entry.document_id],
                flags=re.UNICODE,
            ))
            content_score = len(query_terms & content_terms) / len(query_terms)
            title_score = len(query_terms & title_terms) / len(query_terms)
            score = min(0.85 * content_score + 0.15 * title_score, 1.0)

            if score > 0:
                rank += 1
                results.append(Evidence(
                    id=new_id(),
                    knowledge_node_id=entry.knowledge_node_id,
                    document_id=entry.document_id,
                    document_version_id=entry.version_id,
                    score=score,
                    rank=rank,
                    text=entry.chunk_text,
                    source_anchor=SourceAnchor(
                        page=entry.page_start,
                        canonical_reference=entry.canonical_references[0] if entry.canonical_references else None,
                    ),
                    reason=RetrievalReason(
                        method="keyword",
                        keyword_score=score,
                    ),
                ))

        # Sort by score descending
        results.sort(key=lambda e: e.score, reverse=True)
        for i, e in enumerate(results):
            e.rank = i + 1

        return results

    # ------------------------------------------------------------------
    # Merge and rank
    # ------------------------------------------------------------------

    def _merge_results(
        self,
        *,
        semantic_results: list[SearchResult],
        keyword_results: list[Evidence],
        query: str,
        top_k: int,
    ) -> list[Evidence]:
        """Merge semantic and keyword results on a comparable score scale.

        Semantic cosine similarity and keyword coverage are not directly
        comparable.  Hybrid mode therefore combines semantic relevance with a
        small keyword signal and reciprocal-rank agreement.  Keyword-only hits
        cannot overwhelm a strong semantic match merely because common legal
        words appear in the question.
        """
        semantic_evidence: list[Evidence] = []
        for rank, sr in enumerate(semantic_results, start=1):
            normalized_score = max(0.0, min(1.0, (sr.score + 1.0) / 2.0))
            semantic_evidence.append(Evidence(
                id=new_id(),
                knowledge_node_id=sr.entry.knowledge_node_id,
                document_id=sr.entry.document_id,
                document_version_id=sr.entry.version_id,
                score=round(normalized_score, 4),
                rank=rank,
                text=sr.entry.chunk_text,
                source_anchor=SourceAnchor(
                    page=sr.entry.page_start,
                    canonical_reference=sr.entry.canonical_references[0] if sr.entry.canonical_references else None,
                ),
                reason=RetrievalReason(
                    method="semantic",
                    semantic_score=round(normalized_score, 4),
                ),
            ))

        if not keyword_results:
            return semantic_evidence[:top_k]
        if not semantic_evidence:
            return keyword_results[:top_k]

        def evidence_key(item: Evidence) -> tuple[UUID, UUID, str]:
            return (item.document_id, item.knowledge_node_id, item.text)

        candidates: dict[tuple[UUID, UUID, str], dict[str, object]] = {}
        for rank, item in enumerate(semantic_evidence, start=1):
            candidates[evidence_key(item)] = {
                "item": item,
                "semantic_score": item.score,
                "semantic_rank": rank,
            }
        for rank, item in enumerate(keyword_results, start=1):
            slot = candidates.setdefault(evidence_key(item), {"item": item})
            slot["keyword_score"] = item.score
            slot["keyword_rank"] = rank

        merged: list[Evidence] = []
        rrf_max = 2.0 / 61.0
        identifier_terms = self._document_identifier_terms(query)
        title_term_cache: dict[UUID, set[str]] = {}
        for slot in candidates.values():
            item = slot["item"]
            assert isinstance(item, Evidence)
            semantic_score = float(slot.get("semantic_score", 0.0))
            keyword_score = float(slot.get("keyword_score", 0.0))
            rrf = 0.0
            if "semantic_rank" in slot:
                rrf += 1.0 / (60.0 + int(slot["semantic_rank"]))
            if "keyword_rank" in slot:
                rrf += 1.0 / (60.0 + int(slot["keyword_rank"]))
            rrf_score = min(1.0, rrf / rrf_max)
            if semantic_score and keyword_score:
                # Agreement between semantic and lexical retrieval is the
                # strongest signal, while semantic similarity remains primary.
                fused_score = (
                    0.75 * semantic_score
                    + 0.15 * keyword_score
                    + 0.10 * rrf_score
                )
            elif semantic_score:
                fused_score = 0.95 * semantic_score + 0.05 * rrf_score
            else:
                # Preserve exact legal terms/document-number hits even when
                # the embedding rank is outside the semantic candidate pool.
                fused_score = 0.95 * keyword_score + 0.05 * rrf_score
            if identifier_terms:
                if item.document_id not in title_term_cache:
                    document = self.registry.get_document(item.document_id)
                    title_term_cache[item.document_id] = set(re.findall(
                        r"\w+",
                        document.title.lower() if document is not None else "",
                        flags=re.UNICODE,
                    ))
                identifier_match = self._document_identifier_match_ratio(
                    identifier_terms,
                    title_term_cache[item.document_id],
                )
                if identifier_match:
                    fused_score += 0.08 * identifier_match
            fused_score = min(1.0, fused_score)
            merged.append(item.model_copy(update={
                "score": round(fused_score, 4),
                "reason": RetrievalReason(
                    method="hybrid",
                    semantic_score=(semantic_score or None),
                    keyword_score=(keyword_score or None),
                    rerank_score=round(rrf_score, 4),
                ),
            }))

        merged.sort(key=lambda e: e.score, reverse=True)
        for i, e in enumerate(merged):
            e.rank = i + 1

        return merged[:top_k]

    # ------------------------------------------------------------------
    # Context expansion
    # ------------------------------------------------------------------

    def expand_context(
        self,
        evidence: list[Evidence],
        *,
        window: int = 1,
    ) -> list[Evidence]:
        """Expand evidence with surrounding context.

        For each evidence item, retrieves adjacent entries from the same
        document to provide surrounding context. This is a simplified
        implementation; a production version would use the Knowledge Tree
        hierarchy for context expansion.

        Args:
            evidence: the current evidence list.
            window: number of adjacent entries to include on each side.

        Returns:
            Expanded evidence list.
        """
        if not evidence:
            return evidence

        expanded: list[Evidence] = []
        seen_ids: set[UUID] = set()

        for ev in evidence:
            if ev.id not in seen_ids:
                seen_ids.add(ev.id)
                expanded.append(ev)

            # Find adjacent entries from the same document in the index
            doc_entries = [
                e for e in self.vector_index.entries_snapshot()
                if e.document_id == ev.document_id
                and e.entry_id not in seen_ids
            ]

            # Sort by entry creation order (approximate document order)
            doc_entries.sort(key=lambda e: e.created_at)

            # Find position of current entry
            current_pos = None
            for i, de in enumerate(doc_entries):
                if de.chunk_id == ev.knowledge_node_id:
                    current_pos = i
                    break

            if current_pos is not None:
                start = max(0, current_pos - window)
                end = min(len(doc_entries), current_pos + window + 1)
                for i in range(start, end):
                    if i != current_pos:
                        de = doc_entries[i]
                        if de.entry_id not in seen_ids:
                            seen_ids.add(de.entry_id)
                            ctx_ev = Evidence(
                                id=new_id(),
                                knowledge_node_id=de.chunk_id,
                                document_id=de.document_id,
                                document_version_id=de.version_id,
                                score=ev.score * 0.8,  # Slightly lower score for context
                                rank=len(expanded) + 1,
                                text=de.knowledge_tree_version or "",
                                source_anchor=SourceAnchor(
                                    page=de.page_start,
                                    canonical_reference=de.canonical_references[0] if de.canonical_references else None,
                                ),
                                reason=RetrievalReason(method="context_expansion"),
                            )
                            expanded.append(ctx_ev)

        return expanded

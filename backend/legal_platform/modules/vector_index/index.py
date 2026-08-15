"""Vector index data structures and similarity functions (tasks/008-vector-index.md).

The Vector Index stores and searches embedding vectors. This module defines the
core data structures (``IndexEntry``, ``SearchResult``) and the similarity metric
(``cosine_similarity``).

The index is a derived datastore (ADR-003). It is eventually consistent; the
Knowledge Tree is authoritative.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from legal_platform.contracts.common import now_utc


@dataclass
class IndexEntry:
    """A single indexed vector with metadata.

    Fields:
        entry_id: unique identifier for this index entry.
        embedding_id: the embedding this entry indexes.
        chunk_id: the chunk this embedding was generated from.
        document_id: the document.
        version_id: the document version.
        vault_id: the vault the document belongs to.
        vector: the embedding vector.
        dimension: vector dimension.
        model: embedding model used.
        model_version: embedding model version.
        knowledge_tree_version: KT version at indexing time.
        chunk_type: type of the originating chunk.
        canonical_references: legal references for the chunk.
        document_status: document lifecycle status (ACTIVE/ARCHIVED).
        language: document language.
        created_at: when this entry was indexed.
        status: index entry status (ACTIVE/STALE/DELETED).
    """

    entry_id: UUID = field(default_factory=uuid4)
    embedding_id: UUID = field(default_factory=uuid4)
    chunk_id: UUID = field(default_factory=uuid4)
    # The canonical node represented by this chunk.  Chunk IDs are disposable;
    # citations must point to immutable Knowledge Tree node IDs.
    knowledge_node_id: UUID = field(default_factory=uuid4)
    document_id: UUID = field(default_factory=uuid4)
    version_id: UUID = field(default_factory=uuid4)
    vault_id: Optional[UUID] = None
    vector: list[float] = field(default_factory=list)
    dimension: int = 0
    model: str = "unknown"
    model_version: str = "0.0.0"
    knowledge_tree_version: str = ""
    # The immutable chunk wording is retained with the derived index entry so
    # retrieval can return evidence, not an implementation/version string.
    chunk_text: str = ""
    chunk_type: str = "PARAGRAPH"
    canonical_references: list[str] = field(default_factory=list)
    page_start: int = 1
    page_end: int = 1
    document_status: str = "ACTIVE"
    language: str = "vi"
    created_at: datetime = field(default_factory=now_utc)
    status: str = "ACTIVE"


@dataclass
class SearchResult:
    """A single search result.

    Fields:
        entry: the indexed entry that matched.
        score: similarity score (higher = more similar).
        rank: position in the result list (1 = best).
    """

    entry: IndexEntry
    score: float
    rank: int = 0


# ---------------------------------------------------------------------------
# Similarity functions
# ---------------------------------------------------------------------------


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two vectors.

    Returns a value in [-1, 1]; higher means more similar.
    If either vector is zero-length, returns 0.0.
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


class SimilarityFunction:
    """Enum-like container for supported similarity functions."""

    COSINE = "cosine"
    DOT = "dot"
    EUCLIDEAN = "euclidean"

    @staticmethod
    def compute(name: str, a: list[float], b: list[float]) -> float:
        """Compute the specified similarity between two vectors."""
        if name == SimilarityFunction.COSINE:
            return cosine_similarity(a, b)
        if name == SimilarityFunction.DOT:
            return sum(x * y for x, y in zip(a, b))
        if name == SimilarityFunction.EUCLIDEAN:
            # Convert Euclidean distance to a similarity score
            dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
            return 1.0 / (1.0 + dist)
        raise ValueError(f"Unknown similarity function: {name}")

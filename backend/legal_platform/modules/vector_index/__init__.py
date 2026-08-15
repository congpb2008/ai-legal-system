"""Vector Index (tasks/008-vector-index.md, module Indexing).

The Vector Index is responsible for storing and searching embedding vectors.
It provides efficient similarity search over the document corpus.

Per the task:
    - Stores vectors
    - Updates vectors
    - Deletes vectors
    - Searches vectors
    - Filters by metadata
    - Supports version-aware indexing

The Vector Index does NOT:
    - Generate embeddings, parse documents, understand legal hierarchy,
      rank final answers, or generate citations.

The Vector Index is a derived datastore (ADR-003). The Knowledge Tree remains
the system of record. Index corruption never affects the Knowledge Tree.
"""

from legal_platform.modules.vector_index.index import (
    IndexEntry,
    SearchResult,
    SimilarityFunction,
    cosine_similarity,
)
from legal_platform.modules.vector_index.service import VectorIndexService

__all__ = [
    "IndexEntry",
    "SearchResult",
    "SimilarityFunction",
    "cosine_similarity",
    "VectorIndexService",
]
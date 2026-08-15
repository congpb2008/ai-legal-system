"""Reranker (tasks/010-reranker.md, module Retrieval).

The Reranker refines retrieval candidates and produces the final evidence set
that will be consumed by the Generation Service.

Per the spec:
    - The Retrieval Service prioritizes recall.
    - The Reranker prioritizes precision.
    - The Reranker scores candidates, improves ranking quality, removes weak
      candidates, reduces redundancy, optimizes evidence diversity, and
      respects the retrieval budget.
    - The Reranker does NOT retrieve new documents, generate answers, rewrite
      evidence, or modify Knowledge Trees.
"""

from legal_platform.modules.reranker.reranker import (
    Reranker,
    RerankerConfig,
    RerankedEvidence,
    RerankerMetadata,
)
from legal_platform.modules.reranker.service import RerankerService

__all__ = [
    "Reranker",
    "RerankerConfig",
    "RerankedEvidence",
    "RerankerMetadata",
    "RerankerService",
]
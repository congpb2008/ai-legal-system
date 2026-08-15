"""Embedding Service (tasks/007-embedding.md, module Embedding).

The Embedding Service converts retrieval chunks into vector representations
for semantic search.

Per the task:
    - Renders chunks into embedding text
    - Generates embeddings
    - Attaches metadata
    - Versions embeddings
    - Detects outdated embeddings
    - Submits vectors to the Vector Index

The Embedding Service does NOT:
    - Parse documents, build Knowledge Trees, retrieve documents,
      rank search results, or generate answers.

The embedding engine is replaceable (architecture.md Replaceability).
The application runtime uses native Ollama embeddings.  The deterministic
placeholder remains available only as an explicitly injected test double.
"""

from legal_platform.modules.embedding.engine import (
    EmbeddingEngine,
    EmbeddingEngineError,
    OllamaEmbeddingEngine,
    PlaceholderEmbedder,
    EmbeddingRecord,
    EmbeddingCollection,
)
from legal_platform.modules.embedding.service import EmbeddingService

__all__ = [
    "EmbeddingEngine",
    "EmbeddingEngineError",
    "OllamaEmbeddingEngine",
    "PlaceholderEmbedder",
    "EmbeddingRecord",
    "EmbeddingCollection",
    "EmbeddingService",
]

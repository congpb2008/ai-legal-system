"""Chunking (tasks/006-chunking.md, module Chunking).

The Chunking Service converts a validated Knowledge Tree into retrieval-ready
chunks. Chunking is entirely structure-aware — Knowledge Tree boundaries always
take priority over token limits.

Per the task:
    - Traverses the Knowledge Tree
    - Creates retrieval chunks
    - Preserves legal hierarchy, citations, node references
    - Estimates token counts
    - Splits oversized chunks
    - Merges undersized chunks when appropriate

The Chunking Service does NOT:
    - Parse documents, modify legal wording, generate embeddings,
      retrieve documents, or generate answers.

Chunks are derived, disposable artifacts (ADR-003) — they are NOT the source of
truth. The Knowledge Tree remains canonical.
"""

from legal_platform.modules.chunking.chunker import (
    Chunk,
    ChunkCollection,
    ChunkType,
    ChunkerConfig,
    StructureAwareChunker,
)
from legal_platform.modules.chunking.service import ChunkingService

__all__ = [
    "Chunk",
    "ChunkCollection",
    "ChunkType",
    "ChunkerConfig",
    "StructureAwareChunker",
    "ChunkingService",
]
"""Document Registry (tasks/001-document-registry.md, module Ingestion).

The Registry is the entry point of the knowledge ingestion pipeline. It stores,
manages and tracks every Document known by the platform. It assigns a stable
Document ID, stores metadata and processing status, tracks versions and legal
relationships, manages vault ownership, and performs duplicate detection by
checksum.

Per the task, the Registry does NOT:
    - parse PDF, OCR documents, generate embeddings, build Knowledge Trees,
      or answer user queries.

Security: never expose documents outside their vault; every operation requires
authorization; original files remain immutable.

Subpackages:
    - ``processing`` — the document processing state machine (Registry-owned, separate
      from the canonical Document ``status`` per design decision DC-003/ADR-003).
    - ``repository`` — persistence interface (storage-technology-agnostic).
    - ``service``    — the Registry service API.
"""

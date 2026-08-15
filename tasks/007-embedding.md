# Task 007 — Embedding Service

Status: Planned

Priority: High

Estimated Complexity: Medium

Dependencies

- Task 006 — Chunking

Related Specifications

- processing-pipeline.md
- architecture.md

Related Contracts

- knowledge-tree-contract.md

---

# Goal

Implement the Embedding Service.

The Embedding Service converts retrieval chunks into vector representations for semantic search.

The service is responsible only for vector generation.

It does not perform retrieval.

It does not understand legal meaning.

---

# Background

Embedding is the bridge between structured legal knowledge and semantic search.

Every retrieval chunk should have one corresponding embedding.

Embeddings are treated as derived data.

Knowledge Tree remains the source of truth.

---

# Responsibilities

The Embedding Service shall

- Render chunks into embedding text
- Generate embeddings
- Attach metadata
- Version embeddings
- Detect outdated embeddings
- Submit vectors to the Vector Index

The service shall NOT

- Parse documents
- Build Knowledge Trees
- Retrieve documents
- Rank search results
- Generate answers

---

# Inputs

Input

↓

Chunk Collection

↓

Embedding Configuration

Each chunk contains

- Chunk ID
- Node IDs
- Canonical References
- Metadata

---

# Outputs

Embedding Collection

↓

Embedding Metadata

↓

Ready for Vector Index

---

# Processing Flow

Chunk Collection

↓

Chunk Renderer

↓

Embedding Text

↓

Embedding Model

↓

Vector

↓

Metadata

↓

Vector Index

---

# Chunk Rendering

Embedding is generated from rendered chunk text.

The renderer is responsible for converting

Knowledge Nodes

↓

Readable Text

The Embedding Service never reconstructs legal structure.

---

# Embedding Metadata

Each embedding shall contain

Embedding ID

Chunk ID

Document ID

Knowledge Tree Version

Embedding Model

Embedding Model Version

Embedding Dimension

Embedding Timestamp

Embedding Status

---

# Versioning

Embeddings are versioned independently.

Changes requiring re-embedding include

Knowledge Tree updated

↓

Chunk definition changed

↓

Embedding model changed

↓

Embedding configuration changed

Older embeddings remain available until replacement succeeds.

---

# Re-Embedding

The service shall support asynchronous re-embedding.

Possible triggers

- New embedding model
- Better multilingual model
- Chunk update
- Knowledge Tree migration

Re-embedding should not interrupt retrieval.

---

# Validation

Validate

Embedding successfully generated

↓

Dimension matches configuration

↓

Metadata complete

↓

Chunk exists

↓

Knowledge Tree version exists

Invalid embeddings shall not be indexed.

---

# Batch Processing

Embeddings should be generated in batches.

Large document collections may be processed incrementally.

Parallel workers are supported.

---

# Logging

Record

Embedding Job ID

Embedding Model

Model Version

Document Count

Chunk Count

Execution Time

Failure Count

Warnings

---

# Performance

Embedding generation should execute asynchronously.

Multiple embedding workers may run concurrently.

Generation failures should be retryable.

---

# Error Handling

Possible failures

Embedding model unavailable

↓

Timeout

↓

Chunk missing

↓

Dimension mismatch

↓

Invalid metadata

Every failure shall be logged.

Retry policy is implementation-specific.

---

# Security

Embedding vectors inherit the permissions of their originating document.

Embeddings shall never be shared across unauthorized vaults.

---

# Acceptance Criteria

The task is complete when

✓ Every chunk receives one embedding.

✓ Metadata is complete.

✓ Version information is recorded.

✓ Embeddings are submitted to the Vector Index.

✓ Failed embeddings can be retried.

✓ Re-embedding workflow functions correctly.

---

# Out of Scope

OCR

Parser

Knowledge Tree

Chunking

Vector Search

Retrieval

Generation

Citation

Ranking

---

# Future Improvements

Hybrid embeddings

Multi-vector embeddings

Sparse embeddings

Late interaction models

Incremental embedding

Cross-encoder integration

Embedding quality benchmarking

Automatic model migration
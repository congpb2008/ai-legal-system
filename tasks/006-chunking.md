# Task 006 — Chunking

Status: Planned

Priority: Critical

Estimated Complexity: High

Dependencies

- Task 005 — Knowledge Tree Builder

Related Contracts

- knowledge-tree-contract.md

Related Specifications

- knowledge-tree-specification.md
- processing-pipeline.md

Related Examples

- knowledge-tree-example.json

---

# Goal

Implement the Chunking Service.

The Chunking Service converts a validated Knowledge Tree into retrieval-ready chunks.

Chunking is entirely structure-aware.

Knowledge Tree boundaries always take priority over token limits.

---

# Background

Large Language Models cannot process an entire legal corpus efficiently.

Knowledge must therefore be divided into retrieval units.

A retrieval unit is called a Chunk.

Each Chunk represents a coherent legal concept while preserving traceability back to the Knowledge Tree.

---

# Responsibilities

The Chunking Service shall

- Traverse the Knowledge Tree
- Create retrieval chunks
- Preserve legal hierarchy
- Preserve citations
- Preserve node references
- Estimate token counts
- Split oversized chunks
- Merge undersized chunks when appropriate

The Chunking Service shall NOT

- Parse documents
- Modify legal wording
- Generate embeddings
- Retrieve documents
- Generate answers

---

# Inputs

Input

↓

Knowledge Tree

↓

Chunking Configuration

---

# Outputs

Chunk Collection

↓

Chunk Metadata

↓

Ready for Embedding

---

# Processing Flow

Knowledge Tree

↓

Node Traversal

↓

Candidate Chunk

↓

Token Estimation

↓

Boundary Decision

↓

Chunk Generation

↓

Chunk Validation

---

# Chunking Principles

Chunk boundaries are determined by

1.

Knowledge Tree

↓

2.

Legal Meaning

↓

3.

Token Size

Token limits never override legal hierarchy unless absolutely necessary.

---

# Preferred Chunk Boundaries

Preferred

Article

↓

Clause

↓

Point

Appendix

Avoid splitting inside

- A sentence
- A clause
- A legal definition

unless token limits require it.

---

# Chunk Types

Supported chunk types

ARTICLE

CLAUSE

POINT

APPENDIX

COMPOSITE

Future chunk types may be added.

---

# Oversized Chunks

If a chunk exceeds the configured token limit

Attempt

Article

↓

Clause

↓

Point

↓

Sentence

Splitting should preserve legal meaning whenever possible.

---

# Undersized Chunks

Very small chunks may be merged with adjacent siblings.

Merging rules

Same Parent

↓

Same Legal Context

↓

Within Token Budget

Chunks from different Articles shall never be merged.

---

# Chunk Metadata

Each chunk shall contain

Chunk ID

Document ID

Node IDs

Canonical References

Chunk Type

Estimated Tokens

Hierarchy Path

Creation Version

Source Mapping

---

# Traceability

Every chunk must reference

Original Knowledge Nodes

↓

Original Pages

↓

Original Lines

Chunk content must always be traceable back to the source document.

---

# Validation

Every chunk shall satisfy

At least one Knowledge Node

No duplicate Node IDs

Stable ordering

Valid references

Token estimate recorded

Valid Chunk ID

---

# Chunk Ordering

Chunk order follows the original document order.

Ordering must remain deterministic.

Repeated chunk generation from the same document shall produce identical results.

---

# Configuration

Configurable parameters

Preferred Chunk Size

Maximum Chunk Size

Minimum Chunk Size

Maximum Overlap

Merge Threshold

These parameters are implementation-specific.

---

# Logging

Record

Chunk Job ID

Document ID

Chunk Count

Average Tokens

Largest Chunk

Smallest Chunk

Execution Time

Warnings

Errors

---

# Performance

Chunk generation should execute in linear time relative to Knowledge Tree size.

Chunk generation should not require reparsing the document.

---

# Acceptance Criteria

The task is complete when

✓ Chunks are generated from the Knowledge Tree.

✓ Chunk boundaries respect legal hierarchy.

✓ Oversized chunks are split correctly.

✓ Small chunks are merged appropriately.

✓ Traceability is preserved.

✓ Chunk ordering is deterministic.

✓ Chunk metadata is complete.

---

# Out of Scope

OCR

Parser

Knowledge Tree construction

Embedding

Retrieval

Generation

Citation

Semantic ranking

---

# Future Improvements

Adaptive chunking

Query-aware chunking

Multi-resolution chunks

Table-aware chunks

Automatic overlap optimization

Incremental chunk updates

Chunk quality benchmarking
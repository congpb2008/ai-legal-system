# Task 009 — Retrieval Service

Status: Planned

Priority: Critical

Estimated Complexity: Very High

Dependencies

- Task 008 — Vector Index

Related Specifications

- architecture.md
- processing-pipeline.md

Related Contracts

- retrieval-contract.md
- knowledge-tree-contract.md

Related Examples

- retrieval-example.json

---

# Goal

Implement the Retrieval Service.

The Retrieval Service is responsible for discovering the most relevant legal evidence for a user query.

The Retrieval Service returns evidence.

It does not generate answers.

It does not summarize.

It does not interpret legal meaning.

---

# Background

The Retrieval Service bridges user intent and indexed legal knowledge.

It transforms a natural language query into a ranked collection of evidence.

Generation depends entirely on retrieval quality.

---

# Responsibilities

The Retrieval Service shall

- Understand search intent
- Build retrieval queries
- Perform hybrid retrieval
- Rank candidate evidence
- Remove duplicates
- Expand legal context
- Return Retrieval Contract

The service shall NOT

- Generate answers
- Rewrite legal text
- Perform OCR
- Parse documents
- Build embeddings

---

# Inputs

Input

↓

User Query

↓

Retrieval Options

Optional filters

- Vault
- Document
- Document Type
- Date
- Status
- Knowledge Tree Version

---

# Outputs

Retrieval Contract

↓

Evidence List

↓

Ranking Metadata

↓

Diagnostics

---

# Processing Flow

User Query

↓

Query Analysis

↓

Query Embedding

↓

Hybrid Search

↓

Candidate Collection

↓

Re-ranking

↓

Context Expansion

↓

Deduplication

↓

Retrieval Contract

---

# Query Analysis

The Retrieval Service shall identify

- User intent
- Possible legal references
- Explicit article numbers
- Keywords
- Named entities

Example

"What are the procurement requirements for server purchases?"

↓

Intent

↓

Possible keywords

↓

Potential article references

---

# Search Strategy

The Retrieval Service should support

Semantic Search

+

Keyword Search

+

Metadata Filtering

Hybrid search is the preferred strategy.

Individual search strategies remain replaceable.

---

# Candidate Collection

Retrieve more evidence than ultimately returned.

Example

Top 50

↓

Re-rank

↓

Top 10

↓

Context Expansion

↓

Final Top 8

---

# Re-ranking

Candidates should be ordered by

Semantic relevance

↓

Legal hierarchy

↓

Document priority

↓

Version status

↓

Confidence

The exact ranking algorithm is implementation-specific.

---

# Context Expansion

Legal documents often require surrounding context.

If a retrieved node belongs to

Clause 2

The service may also retrieve

Article

Sibling Clauses

Definitions

Appendices

Context expansion must remain configurable.

---

# Duplicate Removal

Duplicate evidence shall be removed.

Duplicate means

Same Knowledge Node

or

Same Canonical Reference

The highest-ranked evidence is retained.

---

# Retrieval Metadata

Each evidence item shall contain

Chunk ID

Knowledge Node IDs

Document ID

Document Version

Canonical References

Similarity Score

Ranking Score

Retrieval Method

Source Mapping

---

# Source Traceability

Every retrieved item must reference

Knowledge Nodes

↓

Document

↓

Pages

↓

Lines

No retrieved evidence may lose traceability.

---

# Vault Awareness

Retrieval must never search outside authorized vaults.

Common Vault

↓

Department Vault

↓

Personal Vault

Permission filtering occurs before evidence is returned.

---

# Freshness

Prefer

Active documents

↓

Latest versions

↓

Non-superseded documents

Historical documents remain searchable when explicitly requested.

---

# Validation

The Retrieval Contract must satisfy

Valid Chunk IDs

↓

Valid Knowledge Nodes

↓

Existing Documents

↓

Authorized Vault

↓

Source Mapping

↓

Canonical References

---

# Logging

Record

Retrieval Job ID

User ID

Vault

Query

Search Strategy

Retrieved Candidates

Final Results

Execution Time

Warnings

---

# Performance

Retrieval should execute within the configured latency budget.

Vector search, keyword search and metadata filtering may execute in parallel.

Re-ranking should operate on a bounded candidate set.

---

# Error Handling

Possible failures

Search backend unavailable

↓

Embedding unavailable

↓

Vault inaccessible

↓

Invalid filters

↓

Timeout

Return structured retrieval errors.

Never fabricate evidence.

---

# Security

The Retrieval Service shall enforce

Authentication

Authorization

Vault isolation

Document visibility

Every retrieved item must satisfy access policy.

---

# Acceptance Criteria

The task is complete when

✓ Relevant evidence is returned.

✓ Retrieval Contract validation passes.

✓ Hybrid search functions correctly.

✓ Re-ranking improves candidate quality.

✓ Context expansion works.

✓ Duplicate evidence is removed.

✓ Source traceability is preserved.

---

# Out of Scope

OCR

Parser

Knowledge Tree construction

Chunking

Embedding generation

Answer generation

Citation formatting

Legal reasoning

---

# Future Improvements

Cross-encoder reranking

Query rewriting

Multi-hop retrieval

Graph retrieval

Adaptive retrieval

Learning-to-rank

Personalized retrieval

Query cache

Hybrid sparse+dense search

Multi-vector retrieval
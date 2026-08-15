# Task 010 — Reranker

Status: Planned

Priority: High

Estimated Complexity: High

Dependencies

- Task 009 — Retrieval Service

Related Specifications

- architecture.md
- processing-pipeline.md

Related Contracts

- retrieval-contract.md

Related Examples

- retrieval-example.json

---

# Goal

Implement the Reranker.

The Reranker refines retrieval candidates and produces the final evidence set that will be consumed by the Generation Service.

The Reranker improves ranking quality.

It never generates answers.

---

# Background

The Retrieval Service prioritizes recall.

The Reranker prioritizes precision.

The Retrieval Service intentionally retrieves more candidates than necessary.

The Reranker selects the best evidence.

---

# Responsibilities

The Reranker shall

- Score candidates
- Improve ranking quality
- Remove weak candidates
- Reduce redundancy
- Optimize evidence diversity
- Respect retrieval budget

The Reranker shall NOT

- Retrieve new documents
- Generate answers
- Rewrite evidence
- Modify Knowledge Trees

---

# Inputs

Input

↓

Retrieval Contract

↓

Candidate Evidence

↓

Ranking Configuration

---

# Outputs

Ranked Evidence

↓

Ranking Metadata

↓

Ready for Generation

---

# Processing Flow

Candidate Evidence

↓

Candidate Validation

↓

Feature Extraction

↓

Scoring

↓

Duplicate Detection

↓

Budget Optimization

↓

Final Evidence

---

# Ranking Objectives

Evidence should be ranked by

Semantic Relevance

↓

Legal Relevance

↓

Authority

↓

Freshness

↓

Coverage

↓

Diversity

Exact weighting is implementation-specific.

---

# Candidate Validation

Reject

Missing chunks

Missing references

Unauthorized documents

Inactive documents

Invalid metadata

---

# Duplicate Handling

Duplicates should be removed.

Examples

Same Chunk

↓

Same Knowledge Node

↓

Same Canonical Reference

↓

Same Meaning

Keep only the strongest candidate.

---

# Diversity

Avoid returning

Five nearly identical clauses.

Prefer

Article

↓

Clause

↓

Definition

↓

Appendix

when all contribute useful context.

---

# Budget Optimization

Generation has a finite context window.

The Reranker must maximize information density.

Given

40 candidates

↓

Select

Best N

where N satisfies

Context Budget

Coverage

Citation Quality

---

# Ranking Metadata

Each ranked evidence shall contain

Rank

Ranking Score

Similarity Score

Retrieval Method

Selection Reason

Chunk ID

Knowledge Nodes

Canonical References

---

# Validation

Final evidence shall satisfy

Authorized

↓

Traceable

↓

Unique

↓

Ranked

↓

Within Budget

---

# Logging

Record

Ranking Job ID

Input Candidates

Output Candidates

Execution Time

Ranking Strategy

Warnings

Errors

---

# Performance

The Reranker operates on a bounded candidate set.

Execution time should scale linearly with candidate count whenever possible.

---

# Error Handling

Possible failures

Ranking model unavailable

↓

Invalid metadata

↓

Duplicate failure

↓

Budget overflow

↓

Timeout

Return structured ranking errors.

---

# Security

Ranking shall never bypass vault permissions.

Only authorized evidence may enter the final ranking.

---

# Acceptance Criteria

The task is complete when

✓ Candidate quality improves.

✓ Duplicate evidence is removed.

✓ Context budget is respected.

✓ Ranking metadata is generated.

✓ Evidence diversity improves.

✓ Retrieval Contract remains valid.

---

# Out of Scope

OCR

Parser

Knowledge Tree

Chunking

Embedding

Retrieval

Generation

Citation formatting

Legal reasoning

---

# Future Improvements

Cross Encoder

Late Interaction Models

Learning-to-Rank

Neural Reranking

Policy-based Ranking

Domain-specific Ranking

Adaptive Ranking

LLM-assisted Ranking
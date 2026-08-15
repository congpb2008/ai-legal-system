# Task 012 — Citation Builder

Status: Planned

Priority: Critical

Estimated Complexity: High

Dependencies

- Task 011 — Generation Service

Related Specifications

- architecture.md
- processing-pipeline.md

Related Contracts

- answer-contract.md
- retrieval-contract.md
- knowledge-tree-contract.md

Related Examples

- answer-example.json

---

# Goal

Implement the Citation Builder.

The Citation Builder is responsible for constructing, validating and attaching citations to generated answers.

Every factual statement must be traceable back to retrieved evidence.

The Citation Builder does not generate answers.

It validates them.

---

# Background

The platform prioritizes

Accuracy

↓

Citation

↓

Speed

A legal answer without citations is incomplete.

The Citation Builder guarantees traceability between generated responses and the Knowledge Tree.

---

# Responsibilities

The Citation Builder shall

- Build citations
- Validate citations
- Resolve canonical references
- Resolve page references
- Resolve line references
- Detect unsupported claims
- Attach citation metadata

The Citation Builder shall NOT

- Retrieve evidence
- Generate answers
- Rewrite legal wording
- Interpret legal meaning

---

# Inputs

Input

↓

Draft Answer

↓

Evidence Package

↓

Knowledge Tree

---

# Outputs

Verified Answer

↓

Citation List

↓

Validation Report

↓

Answer Contract

---

# Processing Flow

Draft Answer

↓

Sentence Segmentation

↓

Claim Detection

↓

Evidence Mapping

↓

Citation Resolution

↓

Citation Validation

↓

Verified Answer

---

# Citation Model

Every citation shall reference

Document

↓

Knowledge Node

↓

Canonical Reference

↓

Page

↓

Line

↓

Evidence ID

Every citation must be uniquely identifiable.

---

# Claim Detection

The Citation Builder shall identify

Statements of fact

↓

Legal requirements

↓

Definitions

↓

Exceptions

↓

Dates

↓

Thresholds

↓

Legal references

Only supported claims may receive citations.

---

# Evidence Mapping

Every factual claim shall map to one or more evidence items.

Possible mappings

One Claim

↓

One Evidence

or

One Claim

↓

Multiple Evidence

Many-to-many mappings are allowed.

---

# Citation Resolution

Resolve

Document ID

↓

Knowledge Node IDs

↓

Canonical References

↓

Page Numbers

↓

Line Numbers

↓

Evidence IDs

All references originate from the Knowledge Tree.

---

# Citation Validation

Validate

Evidence exists

↓

Node exists

↓

Canonical Reference exists

↓

Page exists

↓

Line exists

↓

Evidence belongs to the Evidence Package

↓

User has permission

Invalid citations shall be rejected.

---

# Unsupported Claims

If a claim cannot be mapped

Return

Unsupported Claim

↓

Validation Failure

↓

Generation Retry (optional)

The platform shall never fabricate citations.

---

# Citation Granularity

Preferred granularity

Clause

↓

Point

↓

Sentence

↓

Article

Avoid citing entire documents when a more precise reference exists.

---

# Multiple Citations

A claim may reference

Multiple clauses

Multiple articles

Multiple documents

Multiple citations shall be preserved.

---

# Citation Metadata

Each citation shall contain

Citation ID

Evidence ID

Document ID

Knowledge Node IDs

Canonical Reference

Page

Line

Confidence

Citation Version

---

# Validation Report

Produce

Supported Claims

Unsupported Claims

Citation Coverage

Validation Errors

Warnings

Generation Status

The report is intended for diagnostics.

---

# Logging

Record

Citation Job ID

Answer ID

Citation Count

Coverage

Validation Result

Execution Time

Warnings

Errors

---

# Performance

Citation validation should scale linearly with the number of claims.

Repeated evidence lookups should be cached where appropriate.

---

# Error Handling

Possible failures

Missing evidence

↓

Invalid reference

↓

Missing page mapping

↓

Permission denied

↓

Validation timeout

Return structured validation errors.

---

# Security

Citation Builder shall never expose

Unauthorized documents

Unauthorized evidence

Hidden vaults

Permission validation occurs before citations are attached.

---

# Acceptance Criteria

The task is complete when

✓ Every supported claim has citations.

✓ Unsupported claims are detected.

✓ Citations resolve to Knowledge Nodes.

✓ Canonical references are correct.

✓ Page and line references are valid.

✓ Answer Contract validation passes.

---

# Out of Scope

OCR

Parser

Knowledge Tree construction

Chunking

Embedding

Retrieval

Ranking

Answer generation

Legal reasoning

---

# Future Improvements

Interactive citations

Inline citation viewer

Citation confidence scoring

Citation deduplication

Visual document highlighting

Citation quality benchmarking

Automatic citation repair
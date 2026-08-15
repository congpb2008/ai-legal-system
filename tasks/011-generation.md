# Task 011 — Generation Service

Status: Planned

Priority: Critical

Estimated Complexity: High

Dependencies

- Task 010 — Reranker

Related Specifications

- architecture.md
- processing-pipeline.md

Related Contracts

- answer-contract.md
- retrieval-contract.md

Related Examples

- answer-example.json

---

# Goal

Implement the Generation Service.

The Generation Service converts retrieved evidence into a clear, structured response for the user.

The service explains retrieved evidence.

It never invents legal facts.

It never retrieves additional evidence.

---

# Background

Generation is the final stage of the RAG pipeline.

Its responsibility is presentation rather than discovery.

All factual information must originate from the Evidence Package.

---

# Responsibilities

The Generation Service shall

- Interpret the user question
- Read the Evidence Package
- Compose a natural-language answer
- Attach citations
- Explain supporting context
- Report uncertainty when evidence is insufficient

The service shall NOT

- Retrieve new evidence
- Ignore retrieved evidence
- Invent legal content
- Modify legal wording inside citations
- Perform legal reasoning beyond available evidence

---

# Inputs

Input

↓

User Query

↓

Evidence Package

↓

Generation Configuration

---

# Outputs

Answer Contract

↓

Answer

↓

Citation List

↓

Generation Metadata

---

# Processing Flow

User Query

↓

Read Evidence Package

↓

Evidence Interpretation

↓

Answer Planning

↓

Answer Generation

↓

Citation Assembly

↓

Answer Validation

↓

Answer Contract

---

# Answer Structure

Every answer should contain

Summary

↓

Explanation

↓

Supporting Evidence

↓

Citations

↓

Confidence

The exact presentation format is configurable.

---

# Evidence Usage

Every factual statement shall be supported by retrieved evidence.

Evidence may be

Quoted

or

Paraphrased

Original legal wording shall be preserved whenever quoting.

---

# Citation Requirements

Every legal statement shall reference

Document

↓

Canonical Reference

↓

Page

↓

Line

The user must be able to trace every statement back to the source.

---

# Confidence

Generation shall report confidence.

Confidence reflects

Evidence Quality

↓

Evidence Coverage

↓

Retrieval Confidence

Generation confidence is never based solely on model confidence.

---

# Missing Evidence

If evidence is insufficient

The service shall

State that available evidence is insufficient.

Explain what information is missing.

Avoid speculation.

Never fabricate an answer.

---

# Multiple Documents

When evidence comes from multiple documents

Clearly distinguish

Document A

↓

Document B

↓

Relationship

The service shall never merge conflicting evidence silently.

---

# Conflicting Evidence

When conflicting evidence exists

Present both.

Identify

- Active version
- Historical version (if applicable)

Explain the relationship when known.

Do not choose one without evidence.

---

# Formatting

Preferred answer style

Direct answer

↓

Detailed explanation

↓

Evidence

↓

Citations

↓

Notes

Formatting is independent of the LLM implementation.

---

# Validation

Before returning an answer verify

Every citation exists.

↓

Every citation references retrieved evidence.

↓

No unsupported claims exist.

↓

Answer Contract validation passes.

---

# Logging

Record

Generation Job ID

User Query

Evidence Count

Generation Model

Generation Version

Execution Time

Warnings

Errors

---

# Performance

Generation should minimize latency while preserving citation quality.

Generation shall operate only on the supplied Evidence Package.

---

# Error Handling

Possible failures

Generation model unavailable

↓

Evidence Package invalid

↓

Citation assembly failure

↓

Context overflow

↓

Timeout

Return structured generation errors.

---

# Security

Generation inherits all retrieval permissions.

The service shall never reveal evidence outside the authorized Evidence Package.

---

# Acceptance Criteria

The task is complete when

✓ Answer Contract is produced.

✓ Every statement is supported.

✓ Citations are complete.

✓ Unsupported claims are rejected.

✓ Missing evidence is reported.

✓ Conflicting evidence is presented correctly.

---

# Out of Scope

OCR

Parser

Knowledge Tree

Chunking

Embedding

Retrieval

Ranking

Document comparison

Legal decision making

---

# Future Improvements

Structured answer templates

Interactive citation viewer

Answer refinement

Multi-turn generation

LLM ensemble generation

Streaming responses

Domain-specific prompting

Automatic explanation quality evaluation
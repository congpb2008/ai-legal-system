# Processing Pipeline

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document describes how data flows through the Banking Legal Platform.

Unlike the Architecture document, which defines system organization, this document defines the lifecycle of documents and user queries.

Every processing stage is deterministic, contract-driven and independently replaceable.

---

# Pipeline Overview

The platform contains two independent pipelines.

```
Document Pipeline

Upload

↓

Knowledge
```

```
Query Pipeline

Question

↓

Answer
```

The Document Pipeline prepares knowledge.

The Query Pipeline consumes knowledge.

---

# Pipeline 1 — Document Processing

The document pipeline transforms uploaded legal documents into canonical legal knowledge.

```
Upload

↓

OCR

↓

Parser

↓

Knowledge Tree

↓

Chunk Generation

↓

Embedding

↓

Index

↓

Ready
```

Only the Knowledge Tree is considered canonical.

Everything after that is derived data.

---

# Stage 1 — Upload

Input:

Document File

Output:

Document Contract

Responsibilities:

- file validation
- metadata collection
- vault assignment
- version registration

Failure:

- unsupported format
- corrupted file

---

# Stage 2 — OCR

Consumes:

Document Contract

Produces:

OCR Text

Responsibilities:

- text extraction
- page mapping
- confidence estimation

Rules:

Original files are never modified.

OCR output remains traceable to the source document.

If OCR confidence falls below an acceptable threshold,

manual review may be requested.

---

# Stage 3 — Parsing

Consumes:

OCR Text

Produces:

Knowledge Tree Contract

Responsibilities:

- detect legal hierarchy
- detect document structure
- identify chapters
- identify articles
- identify clauses
- identify points
- preserve original wording

The parser never summarizes.

The parser never interprets legal meaning.

---

# Stage 4 — Knowledge Tree

Consumes:

Knowledge Tree Contract

Produces:

Persistent Legal Knowledge

Responsibilities:

- validation
- persistence
- version management
- structural verification

The Knowledge Tree becomes the canonical representation of the document.

---

# Stage 5 — Chunk Generation

Consumes:

Knowledge Tree

Produces:

Chunk Collection

Responsibilities:

- create retrieval units
- preserve context
- preserve source mapping

Chunks are optimized for retrieval.

Chunks are not business objects.

---

# Stage 6 — Embedding

Consumes:

Chunks

Produces:

Embedding Collection

Responsibilities:

- vector generation
- embedding versioning

Embeddings contain no legal meaning.

They are retrieval artifacts.

---

# Stage 7 — Indexing

Consumes:

Embeddings

Produces:

Search Index

Responsibilities:

- keyword index
- vector index
- metadata index

Indexes are disposable.

Indexes may always be regenerated.

---

# Stage 8 — Ready

The document becomes searchable.

No additional processing is required until:

- document replacement
- parser upgrade
- OCR upgrade
- embedding upgrade

---

# Reprocessing Pipeline

Documents may be reprocessed.

```
Document

↓

Re-OCR

↓

Re-Parse

↓

Re-Chunk

↓

Re-Embed

↓

Re-Index
```

Reprocessing never changes Document identity.

A new Knowledge Tree is produced.

Historical versions remain available.

---

# Pipeline 2 — Query Processing

The query pipeline transforms user intent into an evidence-based answer.

```
Question

↓

Query Understanding

↓

Retrieval

↓

Evidence

↓

Generation

↓

Citation

↓

Answer
```

---

# Stage 1 — Query

Input:

Natural language question

Examples:

- Which regulation applies?

- Compare Circular A and Circular B.

- Summarize this decision.

---

# Stage 2 — Query Understanding

Responsibilities:

- identify user intent
- detect requested documents
- detect filters
- identify vault scope

No legal reasoning occurs.

The system only prepares retrieval.

---

# Stage 3 — Retrieval

Consumes:

Knowledge Tree

Indexes

Produces:

Retrieval Contract

Responsibilities:

- keyword search
- semantic search
- hybrid search
- ranking
- filtering

Retrieval never generates text.

---

# Stage 4 — Evidence Selection

Responsibilities:

- collect supporting evidence
- remove duplicates
- preserve ranking
- preserve traceability

Evidence always references original Knowledge Nodes.

---

# Stage 5 — Generation

Consumes:

Retrieval Contract

Produces:

Answer Contract

Responsibilities:

- explain
- summarize
- compare
- format

Generation never invents legal information.

---

# Stage 6 — Citation

Responsibilities:

- attach legal references
- attach source anchors
- attach document references

Every factual statement should remain traceable.

---

# Stage 7 — Delivery

The client receives:

- response
- citations
- confidence
- limitations

No internal implementation details are exposed.

---

# Failure Handling

Failures terminate the pipeline early.

Examples:

Upload Failure

↓

Stop

---

OCR Failure

↓

Stop

---

Parser Failure

↓

Stop

---

No Evidence

↓

Answer Contract

status = NO_EVIDENCE

The platform never fabricates information.

---

# Pipeline Independence

The Document Pipeline and Query Pipeline are independent.

Uploading documents never requires user queries.

Answering questions never modifies stored knowledge.

---

# Replaceable Components

The following stages may be replaced independently.

- OCR
- Parser
- Chunk Generator
- Embedding Model
- Vector Database
- Retrieval Strategy
- LLM

Replacement never changes Contracts.

---

# Observability

Every processing stage records:

- execution time
- processing version
- warnings
- errors

Every output remains traceable to its originating input.

---

# Summary

```
Knowledge Creation

Upload

↓

Knowledge Tree

↓

Search Infrastructure

==============================

Knowledge Consumption

Question

↓

Evidence

↓

Answer
```

The two pipelines are connected only through the Knowledge Layer.

Knowledge is created once.

Knowledge is consumed many times.
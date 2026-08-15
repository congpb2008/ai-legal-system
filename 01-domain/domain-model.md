# Domain Model

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the core business entities of the Banking Legal Platform.

The Domain Model is implementation-independent.

It describes the business concepts managed by the platform and their relationships.

---

# Design Principles

The domain model must:

- represent business concepts
- remain stable over time
- avoid implementation details
- remain independent of storage technology
- remain independent of AI models

---

# Domain Overview

```

```text
Organization

└── Vault

      ├── Document

      │      ├── Document Version

      │      │      ├── Knowledge Tree

      │      │      │      ├── Nodes
      │      │      │      └── Relationships

      │      │      ├── Chunks

      │      │      ├── Embeddings

      │      │      └── Search Index

      │      └── Metadata

      └── Users
```

---

# Entity Definitions

---

## Organization

Represents the institution owning the platform.

Examples:

- Bank
- Company
- Government Agency

Responsibilities:

- Owns Vaults
- Owns Users

---

## User

Represents a platform user.

Examples:

- IT Staff
- Procurement Staff
- Legal Staff
- Administrator

Responsibilities:

- Search documents
- Upload documents
- Ask AI questions

---

## Vault

Logical container for documents.

Examples:

Personal Vault

Department Vault

Shared Vault

Responsibilities:

- isolate documents
- enforce permissions
- organize knowledge

---

## Document

Represents one logical legal document.

Examples:

Circular 12/2024

Internal Procurement Regulation

Law on Credit Institutions

A Document is independent from file format.

---

## Document Version

Represents one published revision of a Document.

Examples:

Version 2024

Version 2025

Responsibilities:

- preserve history
- enable version comparison
- support effective dates

---

## Source File

Represents uploaded files.

Examples:

PDF

DOCX

Scanned PDF

Multiple files may correspond to one document version.

---

## Knowledge Tree

Canonical representation of one Document Version.

Responsibilities:

- preserve hierarchy
- preserve wording
- support retrieval

---

## Knowledge Node

Atomic structural unit inside the Knowledge Tree.

Examples:

Article

Clause

Point

Appendix

---

## Chunk

Retrieval projection generated from Knowledge Nodes.

Chunks are temporary derived artifacts.

They are not part of the legal document.

---

## Embedding

Vector representation of one Chunk.

Embeddings are disposable.

---

## Search Index

Retrieval structure built from chunks.

May include:

Keyword Index

Vector Index

Hybrid Index

---

## Citation

Reference from an AI response to one or more Knowledge Nodes.

Responsibilities:

- traceability
- explainability

---

## AI Response

Represents one generated answer.

Contains:

Question

Retrieved Evidence

Generated Answer

Citations

Confidence

---

# Relationships

## Organization

owns

Vault

---

## Vault

contains

Document

---

## Document

contains

Document Versions

---

## Document Version

owns

Knowledge Tree

---

## Knowledge Tree

contains

Knowledge Nodes

---

## Knowledge Tree

produces

Chunks

---

## Chunk

produces

Embedding

---

## Chunk

indexed by

Search Index

---

## AI Response

references

Citation

---

## Citation

references

Knowledge Node

---

# Lifecycle

```

```text
Source File

↓

Document

↓

Document Version

↓

Knowledge Tree

↓

Chunk

↓

Embedding

↓

Search Index

↓

Retrieval

↓

AI Response

↓

Citation
```

---

# Ownership Rules

Original Source File

↓

owns

Document Version

↓

owns

Knowledge Tree

↓

owns

Knowledge Nodes

Knowledge Tree

↓

generates

Chunks

Chunks

↓

generate

Embeddings

Embeddings

↓

populate

Search Index

---

# Immutability Rules

Immutable:

- Source File
- Document Version
- Knowledge Tree
- Knowledge Node

Disposable:

- OCR Output
- Chunk
- Embedding
- Search Index

---

# Invariants

A Chunk must belong to exactly one Document Version.

A Knowledge Node belongs to exactly one Knowledge Tree.

A Knowledge Tree belongs to exactly one Document Version.

A Document Version belongs to exactly one Document.

A Citation must reference existing Knowledge Nodes.

Embeddings never exist without Chunks.

Search Indexes never exist without Embeddings or Keywords.

---

# Non-Domain Concepts

The following are infrastructure concerns and are NOT domain entities:

- PostgreSQL
- Redis
- Qdrant
- Elasticsearch
- OCR Engine
- LLM
- Embedding Model
- Parser Implementation
- REST API
- Message Queue

These belong to the Architecture document.
# Document Contract

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the canonical representation of a Document within the Banking Legal Platform.

A Document represents a logical legal publication independent of any uploaded file, storage mechanism or processing pipeline.

The Document Contract is the root entity of the document lifecycle.

All downstream processing begins from a Document.

---

# Design Principles

A Document:

- represents a logical publication
- is independent of storage format
- owns one or more Document Versions
- never contains parsed knowledge directly
- never stores embeddings or retrieval artifacts

---

# Responsibilities

A Document is responsible for:

- representing a legal publication
- maintaining document identity
- grouping document versions
- exposing document metadata
- participating in search and retrieval

A Document is NOT responsible for:

- OCR
- Parsing
- Chunking
- Embeddings
- AI Generation
- Indexing

---

# Identity

Every Document has a globally unique identifier.

The identifier remains stable throughout the document lifetime.

Changing metadata does not create a new Document.

Uploading a revised legal publication creates a new Document Version, not a new Document.

---

# Ownership

```

```text
Document

├── Metadata

├── Versions

└── Access Control Reference
```

A Document owns:

- Metadata
- Document Versions

A Document references:

- Vault
- Organization
- Permissions

---

# Lifecycle

```text
Created

↓

Active

↓

Archived
```

A Document is never physically deleted by normal business operations.

Archived documents remain available for historical reference unless retention policies specify otherwise.

---

# Contract

```yaml
Document

id:
    UUID

type:
    DocumentType

title:
    string

short_title:
    string | null

description:
    string | null

issuing_authority:
    string

document_number:
    string | null

language:
    string

status:
    ACTIVE
    ARCHIVED

visibility:
    PUBLIC
    DEPARTMENT
    PERSONAL

vault_id:
    UUID

organization_id:
    UUID

created_at:
    datetime

updated_at:
    datetime

metadata:
    Metadata

versions:
    List<DocumentVersionReference>
```

---

# Metadata

Metadata contains searchable business information.

Examples include:

- Document Type
- Issue Date
- Effective Date
- Expiration Date
- Tags
- Keywords

Metadata may evolve without changing document identity.

---

# Version Relationship

A Document may own one or more Document Versions.

Example:

```text
Circular 12/2024

├── Version 1

├── Version 2

└── Version 3
```

Only one version may be designated as the current effective version at any point in time.

Historical versions remain immutable.

---

# Source Files

A Document does not own uploaded files directly.

Uploaded files belong to a specific Document Version.

Example:

```text
Document

↓

Document Version

↓

Source Files
```

This allows multiple uploaded files to represent the same published version.

Examples:

- Original PDF
- OCR PDF
- DOCX
- Scanned Copy

---

# Search Behavior

Search operations may retrieve Documents using:

- Title
- Document Number
- Metadata
- Tags
- Issuing Authority

Full-text retrieval is performed through Knowledge Tree and Retrieval Contracts rather than directly from the Document.

---

# Security

A Document inherits access permissions from its assigned Vault.

The Document itself does not contain permission rules.

---

# Invariants

The following rules must always hold.

## INV-001

A Document must belong to exactly one Vault.

---

## INV-002

A Document must belong to exactly one Organization.

---

## INV-003

A Document must own at least one Document Version.

---

## INV-004

A Document identifier never changes.

---

## INV-005

Removing a Document Version does not change Document identity.

---

## INV-006

A Document never contains parsed content.

---

## INV-007

A Document never stores embeddings.

---

## INV-008

A Document never stores retrieval chunks.

---

## INV-009

A Document never stores AI-generated outputs.

---

# Extension Points

Future versions may support:

- Digital Signatures
- External References
- Classification Labels
- Retention Policies
- Regulatory Categories

These extensions must not alter the core Document identity.

---

# Relationships

```text
Organization

↓

Vault

↓

Document

↓

Document Version

↓

Knowledge Tree

↓

Knowledge Node

↓

Chunk

↓

Embedding
```

The Document Contract defines only the Document layer.

Downstream contracts define lower layers of the processing pipeline.

---

# Architectural Notes

The Document Contract represents business identity rather than physical storage.

It is intentionally independent from:

- databases
- object storage
- OCR engines
- parsers
- embedding models
- LLMs
- retrieval engines

This separation ensures long-term stability of the domain model while allowing implementation details to evolve independently.
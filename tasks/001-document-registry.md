# Task 001 — Document Registry

Status: Planned

Priority: High

Estimated Complexity: Medium

Dependencies:

- document-contract.md
- architecture.md
- module-specifications.md

Related Contracts:

- Document Contract

Related Examples:

- examples/document/active-decision.json

---

# Goal

Implement the Document Registry.

The Document Registry is responsible for storing, managing and tracking every document known by the platform.

It is the entry point of the knowledge ingestion pipeline.

The registry does NOT perform OCR, parsing, embedding or retrieval.

---

# Background

Every uploaded document must exist inside the registry before any processing begins.

The registry provides a canonical identity for every document.

All downstream modules reference documents by Document ID.

---

# Responsibilities

The Document Registry shall

- Register newly uploaded documents
- Store document metadata
- Store processing status
- Track document versions
- Track legal status
- Manage vault ownership
- Maintain relationships between documents

The registry shall NOT

- Parse PDF
- OCR documents
- Generate embeddings
- Build Knowledge Trees
- Answer user queries

---

# Inputs

Input

↓

Uploaded File

Required Metadata

- filename
- mime type
- uploader
- vault
- upload time

Optional Metadata

- title
- issuing authority
- document number

---

# Outputs

A valid Document Contract.

Example

Document ID

↓

Document Metadata

↓

Processing Status

↓

Ready for OCR

---

# Functional Requirements

The registry shall

Generate a unique Document ID.

Store immutable upload information.

Calculate file checksum.

Detect duplicate uploads.

Record upload timestamp.

Assign vault ownership.

Track processing status.

Store document lifecycle state.

---

# Processing States

A document may exist in one of the following states.

UPLOADED

↓

OCR_PENDING

↓

OCR_RUNNING

↓

OCR_COMPLETED

↓

PARSING_PENDING

↓

PARSING_RUNNING

↓

READY

↓

ARCHIVED

↓

FAILED

Only valid transitions are allowed.

---

# Duplicate Detection

Documents with identical checksums should be detected.

Duplicate handling policy.

Same checksum

↓

Existing document found

↓

Notify user

↓

Reuse existing document OR create a new version

Policy implementation is configurable.

---

# Versioning

The registry maintains document versions.

Examples

Original upload

↓

Version 1

↓

Version 2

↓

Version 3

Versions are immutable.

---

# Relationships

The registry stores document relationships.

Examples

Supersedes

Superseded By

Amends

Amended By

References

Relationship discovery is performed by downstream modules.

The registry only stores them.

---

# Vault Integration

Every document belongs to exactly one vault.

Examples

Legal Common

Internal Procurement

Personal Workspace

Future vault types may be added without modifying the registry.

---

# API

Required operations

Create Document

Get Document

List Documents

Update Metadata

Update Processing Status

Archive Document

Restore Document

Delete Document (administrative only)

---

# Validation

Reject unsupported file types.

Reject corrupted uploads.

Reject invalid metadata.

Reject empty files.

Reject invalid vault assignment.

---

# Error Handling

Document registration failures must never create partial records.

Every failed upload shall produce an audit log.

---

# Logging

Record

Document ID

Uploader

Timestamp

Vault

Checksum

Processing Status

Operation Duration

---

# Security

The registry shall never expose documents outside their vault.

Every operation requires authorization.

Original files must remain immutable.

---

# Acceptance Criteria

The task is complete when

✓ Documents receive unique IDs.

✓ Metadata is persisted.

✓ Processing status is tracked.

✓ Duplicate detection works.

✓ Vault ownership is assigned.

✓ Document Contract validation passes.

✓ Example document is accepted without modification.

---

# Out of Scope

OCR

Parser

Knowledge Tree

Chunking

Embedding

Retrieval

Generation

Citation

---

# Future Improvements

Automatic metadata extraction

Document preview

Document tagging

Document similarity

Bulk upload

Batch validation

Document lifecycle automation
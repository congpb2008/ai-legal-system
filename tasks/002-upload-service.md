# Task 002 — Upload Service

Status: Planned

Priority: High

Estimated Complexity: Medium

Dependencies:

- Task 001 — Document Registry
- document-contract.md
- architecture.md

Related Contracts:

- Document Contract

Related Examples:

- examples/document/active-decision.json

---

# Goal

Implement the Upload Service.

The Upload Service is responsible for receiving files from users and preparing them for registration.

It validates uploads, stores original files, and forwards valid documents to the Document Registry.

The Upload Service does NOT perform OCR, parsing, indexing or retrieval.

---

# Background

Uploading a file is not equivalent to registering a document.

The Upload Service only handles file transfer and storage.

Document identity is assigned by the Document Registry.

---

# Responsibilities

The Upload Service shall

- Receive uploaded files
- Validate upload requests
- Store original files
- Compute file checksum
- Detect upload corruption
- Forward metadata to the Document Registry

The Upload Service shall NOT

- Parse PDF
- OCR images
- Extract metadata
- Create Knowledge Trees
- Generate embeddings
- Answer user queries

---

# Inputs

Input

↓

HTTP Upload Request

Supported file types

- PDF
- DOCX

Future

- DOC
- TIFF
- PNG
- JPG

Upload metadata

- filename
- uploader
- vault
- optional description

---

# Outputs

Original file stored.

↓

Checksum calculated.

↓

Upload metadata created.

↓

Forward request to Document Registry.

↓

Receive Document ID.

↓

Return upload result.

---

# Processing Flow

Client

↓

Upload Request

↓

File Validation

↓

Virus Scan (future)

↓

Temporary Storage

↓

Checksum Calculation

↓

Store Original File

↓

Register Document

↓

Return Document ID

---

# Storage Requirements

Original files must never be modified.

Original filename should be preserved.

Storage location is implementation-specific.

The Upload Service must return a storage reference rather than exposing physical storage paths.

---

# Validation

Reject

- Empty files
- Unsupported file types
- Corrupted uploads
- Missing vault
- Invalid authentication
- Oversized files

Validation occurs before permanent storage.

---

# File Integrity

For every uploaded file

Calculate SHA-256 checksum.

Verify upload completeness.

Record file size.

Record MIME type.

Record upload timestamp.

These values become immutable metadata.

---

# Temporary Storage

Files may be stored temporarily before registration.

Temporary files should be automatically cleaned.

Failed uploads must not remain indefinitely.

---

# Duplicate Uploads

The Upload Service may detect duplicate files using checksum.

Duplicate handling policy belongs to the Document Registry.

The Upload Service only reports duplicate candidates.

---

# Security

Every upload requires authentication.

Authorization must be verified before storage.

Users may only upload into vaults they are permitted to access.

Original files are immutable.

---

# Logging

Record

- Upload ID
- User ID
- Vault ID
- Filename
- File Size
- MIME Type
- Checksum
- Upload Duration
- Result

Sensitive document contents must never be logged.

---

# Error Handling

Possible failures

- Connection interrupted
- Storage unavailable
- Invalid file
- Authentication failure
- Authorization failure
- Registry unavailable

All failures should return structured error responses.

No partial uploads should remain after failure.

---

# Performance

The Upload Service should support concurrent uploads.

Large files should be streamed whenever possible.

The service should avoid loading entire files into memory.

---

# API

Required operations

Upload File

Cancel Upload (future)

Resume Upload (future)

Query Upload Status

---

# Acceptance Criteria

The task is complete when

✓ Valid files are accepted.

✓ Invalid files are rejected.

✓ Original files are stored unchanged.

✓ SHA-256 checksum is generated.

✓ Document Registry receives valid metadata.

✓ A Document ID is returned.

✓ Upload logs are recorded.

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

Document version discovery

Legal relationship discovery

---

# Future Improvements

Chunked upload

Resumable upload

Bulk upload

Client-side checksum

Antivirus integration

Content-type verification

Cloud object storage

Upload progress notification
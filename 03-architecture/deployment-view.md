# Deployment View

**Project:** Banking Legal Platform

**Version:** 2.0

---

# Purpose

This document describes how the platform behaves while running.

Unlike the Architecture document, which defines logical modules, the Deployment View explains runtime execution.

It answers questions such as:

- What happens after an API request?
- Which operations run synchronously?
- Which operations become background jobs?
- Which components communicate directly?
- Which tasks may execute in parallel?

Deployment technology is intentionally excluded.

---

# Runtime Philosophy

A runtime request should spend as little time as possible waiting.

Long-running work should be delegated to background processing.

Every operation should have a clearly defined execution boundary.

---

# Runtime Topology

```
                User

                  │

                  ▼

             API Gateway

        ┌─────────┴─────────┐

        ▼                   ▼

 Request Path        Background Jobs

```

The platform separates interactive requests from asynchronous processing.

---

# Request Types

The platform processes two categories of requests.

## Interactive Requests

Examples

- Ask a question
- Search
- Browse document
- View citations

Characteristics

- low latency
- synchronous
- immediate response

---

## Background Requests

Examples

- OCR
- Parsing
- Re-indexing
- Re-embedding
- Batch upload

Characteristics

- long running
- asynchronous
- retryable
- observable

---

# Upload Runtime

```
Client

↓

Upload Request

↓

Gateway

↓

Store Original File

↓

Create Processing Job

↓

Return Job ID

----------------------------

Worker

↓

OCR

↓

Parser

↓

Knowledge Tree

↓

Chunk

↓

Embedding

↓

Index

↓

Completed
```

The client never waits for OCR or indexing.

---

# Query Runtime

```
Client

↓

Gateway

↓

Authentication

↓

Vault Authorization

↓

Retrieval

↓

Generation

↓

Streaming Response

↓

Client
```

The query path should remain synchronous.

---

# Background Processing

Background workers execute independently from user requests.

Examples

- OCR

- Parsing

- Rebuild Index

- Rebuild Embeddings

- Parser Upgrade

Workers may execute in parallel.

---

# Retry Strategy

Recoverable failures are retried.

Examples

OCR timeout

↓

Retry

---

Embedding timeout

↓

Retry

---

Vector indexing failure

↓

Retry

Unrecoverable failures require manual intervention.

---

# Runtime Isolation

User requests never execute OCR.

User requests never rebuild indexes.

Background workers never block query execution.

---

# Concurrency

Multiple document processing jobs may execute simultaneously.

Multiple query requests may execute simultaneously.

The platform shall avoid global locks whenever possible.

---

# Processing Priority

Highest Priority

- user queries

Medium Priority

- document upload

Lowest Priority

- maintenance tasks
- re-indexing
- parser migration

---

# Observability

Every runtime operation records

- start time
- finish time
- duration
- status
- warnings
- failures

Every processing job receives a unique identifier.

---

# Runtime States

A document may exist in one of the following states.

Uploaded

↓

Queued

↓

Processing

↓

Indexing

↓

Ready

↓

Archived

↓

Reprocessing

---

# Runtime Guarantees

The platform guarantees

- original documents are never modified
- user queries never block background processing
- failed jobs never corrupt canonical knowledge
- every job is traceable

---

# Summary

Architecture describes **what the system is**.

Processing Pipeline describes **how knowledge flows**.

Deployment View describes **how the system behaves while running**.
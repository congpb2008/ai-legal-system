> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# API Guide — Legal Knowledge Platform

This guide documents the REST API exposed by the Legal Knowledge Platform.

**Base URL:** `http://localhost:8080/api`

**Authentication:** All endpoints except `/health`, `/ready`, `/live`, and `/v1/auth/login` require a Bearer token in the `Authorization` header.

**Content-Type:** `application/json` for all requests and responses.

---

## Standard Response Format

Every API response follows this envelope:

```json
{
  "request_id": "uuid",
  "timestamp": "2026-08-07T10:00:00+00:00",
  "status": 200,
  "success": true,
  "data": { ... },
  "error": null,
  "warnings": []
}
```

On error:

```json
{
  "request_id": "uuid",
  "timestamp": "2026-08-07T10:00:00+00:00",
  "status": 400,
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message.",
    "category": "VALIDATION",
    "correlation_id": "uuid",
    "retryable": false
  }
}
```

---

## Authentication

### POST /v1/auth/login

Authenticate a user and receive a Bearer token.

**Request:**
```json
{
  "user_id": "admin",
  "password": "admin"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "admin",
    "token_type": "Bearer"
  }
}
```

> **Note:** The MVP accepts any non-empty credentials. No real password verification is performed.

### POST /v1/auth/logout

Invalidate the current session.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": { "message": "Logged out." }
}
```

### GET /v1/auth/me

Get the current user's information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "admin"
  }
}
```

---

## Health

### GET /health

Overall health check. No authentication required.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "0.1.0",
    "uptime_seconds": 42.5,
    "checks": {
      "database": "healthy",
      "storage": "healthy"
    }
  }
}
```

### GET /ready

Readiness check. No authentication required.

### GET /live

Liveness check. No authentication required.

---

## Vaults

### GET /v1/vaults

List all vaults.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | null | Filter by vault type (`COMMON`, `DEPARTMENT`, `PROJECT`, `PERSONAL`) |
| `status` | string | null | Filter by status (`ACTIVE`, `ARCHIVED`) |
| `limit` | int | 100 | Maximum items |
| `offset` | int | 0 | Pagination offset |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "uuid",
        "name": "IT Department Policies",
        "vault_type": "DEPARTMENT",
        "description": null,
        "status": "ACTIVE",
        "owner": "admin",
        "document_count": 5,
        "member_count": 3,
        "created_at": "2026-08-07T10:00:00+00:00",
        "updated_at": "2026-08-07T10:00:00+00:00"
      }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
  }
}
```

### POST /v1/vaults

Create a new vault.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "IT Department Policies",
  "vault_type": "DEPARTMENT",
  "description": "IT-related policies and procedures"
}
```

**Vault types:** `COMMON`, `DEPARTMENT`, `PROJECT`, `PERSONAL`

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "IT Department Policies",
    "vault_type": "DEPARTMENT",
    "description": "IT-related policies and procedures",
    "status": "ACTIVE",
    "owner": "admin",
    "document_count": 0,
    "member_count": 1,
    "created_at": "2026-08-07T10:00:00+00:00",
    "updated_at": "2026-08-07T10:00:00+00:00"
  }
}
```

### GET /v1/vaults/{vault_id}

Get a single vault's details.

**Headers:** `Authorization: Bearer <token>`

**Response (200):** Same shape as a single vault item above.

### PATCH /v1/vaults/{vault_id}

Update a vault's properties.

**Headers:** `Authorization: Bearer <token>`

**Request (partial):**
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

### DELETE /v1/vaults/{vault_id}

Archive a vault (makes it read-only).

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": { "message": "Vault archived." }
}
```

---

## Documents

### POST /v1/documents

Create a document record.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "title": "Server Procurement Policy",
  "document_type": "INTERNAL_REGULATION",
  "issuing_authority": "IT Department",
  "vault_id": "uuid"
}
```

**Document types:** `LAW`, `DECREE`, `CIRCULAR`, `DECISION`, `INTERNAL_REGULATION`, `INTERNAL_POLICY`

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "type": "INTERNAL_REGULATION",
    "title": "Server Procurement Policy",
    "issuing_authority": "IT Department",
    "status": "ACTIVE",
    "vault_id": "uuid",
    "created_at": "2026-08-07T10:00:00+00:00",
    "updated_at": "2026-08-07T10:00:00+00:00",
    "version_count": 1
  }
}
```

### GET /v1/documents

List documents.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vault_id` | UUID | null | Filter by vault |
| `status` | string | null | Filter by status (`ACTIVE`, `ARCHIVED`) |
| `limit` | int | 100 | Maximum items |
| `offset` | int | 0 | Pagination offset |

**Response (200):** Paginated list of document objects.

### GET /v1/documents/{document_id}

Get a single document's details.

**Headers:** `Authorization: Bearer <token>`

**Response (200):** Single document object.

### GET /v1/documents/{document_id}/status

Get document processing status.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "title": "Server Procurement Policy",
    "status": "ACTIVE",
    "processing_state": "UPLOADED",
    "created_at": "2026-08-07T10:00:00+00:00",
    "updated_at": "2026-08-07T10:00:00+00:00"
  }
}
```

**Processing states:** `UPLOADED`, `OCR_PENDING`, `OCR_RUNNING`, `OCR_COMPLETED`, `PARSING_PENDING`, `PARSING_RUNNING`, `READY`, `ARCHIVED`, `FAILED`

### DELETE /v1/documents/{document_id}

Permanently delete a document.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": { "message": "Document deleted." }
}
```

---

## Uploads

### POST /v1/uploads

Upload a file and register it as a document.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "filename": "policy.pdf",
  "content_base64": "<base64-encoded file content>",
  "mime_type": "application/pdf",
  "title": "Server Procurement Policy",
  "document_type": "INTERNAL_REGULATION",
  "issuing_authority": "IT Department",
  "vault_id": "uuid"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "filename": "policy.pdf",
    "size_bytes": 251123,
    "checksum_sha256": "a1b2c3d4e5f6...",
    "status": "ACCEPTED",
    "duplicate_candidates": []
  }
}
```

### GET /v1/uploads/{document_id}

Get upload/processing status for a document.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "document_id": "uuid",
    "title": "Server Procurement Policy",
    "status": "ACTIVE",
    "processing_state": "UPLOADED",
    "created_at": "2026-08-07T10:00:00+00:00",
    "updated_at": "2026-08-07T10:00:00+00:00"
  }
}
```

---

## Search

### POST /v1/search

Hybrid search (keyword + semantic, recommended).

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "query": "server procurement requirements",
  "top_k": 20,
  "vault_id": "uuid (optional)",
  "document_id": "uuid (optional)"
}
```

### POST /v1/search/semantic

Semantic-only search.

**Headers:** `Authorization: Bearer <token>`

**Request:** Same shape as above.

### POST /v1/search/keyword

Keyword-only search.

**Headers:** `Authorization: Bearer <token>`

**Request:** Same shape as above.

### POST /v1/search/hybrid

Explicit hybrid search (same as POST /v1/search).

**Headers:** `Authorization: Bearer <token>`

**Request:** Same shape as above.

### Search Response

All search endpoints return the same response shape:

```json
{
  "success": true,
  "data": {
    "query_id": "uuid",
    "strategy": "HYBRID",
    "generated_at": "2026-08-07T10:00:00+00:00",
    "query": "server procurement requirements",
    "evidence": [
      {
        "id": "uuid",
        "knowledge_node_id": "uuid",
        "document_id": "uuid",
        "document_version_id": "uuid",
        "score": 0.95,
        "rank": 1,
        "text": "Article 1: This regulation governs server procurement...",
        "source_anchor": {
          "canonical_reference": "Điều 1",
          "page": 1
        }
      }
    ],
    "metadata": {
      "strategy": "HYBRID",
      "latency_ms": 42,
      "candidate_count": 50,
      "returned_count": 20
    }
  }
}
```

---

## Answers

### POST /v1/answers

Ask a question and receive an evidence-grounded answer.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "query": "What are the server procurement requirements?",
  "vault_id": "uuid (optional)",
  "document_id": "uuid (optional)"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "request_id": "uuid",
    "generated_at": "2026-08-07T10:00:00+00:00",
    "status": "SUCCESS",
    "response": {
      "format": "MARKDOWN",
      "content": "## Kết quả tra cứu\n\n### Thông tin tìm thấy\n..."
    },
    "citations": [
      {
        "id": "uuid",
        "document_id": "uuid",
        "document_version_id": "uuid",
        "knowledge_node_id": "uuid",
        "source_anchor": "Điều 1",
        "label": "Điều 1"
      }
    ],
    "evidence": [
      {
        "evidence_id": "uuid",
        "usage": "DIRECT"
      }
    ],
    "confidence": {
      "level": "HIGH",
      "score": 0.95,
      "reason": "Based on 3 evidence items with high relevance scores."
    },
    "limitations": []
  }
}
```

**Status values:** `SUCCESS`, `PARTIAL`, `NO_EVIDENCE`, `ERROR`

**Confidence levels:** `HIGH` (0.8+), `MEDIUM` (0.5–0.79), `LOW` (below 0.5)

---

## Admin

### GET /v1/jobs

List recent document processing jobs.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter by document status |
| `limit` | int | 100 | Maximum items |
| `offset` | int | 0 | Pagination offset |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "document_id": "uuid",
        "title": "Server Procurement Policy",
        "status": "ACTIVE",
        "processing_state": "UPLOADED",
        "created_at": "2026-08-07T10:00:00+00:00"
      }
    ],
    "total": 1,
    "limit": 100,
    "offset": 0
  }
}
```

### GET /v1/system

Get system information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "version": "0.1.0",
    "index": {
      "total_entries": 42
    },
    "document_count": 5
  }
}
```

### POST /v1/reindex

Rebuild the search index.

**Headers:** `Authorization: Bearer <token>`

**Request (optional document-specific):**
```json
{
  "document_id": "uuid (optional — omit to reindex all)"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Full reindex completed.",
    "entries_rebuilt": 42
  }
}
```

### POST /v1/reembed

Trigger re-embedding of documents.

**Headers:** `Authorization: Bearer <token>`

**Request (optional):**
```json
{
  "document_id": "uuid (optional — omit to re-embed all)"
}
```

### POST /v1/reparse

Trigger re-parsing of documents.

**Headers:** `Authorization: Bearer <token>`

**Request (optional):**
```json
{
  "document_id": "uuid (optional — omit to re-parse all)"
}
```

---

## Error Codes

| Code | Category | HTTP Status | Description |
|------|----------|-------------|-------------|
| `INVALID_JSON` | VALIDATION | 400 | Request body is not valid JSON |
| `VALIDATION_ERROR` | VALIDATION | 400 | Missing or invalid parameters |
| `INVALID_ENCODING` | VALIDATION | 400 | Base64 encoding is invalid |
| `INVALID_ID` | VALIDATION | 400 | UUID format is invalid |
| `UPLOAD_ERROR` | VALIDATION | 400 | Upload validation failed |
| `NOT_AUTHENTICATED` | AUTHENTICATION | 401 | Missing or invalid Bearer token |
| `FORBIDDEN` | AUTHORIZATION | 403 | Insufficient permissions |
| `NOT_FOUND` | NOT_FOUND | 404 | Resource not found |
| `DOCUMENT_NOT_FOUND` | NOT_FOUND | 404 | Document not found |
| `CONFLICT` | CONFLICT | 409 | Resource conflict (e.g., duplicate) |
| `RATE_LIMITED` | RATE_LIMITED | 429 | Too many requests |
| `INTERNAL_ERROR` | INTERNAL | 500 | Internal server error |
| `DEPENDENCY` | DEPENDENCY | 502 | Downstream service failure |
| `TIMEOUT` | TIMEOUT | 504 | Request timeout |

---

## Complete API Route Table

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | No | Health check |
| GET | /ready | No | Readiness check |
| GET | /live | No | Liveness check |
| POST | /v1/auth/login | No | Log in |
| POST | /v1/auth/logout | Yes | Log out |
| GET | /v1/auth/me | Yes | Current user |
| GET | /v1/vaults | Yes | List vaults |
| POST | /v1/vaults | Yes | Create vault |
| GET | /v1/vaults/{id} | Yes | Get vault |
| PATCH | /v1/vaults/{id} | Yes | Update vault |
| DELETE | /v1/vaults/{id} | Yes | Archive vault |
| POST | /v1/documents | Yes | Create document |
| GET | /v1/documents | Yes | List documents |
| GET | /v1/documents/{id} | Yes | Get document |
| GET | /v1/documents/{id}/status | Yes | Document status |
| DELETE | /v1/documents/{id} | Yes | Delete document |
| POST | /v1/uploads | Yes | Upload file |
| GET | /v1/uploads/{id} | Yes | Upload status |
| POST | /v1/search | Yes | Hybrid search |
| POST | /v1/search/semantic | Yes | Semantic search |
| POST | /v1/search/keyword | Yes | Keyword search |
| POST | /v1/search/hybrid | Yes | Hybrid search |
| POST | /v1/answers | Yes | Ask question |
| GET | /v1/jobs | Yes | List jobs |
| GET | /v1/system | Yes | System info |
| POST | /v1/reindex | Yes | Rebuild index |
| POST | /v1/reembed | Yes | Re-embed |
| POST | /v1/reparse | Yes | Re-parse |
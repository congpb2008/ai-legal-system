> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Uploading Documents

This guide explains how to upload documents to the platform and understand the processing pipeline.

---

## Before You Begin

### What You Need
- A running server (see [Quick Start](02-quick-start.md))
- A valid login
- At least one vault

### Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Digital or scanned |
| Word | `.docx` | Microsoft Word documents |

> **Warning:** Other formats (`.doc`, `.txt`, `.png`, `.jpg`) are not yet supported. The platform will reject them with an error.

### Maximum File Size
The default maximum upload size is **100 MB**.

---

## Uploading via the Web Interface

1. Navigate to **📤 Tải lên** (Upload) in the sidebar
2. Fill in the form:

| Field | Description | Example |
|-------|-------------|---------|
| Tệp tin (File) | The PDF or DOCX file | `policy.pdf` |
| Tiêu đề (Title) | A descriptive title | `Server Procurement Policy` |
| Cơ quan ban hành (Issuing authority) | Who issued the document | `IT Department` |
| Loại tài liệu (Document type) | The document category | `INTERNAL_REGULATION` |
| Kho tài liệu (Vault) | Where to store it | `My Documents` |

3. Click **Tải lên** (Upload)

### Expected Output

After a successful upload, you will see:

```
✅ Tải lên thành công
Mã tài liệu: 550e8400-e29b-41d4-a716-446655440000
Kích thước: 245.3 KB
```

If a duplicate is detected (same file content), you will see:

```
⚠️ Tài liệu trùng lặp được phát hiện
```

---

## Uploading via the API

You can also upload documents programmatically using `curl`:

```bash
# 1. Log in and get a token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

# 2. Encode the file as base64
BASE64=$(base64 -w0 policy.pdf)

# 3. Upload the document
curl -X POST http://localhost:8080/api/v1/uploads \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"filename\": \"policy.pdf\",
    \"content_base64\": \"$BASE64\",
    \"title\": \"Server Procurement Policy\",
    \"document_type\": \"INTERNAL_REGULATION\",
    \"issuing_authority\": \"IT Department\",
    \"vault_id\": \"VAULT_ID_FROM_STEP_3\"
  }"
```

> **Important:** Replace `VAULT_ID_FROM_STEP_3` with the actual vault ID you received when creating the vault. The example UUID `550e8400-e29b-41d4-a716-446655440000` is a placeholder — using it verbatim will result in a "Vault not found" error.
```

Expected response:
```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "filename": "policy.pdf",
    "size_bytes": 251123,
    "checksum_sha256": "a1b2c3d4e5f6...",
    "status": "ACCEPTED"
  }
}
```

> **Note:** The API expects the file content encoded as base64 in the `content_base64` field. This is different from standard multipart uploads.

---

## Document Types

The platform recognizes these document types:

| Type | Value |
|------|-------|
| Law | `LAW` |
| Decree | `DECREE` |
| Circular | `CIRCULAR` |
| Decision | `DECISION` |
| Internal Regulation | `INTERNAL_REGULATION` |
| Internal Policy | `INTERNAL_POLICY` |

---

## Understanding the Processing Pipeline

When you upload a document, it enters a processing pipeline:

```
Uploaded
    ↓
OCR (if scanned)
    ↓
Parser
    ↓
Knowledge Tree
    ↓
Chunking
    ↓
Embedding
    ↓
Indexing
    ↓
Ready
```

### Current MVP Status

> **Important:** In the current MVP, documents are **registered** upon upload but the downstream processing (OCR, parsing, embedding, indexing) is **not automatically triggered**. Your document is stored and registered, but it may not yet be searchable.

This means:
- You can see the document in the Documents list
- The document's processing state may remain at `UPLOADED`
- Full search indexing requires the processing pipeline to run

The automated processing pipeline is **planned** for a future release.

---

## Checking Upload Status

### Via the Web Interface
Navigate to **📄 Tài liệu** (Documents) to see all uploaded documents and their status.

### Via the API

```bash
curl -X GET http://localhost:8080/api/v1/uploads/YOUR_DOCUMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected response:
```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-e29b-41d4-a716-446655440001",
    "title": "Server Procurement Policy",
    "status": "ACTIVE",
    "processing_state": "UPLOADED",
    "created_at": "2026-08-07T10:00:00+00:00",
    "updated_at": "2026-08-07T10:00:00+00:00"
  }
}
```

---

## Common Mistakes

### ❌ Wrong File Format
Uploading a `.txt` or `.doc` file will fail with:
```
Unsupported file type: document.doc
```

**Fix:** Convert to PDF or DOCX first.

### ❌ Empty File
Uploading an empty file will fail with:
```
Uploaded file is empty
```

**Fix:** Ensure the file has content.

### ❌ Fake PDF
Uploading a file named `.pdf` that isn't actually a PDF will fail with:
```
File declared as PDF but does not start with PDF magic bytes
```

**Fix:** Verify the file is a valid PDF.

### ❌ Missing Vault
Uploading without selecting a vault will fail:
```
Vault ... does not exist
```

**Fix:** Create a vault first and select it.

### ❌ No Permission
Uploading to a vault you don't have permission for will fail:
```
User ... is not authorized to upload to vault ...
```

**Fix:** Request access to the vault from its owner.

---

## Next Steps

- Learn how to [search and retrieve](04-search-and-retrieval.md) information
- Understand [question answering](05-question-answering.md)
- Manage your [documents and vaults](06-document-management.md)
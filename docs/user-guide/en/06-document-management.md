> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Document Management

This guide explains how to manage documents and vaults in the platform.

---

## Vaults

### What is a Vault?

A vault is a logical container for documents. Vaults provide:

- **Isolation** — documents in different vaults cannot access each other
- **Organization** — group documents by department, project, or purpose
- **Security** — access is controlled per vault

### Vault Types

| Type | Description | Example |
|------|-------------|---------|
| **Common** | Shared knowledge accessible to all authorized users | Laws, regulations, national standards |
| **Department** | Department-specific documents | IT policies, HR procedures |
| **Project** | Project-specific documents with optional expiry | Migration project, audit project |
| **Personal** | User-owned private documents | Personal uploads, draft notes |

### Creating a Vault

#### Via the Web Interface
1. Click **📁 Kho tài liệu** (Vaults)
2. Click **+ Tạo mới** (Create New)
3. Enter a name and type

#### Via the API
```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

curl -X POST http://localhost:8080/api/v1/vaults \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "IT Department Policies",
    "vault_type": "DEPARTMENT"
  }'
```

### Viewing Vaults

The Vaults page shows:
- Vault name and type
- Document count
- Member count
- Status (ACTIVE or ARCHIVED)

### Archiving a Vault

Archiving a vault makes it read-only. Documents remain accessible for historical reference but new documents cannot be added.

#### Via the API
```bash
curl -X DELETE http://localhost:8080/api/v1/vaults/VAULT_ID \
  -H "Authorization: Bearer $TOKEN"
```

> **Note:** This archives the vault; it does not permanently delete it.

---

## Documents

### Viewing Documents

#### Via the Web Interface
Click **📄 Tài liệu** (Documents) to see all documents in a table with:
- Title
- Document type
- Issuing authority
- Status (ACTIVE or ARCHIVED)
- Creation date
- Actions (view details, upload new version)

#### Via the API
```bash
# List all documents
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

curl -X GET http://localhost:8080/api/v1/documents \
  -H "Authorization: Bearer $TOKEN"

# Get a specific document
curl -X GET http://localhost:8080/api/v1/documents/DOCUMENT_ID \
  -H "Authorization: Bearer $TOKEN"

# Get document processing status
curl -X GET http://localhost:8080/api/v1/documents/DOCUMENT_ID/status \
  -H "Authorization: Bearer $TOKEN"
```

### Document Status

| Status | Meaning |
|--------|---------|
| **ACTIVE** | Document is available and searchable |
| **ARCHIVED** | Document is archived (historical reference only) |

### Processing States

Documents go through these processing stages:

```
UPLOADED → OCR_PENDING → OCR_RUNNING → OCR_COMPLETED →
PARSING_PENDING → PARSING_RUNNING → READY → ARCHIVED
```

> **Note:** In the current MVP, documents remain at `UPLOADED` state. The automated processing pipeline is planned for a future release.

### Deleting a Document

> **Warning:** Document deletion is permanent and irreversible.

#### Via the API
```bash
curl -X DELETE http://localhost:8080/api/v1/documents/DOCUMENT_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## Permissions

### Roles

Each vault member has a role that determines their permissions:

| Role | Permissions |
|------|-------------|
| **VIEWER** | Read documents |
| **CONTRIBUTOR** | Read, upload, update |
| **MANAGER** | Read, upload, update, delete, share, manage |
| **OWNER** | Full control (including member management) |

### Adding Members

#### Via the API
```bash
# Add a member to a vault
curl -X POST http://localhost:8080/api/v1/vaults/VAULT_ID/members \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "john.doe", "role": "VIEWER"}'
```

> **Note:** Member management via the API requires direct calls to the Vault Service. Web UI member management is planned for a future release.

---

## Document Lifecycle

```
Created → Active → Archived
```

- **Created:** Document is registered in the system
- **Active:** Document is available for search and retrieval
- **Archived:** Document is read-only (historical reference)

Documents are never permanently deleted by normal operations. Deletion is an administrative action.

---

## Best Practices

### Organizing Documents
- Create vaults by department or project
- Use descriptive titles for documents
- Include the issuing authority for easy identification
- Use the correct document type for filtering

### Managing Access
- Assign the minimum role needed (principle of least privilege)
- Use Department vaults for team documents
- Use Personal vaults for private documents
- Use Common vaults for organization-wide policies

### Cleaning Up
- Archive outdated documents rather than deleting them
- Review vault membership periodically
- Remove users who no longer need access

---

## Next Steps

- Review [configuration options](07-configuration.md)
- See [troubleshooting](08-troubleshooting.md) for common issues
- Check the [FAQ](09-faq.md)
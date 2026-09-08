> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Quick Start Guide

This guide walks you through starting the server, logging in, and performing your first search.

---

## Step 1: Start the Server

From the project root directory, with your virtual environment activated:

```bash
cd legal-platform
source .venv/bin/activate
```

Start the server using the canonical command:

```bash
legal-platform
```

Or, equivalently, using the Python module:

```bash
python -m legal_platform
```

Expected output:
```
Platform API listening on http://0.0.0.0:8080
  Health:  http://0.0.0.0:8080/health
  API v1:  http://0.0.0.0:8080/api/v1/...
```

The server is now running. Open your web browser and visit:

```
http://localhost:8080
```

You should see the login screen.

> **Note:** This starts the server in the current terminal. To stop it, press `Ctrl+C`. For background operation, use a terminal multiplexer like `tmux` or `screen`.

To use a different host or port:

```bash
legal-platform --host 127.0.0.1 --port 9000
```

Or via environment variables:

```bash
LEGAL_PLATFORM_HOST=127.0.0.1 LEGAL_PLATFORM_PORT=9000 legal-platform
```

---

## Step 2: Log In

The platform uses a simple token-based authentication system.

1. Open `http://localhost:8080` in your browser
2. You will see a login form
3. Enter any username and password (for MVP, any non-empty values work)
4. Click **Đăng nhập** (Login)

Example credentials:
```
Username: admin
Password: admin
```

After logging in, you will see the home page with shortcuts to upload, search, and ask questions.

---

## Step 3: Create a Vault

Vaults are containers for documents. You need at least one vault before uploading.

1. Click **📁 Kho tài liệu** (Vaults) in the sidebar
2. Click **+ Tạo mới** (Create New)
3. Enter a name (e.g., "My Documents")
4. Enter the vault type: `DEPARTMENT`
5. The vault will appear in the list

Alternatively, use the API:

```bash
# Login
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}'

# Save the token from the response, then:
curl -X POST http://localhost:8080/api/v1/vaults \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"name": "My Documents", "vault_type": "DEPARTMENT"}'
```

Expected response:
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "My Documents",
    "vault_type": "DEPARTMENT",
    "owner": "admin",
    "status": "ACTIVE"
  }
}
```

> **Important:** Save the vault ID (`id` field) — you will need it when uploading documents.

---

## Step 4: Upload a Document

1. Click **📤 Tải lên** (Upload) in the sidebar
2. Select a PDF or DOCX file
3. Enter a title (e.g., "Server Procurement Policy")
4. Enter the issuing authority (e.g., "IT Department")
5. Select the vault you created
6. Click **Tải lên** (Upload)

After uploading, you will see a success message with the document ID.

> **Note:** The platform accepts PDF and DOCX files. Maximum file size is 100 MB.

---

## Step 5: Search

1. Click **🔍 Tra cứu** (Search) in the sidebar
2. Select a search mode:
   - **Hybrid** (recommended) — combines keyword and semantic search
   - **Semantic** — finds documents by meaning
   - **Keyword** — finds documents by exact words
3. Enter your query (e.g., "server procurement requirements")
4. Click **Tìm kiếm** (Search)

Results will show:
- Relevance score (percentage)
- Source reference (e.g., "Điều 1")
- Text preview with highlighted matches
- Copy citation button

---

## Step 6: Ask a Question

1. Click **❓ Hỏi đáp** (Ask) in the sidebar
2. Type your question (e.g., "What are the server procurement requirements?")
3. Press `Ctrl+Enter` or click **Gửi câu hỏi** (Send)

The answer will include:
- Answer status (SUCCESS, PARTIAL, or NO_EVIDENCE)
- Confidence level and score
- The generated answer text
- Expandable citations showing source documents
- Limitations or warnings

---

## What's Next?

- Learn how to [upload and manage documents](03-uploading-documents.md)
- Explore [search and retrieval](04-search-and-retrieval.md) in detail
- Understand [question answering](05-question-answering.md)
- Manage your [documents and vaults](06-document-management.md)
- Review [configuration options](07-configuration.md)
- See [troubleshooting](08-troubleshooting.md) for common issues
- Check the [FAQ](09-faq.md) for frequently asked questions
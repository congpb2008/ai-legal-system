# Frequently Asked Questions

---

## General

### What is the Legal Knowledge Platform?
It is an AI-powered system that helps organizations manage and search legal documents. It transforms uploaded documents into structured knowledge and provides evidence-based answers with verifiable citations.

### Who is this platform for?
The platform is designed for legal professionals, compliance officers, and knowledge managers who need to search, retrieve, and understand legal documents efficiently.

### What languages does it support?
The platform is optimized for **Vietnamese** legal documents. The user interface is in Vietnamese. English queries are supported but the platform works best with Vietnamese content.

### Is this a replacement for a lawyer?
**No.** The platform is a research assistant, not a legal advisor. It helps you find and understand information in legal documents, but all final legal decisions must be made by a qualified human.

---

## Installation & Setup

### What are the system requirements?
Python 3.12 or newer, 2 GB RAM minimum (4 GB recommended), and 500 MB disk space.

### How do I install it?
See the [Installation Guide](01-installation.md) for step-by-step instructions.

### Does it require a GPU?
No. The MVP uses a placeholder embedding engine and does not require a GPU. GPU support is planned for future releases.

### Does it require an internet connection?
No. The platform runs entirely offline. No external API calls are made.

---

## Usage

### How do I start the server?
```bash
legal-platform
```
See the [Quick Start Guide](02-quick-start.md) for details.

### How do I upload a document?
Use the Web UI at **📤 Tải lên** (Upload) or the API. See [Uploading Documents](03-uploading-documents.md).

### What file formats are supported?
PDF (`.pdf`) and Word (`.docx`). Other formats are not yet supported.

### Is there a file size limit?
Yes, the default maximum is 100 MB per file.

### How do I search?
Use the **🔍 Tra cứu** (Search) page. You can choose between Hybrid, Semantic, and Keyword search modes. See [Search and Retrieval](04-search-and-retrieval.md).

### How do I ask a question?
Use the **❓ Hỏi đáp** (Ask) page. Type your question and press Ctrl+Enter. See [Question Answering](05-question-answering.md).

### Why did my question return NO_EVIDENCE?
The platform could not find relevant documents to answer your question. Try uploading relevant documents or rephrasing your question.

---

## Documents

### How are documents stored?
Uploaded files are stored on the filesystem. Document metadata is stored in SQLite.

### Can I delete a document?
Yes, but deletion is permanent. Use the API: `DELETE /v1/documents/{id}`.

### What is a vault?
A vault is a container for documents that provides isolation and access control. See [Document Management](06-document-management.md).

### How do I create a vault?
Use the **📁 Kho tài liệu** (Vaults) page and click **+ Tạo mới**.

### Can I move a document between vaults?
Document reassignment between vaults is not yet supported in the MVP.

---

## Permissions

### How do permissions work?
Each vault has members with roles (VIEWER, CONTRIBUTOR, MANAGER, OWNER). Your role determines what you can do in that vault.

### How do I add someone to a vault?
Member management via the Web UI is planned. Currently, use the API:
```bash
curl -X POST http://localhost:8080/api/v1/vaults/VAULT_ID/members \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"user_id": "username", "role": "VIEWER"}'
```

### What's the difference between vault types?
- **Common:** Shared knowledge (laws, regulations)
- **Department:** Team-specific documents
- **Project:** Project-specific with optional expiry
- **Personal:** Private documents

---

## Technical

### What database does it use?
SQLite (in-memory by default). Persistent SQLite is configurable.

### Is there an API?
Yes. The REST API is available at `/api/v1/`. See the [Quick Start Guide](02-quick-start.md) for examples.

### How do I check the server is running?
```bash
curl http://localhost:8080/api/health
```
Returns `{"status": "healthy"}` if the server is running.

### How do I view logs?
Logs are written to stderr in JSON format. Run the server in a terminal to see them.

### How do I backup data?
Backup is not yet automated. To back up manually, configure persistent SQLite storage and copy the database file. See [Configuration](07-configuration.md).

### How do I upgrade?
There is no formal upgrade process yet. To upgrade, pull the latest code and restart the server.

---

## Limitations

### What doesn't the MVP do?
- Automated document processing pipeline (OCR → Parse → Embed → Index)
- Background workers for async processing
- Persistent storage by default
- Conversation memory (each question is independent)
- Streaming responses
- Rate limiting
- Multi-factor authentication
- SSO / OAuth integration

### When will these features be available?
These features are planned for Milestone 5 (Enterprise) and Milestone 6 (Intelligence). See the [Roadmap](../../../tasks/019-roadmap.md) for details.

---

## Troubleshooting

### The server won't start
Check that port 8080 is not in use. Try a different port.

### Upload fails
Check file format (PDF or DOCX only) and size (max 100 MB).

### Search returns nothing
Upload documents first, ensure they are in a vault you can access.

### All data disappeared
By default, data is stored in memory. Configure persistent storage to keep data between restarts.

### Still stuck?
See the [Troubleshooting Guide](08-troubleshooting.md) for detailed solutions.
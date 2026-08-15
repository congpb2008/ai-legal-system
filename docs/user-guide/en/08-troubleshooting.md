# Troubleshooting

This guide helps you diagnose and resolve common issues with the platform.

---

## Server Won't Start

### Symptom
Running the startup command produces an error or nothing happens.

### Possible Causes & Fixes

**Port already in use**
```
Address already in use
```
Change the port:
```bash
legal-platform --port 9090
```
Or via environment variable:
```bash
LEGAL_PLATFORM_PORT=9090 legal-platform
```

### Virtual environment not activated
```
ModuleNotFoundError: No module named 'legal_platform'
```
Activate the virtual environment:
```bash
source .venv/bin/activate
```

### Package not installed
```
ModuleNotFoundError: No module named 'legal_platform'
```
Install the package:
```bash
pip install -e .
```

### Wrong directory
Run from the project root:
```bash
cd legal-platform
```

---

## Can't Log In

### Symptom
The login form rejects your credentials.

### Possible Causes & Fixes

**Using the wrong credentials**
The MVP accepts any non-empty username and password. Try:
```
Username: admin
Password: admin
```

**Server not running**
Ensure the server is running and you can access `http://localhost:8080`.

**Browser cache**
Clear your browser cache and reload the page.

---

## Upload Fails

### Symptom
The upload returns an error.

### Error Messages & Fixes

**"Unsupported file type"**
```
Unsupported file type: document.doc
```
The platform only accepts PDF (`.pdf`) and Word (`.docx`) files. Convert your file to a supported format.

**"Uploaded file is empty"**
The file has no content. Choose a valid file.

**"File declared as PDF but does not start with PDF magic bytes"**
The file has a `.pdf` extension but is not actually a PDF. Rename it correctly or convert it to a valid PDF.

**"Vault ... does not exist"**
The vault ID is invalid. Create a vault first and use its correct ID.

**"User ... is not authorized to upload to vault ..."**
You don't have upload permission for that vault. Contact the vault owner to request access.

---

## Search Returns No Results

### Symptom
Search returns "Không tìm thấy kết quả phù hợp" (No matching results found).

### Possible Causes & Fixes

**Documents not uploaded**
Upload documents first, then search.

**Documents not processed**
In the current MVP, uploaded documents are registered but may not be fully indexed. The automated processing pipeline is planned for a future release.

**Wrong search mode**
Try switching from Keyword to Hybrid mode.

**No access to vault**
Ensure you have access to the vault containing the documents.

**Query too specific**
Try rephrasing with simpler or more general terms.

---

## Question Returns NO_EVIDENCE

### Symptom
Asking a question returns:
```
Status: NO_EVIDENCE
```

### Possible Causes & Fixes

**No relevant documents**
The platform could not find evidence to answer your question. Upload relevant documents or rephrase.

**Documents not processed**
Ensure documents are fully processed and indexed.

**Out of scope**
The question may be about topics not covered by the uploaded documents.

---

## Low Confidence Answers

### Symptom
Answers consistently show LOW or MEDIUM confidence.

### Possible Causes & Fixes

**Insufficient evidence**
Upload more documents related to your question.

**Ambiguous query**
Make your question more specific.

**Poor document quality**
Ensure documents are clear and well-formatted.

---

## Slow Performance

### Symptom
Search or question answering is slow.

### Possible Causes & Fixes

**Large document collection**
Reduce the number of documents or use filters.

**In-memory index**
The MVP uses an in-memory vector index. For large collections, consider a production vector database (planned).

**Resource constraints**
Ensure the server has adequate CPU and memory.

---

## Data Loss on Restart

### Symptom
All documents disappear after restarting the server.

### Explanation
By default, the platform uses **in-memory SQLite databases**. All data is lost when the server stops.

### Fix
Configure persistent storage (see the [Configuration guide](07-configuration.md)):
```python
from legal_platform.storage.db import connect
from legal_platform.modules.document_registry.repository import SqliteDocumentRepository

conn = connect('/path/to/data/platform.db')
repo = SqliteDocumentRepository(conn=conn)
```

---

## How to Check Logs

The platform writes structured JSON logs to **stderr**. To see logs:

1. Run the server in a terminal
2. Log output appears in that terminal

Example log entry:
```json
{"timestamp": "2026-08-07T10:00:00+00:00", "service": "document-registry", "module": "registry", "severity": "INFO", "message": "Document created", "metadata": {"type": "INTERNAL_REGULATION"}}
```

To capture logs to a file:
```bash
legal-platform 2> server.log
```

---

## How to Update Embeddings

> **Note:** The automated embedding pipeline is planned for a future release. The current MVP provides a placeholder embedding engine.

To trigger re-embedding via the API:

```bash
curl -X POST http://localhost:8080/api/v1/reembed \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"document_id": "DOCUMENT_ID"}'
```

To re-embed all documents:
```bash
curl -X POST http://localhost:8080/api/v1/reembed \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'
```

---

## How to Rebuild the Index

### Rebuild All
```bash
curl -X POST http://localhost:8080/api/v1/reindex \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'
```

### Rebuild One Document
```bash
curl -X POST http://localhost:8080/api/v1/reindex \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"document_id": "DOCUMENT_ID"}'
```

---

## How to Check System Status

```bash
# Health check
curl http://localhost:8080/api/health

# Readiness
curl http://localhost:8080/api/ready

# Liveness
curl http://localhost:8080/api/live

# System information (requires auth)
curl -X GET http://localhost:8080/api/v1/system \
  -H "Authorization: Bearer $TOKEN"
```

---

## Still Having Problems?

If you've tried the solutions above and still have issues:

1. Check the [FAQ](09-faq.md) for additional help
2. Review the server logs for error messages
3. Consult the [Documentation Audit Report](../../README.md) for known limitations
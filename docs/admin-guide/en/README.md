# Admin Guide — Legal Knowledge Platform

This guide is for the person responsible for installing, configuring, operating, and maintaining the Legal Knowledge Platform deployment.

---

## Overview

The Legal Knowledge Platform is a self-contained Python application. It consists of:
- A **backend** (`backend/legal_platform/`) exposing a REST API and serving the Web UI
- A **frontend** (`frontend/`) — a static single-page application served by the backend
- **SQLite** for document metadata and audit logs (in-memory by default)
- **Filesystem** storage for uploaded files (temporary directory by default)

The application runs entirely offline. It makes **no external API calls** and requires no internet connection.

---

## Installation

### Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.12 | 3.12 or newer |
| RAM | 2 GB | 4 GB or more |
| Disk space | 500 MB | 2 GB (for documents + index) |
| Operating system | Linux, macOS | Linux (Ubuntu 22.04+) |

### Install

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package and dependencies
pip install -e .

# Optionally install test tooling
pip install -e ".[test]"
```

### Verify Installation

```bash
python -m pytest
```

Expected result: `628 passed`.

---

## Configuration

### Environment Variables

The application reads the following environment variables at startup:

| Variable | Default | Description |
|----------|---------|-------------|
| `LEGAL_PLATFORM_HOST` | `0.0.0.0` | Host/interface to bind to |
| `LEGAL_PLATFORM_PORT` | `8080` | TCP port to listen on |

Example:

```bash
export LEGAL_PLATFORM_HOST=127.0.0.1
export LEGAL_PLATFORM_PORT=9000
legal-platform
```

### Command-Line Arguments

The same settings are available as CLI flags (these take precedence over environment variables):

```bash
legal-platform --host 127.0.0.1 --port 9000
```

---

## Starting the Service

### Canonical Startup

```bash
# From the project root, with the venv activated
legal-platform
```

Or equivalently:

```bash
python -m legal_platform
```

### Running in the Background

To run the server detached from the terminal:

```bash
# Using nohup
nohup legal-platform > server.log 2>&1 &

# Or using a terminal multiplexer
tmux new -s legal-platform
legal-platform
```

### Verifying Startup

The server prints:

```
Platform API listening on http://0.0.0.0:8080
  Health:  http://0.0.0.0:8080/health
  API v1:  http://0.0.0.0:8080/v1/...
```

---

## Stopping the Service

Press `Ctrl+C` in the terminal running the server. The server catches `KeyboardInterrupt` and shuts down gracefully.

For a background process:

```bash
# Find the PID
pgrep -f "legal-platform"

# Send SIGTERM
kill <PID>
```

---

## Service Health

Three health endpoints are available (no authentication required):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Overall health status |
| `GET /api/ready` | Readiness (dependencies available) |
| `GET /api/live` | Liveness (process alive) |

```bash
curl http://localhost:8080/api/health
```

Expected response:

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "0.1.0",
    "checks": {
      "database": "healthy",
      "storage": "healthy"
    }
  }
}
```

---

## Logs

The application writes **structured JSON logs to stderr**. To capture logs:

```bash
legal-platform 2> server.log
```

Example log entry:

```json
{"timestamp": "2026-08-07T10:00:00+00:00", "service": "document-registry", "module": "registry", "severity": "INFO", "message": "Document created"}
```

Log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`.

---

## Storage

### Default (In-Memory)

By default, the platform stores all data **in memory**:
- Document metadata is held in an in-memory SQLite database
- Uploaded files are stored in a temporary directory
- **All data is lost when the server stops**

### Persistent Storage

To configure persistent storage, modify the `DocumentRegistry` initialization in the backend:

```python
from legal_platform.storage.db import connect
from legal_platform.modules.document_registry.repository import SqliteDocumentRepository

conn = connect('/path/to/data/platform.db')
repo = SqliteDocumentRepository(conn=conn)
```

And configure file storage:

```python
from legal_platform.modules.upload_service.file_storage import LocalFileStorage

file_storage = LocalFileStorage(base_path='/path/to/data/uploads')
```

> **NOT YET IMPLEMENTED:** Persistent storage is not wired into the default startup path. The default server uses in-memory storage. Configuring persistent storage currently requires code changes.

### Data Locations

| Data | Default Location | Persistent |
|------|-----------------|------------|
| Document metadata | In-memory SQLite | No (default) |
| Uploaded files | Temp directory | No (default) |
| Audit log | In-memory SQLite | No (default) |
| Vector index | In-memory | No |

---

## Backup and Restore

> **NOT YET IMPLEMENTED:** Automated backup and restore are not implemented in the MVP.

**What currently exists:**
- With persistent SQLite storage configured, the database file can be copied while the server is stopped.
- Uploaded files can be copied from the configured storage directory.

**Limitations:**
- No automated backup scheduling
- No online (hot) backup — copying a live in-memory database is not possible
- No documented restore procedure beyond restoring the files

---

## Updating the Application

> **NOT YET IMPLEMENTED:** There is no formal upgrade process.

**Current procedure:**
1. Stop the server
2. Pull the latest code (`git pull` or replace files)
3. Reinstall dependencies (`pip install -e .`)
4. Restart the server

> **Warning:** With in-memory storage, restarting the server loses all data. Ensure persistent storage is configured before upgrading.

---

## Authentication Configuration

> **NOT YET IMPLEMENTED:** Real authentication (identity provider, OAuth2, LDAP, SAML) is not implemented in the MVP.

**Current behavior:**
- The MVP accepts **any non-empty username and password**
- A token is issued on login and stored in the browser's `localStorage`
- Tokens are UUIDs generated by the server
- There is no password verification, account locking, or session expiry

**Security note:** The MVP authentication is suitable for demonstration/development only. Production deployments must add real authentication (planned for Milestone 5).

---

## Operational Limitations

| Limitation | Impact |
|------------|--------|
| In-memory storage by default | Data loss on restart |
| No automated processing pipeline | Uploaded documents may not be searchable until manually processed |
| No real authentication | Any credentials accepted |
| No backup/restore | Manual file copying only |
| No TLS/HTTPS | Traffic is plain HTTP |
| No rate limiting | No protection against abuse |
| Single-process | No horizontal scaling |
| Placeholder embedding engine | Semantic search quality is limited |

---

## Troubleshooting

### Server Won't Start

**Symptom:** `Address already in use`
**Cause:** Port 8080 is occupied.
**Resolution:** Use a different port:
```bash
legal-platform --port 9090
```

**Symptom:** `ModuleNotFoundError: No module named 'legal_platform'`
**Cause:** The package is not installed or the venv is not activated.
**Resolution:**
```bash
source .venv/bin/activate
pip install -e .
```

### Data Lost After Restart

**Symptom:** All documents disappear after restarting.
**Cause:** In-memory storage (default).
**Resolution:** Configure persistent storage (see [Storage](#storage)).

### Uploaded Documents Not Searchable

**Symptom:** Documents appear in the list but search returns nothing.
**Cause:** The automated processing pipeline is not triggered in the MVP.
**Resolution:** Use the Admin panel (**⚙️ Quản trị**) to trigger Re-index, Re-embed, and Re-parse.

---

## Known MVP Limitations

- Automated document processing pipeline is not triggered after upload
- In-memory storage by default
- No real authentication
- No backup/restore automation
- No TLS/HTTPS
- No rate limiting
- No conversation memory
- No streaming responses
- Placeholder embedding engine (not production semantic search)

---

## Security Considerations

### Authentication

The MVP uses a simple token-based authentication system. **Any non-empty username and password are accepted.** This is suitable for development/demonstration only. A production deployment must integrate with a real identity provider (OAuth2, LDAP, SAML). See `04-decisions/` for architecture decisions.

### Provider Credentials

AI provider API keys are stored in `$LEGAL_PLATFORM_DATA_DIR/provider_config.json` (the project's `storage/provider_config.json` by default). The file is restricted to the application user (`chmod 600`). API keys are:

- Never returned by API responses (only `has_api_key: true/false` is exposed)
- Never logged
- Never embedded into frontend source code
- Never included in error messages
- Transmitted only to the configured provider endpoint

### Provider URL Validation

Provider base URLs are validated before any outbound request is made:
- Only `http` and `https` schemes are allowed
- Embedded credentials in URLs are rejected
- Private/loopback IP addresses (10.x.x.x, 192.168.x.x, 172.16-31.x.x, 127.x.x.x) are blocked
- Explicit `localhost` is permitted (for local Ollama deployments)

### File Upload Security

Uploaded filenames are sanitized to prevent path traversal:
- Path separators (`/`, `\`), null bytes, and Windows special characters are removed
- The sanitized filename is used for storage; the original filename is preserved in metadata only
- File content is validated against the declared MIME type (PDF magic bytes check)
- Maximum file size is enforced (100 MB default)
- Failed uploads are cleaned up (no partial state)

### Error Handling

Internal server errors return a generic message: "An internal error occurred. Please check the server logs." Detailed diagnostic information (stack traces, exception messages) is written to stderr only and is never exposed to API clients.

### Security Headers

All API responses and static file responses include:
- `X-Content-Type-Options: nosniff` — prevents MIME type sniffing
- `X-Frame-Options: DENY` — prevents clickjacking
- `X-XSS-Protection: 0` — disables legacy XSS filter (modern browsers)

### Prompt Injection Mitigation

Retrieved documents are treated as untrusted evidence. The system prompt (from `design/system-prompt.md`) instructs the LLM to base answers solely on retrieved evidence. The Generation Service architecture (ADR-002) ensures:
- The LLM never retrieves documents directly
- The LLM never accesses vector databases
- The LLM never reads original documents
- Retrieved document content cannot override system instructions

---

## Next Steps

- See the [API Guide](../../api-guide/en/) for endpoint documentation
- See the [Developer Guide](../../developer-guide/en/) for development setup
- See the [User Guide](../../user-guide/en/) for end-user instructions

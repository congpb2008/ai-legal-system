# Developer Guide — Legal Knowledge Platform

This guide is for developers who want to work on the Legal Knowledge Platform codebase.

---

## Repository Structure

```
├── backend/legal_platform/     # Python backend package
│   ├── __init__.py             # Package version
│   ├── __main__.py             # CLI entrypoint (Task 020)
│   ├── api/                    # HTTP API server (Task 014)
│   │   ├── handlers.py         # 8 domain handlers
│   │   ├── models.py           # Response/error models
│   │   └── server.py           # HTTP server + static file serving
│   ├── contracts/              # Canonical data contracts
│   │   ├── answer.py           # Answer Contract
│   │   ├── common.py           # Shared primitives
│   │   ├── document.py         # Document Contract
│   │   ├── knowledge_tree.py   # Knowledge Tree Contract
│   │   └── retrieval.py        # Retrieval Contract
│   ├── modules/                # Business logic modules
│   │   ├── chunking/           # Task 006
│   │   ├── citation/           # Task 012
│   │   ├── document_registry/  # Task 001
│   │   ├── embedding/          # Task 007
│   │   ├── evaluation/         # Task 017
│   │   ├── generation/         # Task 011
│   │   ├── knowledge_tree_builder/ # Task 005
│   │   ├── observability/      # Task 016
│   │   ├── ocr_service/        # Task 003
│   │   ├── parser/             # Task 004
│   │   ├── release/            # Task 018
│   │   ├── reranker/           # Task 010
│   │   ├── retrieval/          # Task 009
│   │   ├── upload_service/     # Task 002
│   │   ├── vault/              # Task 013
│   │   └── vector_index/       # Task 008
│   └── storage/                # Shared storage infrastructure
│       ├── db.py               # SQLite connection helper
│       └── eventlog.py         # Structured audit log
├── frontend/                   # Web UI (Task 015)
│   ├── index.html              # SPA shell
│   ├── css/main.css            # Styles (light/dark/high-contrast)
│   └── js/
│       ├── api.js              # API client
│       └── app.js              # Application logic
├── tests/                      # Test suite (628 tests)
│   ├── test_api.py
│   ├── test_chunking.py
│   ├── test_citation.py
│   ├── test_document_registry.py
│   ├── test_embedding.py
│   ├── test_evaluation.py
│   ├── test_generation.py
│   ├── test_knowledge_tree_builder.py
│   ├── test_observability.py
│   ├── test_ocr_service.py
│   ├── test_packaging.py
│   ├── test_parser.py
│   ├── test_release.py
│   ├── test_reranker.py
│   ├── test_retrieval.py
│   ├── test_upload_service.py
│   ├── test_vault.py
│   └── test_vector_index.py
├── docs/                       # User/admin/API/developer documentation
├── tasks/                      # Implementation task specifications
├── 00-product/                 # Product specifications
├── 01-domain/                  # Domain model
├── 02-contracts/               # Contract specifications
├── 03-architecture/            # Architecture documents
├── 04-decisions/               # Architecture Decision Records
├── design/                     # Design documents
│   ├── system-prompt.md        # Generation policy
│   └── benchmark-dataset-spec.md
├── examples/                   # Contract example files
├── pyproject.toml              # Python packaging config
└── developer-guide.md          # Original developer guide (specifications)
```

---

## Development Environment

### Prerequisites

- Python 3.12 or newer
- Git
- (Optional) Tesseract OCR for scanned document processing

### Setup

```bash
# Clone the repository
git clone <repository-url> legal-platform
cd legal-platform

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package in development mode with test dependencies
pip install -e ".[test]"
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_api.py

# Run a specific test class
python -m pytest tests/test_api.py::TestApiResponse

# Run with coverage (requires pytest-cov)
python -m pytest --cov=backend/legal_platform
```

Expected result: **628 tests passing**.

### Running the Application

```bash
# Start the server
legal-platform

# Or via Python module
python -m legal_platform

# With custom host/port
legal-platform --host 127.0.0.1 --port 9000
```

The server starts on `http://0.0.0.0:8080` by default.

---

## Frontend Development

The frontend is a vanilla JavaScript single-page application. There is no build step — the HTML, CSS, and JS are served directly by the backend.

### Structure

- `frontend/index.html` — SPA shell with sidebar, login modal, toast container
- `frontend/css/main.css` — All styles (light, dark, high-contrast themes; responsive breakpoints)
- `frontend/js/api.js` — `ApiClient` class wrapping `fetch()` calls to the backend API
- `frontend/js/app.js` — Application logic: page rendering, routing, auth, form handling

### Development Workflow

1. Start the backend server (`legal-platform`)
2. Edit frontend files in `frontend/`
3. Refresh the browser to see changes (no build step required)

### Key Patterns

- All API calls go through `api.js` — the UI never calls backend services directly
- Page rendering is done by `app.render*()` methods that set `innerHTML`
- State is managed in `app.state` object
- Routing uses URL hash (`#/search`, `#/ask`, etc.)
- Authentication token is stored in `localStorage`

---

## Backend Development

### Module Architecture

Each module in `backend/legal_platform/modules/` owns one responsibility and communicates only through contracts. See `03-architecture/module-specifications.md` for the authoritative module boundaries.

### Adding a New Module

1. Create `backend/legal_platform/modules/<name>/`
2. Implement the module with a service class
3. Add tests in `tests/test_<name>.py`
4. Wire the module into the API handler if it needs HTTP endpoints
5. Follow the existing patterns (constructor injection, contract-driven interfaces)

### Key Contracts

The four canonical contracts are in `backend/legal_platform/contracts/`:

| Contract | File | Produced By | Consumed By |
|----------|------|-------------|-------------|
| Document Contract | `document.py` | Document Registry | Upload, OCR, Parser, Knowledge, Vault |
| Knowledge Tree Contract | `knowledge_tree.py` | Knowledge Tree Builder | Chunking, Retrieval, Citation |
| Retrieval Contract | `retrieval.py` | Retrieval + Reranker | Generation |
| Answer Contract | `answer.py` | Generation + Citation | Platform API → Client |

### API Structure

The HTTP API is in `backend/legal_platform/api/`:

- `server.py` — `PlatformAPI` class wrapping `HTTPServer`, request routing, static file serving
- `handlers.py` — 8 domain handlers (Auth, Vault, Document, Upload, Search, Answer, Admin, Health)
- `models.py` — `ApiResponse`, `ApiError`, `ErrorCategory`, `HealthStatus`, `PaginatedResponse`

The server uses Python's stdlib `http.server` (not FastAPI/Flask). This is an MVP choice; a production deployment should use a proper ASGI/WSGI server.

---

## Configuration

Configuration is currently done through:

1. **Environment variables** at startup: `LEGAL_PLATFORM_HOST`, `LEGAL_PLATFORM_PORT`
2. **Constructor injection** — services accept dependencies via their `__init__` parameters
3. **Direct code changes** — for persistent storage, embedding model, etc.

See `docs/admin-guide/en/` for configuration details.

---

## Debugging

### Logs

The application writes structured JSON logs to stderr:

```bash
legal-platform 2> server.log
```

### Common Issues

**"ModuleNotFoundError: No module named 'legal_platform'"**
→ The package is not installed. Run `pip install -e .`

**Tests fail with import errors**
→ Ensure the virtual environment is activated and the package is installed.

**Server won't start on port 8080**
→ Another process is using the port. Use `--port` to specify a different port.

**Frontend changes not visible**
→ Hard-refresh the browser (`Ctrl+Shift+R` or `Cmd+Shift+R`).

---

## Test Conventions

- Tests use `pytest` (configured in `pyproject.toml`)
- Test files are in `tests/` and named `test_<module>.py`
- Test classes are named `Test<Feature>` (e.g., `TestApiResponse`)
- Tests use `from legal_platform...` imports (package is installed, no PYTHONPATH needed)
- In-memory SQLite is used for database-dependent tests
- Tests should not depend on external services or network access

---

## Packaging

The project uses standard Python packaging via `pyproject.toml`:

```bash
# Build distribution packages
python -m build

# Install in development mode
pip install -e .
```

The package name is `legal-platform`. The console script is `legal-platform`. The module is `legal_platform`.

---

## Documentation Hierarchy

When documentation conflicts, the following order applies:

1. **ADR** (Architecture Decision Records) — highest authority
2. **Contracts** — stable interface definitions
3. **Architecture** — system design documents
4. **Examples** — expected behavior
5. **Implementation** — code (lowest authority)

See `developer-guide.md` (repository root) for the authoritative developer workflow specification.

---

## Related Documentation

- [Architecture](../../../03-architecture/architecture.md)
- [Module Specifications](../../../03-architecture/module-specifications.md)
- [Processing Pipeline](../../../03-architecture/processing-pipeline.md)
- [Contracts](../../../02-contracts/)
- [ADRs](../../../04-decisions/)
- [Task Specifications](../../../tasks/)
- [Original Developer Guide](../../../developer-guide.md)
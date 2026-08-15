# Legal Knowledge Platform

> An AI-powered legal knowledge platform that transforms legal documents into structured knowledge and provides evidence-based, fully traceable answers.

---

## What It Does

The Legal Knowledge Platform helps organizations manage, search, and understand legal documents. It:

- **Accepts** digital PDF and DOCX uploads; scanned PDFs require Tesseract plus Vietnamese language data
- **Parses** documents into a structured Knowledge Tree preserving legal hierarchy
- **Indexes** content for hybrid (keyword + semantic) retrieval scoped by vault
- **Generates** evidence-grounded answers with verifiable citations
- **Abstains** instead of hallucinating when evidence is insufficient
- **Enforces** vault isolation for document access control

**Primary language:** Vietnamese (vi) — optimized for Vietnamese legal documents (Decisions, Circulars, Decrees, Laws, internal regulations).

---

## Intended Users

- **Legal professionals** — search and retrieve legal documents
- **Compliance officers** — verify internal regulations
- **Knowledge managers** — organize and manage document collections
- **Department staff** — access policies and procedures

---

## Current Status — v0.1 (MVP)

The platform implements a complete document management and retrieval pipeline:

| Capability | Status |
|-----------|--------|
| Document upload (PDF, DOCX) | ✅ Implemented |
| Digital PDF/DOCX extraction | ✅ Implemented |
| Scanned-PDF OCR | ⚠️ Requires Tesseract + Vietnamese language data |
| Document parsing → Knowledge Tree | ✅ Implemented |
| Structure-aware chunking | ✅ Implemented |
| Embedding generation | ✅ Native Ollama embeddings (BGE-M3 default) |
| Hybrid search (keyword + semantic) | ✅ Implemented |
| Reranking & evidence selection | ✅ Implemented |
| Configured answer generation | ✅ OpenAI-compatible provider (including Ollama) |
| Verifiable citations/source inspection | ✅ Authorized node/page/source traceability |
| Vault isolation & permissions | ✅ Implemented |
| Durable jobs and exact-stage reprocessing | ✅ Implemented |
| SQLite/source restart persistence | ✅ Implemented |
| Web UI (7 pages) | ✅ Implemented |
| Observability (logs, metrics, traces) | ✅ Implemented |
| Evaluation platform | ✅ Implemented |
| Release checklist | ✅ Implemented |

**Known MVP limitations:**
- Authentication is an MVP identity stub: any non-empty username/password is accepted. Vault authorization is enforced for that presented identity, but deploy behind a real identity provider before multi-user production use.
- Scanned PDFs need a system Tesseract installation with Vietnamese data. Without it, the document remains visibly `FAILED` and can be recovered with Re-OCR after the dependency is installed.
- A reachable Ollama/OpenAI-compatible generation provider and Ollama embedding endpoint are required for normal Ask and semantic retrieval.
- No conversation memory — each question is independent.

---

## Quick Start

### Prerequisites

- Python 3.12 or newer
- 2 GB RAM (4 GB recommended)
- 500 MB disk space
- A reachable Ollama-compatible embedding service; a generation model exposed through an OpenAI-compatible `/v1` endpoint
- Optional for scanned PDFs: Tesseract OCR and Vietnamese language data

### Installation

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package and dependencies
pip install -e .
```

### Start the Server

```bash
legal-platform
```

Or equivalently:

```bash
python -m legal_platform
```

The server starts on `http://0.0.0.0:8080`. Open `http://localhost:8080`. Persistent state is stored under `storage/` by default; set `LEGAL_PLATFORM_DATA_DIR` to choose another durable root.

### First Steps

1. Complete the first-run provider form. For Ollama, use its OpenAI-compatible base URL ending in `/v1`. If a reasoning model consumes its response budget without visible text, select **None / none** for reasoning effort; keep a sensible output cap such as 4096 tokens.
2. Log in with any username and password (MVP identity stub).
3. Create a vault (**📁 Kho tài liệu** → **+ Tạo mới**).
4. Upload one file or choose **Tải lên thư mục**; Office `~$` lock files are skipped.
5. Wait for the document's processing state to become `READY`, then Search or Ask.

---

## Documentation

| Guide | English | Vietnamese |
|-------|---------|------------|
| User Guide | [docs/user-guide/en/](docs/user-guide/en/) | [docs/user-guide/vi/](docs/user-guide/vi/) |
| Admin Guide | [docs/admin-guide/en/](docs/admin-guide/en/) | [docs/admin-guide/vi/](docs/admin-guide/vi/) |
| API Guide | [docs/api-guide/en/](docs/api-guide/en/) | [docs/api-guide/vi/](docs/api-guide/vi/) |
| Developer Guide | [docs/developer-guide/en/](docs/developer-guide/en/) | [docs/developer-guide/vi/](docs/developer-guide/vi/) |

### Specification Documents

The authoritative project specifications are in the repository root:

- `00-product/` — Vision, scope, constraints, glossary
- `01-domain/` — Domain model, knowledge tree specification
- `02-contracts/` — Four canonical contracts
- `03-architecture/` — Architecture, deployment, modules, pipeline
- `04-decisions/` — Architecture Decision Records (ADRs)
- `design/` — System prompt, benchmark dataset spec
- `tasks/` — Implementation task specifications
- `examples/` — Contract example files

---

## Repository Structure

```
├── backend/legal_platform/     # Python backend package
│   ├── api/                    # HTTP API server (Task 014)
│   ├── contracts/              # Canonical data contracts
│   ├── modules/                # Business logic modules
│   └── storage/                # SQLite + audit log
├── frontend/                   # Web UI (Task 015)
│   ├── index.html              # SPA shell
│   ├── css/main.css            # Styles
│   └── js/                     # API client + application logic
├── tests/                      # Regression suite (708 tests at final validation)
├── docs/                       # Documentation
├── tasks/                      # Task specifications
├── 00-product/                 # Product specifications
├── 01-domain/                  # Domain model
├── 02-contracts/               # Contract specifications
├── 03-architecture/            # Architecture documents
├── 04-decisions/               # Architecture Decision Records
├── design/                     # Design documents
└── examples/                   # Contract examples
```

---

## Architecture Overview

```
Upload → OCR → Parser → Knowledge Tree → Chunking → Embedding → Vector Index
                                                                        ↓
Question → Retrieval → Reranker → Generation → Citation Builder → Answer
```

The system follows a **contract-driven architecture** with five layers:
1. **Ingestion** — OCR, parsing, metadata extraction
2. **Knowledge** — persistence, versioning, vault organization
3. **Retrieval** — hybrid search, ranking, filtering
4. **Generation** — explanation, formatting, citation generation
5. **Presentation** — Web UI, API gateway

Modules communicate **only through Contracts**. Lower layers never depend on higher layers.

---

## License

TBD

---

## Project Status

- ✅ Core upload → processing → retrieval → answer → citation workflow validated with real legal documents
- ✅ 708 tests passing in an isolated persistent data root
- ✅ Packaging & distribution (Task 020) — installable via `pip install -e .`
- ✅ Frontend polish (Task 021) — responsive, accessible Web UI
- ✅ Documentation (Task 022) — user, admin, API, and developer guides
- ✅ Browser and restart-persistence acceptance completed for the MVP path
- ⚠️ Scanned OCR and production authentication remain documented deployment limitations

# Changelog

## v0.1.0 (2026-08-08)

Initial MVP release of the Legal Knowledge Platform.

### Added

- **Document Registry** (Task 001) — stable Document ID assignment, metadata storage, SHA-256 checksum duplicate detection, document lifecycle (Created → Active → Archived), document relationships, processing state machine.
- **Upload Service** (Task 002) — file validation (MIME type, size, magic bytes), SHA-256 checksum, temporary storage, vault authorization.
- **OCR Service** (Task 003) — digital PDF text extraction (PyMuPDF), scanned page OCR (Tesseract), hybrid mode, confidence scoring, reading order preservation.
- **Parser** (Task 004) — structure detection (Chapters, Sections, Articles, Clauses, Points, Appendices, Tables, Figures), source location mapping, graceful UNKNOWN node type handling.
- **Knowledge Tree Builder** (Task 005) — validated, immutable Knowledge Tree Contract construction, parent-child linking, canonical references, tree integrity validation.
- **Chunking** (Task 006) — structure-aware chunking respecting Knowledge Tree boundaries over token limits, source mapping preservation.
- **Embedding Service** (Task 007) — pluggable embedding engine, deterministic placeholder embedder for MVP, batch embedding.
- **Vector Index** (Task 008) — in-memory vector store, metadata filtering, similarity search, rebuild support.
- **Retrieval Service** (Task 009) — hybrid (keyword + semantic) search, Reciprocal Rank Fusion, context expansion, vault/document scoping.
- **Reranker** (Task 010) — evidence scoring, deduplication, diversity optimization, budget constraints, configurable weights.
- **Generation Service** (Task 011) — template-based answer generation from evidence, confidence computation, NO_EVIDENCE/PARTIAL handling, audit logging.
- **Citation Builder** (Task 012) — sentence segmentation, claim detection (7 types), evidence mapping, citation resolution, unsupported claim detection.
- **Vault Service** (Task 013) — 4 vault types (Common/Department/Project/Personal), RBAC (6 permissions, 4 roles), document assignment, member management.
- **Platform API** (Task 014) — 28 REST endpoints across 8 domains (Auth, Vault, Document, Upload, Search, Answer, Admin, Health), Bearer token auth, standardized error schema.
- **Web UI** (Task 015) — 7-page single-page application (Home, Search, Ask, Vaults, Documents, Upload, Admin), Vietnamese language, responsive layout, light/dark/high-contrast themes.
- **Observability** (Task 016) — structured JSON logging, metrics (counters/gauges/histograms with p50/p95/p99), distributed tracing, job monitoring, alert rules.
- **Evaluation Platform** (Task 017) — IR metrics (recall@K, precision@K, MRR, nDCG, F1), per-component evaluators, regression detection, report persistence.
- **Release Checklist** (Task 018) — 18 categories, ~90 checks, critical failure gating, rollback plan, post-release verification.
- **Packaging & Distribution** (Task 020) — `python -m legal_platform` entrypoint, `legal-platform` console script, `pyproject.toml` packaging, environment variable configuration.
- **Frontend Polish** (Task 021) — responsive sidebar with hamburger toggle, proper vault creation modal, document detail panel, button disabling during operations, client-side validation, improved empty/error/loading states, accessibility improvements.
- **Documentation** (Task 022) — User Guide (EN + VI), Admin Guide (EN + VI), API Guide (EN + VI), Developer Guide (EN + VI), updated README.

### Fixed

- `PaginatedResponse` serialization — now serializes to a JSON object instead of a raw string (Task 023).
- Handler state isolation — all API handlers now share a single `DocumentRegistry` with shared in-memory SQLite, so uploaded documents are visible across handlers (Task 023).
- `VaultService` thread-safety — SQLite connection uses `check_same_thread=False` for cross-thread access (Task 023).
- Server banner now correctly prints `/api/v1/...` (Task 023).
- Documentation bugs from first-user audit — venv creation failure, PEP 668, missing pytest dependency, placeholder tokens in curl examples, fake vault_id UUIDs, server blocking terminal (Task 022).

### Known Limitations

- **Automated processing pipeline not triggered** — uploaded documents are registered but not automatically OCR'd, parsed, embedded, or indexed. Documents may not be searchable until manually processed via the Admin panel.
- **In-memory storage by default** — all data is lost when the server stops. Persistent SQLite storage requires code changes.
- **No LLM integration** — answers use a template-based approach (no external AI provider required or configured).
- **No conversation memory** — each question is independent.
- **Placeholder embedding engine** — semantic search quality is limited; not suitable for production.
- **No real authentication** — MVP accepts any non-empty credentials.
- **No TLS/HTTPS** — traffic is plain HTTP.
- **No rate limiting** — no protection against abuse.
- **No backup/restore automation** — manual file copying only.
- **No `.gitignore`** — risk of committing secrets.
- **Responsive/visual rendering not verified in a real browser** — CSS breakpoints reviewed but no browser E2E testing performed.
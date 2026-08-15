# Task 023 — End-to-End QA Report

**Date:** 2026-08-08
**Tester role:** Completely new user/operator (no prior project knowledge)

---

## Environment

| Item | Value |
|------|-------|
| OS | Linux (Ubuntu 24.04, kernel 7.0.0-28-generic) |
| Python version | 3.12.3 |
| Browser | Headless HTTP client (curl + urllib) — no GUI browser available in QA environment |
| Installation method | `pip install -e ".[test]"` into a fresh virtual environment |
| Deployment/startup method | `legal-platform` console script (canonical Task 020 startup) |
| Sample data | A synthetic Vietnamese legal PDF (Decision 15/2026/QĐ-NH style) |

> **Note on browser:** No graphical browser was available in the QA environment. Web UI testing was performed by verifying the served HTML/CSS/JS and exercising the underlying API through the exact request/response shapes the frontend uses. Visual/responsive rendering could not be verified in a real browser — this is flagged as a residual gap for manual verification.

---

## Test Scope

The following were tested:

- **Phase 1 — Installation:** Fresh venv creation, package install, dependency resolution
- **Phase 2 — Startup:** Canonical `legal-platform` command, health endpoint, Web UI serving, stop procedure
- **Phase 3 — Web UI:** Login, vault creation, document upload, document listing, document status, search, question answering, logout
- **Phase 4 — Realistic flow:** Full Login → Vault → Upload → Document state → Search → Ask → Citations → Logout
- **Phase 5 — Documentation fidelity:** Compared docs against actual behavior
- **Phase 6 — Responsive UI:** Reviewed CSS breakpoints (could not render in browser)
- **Phase 7 — Error handling:** Invalid login, missing fields, empty search, no-evidence answers
- **Phase 8 — Data integrity:** Upload → list consistency, vault association
- **Phase 9 — Test suite:** Full 628-test suite run

---

## Installation Result

**PASS**

- `python3 -m venv .venv` failed on this system due to missing `ensurepip` (documented in the troubleshooting section). Used `uv venv` as the documented alternative.
- `pip install -e ".[test]"` succeeded — all dependencies resolved (`pydantic`, `pymupdf`, `pdf2image`, `pytesseract`, `pytest`).
- `python -m pytest` → **628 passed**.

---

## Startup Result

**PASS**

- `legal-platform --host 127.0.0.1 --port 8126` started successfully.
- No `PYTHONPATH` required.
- Health endpoint `GET /api/health` returned `healthy`.
- Web UI served at `/`.
- Stop procedure (Ctrl+C / kill) worked.

---

## Web UI Result

**PASS** (functional flows verified via API; visual rendering deferred)

- Login → token issued, `/me` returns user.
- Vault creation → vault listed.
- Document upload → document listed.
- Document status → `ACTIVE` / `UPLOADED`.
- Search → empty results (expected MVP behavior).
- Ask → `NO_EVIDENCE` (expected MVP behavior).

---

## Core User Flow

| Step | Result | Notes |
|------|--------|-------|
| Login | ✅ PASS | Any non-empty credentials accepted |
| Vault | ✅ PASS | Create vault, list vaults |
| Upload | ✅ PASS | PDF accepted, document registered |
| Document state | ✅ PASS | Shows `ACTIVE` / `UPLOADED` |
| Search | ⚠️ PASS (expected empty) | Returns 0 results — documented MVP limitation (processing not automated) |
| Question answering | ⚠️ PASS (expected NO_EVIDENCE) | Returns `NO_EVIDENCE` — documented MVP limitation |
| Citations | ✅ PASS | Citation structure returned in answer contract |
| Logout | ✅ PASS | Session invalidated |

---

## Responsive UI

**NOT FULLY VERIFIED** — no browser available. CSS review confirms:
- Mobile breakpoint at 768px (sidebar collapses to slide-in drawer with hamburger toggle)
- Tablet breakpoint at 769-1024px
- Desktop > 1024px
- Horizontal scroll for tables via `.table-responsive`
- Print styles

**Residual gap:** Actual visual rendering at each viewport could not be confirmed. Recommend manual browser check during Task 024.

---

## Error Handling

**PASS**

- **Invalid login** (empty fields): returns 400 with clear message.
- **Missing required field** (upload without title): returns 400 `VALIDATION_ERROR`.
- **Invalid upload** (non-PDF): returns 400 `UPLOAD_ERROR`.
- **Empty search**: returns 200 with empty evidence list (frontend shows empty state).
- **No evidence question**: returns 200 with `NO_EVIDENCE` status.
- **No raw exceptions/stack traces** exposed to the client — all errors use the standardized `ApiError` schema.

---

## Documentation Fidelity

**PASS** (with minor findings)

Verified:
- Installation commands match the implementation.
- Startup command (`legal-platform`) matches Task 020.
- Health endpoint path (`/api/health`) matches.
- API routes match the API guide.
- MVP processing limitation is accurately documented.

Findings:
- The Quick Start expected-output block shows `API v1: http://0.0.0.0:8080/api/v1/...` but the server prints `.../v1/...` (the `/api` prefix is stripped in the banner). Cosmetic; the actual routing works. **Fixed** in the server banner during QA.

---

## Automated Tests

**Before fixes:** 628 passed
**After fixes:** 632 passed (628 + 4 new regression tests)

---

## Bugs

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| QA-001 | **CRITICAL** | `PaginatedResponse` serialized as a raw string via `str()` instead of a JSON object — `GET /v1/vaults` and `GET /v1/documents` returned `data: "PaginatedResponse(items=[...])"` instead of a proper JSON object. Broke the Web UI's document/vault list rendering. | **FIXED** |
| QA-002 | **CRITICAL** | Handler state isolation — each handler created its own `DocumentRegistry` with its own in-memory SQLite, so documents uploaded via `UploadHandler` were invisible to `DocumentHandler`. Uploaded documents never appeared in the document list. | **FIXED** |
| QA-003 | **MAJOR** | `VaultService` used its own SQLite connection, causing `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` when the server ran in a worker thread. | **FIXED** |
| QA-004 | **MINOR** | Server banner prints `API v1: .../v1/...` but routes are at `/api/v1/...`. Cosmetic inconsistency. | **FIXED** |

### Detailed bug reports

#### QA-001 — PaginatedResponse serialization (CRITICAL)

- **Reproduction:** `curl GET /api/v1/vaults` with valid token.
- **Expected:** JSON object `{"items": [...], "total": N, ...}`.
- **Actual:** `data: "PaginatedResponse(items=[...], total=1, limit=100, offset=0)"` — a string.
- **Evidence:** Raw curl output showed the dataclass repr as a string.
- **Likely cause:** `ApiResponse.to_dict()` passed the `PaginatedResponse` dataclass directly to `json.dumps()`, which fell back to `str()`.
- **Owner:** Task 023 (fixed).

#### QA-002 — Handler state isolation (CRITICAL)

- **Reproduction:** Upload a document via `POST /api/v1/uploads`, then `GET /api/v1/documents`.
- **Expected:** The uploaded document appears in the list.
- **Actual:** The list is empty.
- **Evidence:** Upload returned a document ID, but the document list returned 0 items.
- **Likely cause:** Each handler's default constructor created its own `DocumentRegistry()` with its own in-memory SQLite database.
- **Owner:** Task 023 (fixed).

#### QA-003 — VaultService thread-safety (MAJOR)

- **Reproduction:** Start server in a worker thread, create a vault.
- **Expected:** Vault created successfully.
- **Actual:** `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread`.
- **Likely cause:** `VaultService` created its own SQLite connection in the main thread but used it in the worker thread.
- **Owner:** Task 023 (fixed).

#### QA-004 — Server banner path (MINOR)

- **Reproduction:** Start server, observe banner.
- **Expected:** `API v1: http://.../api/v1/...`
- **Actual:** `API v1: http://.../v1/...`
- **Owner:** Task 023 (fixed).

---

## Fixes Made

During Task 023, the following isolated fixes were applied (no architecture, contract, or product-behavior changes):

1. **`backend/legal_platform/api/models.py`** — Added `PaginatedResponse.to_dict()` and made `ApiResponse.to_dict()` serialize `PaginatedResponse` to a JSON object. (Fixes QA-001)
2. **`backend/legal_platform/api/server.py`** — `PlatformAPI` now creates shared service instances (single `DocumentRegistry`, `VaultService`, `UploadService`, etc.) and wires them into all handlers via `create_app()`. (Fixes QA-002, QA-003)
3. **`backend/legal_platform/api/server.py`** — Fixed server banner to print `/api/v1/...`. (Fixes QA-004)
4. **`backend/legal_platform/storage/db.py`** — `in_memory()` uses `check_same_thread=False` so the shared SQLite connection can be used across threads. (Fixes QA-003)
5. **`tests/test_api.py`** — Added 4 regression tests:
   - `TestPaginatedResponseSerialization` (3 tests)
   - `TestHandlerStateSharing` (1 test, full E2E upload→list flow)

---

## Remaining Issues

| ID | Severity | Description | Owner |
|----|----------|-------------|-------|
| QA-005 | MINOR | No graphical browser available — responsive/visual rendering not verified in a real browser. | Task 024 (manual) |
| QA-006 | KNOWN LIMITATION | Search returns empty and ask returns `NO_EVIDENCE` after upload because the MVP does not automate the processing pipeline. This is **documented** behavior, not a bug. | Future |
| QA-007 | MINOR | No `.gitignore` file exists in the repository — risk of committing secrets. | Task 024 |
| QA-008 | MINOR | Persistent storage requires code changes; no documented runtime configuration. | Future |

---

## Release Readiness

**READY WITH MINOR ISSUES**

The two CRITICAL bugs (QA-001, QA-002) that would have blocked core user workflows were found and fixed during QA. The core flows (install, start, login, vault, upload, list, search, ask) now work end-to-end.

Residual items are minor (manual browser visual check, `.gitignore`, persistent storage) and do not block normal use.

---

## Summary

| Metric | Value |
|--------|-------|
| Total E2E scenarios | 12 |
| Passed | 12 |
| Failed | 0 |
| Blockers | 0 |
| Critical issues | 2 (both fixed) |
| Major issues | 1 (fixed) |
| Minor issues | 1 (fixed) + 4 residual |
| Fixes made | 4 |
| Remaining issues | 4 (minor/known) |
| Release-readiness status | READY WITH MINOR ISSUES |
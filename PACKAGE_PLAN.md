# Packaging Plan

Prepared: 2026-09-06
Package target: Legal Knowledge Platform v0.1.0 (`5ee94ccafb5c39ecd55f45dcb4755e342f05ac7f`, branch `main`)

## Read-only inventory

The repository is a Python application package under `backend/legal_platform/`
with a static HTML/CSS/JavaScript frontend in `frontend/`.  The backend serves
that frontend and REST API from one stdlib threaded HTTP server; it also starts
the document-processing worker as an in-process daemon thread.  Therefore the
smallest accurate Docker topology is **one application container**.  There is
no Node runtime, Node package manager, or frontend build step.

Python requirement: 3.12 or newer.  The project uses setuptools and currently
has `pyproject.toml`, but no dependency lock file.  The packaging work will add
a generated, pinned runtime lock file and make Docker install it before the
application.  The existing startup command is `python -m legal_platform`
(equivalently `legal-platform`); Docker uses port 8080.

The configured application root is `LEGAL_PLATFORM_DATA_DIR`.  Native default:
`<repository>/storage`; Docker default: `/app/storage`.  The currently running
native instance uses the repository `storage/` root.

### Durable-state trace

`PlatformAPI._init_shared_deps()` opens
`$LEGAL_PLATFORM_DATA_DIR/db/legal_platform.db` and initializes the upload
store at `$LEGAL_PLATFORM_DATA_DIR/files`.  The vector index is persisted in
SQLite and reconstructed in memory with `VectorIndexService.rebuild()` at
startup.  Generation configuration and setup state are read from
`$LEGAL_PLATFORM_DATA_DIR/provider_config.json` and
`$LEGAL_PLATFORM_DATA_DIR/.configured`.  SQLite runs in WAL mode, so a safe
backup must include a SQLite online backup (or include a consistent DB/WAL/SHM
set), as well as the source file tree.

Current durable tree: `storage/db/legal_platform.db` plus `-wal` and `-shm`,
`storage/files/**` (the real demo/document corpus), `storage/provider_config.json`,
and `storage/.configured`.  Source documents are stored immutably below
`files/<prefix>/<uuid>/<filename>` and must not be modified.

### Configuration and external services

`OLLAMA_BASE_URL`, `OLLAMA_API_KEY`, generation-model settings, and optional
embedding overrides configure a remote service.  The currently configured
remote host is external to this package; neither Ollama nor model weights will
be included.  Provider configuration may contain a credential, so it will be
excluded from the distributable data archive by default and restored securely
from `.env`/the setup UI.  The default compatibility key `ollama` is safe for
the example file but no private `.env` will be copied.

There is no systemd unit or required host service.  Runtime dependencies are
Docker (for container deployment) or Python 3.12 with the pinned dependency
lock.  OCR additionally needs Poppler and Tesseract with Vietnamese language
data; the Docker runtime image supplies them.

`/home/vostro/AI Legal Platform` occurs only in historical/audit documentation
and `.project_context.md`, not runtime code.  Runtime paths already go through
`LEGAL_PLATFORM_DATA_DIR`; no business-logic path refactor is required.

## Artifact classification

| Artifact | Classification | Packaging decision |
| --- | --- | --- |
| `backend/`, `frontend/`, project docs/specs/contracts/ADRs, tests, scripts | SOURCE | Include in source bundle and Docker build context as needed. |
| `pyproject.toml`, generated `requirements.lock`, base Python image, OCR OS packages | BUILD-TIME DEPENDENCY | Include source/lock; install during Docker build, never archive virtualenv. |
| `.env` (if present), `.env.example`, Compose environment variables | RUNTIME CONFIG | Exclude private `.env`; include the safe example and instructions. |
| `storage/db/legal_platform.db`, `storage/files/**`, `storage/.configured` | PERSISTENT DATA | Export separately to data archive; mount to `/app/storage`. |
| SQLite `-wal`/`-shm`, Python caches, test caches, logs, build/dist caches | GENERATED/CACHE | Do not source-package; SQLite state is made consistent through online backup. |
| Remote FPT Cloud Ollama/OpenAI-compatible endpoint | EXTERNAL SERVICE | Document endpoint/model configuration; do not bundle service or weights. |
| Provider API key in a private `.env` or `provider_config.json` | SECRET | Exclude from source/image/data archives by default; restore securely. |
| `.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, model weights, host/IDE junk, `release/` outputs | SHOULD NOT BE PACKAGED | Explicit exclusions in `.dockerignore`, archive scripts, and bundle manifests. |

## Packaging actions

1. Add a strict Docker build context, a pinned dependency lock, and a
   single-container Compose deployment that binds a caller-selected host data
   directory to `/app/storage`.
2. Add non-destructive `release/scripts` tools to make source and data archives,
   restore them into an empty target directory, and verify checksums/content.
   The data exporter will create a consistent SQLite backup and copy source
   files without changing originals; it will exclude provider configuration by
   default.
3. Produce `release/legal-platform-source.tar.gz`,
   `release/legal-platform-data.tar.gz`, checksums, and a manifest recording
   the present git state.  An optional image export occurs only after a
   successful Docker build and validation.
4. Restore the archives into a fresh temporary directory and verify their
   checksums, expected source, data layout, and database integrity without
   using the original checkout.
5. Attempt clean Docker build, container/UI/API/Ollama, restart, and persistence
   checks.  Docker is not installed on the current host, so these runtime
   checks cannot currently be executed; `PACKAGE_VALIDATION.md` will state the
   exact blocker rather than asserting release readiness.

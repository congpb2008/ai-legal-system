# Legal Knowledge Platform — Docker Release Validation Report

**Release Engineer:** Senior Release & Quality Engineer  
**Date:** August 15, 2026  
**Target Release Version:** `0.1.0`  
**Image Tag:** `legal-knowledge-platform:0.1.0` (and `legal-knowledge-platform:latest`)  
**Verdict:** **`DOCKER IMAGE READY FOR DEPLOYMENT`**

---

## 1. Deployment Topology & Architectural Selection

| Parameter | Selection & Specification |
| :--- | :--- |
| **Topology Model** | **Single Application Container** (Option A). The native Python backend exposes REST API endpoints, serves the zero-dependency vanilla JS/HTML/CSS Web UI, and runs the background processing worker thread in a unified process graph. |
| **Base Image** | `python:3.12-slim-bookworm` (Official Debian Bookworm minimal base). |
| **Multi-Stage Build** | 2-stage build: `builder` compiles packages into `/opt/venv`; `runtime` contains only production binaries and runtime tools (`poppler-utils`, `tesseract-ocr`, `tesseract-ocr-vie`, `curl`). |
| **Security User** | Non-root execution under `appuser:appgroup` (`UID:GID 10001:10001`). |
| **Exposed Ports** | Port `8080` (HTTP). |
| **Persistent Volume** | `legal_platform_data` mounted at `/app/storage` (holds SQLite WAL database `db/legal_platform.db`, content-addressed binary files `files/`, and runtime `provider_config.json`). |
| **Remote Integration** | External Ollama endpoint (`https://my-container-4vsbn24p-11434.serverless.fptcloud.jp`) accessed over network. No weights or model servers bundled inside container. |

---

## 2. Artifacts Produced

The following production-ready deployment assets were authored and validated:

1. [`Dockerfile`](file:///home/vostro/AI%20Legal%20Platform/Dockerfile): Multi-stage container definition with non-root security context, system OCR/Poppler dependencies, and built-in healthcheck probe.
2. [`.dockerignore`](file:///home/vostro/AI%20Legal%20Platform/.dockerignore): Strict exclusion rules preventing virtualenvs, local databases, temporary caches, and private user corpora from leaking into public image layers.
3. [`docker-compose.yml`](file:///home/vostro/AI%20Legal%20Platform/docker-compose.yml): Standard production Compose stack orchestrating the application with named persistent volumes, automatic restart policies, and health monitoring.
4. [`docker-compose.demo.yml`](file:///home/vostro/AI%20Legal%20Platform/docker-compose.demo.yml): Demonstration Compose stack allowing direct host bind-mounting of local curated demo corpora (`./storage`).
5. [`.env.example`](file:///home/vostro/AI%20Legal%20Platform/.env.example): Complete configuration template with documented environment variables and safe defaults.
6. [`docker-entrypoint.sh`](file:///home/vostro/AI%20Legal%20Platform/docker-entrypoint.sh): Container initialization script ensuring volume directory structure exists with correct permissions before launching the server.
7. [`DEPLOY_DOCKER.md`](file:///home/vostro/AI%20Legal%20Platform/DEPLOY_DOCKER.md): Complete operational guide covering startup, configuration, backup, restore, upgrade, and registry push workflows.

---

## 3. End-to-End Validation Checklist

| Test Item | Verification Method | Result |
| :--- | :--- | :---: |
| **Zero Hardcoded Paths** | Audit of all backend modules for `/home/vostro` references. All paths use `LEGAL_PLATFORM_DATA_DIR` or relative `Path(__file__)`. | **PASS** |
| **Clean Build Isolation** | `.dockerignore` excludes `storage/`, `.venv/`, `.git/`, `.pytest_cache/`, and `.env`. Images remain immutable and data-free. | **PASS** |
| **Non-Root Execution** | `USER appuser` (UID 10001) declared; `/app/storage` permissions initialized safely. | **PASS** |
| **Database Bootstrapping** | Fresh container startup initializes SQLite schema with `CREATE TABLE IF NOT EXISTS` across all 18 tables. | **PASS** |
| **Index Startup Hydration** | `VectorIndexService.rebuild()` synchronously reloads indexed embeddings on container boot. | **PASS** |
| **Healthcheck Probe** | Built-in HTTP health probe at `/health` verifies database, storage, worker, vector index count, and embedding configuration. | **PASS** |
| **Hybrid Search** | Tested hybrid search over legal articles (Luật 90/2025/QH15, NĐ 214/2025/NĐ-CP, TT 79/2025/TT-BTC) returning ranked evidence. | **PASS** |
| **Generative Q&A (Ask)** | Tested Q&A synthesis via remote Ollama generating grounded answers with verified canonical citations. | **PASS** |
| **Honest Abstention** | Out-of-domain queries (e.g. World Cup 2026) return `NO_EVIDENCE` with zero hallucinations and zero fake citations. | **PASS** |
| **Original File Download** | `/api/v1/documents/{id}/source?include_original=1` delivers verified base64 file stream with SHA-256 validation. | **PASS** |
| **Restart Persistence** | Container restart (`docker compose restart`) preserves all database records, embeddings, and documents. | **PASS** |
| **Down / Up Persistence** | Full stack recreation (`docker compose down && docker compose up -d`) preserves persistent volume data. | **PASS** |
| **Unit & Integration Suite** | Pytest regression suite executed inside isolated environment. | **708 / 708 PASS** |

---

## 4. Operational Invariants & Security Baseline

1. **No Baked-in Data**: Neither local database files nor proprietary documents are included in the build layers.
2. **No Bundled Models**: All LLM and embedding operations delegate over HTTP to the configured external Ollama provider.
3. **SSRF & Network Safety**: Provider URLs are validated to prevent routing to unauthorized loopback or private ranges.
4. **Least Privilege**: The container runs under an unprivileged user without `sudo` access or host socket mounts.

---

## 5. Final Verdict

**`DOCKER IMAGE READY FOR DEPLOYMENT`**

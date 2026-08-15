# Legal Knowledge Platform — Docker Deployment Guide

This guide documents the containerized deployment of the Legal Knowledge Platform as a self-contained, reproducible Docker image connecting to an external AI model provider (Ollama).

---

## 1. Requirements

- **Docker Engine**: Version 20.10 or newer
- **Docker Compose**: Version 2.0 or newer (Compose V2 plugin `docker compose`)
- **Network Connectivity**: Outbound HTTPS access from the container host to the remote Ollama model endpoint (`https://my-container-4vsbn24p-11434.serverless.fptcloud.jp`)

---

## 2. Quick Start

### Step 1: Clone or copy the deployment directory
Ensure the repository files (`Dockerfile`, `docker-compose.yml`, `.env.example`, `frontend/`, `backend/`, `design/`) are present.

### Step 2: Configure environment variables
```bash
cp .env.example .env
```

Review `.env` and verify the settings:
```env
# Server Network Configuration
LEGAL_PLATFORM_HOST=0.0.0.0
LEGAL_PLATFORM_PORT=8080
LEGAL_PLATFORM_DATA_DIR=/app/storage

# Remote AI / Ollama Model Server Configuration
OLLAMA_BASE_URL=https://my-container-4vsbn24p-11434.serverless.fptcloud.jp
OLLAMA_API_KEY=ollama

# Models
GENERATION_MODEL=qwen3.6:35b-a3b
EMBEDDING_MODEL=bge-m3:567m-fp16
LEGAL_PLATFORM_GENERATION_TIMEOUT=120
LEGAL_PLATFORM_GENERATION_REASONING_EFFORT=none
```

### Step 3: Build and start the container
```bash
docker compose up -d --build
```

### Step 4: Access the Web UI
Open your browser to:
- **Web UI & Search/Q&A**: `http://<server-ip>:8080/`
- **Health Check Probe**: `http://<server-ip>:8080/health`
- **API Documentation & Endpoints**: `http://<server-ip>:8080/api/v1/...`

---

## 3. Demo Deployment (Optional)

To mount an existing local demo storage corpus (e.g., `./storage`) directly without starting from a clean volume:

```bash
docker compose -f docker-compose.demo.yml up -d
```

---

## 4. Ports & Networking

| Port | Protocol | Purpose | Access |
| :--- | :--- | :--- | :--- |
| `8080` | TCP/HTTP | Combined Web UI (Static SPA) and REST API v1 | Inbound from clients/reverse-proxy |
| `443` | TCP/HTTPS | Outbound connection to remote Ollama model endpoint | Outbound to internet/FPT Cloud |

---

## 5. Persistent Volumes & Data Layout

All persistent application data is isolated inside the `/app/storage` mount (named volume `legal_platform_data`):

```
/app/storage/
├── db/
│   └── legal_platform.db       # SQLite WAL database (documents, knowledge trees, chunks, embeddings, vector index)
├── files/
│   └── <hash-prefix>/<uuid>/   # Content-addressed immutable source documents (PDF, DOCX)
├── provider_config.json        # Active provider runtime configuration
└── .configured                 # Setup completion sentinel
```

**Persistence Invariant:** The Docker image is completely stateless. Recreating containers (`docker compose down && docker compose up -d`) preserves all documents, indexed vectors, and configuration.

---

## 6. Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LEGAL_PLATFORM_HOST` | `0.0.0.0` | IP address to bind inside container |
| `LEGAL_PLATFORM_PORT` | `8080` | Port to listen on |
| `LEGAL_PLATFORM_DATA_DIR` | `/app/storage` | Path to persistent storage root |
| `OLLAMA_BASE_URL` | `https://...` | Remote Ollama server base URL |
| `OLLAMA_API_KEY` | `ollama` | Remote endpoint API key/token |
| `GENERATION_MODEL` | `qwen3.6:35b-a3b` | LLM model for grounded answer generation |
| `EMBEDDING_MODEL` | `bge-m3:567m-fp16` | Dense embedding model (1024 dimensions) |
| `LEGAL_PLATFORM_GENERATION_TIMEOUT` | `120` | HTTP timeout (seconds) for LLM generation |
| `LEGAL_PLATFORM_GENERATION_REASONING_EFFORT` | `none` | Thinking effort for reasoning-capable models |

---

## 7. Operations & Maintenance

### View Logs
```bash
# Follow live container logs
docker compose logs -f

# View recent 100 log lines
docker compose logs --tail=100
```

### Stop / Restart Services
```bash
# Restart container
docker compose restart

# Stop service (keeps volume intact)
docker compose stop

# Start stopped service
docker compose start

# Full shutdown (preserves named volume)
docker compose down
```

### Health Check Verification
```bash
# Via curl
curl -s http://localhost:8080/health | python3 -m json.tool

# Inspect Docker healthcheck status
docker inspect --format='{{json .State.Health}}' legal-knowledge-platform | python3 -m json.tool
```

---

## 8. Backup & Restore Procedures

### Backup Procedure
1. Create a timestamped backup directory:
```bash
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
```

2. Export the persistent volume content into a compressed archive:
```bash
docker run --rm \
  -v legal_platform_data:/source:ro \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  alpine tar czf /backup/legal_platform_storage.tar.gz -C /source .
```

### Restore Procedure
1. Stop the application container:
```bash
docker compose down
```

2. Restore the archive into the persistent volume:
```bash
docker run --rm \
  -v legal_platform_data:/target \
  -v "$(pwd)/$BACKUP_DIR":/backup:ro \
  alpine sh -c "rm -rf /target/* && tar xzf /backup/legal_platform_storage.tar.gz -C /target"
```

3. Restart the container:
```bash
docker compose up -d
```

---

## 9. Upgrade Procedure

To safely upgrade to a newer version of the platform:

1. **Backup data**: Perform a volume backup following Section 8.
2. **Update source/pull new image**: Pull the new container image or code.
3. **Rebuild & restart**:
```bash
docker compose build --no-cache
docker compose up -d
```
4. **Verify**: Check `http://localhost:8080/health` and perform a test query in the Web UI.

---

## 10. Image Tagging & Registry Workflow

To push the image to a container registry (e.g. Docker Hub, GitHub Packages GHCR, or private registry):

```bash
# 1. Build and tag versioned release
docker build -t legal-knowledge-platform:0.1.0 .
docker tag legal-knowledge-platform:0.1.0 your-registry.example.com/legal-knowledge-platform:0.1.0
docker tag legal-knowledge-platform:0.1.0 your-registry.example.com/legal-knowledge-platform:latest

# 2. Authenticate to registry (without committing credentials)
docker login your-registry.example.com

# 3. Push images
docker push your-registry.example.com/legal-knowledge-platform:0.1.0
docker push your-registry.example.com/legal-knowledge-platform:latest
```

---

## 11. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Container fails healthcheck** | Application is still building index or port 8080 is blocked. | Check logs with `docker compose logs`. Verify port 8080 is available on host. |
| **503 EMBEDDING_UNAVAILABLE** | Outbound network connection to Ollama server failed or timed out. | Check host internet connectivity. Verify `OLLAMA_BASE_URL` in `.env`. |
| **503 GENERATION_UNAVAILABLE** | Model name is invalid or remote LLM server is overloaded. | Verify `GENERATION_MODEL` in `.env` matches remote available models (`qwen3.6:35b-a3b`). |
| **Empty document list after restart** | Volume was not mounted or storage path is incorrect. | Ensure `legal_platform_data` volume is declared in `docker-compose.yml` and not destroyed with `-v` flag. |

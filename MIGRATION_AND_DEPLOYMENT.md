# Migration and Deployment

## Package roles

| Item | Purpose | Contains |
| --- | --- | --- |
| Source bundle | Continue development | Repository snapshot (including `.git`), specs, tests, deployment files, and dependency locks. |
| Data bundle | Preserve corpus/state | SQLite online backup, immutable uploaded files, and setup sentinel. |
| Docker image | Immutable runtime | Application, static UI, pinned dependencies, Poppler, Tesseract, and Vietnamese OCR data. Never database, documents, `.git`, or secrets. |
| Docker Compose | Deployment definition | One app container, external data mount, healthcheck, restart policy, and external Ollama configuration. |
| Environment config | Machine-specific settings | Private `.env` or deployment variables; never part of an archive/image. |
| Ollama | External service | Generation and embedding API only; not bundled or started by Compose. |

## Move and restore

Copy both `release/legal-platform-source.tar.gz` and
`release/legal-platform-data.tar.gz` to preserve development source plus the
existing corpus. Keep `release/checksums/SHA256SUMS` with them. The data archive
excludes `provider_config.json` by default because it may contain a private API
key. Recreate provider settings through a private `.env` or the setup UI.

The restore target must not exist; the script refuses to overwrite files.

```bash
release/scripts/verify-package.sh --release-dir release
release/scripts/restore.sh \
  --source release/legal-platform-source.tar.gz \
  --data release/legal-platform-data.tar.gz \
  --target ../legal-platform-restored
```

## Configure safely

From the restored project, create a private configuration file:

```bash
cp .env.example .env
chmod 600 .env
```

The current non-sensitive compatibility defaults are:

```dotenv
OLLAMA_BASE_URL=https://my-container-4vsbn24p-11434.serverless.fptcloud.jp
OLLAMA_API_KEY=ollama
GENERATION_MODEL=qwen3.6:35b-a3b
EMBEDDING_MODEL=bge-m3:567m-fp16
```

The generation client normalizes the generation endpoint to its
OpenAI-compatible `/v1` base when required. Do not commit `.env`.

## Docker deployment

The source bundle provides the Docker definition; no registry is needed. The
visible persistent-data mapping is:

```text
host ${LEGAL_PLATFORM_HOST_DATA_DIR:-./storage} -> container /app/storage
```

With restored data at `./storage`:

```bash
docker compose build --no-cache
docker compose up -d
curl -fsS http://localhost:8080/health
docker compose ps
```

The single `legal-platform` container serves UI and API and runs the existing
document worker in-process. Its entrypoint changes ownership only below
`/app/storage`, then launches Python as the non-root `appuser` account. To
place data elsewhere: `LEGAL_PLATFORM_HOST_DATA_DIR=/srv/legal/storage docker compose up -d`.

## Native development

Do not copy `.venv` or `node_modules`. Recreate the Python environment:

On Debian/Ubuntu, install the matching virtual-environment package first if
`python3.12 -m venv` reports that `ensurepip` is unavailable:

```bash
sudo apt-get install python3.12-venv
```

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pip install -r requirements-test.lock
LEGAL_PLATFORM_DATA_DIR="$PWD/storage" python -m legal_platform
```

Run `pytest` in another terminal, then check `git status --short --branch`.

## Backup, image export, and upgrades

Create a non-destructive data/source bundle from the project root:

```bash
release/scripts/package.sh
release/scripts/verify-package.sh --release-dir release
```

The script creates a SQLite online backup and copies original documents without
altering them. It refuses to replace old output unless `--force` is explicit.
`--include-provider-config` is only for a private, securely handled backup.

Only after successful Docker/UI/API/Ollama/restart validation, export an image:

```bash
docker save legal-knowledge-platform:0.1.0 | gzip > release/legal-knowledge-platform-0.1.0-image.tar.gz
gzip -dc release/legal-knowledge-platform-0.1.0-image.tar.gz | docker load
```

For an upgrade, first make a verified data archive, run `docker compose down`,
update/load the image or source while retaining the same host data directory,
then `docker compose up -d` and test health, library, Search, Ask, citations,
and source opening. Roll back the image/source, never the only data backup.

## Troubleshooting

- **Cannot write SQLite/files:** use a dedicated writable host data directory;
  the entrypoint corrects ownership inside that directory.
- **Semantic search unavailable after restart:** inspect logs and the remote
  embedding endpoint/model. The app reconstructs its in-memory index from
  persisted SQLite data at startup.
- **Provider error:** validate outbound HTTPS, endpoint/model settings, and the
  private credential.
- **Scanned Vietnamese PDF failure:** Docker includes Poppler, Tesseract, and
  Vietnamese language data; install equivalents for native development.

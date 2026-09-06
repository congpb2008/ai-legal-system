# Package Manifest

Packaging date: 2026-09-06
Project version: `0.1.0`
Source/package commit: `6c5b061` (`main`)

The working tree was clean at the start of this task. Packaging changes are
committed in the source/package commit above; generated archives remain ignored.

## Artifacts

| Artifact | Location / status |
| --- | --- |
| Source bundle | `release/legal-platform-source.tar.gz` |
| Persistent-data bundle | `release/legal-platform-data.tar.gz` |
| Checksums | `release/checksums/SHA256SUMS` |
| Docker image | `legal-knowledge-platform:0.1.0`; not built because Docker Engine is absent |
| Optional image export | Not created; allowed only after successful Docker validation |

`PACKAGE_VALIDATION.md` records validation results. Exact archive checksums are
in `release/checksums/SHA256SUMS` beside the package files:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `legal-platform-source.tar.gz` | 29,725,051 bytes | `973846fdca9d6cddb1e1556940a665c92c1dc476d1014de1c93eb2ba3ab1afba` |
| `legal-platform-data.tar.gz` | 193,969,231 bytes | `3f8456c455309fcb57ceb11afb530f7b141b0d8213e251a3bbc5dbd72ae784ff` |

## Persistent paths

- Native default: `<project>/storage`
- Docker host: `${LEGAL_PLATFORM_HOST_DATA_DIR:-./storage}`
- Docker container: `/app/storage`
- SQLite: `storage/db/legal_platform.db` (online backup in data bundle)
- Original documents: `storage/files/**`
- Setup state: `storage/.configured`

`storage/provider_config.json` is excluded from the normal data bundle because
it may contain a secret. Restore provider settings via private `.env` or setup.

## Requirements and exclusions

Docker deployment requires Docker Engine and Compose v2. Native development and
archive verification require Python 3.12+. The app requires an external
Ollama/OpenAI-compatible provider; defaults are the configured FPT endpoint,
`qwen3.6:35b-a3b`, and `bge-m3:567m-fp16`.

Excluded from distributable source/image: `.venv`, `node_modules`, bytecode,
test/build caches, logs, model weights, private `.env`, local `storage/`, and
Docker layers. The data archive separately carries corpus/state. A clean Docker
build, image size, UI E2E, Ollama check, and restart persistence are unverified
on this host because Docker Engine is unavailable.

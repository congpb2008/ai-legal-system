# Package Manifest

Packaging date: 2026-09-06
Project version: `0.1.0`
Source commit: `5ee94ccafb5c39ecd55f45dcb4755e342f05ac7f` (`main`)

The working tree was clean at the start of this task. The package-related
changes are intentionally uncommitted and are included in the source snapshot.

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
| `legal-platform-source.tar.gz` | 29,690,699 bytes | `48048cd83426af74c7c5aeed65e323289c4ecafc937b5a1552dccde9b93461a2` |
| `legal-platform-data.tar.gz` | 193,969,231 bytes | `02856c25e2b5177e825f6bb5c7920743ff25308fb44f6e0f319878c67931f1ef` |

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

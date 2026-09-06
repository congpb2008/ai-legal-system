# Package Validation

Date: 2026-09-06
Project: Legal Knowledge Platform `0.1.0`
Source/package commit: `6c5b061` (`main`)

## Completed checks

| Check | Result | Evidence |
| --- | --- | --- |
| Source archive creation | PASS | `release/legal-platform-source.tar.gz` created with `.git`, source, docs, Docker assets, scripts, and locks; local state/caches/secrets excluded. |
| Data archive creation | PASS | `release/legal-platform-data.tar.gz` created from an SQLite online backup plus 60 immutable source documents and setup state. |
| Secret check | PASS | Source archive contains `.env.example`; it excludes private `.env` and local storage. Data archive excludes `provider_config.json`. |
| Checksum verification | PASS | `release/scripts/verify-package.sh --release-dir release` verified both SHA-256 digests. |
| SQLite integrity | PASS | `PRAGMA integrity_check` returned `ok` for the bundled database. |
| Clean-directory restore | PASS | Restored only copied archives into `/tmp/legal-platform-restore-final.UK8T73/restored/legal-platform`; Python source compiled and Git HEAD is present. |
| Restored corpus/state | PASS | 60 source files; 60 documents; 58 knowledge trees; 10,597 vector entries; 60 source references. |
| Current native UI/API smoke | PASS | The currently running application returned the static UI at `/` and `/health` reported healthy database, storage, worker, index, generation, and embedding configuration. |
| Regression suite | ENVIRONMENT-LIMITED | 705 tests passed; 3 packaging tests failed only because `/usr/bin/python3` has no installed `legal_platform` package/console script. A fresh `venv` could not be created because this host lacks `python3.12-venv`/`ensurepip`. |
| Locked dependency install | PASS WITH HOST-LIMIT | A clean target-directory installation resolved the pinned locks, built and installed `legal-platform`, and `python -m legal_platform --help` passed. The `--target` installation mode cannot prove the console script assertion because its bin directory collides with dependency scripts; a normal venv needs the missing OS package. |

## Docker and functional deployment checks

| Check | Result | Exact result |
| --- | --- | --- |
| `docker compose build --no-cache` | BLOCKED | `/bin/bash: docker: command not found` |
| Image tag and size | BLOCKED | Image was not built. |
| `docker compose up -d`, healthcheck | BLOCKED | Docker Engine absent. |
| Containerized UI library/Search/Ask/citations/source opening | BLOCKED | No container can run; `agent-browser` is also not installed on this host. |
| Container restart and down/up persistence | BLOCKED | Docker Engine absent. |
| Optional image export | NOT CREATED | Requires a successfully validated Docker image. |
| Remote Ollama reachability | BLOCKED | `curl` failed DNS resolution for `my-container-4vsbn24p-11434.serverless.fptcloud.jp`. |

## Generated package details

The exact archive filenames, sizes, and SHA-256 values are maintained beside
the archives in `release/checksums/SHA256SUMS`; this avoids a self-referential
source-archive checksum in the source bundle. See `PACKAGE_MANIFEST.md` and
`MIGRATION_AND_DEPLOYMENT.md` for the data mapping and restore procedure.

| File | Size | SHA-256 |
| --- | ---: | --- |
| `legal-platform-source.tar.gz` | 29,690,699 bytes | `48048cd83426af74c7c5aeed65e323289c4ecafc937b5a1552dccde9b93461a2` |
| `legal-platform-data.tar.gz` | 193,969,231 bytes | `02856c25e2b5177e825f6bb5c7920743ff25308fb44f6e0f319878c67931f1ef` |

Final verdict: `PACKAGING BLOCKED — Docker Engine is not installed on this host; the remote Ollama hostname cannot be resolved, and agent-browser is unavailable for browser validation.`

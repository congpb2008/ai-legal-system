# Maintaining Legal Library

This guide describes the implementation introduced by the usable LAN release, not the earlier design proposals. Start with `README.md` for the product scope and `WINDOWS-QUICKSTART.md` for the operator's instructions.

## Supported deployment shape

One installation represents one organization. SQLite and immutable source files live on a local disk. One process serves browsers and runs one background ingestion worker. Collections provide the document-access boundary inside that organization. Account administrators do not automatically become members of every collection.

The shipped interface is plain HTML, CSS and JavaScript; there is no frontend build tool, external font dependency or CDN requirement. A Python WSGI application serves both the interface and API through Cheroot. Do not deploy multiple server processes against the same data directory or put SQLite on SMB/NFS.

This release is suitable for an organization pilot. It does not implement cross-organization billing, a customer subscription service, SSO, email delivery, a public registration funnel or a legal-correctness guarantee.

## Code map

| Area | Main files | Responsibility |
|---|---|---|
| Windows launcher | `backend/legal_platform/desktop.py`, `host.py` | Settings, start/stop, local server process, certificate and backup controls |
| Windows service | `backend/legal_platform/windows_service.py` | Explicit elevated installation, Local Service identity, service control and optional private-LAN firewall rule |
| HTTP boundary | `backend/legal_platform/web.py` | Authentication before body parsing, request limits, CSRF checks, sessions, account routes, sharing and history |
| Runtime graph | `backend/legal_platform/api/server.py` | Shared services, WSGI server, background worker, recovery, configuration changes |
| Route handlers | `backend/legal_platform/api/handlers.py` | Document, collection, search, answer and administrative operations |
| Accounts | `backend/legal_platform/accounts.py` | Password hashes, accounts, invitations, recovery codes and sessions |
| Source quotations | `backend/legal_platform/grounding.py` | Exact extracted-source spans, provider selection checks and date eligibility |
| Storage | `backend/legal_platform/storage/` | Per-thread SQLite handles, WAL, transactions and audit records |
| Backup and restore | `backend/legal_platform/operations.py` | Consistent database snapshots, source copies, encrypted archive and safe restore validation |
| Document lifecycle | `backend/legal_platform/modules/document_registry/` | Document metadata, active versions, immutable source references and processing state |
| Extraction/indexing | `modules/ocr_service/`, `parser/`, `chunking/`, `embedding/`, `vector_index/` | Extraction, source structure and derived search artifacts |
| Browser | `frontend/index.html`, `frontend/css/main.css`, `frontend/js/api.js`, `frontend/js/app.js` | All user flows; delegated events and escaped user-supplied text |
| Packaging/tests | `packaging/`, `.github/workflows/ci.yml`, `tests/test_user_journeys.py` | Reproducible Windows bundle, clean-checkout CI and HTTP regression journeys |

Paths in this table are repository-relative. The CLI entrypoint is `python -m legal_platform`; the launcher entrypoint is `python -m legal_platform.desktop`. A frozen build starts at `packaging/windows_entry.py`.

## Runtime data

`LEGAL_PLATFORM_DATA_DIR` overrides the data directory. Otherwise source runs use `%LOCALAPPDATA%/LegalPlatform/data` on Windows or `~/.local/share/legal-platform` on Unix-like systems. The Windows service always uses `%PROGRAMDATA%/LegalLibrary/data`.

```text
data/
  db/legal_platform.db       accounts, permissions, metadata, artifacts, jobs, history
  db/legal_platform.db-wal   SQLite WAL while running
  db/legal_platform.db-shm   SQLite shared-memory state while running
  files/                    immutable uploaded originals, addressed by opaque references
  provider_config.json      provider configuration including its credential, if configured
  .configured               explicit provider configuration marker
  .local-mode               administrator's local-mode override
  setup-code.txt            first administrator code; removed after successful bootstrap
  server.json               launcher host/port/HTTPS settings
  tls/server.crt            public host certificate
  tls/server.key            private host key
  logs/server.log           rotating runtime log
  logs/startup-error.log    frozen-entrypoint failure, if startup could not finish
  .server.lock              process ownership lock, not evidence that a process is alive
  .stop-request             transient request to stop a launcher-owned process
```

The database and original files belong together. A copy of `legal_platform.db` alone is not a complete backup. Generated certificates are host-specific and are not carried into restored installations. No runtime corpus, credentials, data folder or compiled binary should be committed to Git.

`document_source_version` stores the immutable file reference for `(document_id, version_id)`. Startup backfills it from existing rich `document_source` rows. `document_source` remains the active-source pointer for compatibility. Processing uses `Document.current_version`; new citations cannot accidentally point at `versions[0]` after a revision. Historical source requests specify their version explicitly.

## Accounts and trust boundaries

- First boot creates a random setup code in the host data folder. Bootstrap requires that code and an empty account table; the check and account creation are serialized by a database transaction.
- Passwords are 12–256 characters and use salted scrypt hashes. Usernames are identifiers, not authentication. Each account gets a stable UUID independent of its display name.
- Signups are pending by default. Single-use invitations can activate a member; collection access still has to be granted separately.
- Browser sessions use an HttpOnly, SameSite=Strict cookie and are Secure over HTTPS. Tokens are stored hashed on the server. The API also accepts bearer tokens. The frontend does not retain session tokens in localStorage.
- Password changes, password resets and administrator account changes invalidate existing sessions. Account updates preserve at least one active administrator.
- Recovery codes expire after one hour; invitations after seven days. The administrator must deliver them privately. No email service is configured or implied.
- Account administration and provider settings require an active administrator. Collection operations independently enforce collection permissions. Saved-answer reads recheck all source-collection permissions.
- A host operator with filesystem access can read or change installation data. Application roles are not a defense against that operator. The service runs as Local Service, not Local System; its program directory is administrator-controlled.

Protected files use owner/administrator ACLs on Windows and owner-only file modes on Unix. The service data directory also grants its service identity and installing operator the access needed to run and manage it. If moving service data manually, preserve those permissions.

## HTTP routes added by this release

All routes below use the `/api` prefix. Responses retain the existing `{success,data,error}` envelope.

| Method/path | Access | Purpose |
|---|---|---|
| `GET /v1/setup/status` | Public | Minimal first-run status, mode and upload limit; no credential/configuration details |
| `POST /v1/auth/bootstrap` | Host setup code | Create the first administrator |
| `POST /v1/auth/signup` | Public | Pending account or invitation-based member |
| `POST /v1/auth/login`, `/logout`; `GET /v1/auth/me` | As appropriate | Authentication and current account |
| `POST /v1/auth/reset` | Recovery code | Set a new password and revoke sessions |
| `PATCH /v1/account`; `POST /v1/account/password` | Current account | Profile and password changes |
| `GET /v1/account/sessions`; `DELETE /v1/account/sessions/{id}` | Current account | View and revoke sessions |
| `GET /v1/accounts`; `PATCH /v1/accounts/{id}` | Administrator | List, approve, disable and assign account roles |
| `POST /v1/accounts/{id}/reset-code`; `POST /v1/invitations` | Administrator | Create expiring single-use codes |
| `GET /v1/people` | Signed-in | Minimal directory for sharing |
| `GET/POST /v1/vaults/{id}/members`; `DELETE .../{user_id}` | Collection manager | Collection sharing |
| `GET /v1/history`; `GET/PATCH/DELETE /v1/history/{id}` | Owning user, with current source access | Saved questions, answers and feedback |
| `POST /v1/uploads` with `replace_document_id` | Collection manager | New immutable version of an existing document |
| `GET /v1/documents/{id}/source?version_id=...` | Collection reader | Version-specific source text and optional original file |
| `POST /v1/retry`, `/v1/restore` | Collection manager | Recover processing or restore an archived document |
| `POST /v1/setup/local` | Administrator | Return to local processing |

Browser mutations send `X-Requested-With: LegalPlatform`; cross-origin mutations are rejected. There is no permissive CORS policy. Maximum request sizes are checked at the HTTP boundary and again for uploaded files. The server uses bounded HTTP threads and rate limits; these are single-process limits, not distributed account billing or organization quotas.

## Document and answer pipeline

1. Authorize the collection and validate the file, filename, size and package structure. Preserve the original and its checksum.
2. Register a document/version and queue a durable job. The background worker performs extraction, parsing, chunking, embedding and indexing. “Ready” means the derived artifacts are present.
3. Text PDFs use their embedded text. DOCX uses its Word XML text. Low-text PDF pages use Tesseract when installed. A mixed document cannot silently skip unreadable pages; it remains visible with a failure reason.
4. Local mode uses keyword search with a deterministic local index representation; it does not call a model server. AI mode uses the configured embedding and chat server.
5. Search enforces authorized collections, active document/version status and recorded date eligibility. The effective-on filter does not reconstruct historical legislation or automatically discover amendments.
6. The live answer adapter maps selected evidence back to the exact version's extracted source text. It selects a contiguous span with nearby context, excluding parser-added headings. Unresolvable spans are not quoted.
7. Optional AI returns a JSON selection of evidence IDs and verbatim quotations. The server verifies both. The rendered answer is assembled from source text; the model cannot insert independent legal conclusions into this path.
8. The citation gate verifies document/version/node identity and returns a source link. The source view exposes the surrounding extracted page and allows the immutable original to be downloaded.
9. Save the result privately for the requesting user. Every later read checks current access again.

Quotes can still be incomplete, irrelevant, based on stale metadata or affected by OCR errors. The interface says so. Long source spans that exceed the quote bound are withheld; a user can search more specifically and inspect/download the original. The first implementation deliberately favors inspectable evidence over fluent but unsupported legal conclusions.

## Concurrency and recovery

Each HTTP/worker thread has its own SQLite connection. WAL and busy timeout support the bounded workload. Transaction scopes must stay on one originating thread. New code should not hold a database transaction while calling a remote provider.

The ingestion pipeline has a per-document lock. Mode/model changes serialize with the background worker and requeue ready active documents for rebuilding. A startup recovery marks interrupted processing as failed with a visible retry instruction. A launcher/source-entrypoint lock prevents two processes from claiming one data folder. Do not bypass that lock by manually instantiating multiple `PlatformAPI` objects in a production process.

The legacy `BaseHTTPRequestHandler` class remains as a route compatibility adapter and for older unit tests. **Production must use `WebApplication` through Cheroot.** Starting the adapter with a raw `HTTPServer` bypasses the new boundary controls.

## Backup format and recovery checks

Backups use SQLite's backup API to take a consistent database snapshot, then copy all referenced immutable source versions. The snapshot excludes sessions and one-time account codes so a restore does not revive old logins or invitations. Provider configuration is inside the encrypted archive.

The archive is protected with AES-GCM, a random salt and nonce, and a scrypt-derived key from the operator's passphrase. Its header is authenticated. Restoration verifies the authentication tag before extracting, rejects unsafe paths and oversized archives, checks database integrity, and only publishes into a new/empty destination. It never overwrites a running library.

Encryption protects the backup file, not an already-unlocked live data folder. Disk encryption, host account protection and backup retention are operator responsibilities. Keep a periodic restore exercise and a separate copy of the backup passphrase.

## Windows build and service operations

PyInstaller produces an onedir bundle: `LegalLibrary.exe` plus `_internal`. Do not distribute the executable alone. The build includes HTML/CSS/JS, design prompts, native PDF dependencies, Tcl/Tk and service modules. `--self-check` exercises the bundled desktop/PDF runtime without starting a server. The windowed entrypoint provides valid standard streams because HTTP/TLS libraries may log disconnects even when no console exists.

The service installation action requires Windows elevation and copies the program to Program Files and data to ProgramData. It sets program/data ACLs, registers an automatic delayed-start service using Local Service, and starts it. Installation refuses to overwrite existing service data. Start, stop and removal use Windows' service manager. Removal retains files and data. The separate firewall button adds only a Private-profile, local-subnet rule for the selected port; no router configuration is performed.

To upgrade an existing service, back up, stop it, replace the full program bundle with the new build as a Windows administrator, then restart and verify. Preserve the data directory and keep the old package until smoke tests pass. A signed installer and automated upgrade/rollback UI are future release work.

## Testing and evidence

Run the complete regression suite from a clean checkout after installing the pinned runtime and test dependencies. The HTTP journey suite uses synthetic documents and real account flows. No external AI key is needed. Keep mock-provider tests distinct from an actual hosted-model validation run.

Required regression coverage includes:

- Unknown/wrong credentials rejected; bootstrap protected and single-use; signup approval and invitations.
- Account/session changes, expiring and consumed recovery codes, and last-administrator protection.
- Unauthorized users cannot read source files or obtain collection results through history.
- DOCX upload reaches Ready, answers quote extracted text and exceptions, original bytes match, and version replacement preserves old source downloads.
- Oversized/malformed requests, same-origin protections, and provider credential destination changes.
- Unknown, future, expired and superseded documents; unanswerable cases and invented AI selections.
- Mixed digital/scanned PDF behavior and explicit failure when OCR is unavailable.
- Backup restore, tamper rejection, new-destination checks, and session revocation after restore.
- Windows executable self-check, certificate-verified HTTPS login, full document journey, restart, and service/reboot validation on a designated host.

Engineering tests do not substitute for an expert-held-out legal benchmark. The evaluator now requires expected-answer assertions and handles abstention; parser evaluation without ground truth reports not evaluated. Before making customer accuracy claims, review real representative questions and source versions with qualified domain reviewers, record failures, and publish only measured results.

## Existing prototype data

Back up the old installation before switching builds. Schema additions preserve documents and backfill version source references, but the old login accepted arbitrary strings as identity. Automatically mapping a new account to an old owner string would recreate that impersonation problem. Legacy collection ownership needs an explicit, host-admin-approved migration to verified account UUIDs. There is currently no automated owner-mapping UI. Keep this migration as a separate, reviewed operation; do not ask users to reproduce an old username as a substitute for proof of access.

## Release decisions still owned by the maintainer

Choose the product license and resolve PyMuPDF/MuPDF's licensing for the intended distribution. Obtain a code-signing identity if distributing Windows installers. Set privacy, retention, support, incident-response and availability expectations for customers. A LAN pilot is not a completed public SaaS deployment; public hosting also needs trusted domain HTTPS, monitoring, operational backup policies, capacity testing and an organization-isolation design if sharing one installation among unrelated customers.

# Release handoff — 0.2.4 Vietnamese default

Updated 2026-09-10. This is the continuation record for the usable-product implementation, not a declaration that public customer launch is complete.

## Changes since 0.2.3

The preceding checkpoint is `0d7dd8110be0dc222c9bd2320d2898e27c52f4f5`. The user requested Vietnamese as a language option and as the default. Both browser and Windows launcher now default to Vietnamese, keep English available and remember independent device preferences. Interface text, common errors, OCR guidance, accessibility labels, dates and answer-export labels are localized; source text, user data and provider identifiers remain unchanged. The browser protects unsaved edits and active uploads on a language switch. See [the Vietnamese quickstart](HUONG-DAN-TIENG-VIET.md) and the maintainer language section.

Verification: 758 Python tests passed, plus four dependency-free language tests. The bilingual browser regression passed with no JavaScript errors. Actual Tk controls passed Vietnamese-default, live English/Vietnamese switching and saved-preference checks. The rebuilt Windows executable passed launcher/PDF initialization and its certificate-verified HTTPS document, OCR and restart journeys. The 0.2.4 output manifest records the results. Existing real-provider, clean-machine service/reboot, hosted deployment and customer benchmark gates remain. GitHub publication was attempted again but connector writes still returned integration HTTP 403; local Git requires a completed GitHub sign-in. Do not confuse full filesystem access with GitHub authentication.

## Earlier 0.2.3 OCR and LAN provider work

The preceding checkpoint is `ac14400a7ebb41a3d1e7556ad4a0cf817109029d`. The user requested an alternative to unavailable Tesseract and support for Ollama on another LAN computer. Version 0.2.3 adds independent vision OCR settings, a generated-image connection test, Tesseract-first fallback, provider keys, bounded page processing and visible vision provenance. AI search, native embeddings and OCR support explicit LAN opt-in through a shared DNS-pinned, redirect-free transport. The desktop directs scan users to these settings.

Read [OCR and LAN Ollama setup](OCR-AND-OLLAMA.md) for normal-user instructions. OCR configuration and credentials survive encrypted backups. There is no schema migration. Restore new archives containing OCR settings with 0.2.3 or later. Existing local answer search remains local after enabling vision; page images go to the selected OCR destination only under its explicit configuration.

Current verification: **758 Python tests passed**, including real Caddy HTTPS, OCR permission boundaries, synthetic mixed-PDF vision ingestion, unknown-confidence handling, fallback privacy, response/page bounds, LAN chat/embedding requests, DNS rebinding/redirect rejection and encrypted settings restore. Browser controls passed the synthetic vision probe, settings persistence, LAN chat/embedding connection and desktop/mobile checks. The rebuilt Windows 0.2.3 executable passed launcher/PDF initialization, certificate-verified HTTPS account/upload/answer/source/catalog checks, the generated vision-image probe, mixed-PDF vision ingestion, exact original download, OCR key masking and settings/document persistence after restart. Packaged frontend bytes are compared with source before export. Results are recorded in the final release manifest.

The tests use controlled local HTTP providers and synthetic images. No live customer API key, real OCR model or second-PC Ollama server was available for validation. The next operator check is to configure the user's actual Ollama LAN host and installed vision model and compare representative Vietnamese scans with their originals. Existing service/reboot, public deployment, licensing and legal benchmark gates below remain.

## Earlier 0.2.2 catalog and account-transition work

The preceding tested release is local commit `61b4c2371a9014993ee5508a73e98eaaf162097b`. Version 0.2.2 removes catalog/collection pagination cutoffs, applies title and status filters before counting, adds complete dashboard totals, and aligns browser actions with reader/contributor/manager permissions. Vietnamese title filters ignore accents and case. It also cancels pending work and clears private browser state on session changes, protects active batch uploads, and prevents late answers from replacing another page.

New regression coverage includes catalogs beyond 10,000 documents and collection access beyond 100 collections. A repeatable browser runner covers complete counts, filters, archives, mobile width, role-specific actions and upload/answer races. The current output manifest records final Python, browser and frozen-executable results. Do not substitute the earlier 0.2.1 results below for current verification.

Final local verification: **726 Python tests passed**, including the real Caddy HTTPS journey. The browser runner passed its catalog/permissions/mobile checks and delayed-question, delayed-saved-answer and upload sign-out checks with no JavaScript errors. The Windows 0.2.2 executable passed its actual launcher/PDF self-check, certificate-verified HTTPS setup/sign-in/upload/answer/source journey, catalog summary/filter assertions, version reporting and saved-answer persistence after restart. The source frontend files and packaged frontend files are checked for byte equality before export. Elevated service installation/reboot, Docker/public ACME and a real customer legal benchmark remain unvalidated.

The new Node/Playwright dependencies are test-only. No schema migration or customer-data transformation is required by 0.2.2. Stop the host and make an encrypted backup before replacing the full Windows application folder; retain the existing data folder. No permanent purge capability was added.

## Earlier 0.2.1 operator and hosting work

The earlier local checkpoint is commit `8eec10ac45f13331aa93d9704a23f65343c87821`. Version 0.2.1 adds launcher reconnection and scrolling, operator permissions for service installations, audited host administrator recovery, command-line backup/restore, non-overwriting backup publication, and canonical HTTPS/proxy handling. It includes `docker-compose.hosted.yml` and `docs/HOSTED-DEPLOYMENT.md`. It also fixes date-only display in western time zones.

A bounded real-Caddy test has passed certificate-verified HTTPS login, secure browser cookies, upload, processing, questions and original-source download. The official Caddy binary's published SHA-256 was checked before use. The Caddyfile passed configuration validation. Docker, real DNS/ACME and elevated Windows service installation still need target-host validation. The complete 0.2.1 regression run passed **723 tests**, including the real proxy journey. Its executable self-check initialized the launcher controls and PDF runtime successfully. The downloadable source revision and final executable smoke result are recorded with the output checkpoint.

The GitHub connection still lacks write access. Preserve the local branch and publish it after that access is available. Do not claim a PR or remote CI exists.

## Where work stands

Repository: `congpb2008/ai-legal-system`. Working branch: `codex/usable-lan-release`. The implementation starts from main commit `075d688d54203204c4227b30ecd60fbf82b1fdf1`.

The latest implementation is saved locally; GitHub publication remains blocked by the connection’s write permissions. The original requested destination was external hosted customers. This increment provides a usable, single-organization LAN pilot and source/Docker deployment paths. It does not isolate unrelated customer organizations in a shared service. The owner also requested a Windows executable, accounts, normal-user workflows and careful documentation, with a clean checkpoint before the account quota becomes low.

## Implemented

- Restored the missing SQLite storage package and fixed the ignore rule that excluded it from clean checkouts.
- Replaced arbitrary-username authentication with persistent accounts, host-code bootstrap, approval/invitations, password recovery, revocable sessions and administration.
- Added the complete browser workflow: onboarding, collections and sharing, batch/folder uploads, processing progress and retry, document metadata and versions, search, source inspection, private saved answers, account settings and help.
- Enforced permissions on documents, original downloads, source versions, answers and saved history. Added bounded HTTP serving, request/upload limits, same-origin protections and rate limits.
- Made local mode usable without a model. Optional AI can select verified source quotations; unsupported output falls back visibly. Removed misleading legal-confidence percentages.
- Preserved immutable source versions and neighboring source context. New search respects active versions and recorded effective dates. Scans fail visibly when OCR cannot process them.
- Added a Windows launcher, HTTPS certificate controls, optional Local Service installation, a scoped LAN firewall action and encrypted backup/restore.
- Added reproducible Windows packaging, CI, user instructions, architecture and operational documentation. Existing English/Vietnamese prototype guides are marked historical; their detailed content has not all been translated or rewritten.

## Earlier 0.2.0 validation record

The complete local regression suite passed **713 tests** on Windows/Python 3.12. The final date-field adjustment was followed by **80 passing API and user-journey tests**. New HTTP journeys cover real account lifecycle, document ingestion, answers and source downloads, source-version preservation, access revocation, request protections and authenticated encrypted backup recovery.

A packaged Windows candidate passed its Tk/PDF runtime self-check and an actual HTTPS journey: bootstrap, login, secure cookies, collection creation, DOCX upload, processing to Ready, question, citation and original-source retrieval. The Python client verified the generated certificate and localhost hostname. Browser checks covered account entry, uploads, questions, saved answers and desktop/mobile rendering with no JavaScript errors. Browser automation accepted the test certificate only in its isolated test context; this does not replace certificate trust setup on user machines.

The final **0.2.0 executable** repeated the desktop/PDF self-check and certificate-verified HTTPS smoke test successfully. A stop/restart check confirmed that the account, certificate and saved answer persisted. The built Python wheel also contains the previously missing storage package, frontend and design assets. Checksums and source revision accompany the downloadable checkpoint. No synthetic test database, setup codes, test credentials, certificates or backups belong in the release package.

**Not yet validated:** a Windows service installation under elevation on a clean machine, reboot recovery, a second LAN computer, actual Tesseract/Vietnamese OCR installation, Docker runtime deployment, a live external model, production load, or a held-out expert legal benchmark. GitHub write access returned HTTP 403 (Resource not accessible by integration); no remote branch or pull request has been created and CI has not run remotely. Do not describe these checks as passed merely because their code exists.

## Read next

1. [Windows quickstart](WINDOWS-QUICKSTART.md): normal-user instructions, certificate trust, accounts, OCR, backups and service operations.
2. [Maintainer guide](MAINTAINER-GUIDE.md): module map, data layout, security boundaries, routes, concurrency, backup format and legacy migration.
3. [Architecture decision](../04-decisions/adr-usable-lan-release.md): reasons for the current scope and design.
4. [Third-party notices](../packaging/THIRD-PARTY-NOTICES.md): unsigned build and outstanding product/dependency licensing decisions.

## First work in the next session

1. Inspect the local branch and any new main changes. GitHub write access previously returned HTTP 403; there is no published draft PR or remote CI result. Once access is restored, publish this branch, create the PR and inspect its CI results. Preserve the release checkpoint; do not start a second implementation from the old prototype.
2. On a designated clean Windows test machine, extract the full bundle, verify its checksum and runtime, create the administrator, trust the certificate, and test from a second LAN browser.
3. Exercise service install, start, stop, reboot, upgrade and removal. Confirm Local Service identity, Program Files/data ACLs, Private-profile local-subnet firewall scope and preservation of documents. These actions need Windows administrator access on that test host.
4. Follow the OCR/LAN guide to test the actual remote Ollama host and vision model, and/or install Tesseract with Vietnamese/English data. Test real mixed PDFs, rotations, empty pages and low-quality scans. Review extracted quotations against originals.
5. Restore an encrypted backup to a separate folder/host and verify accounts, source versions, permissions, history, provider settings and revoked old sessions. Never overwrite the only good library.
6. Run Docker behind trusted HTTPS; validate proxy behavior, request limits, storage persistence, restart and backups. Decide whether public customers get separate installations or a new tested organization-isolation design.
7. Build the expert-reviewed legal benchmark before claiming answer accuracy. Test dates, exceptions, conflicting sources, missing evidence and document-borne prompt injection. Mock AI tests are not live-provider evidence.
8. Finish customer release decisions: product/dependency licensing, code signing, trusted domain, privacy/retention policy, support ownership, monitoring, alerts and capacity targets.

## Deliberate limits and pending decisions

- **Permanent document deletion is not implemented.** Archiving/restoration works. Automatic approval review rejected the proposed irreversible purge capability because it was not specifically authorized. A separate user question about protected permanent deletion remains pending. Do not interpret subsequent continuation or documentation requests as that approval. If explicitly approved, retain a minimal deletion audit record and explain that backups retain separate copies.
- Existing prototype owner strings are not automatically mapped to verified accounts. Design a reviewed host-admin migration with a backup and rollback; reusing an old username must not grant ownership.
- Password recovery and invitations are delivered manually by an administrator. There is no email verification/delivery. Version 0.2.1 adds host-only recovery for an existing active administrator. Keep two trusted administrators.
- Windows output is an unsigned onedir bundle, not a signed installer. Keep `_internal` with the executable. Tesseract is optional and external in this Windows build.
- The live library uses host filesystem protection; backup encryption does not encrypt an unlocked database. Host administrators remain trusted.
- Search/date metadata is not a comprehensive legal-validity or amendment engine. Saved answers are evidence records, not verified legal opinions.

## Reproduce the checks

Use the source setup in the repository README, then:

```sh
python -m pip install -r requirements-test.lock
python -m pytest --tb=short
python -m pytest tests/test_api.py tests/test_user_journeys.py --tb=short
# Windows packaging:
python -m pip install -r packaging/requirements-build.lock
python -m PyInstaller --noconfirm packaging/LegalLibrary.spec
python packaging/collect_licenses.py dist/LegalLibrary
dist/LegalLibrary/LegalLibrary.exe --self-check --data-dir ./build-check
```

On the original Codex workstation only, redirected Windows paths required relative `TCL_LIBRARY` and `TK_LIBRARY` paths to the bundled Python Tcl directories while building. A missing `msvcp140.dll` in the workstation's PyMuPDF environment was supplied from the installed runtime; the spec includes it when present. Treat these as build-environment notes, not steps every end user should perform. The frozen self-check catches missing Tk/PDF dependencies.

Keep test data in a separate working folder. If a test host has alternating sandbox owners, use a fresh pytest `--basetemp` and disable its cache rather than reusing inaccessible temporary directories. The CI runners normally do not have that workstation-specific issue.

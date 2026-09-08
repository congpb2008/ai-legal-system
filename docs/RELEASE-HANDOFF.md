# Release handoff — 0.2.0 LAN pilot

Updated 2026-09-08. This is the continuation record for the usable-product implementation, not a declaration that public customer launch is complete.

## Where work stands

Repository: `congpb2008/ai-legal-system`. Working branch: `codex/usable-lan-release`. The implementation starts from main commit `075d688d54203204c4227b30ecd60fbf82b1fdf1`.

The original requested destination was external hosted customers. This increment provides a usable, single-organization LAN pilot and source/Docker deployment paths. It does not isolate unrelated customer organizations in a shared service. The owner also requested a Windows executable, accounts, normal-user workflows and careful documentation, with a clean checkpoint before the account quota becomes low.

## Implemented

- Restored the missing SQLite storage package and fixed the ignore rule that excluded it from clean checkouts.
- Replaced arbitrary-username authentication with persistent accounts, host-code bootstrap, approval/invitations, password recovery, revocable sessions and administration.
- Added the complete browser workflow: onboarding, collections and sharing, batch/folder uploads, processing progress and retry, document metadata and versions, search, source inspection, private saved answers, account settings and help.
- Enforced permissions on documents, original downloads, source versions, answers and saved history. Added bounded HTTP serving, request/upload limits, same-origin protections and rate limits.
- Made local mode usable without a model. Optional AI can select verified source quotations; unsupported output falls back visibly. Removed misleading legal-confidence percentages.
- Preserved immutable source versions and neighboring source context. New search respects active versions and recorded effective dates. Scans fail visibly when OCR cannot process them.
- Added a Windows launcher, HTTPS certificate controls, optional Local Service installation, a scoped LAN firewall action and encrypted backup/restore.
- Added reproducible Windows packaging, CI, user instructions, architecture and operational documentation. Existing English/Vietnamese prototype guides are marked historical; their detailed content has not all been translated or rewritten.

## Validation at this checkpoint

The complete local regression suite passed **713 tests** on Windows/Python 3.12. The final date-field adjustment was followed by **80 passing API and user-journey tests**. New HTTP journeys cover real account lifecycle, document ingestion, answers and source downloads, source-version preservation, access revocation, request protections and authenticated encrypted backup recovery.

A packaged Windows candidate passed its Tk/PDF runtime self-check and an actual HTTPS journey: bootstrap, login, secure cookies, collection creation, DOCX upload, processing to Ready, question, citation and original-source retrieval. The Python client verified the generated certificate and localhost hostname. Browser checks covered account entry, uploads, questions, saved answers and desktop/mobile rendering with no JavaScript errors. Browser automation accepted the test certificate only in its isolated test context; this does not replace certificate trust setup on user machines.

The final **0.2.0 executable** repeated the desktop/PDF self-check and certificate-verified HTTPS smoke test successfully. A stop/restart check confirmed that the account, certificate and saved answer persisted. The built Python wheel also contains the previously missing storage package, frontend and design assets. Checksums and source revision accompany the downloadable checkpoint. No synthetic test database, setup codes, test credentials, certificates or backups belong in the release package.

**Not yet validated:** a Windows service installation under elevation on a clean machine, reboot recovery, a second LAN computer, actual Tesseract/Vietnamese OCR installation, Docker runtime deployment, a live external model, production load, or a held-out expert legal benchmark. The CI workflow is added; its remote result must be checked on the pull request. Do not describe these checks as passed merely because their code exists.

## Read next

1. [Windows quickstart](WINDOWS-QUICKSTART.md): normal-user instructions, certificate trust, accounts, OCR, backups and service operations.
2. [Maintainer guide](MAINTAINER-GUIDE.md): module map, data layout, security boundaries, routes, concurrency, backup format and legacy migration.
3. [Architecture decision](../04-decisions/adr-usable-lan-release.md): reasons for the current scope and design.
4. [Third-party notices](../packaging/THIRD-PARTY-NOTICES.md): unsigned build and outstanding product/dependency licensing decisions.

## First work in the next session

1. Inspect this branch and the draft PR, including CI failures and any new main changes. Preserve the release checkpoint; do not start a second implementation from the old prototype.
2. On a designated clean Windows test machine, extract the full bundle, verify its checksum and runtime, create the administrator, trust the certificate, and test from a second LAN browser.
3. Exercise service install, start, stop, reboot, upgrade and removal. Confirm Local Service identity, Program Files/data ACLs, Private-profile local-subnet firewall scope and preservation of documents. These actions need Windows administrator access on that test host.
4. Install Tesseract with Vietnamese/English data and test real mixed PDFs, rotations, empty pages and low-quality scans. Review extracted quotations against originals.
5. Restore an encrypted backup to a separate folder/host and verify accounts, source versions, permissions, history, provider settings and revoked old sessions. Never overwrite the only good library.
6. Run Docker behind trusted HTTPS; validate proxy behavior, request limits, storage persistence, restart and backups. Decide whether public customers get separate installations or a new tested organization-isolation design.
7. Build the expert-reviewed legal benchmark before claiming answer accuracy. Test dates, exceptions, conflicting sources, missing evidence and document-borne prompt injection. Mock AI tests are not live-provider evidence.
8. Finish customer release decisions: product/dependency licensing, code signing, trusted domain, privacy/retention policy, support ownership, monitoring, alerts and capacity targets.

## Deliberate limits and pending decisions

- **Permanent document deletion is not implemented.** Archiving/restoration works. Automatic approval review rejected the proposed irreversible purge capability because it was not specifically authorized. A separate user question about protected permanent deletion remains pending. Do not interpret subsequent continuation or documentation requests as that approval. If explicitly approved, retain a minimal deletion audit record and explain that backups retain separate copies.
- Existing prototype owner strings are not automatically mapped to verified accounts. Design a reviewed host-admin migration with a backup and rollback; reusing an old username must not grant ownership.
- Password recovery and invitations are delivered manually by an administrator. There is no email verification/delivery or sole-administrator recovery UI. Keep two trusted administrators.
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

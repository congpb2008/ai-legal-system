# Legal Library

A shared document library for one organization: upload Vietnamese policies and legal documents, search them, ask for supporting source passages, and keep references you can inspect.

This release makes the existing backend usable as a LAN application. It includes a Windows control panel and executable packaging, real accounts, collection sharing, document processing, saved research, and encrypted backups. Local mode works without an AI subscription or model server.

Vietnamese is the default interface language from 0.2.4. Choose **English** in **Ngôn ngữ / Language** to switch. [Hướng dẫn nhanh bằng tiếng Việt](docs/HUONG-DAN-TIENG-VIET.md).

## Start on Windows

Download the Windows x64 package from the **Verify and package** workflow artifact, extract the whole ZIP, and open **LegalLibrary.exe**. Keep its `_internal` folder beside it. Choose **Start server**, trust the installation's HTTPS certificate, then choose **Open library**. Create the first administrator using the setup code displayed on the host.

The default LAN port is **8443** with HTTPS. Colleagues only need a browser. **Install as service…** lets a Windows administrator run the library automatically after restart under the limited Local Service account.

Maintainers: see the [maintainer guide](docs/MAINTAINER-GUIDE.md) and [release handoff](docs/RELEASE-HANDOFF.md).

See **[Windows quickstart](docs/WINDOWS-QUICKSTART.md)** for accounts, firewall access, certificate setup, OCR, backups and recovery. This is an unsigned pilot build; signing and customer distribution licensing remain owner release decisions.

## What people can do

- Create an account with an invitation or request administrator approval; sign in and manage their profile, password and sessions.
- Create collections and share them with viewers, contributors or managers.
- Upload PDF/DOCX files individually, in a batch or from a selected folder; see progress, failures and retry controls.
- Find documents across the whole library by title or number, collection and processing/archive status; browse complete paginated results. Vietnamese title filters work with or without accents.
- Search a collection or document and filter by recorded effective dates.
- Ask questions and inspect quotations, source text and original files from the cited version.
- Save research privately, copy or download answers with references, and record feedback.
- Edit document metadata, upload a new version, archive and restore documents.
- Administer accounts and optionally enable an approved AI provider, including Ollama on another LAN computer.
- Read scanned PDFs with local Tesseract, an independently configured vision model, or an explicit vision fallback. See the [OCR and LAN Ollama guide](docs/OCR-AND-OLLAMA.md).
- Start and stop a Windows server, manage its service, export its HTTPS certificate, and back up or restore the library.

There are no default accounts or passwords. The first administrator needs a random setup code available only on the host. New signups need approval unless they use a one-time invitation. Password recovery is administered with one-time codes; email delivery is not required.

## Answer behavior

The live answer path renders contiguous quotations from extracted source text. Optional AI selects relevant quotations; invented quotes and unknown evidence IDs are rejected. Unverifiable provider responses or provider outages produce a marked source-search fallback. Retrieval relevance is not shown as a legal-correctness percentage.

Quotations establish what the uploaded source says, subject to extraction quality. They do not certify current law, completeness, applicability or the absence of exceptions elsewhere. Dates come from document metadata, undated documents are marked, and superseded file versions are excluded from new searches. Historical citations still open their original files. Word extraction does not preserve printed page layout. PDF scans require OCR and original-file review.

## Run from source

Requires Python 3.12 or later. From the repository:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m legal_platform --host 127.0.0.1 --port 8080
```

Open `http://localhost:8080`. The data folder defaults to `%LOCALAPPDATA%/LegalPlatform/data` on Windows and `~/.local/share/legal-platform` elsewhere. Set `LEGAL_PLATFORM_DATA_DIR` to use a different local folder. The initial administrator code is in that folder's `setup-code.txt`. Never put the SQLite database on a network share.

On Windows, `python -m legal_platform.desktop` starts the control panel. The source command serves HTTP; configure `LEGAL_PLATFORM_TLS_CERT` and `LEGAL_PLATFORM_TLS_KEY`, or use a trusted HTTPS reverse proxy, before exposing private data on a network.

## Docker

For a domain with automatic HTTPS, use the separate [hosted deployment recipe](docs/HOSTED-DEPLOYMENT.md) and `docker-compose.hosted.yml`. The basic Compose file below is for local access.

```sh
docker compose up --build -d
docker compose exec legal-platform cat /app/storage/setup-code.txt
```

Compose binds to the host loopback address by default. Place it behind a trusted HTTPS reverse proxy for hosted access. Keep the data volume; it contains the database, immutable sources and provider configuration. There is no preconfigured external model destination. Configure an approved provider in the application after signing in as administrator.

The Docker image installs Tesseract and Vietnamese language data. The Windows package finds an optional system Tesseract installation; see the quickstart.

## Runtime and protection

The server uses a bounded Cheroot worker pool, request-size limits, per-address and per-account request throttles, same-origin browser requests and HttpOnly sessions. Passwords use salted scrypt hashes; server-side sessions and one-time codes are revocable. Collection permissions are checked for documents, source downloads, search, questions and saved answers. Provider configuration is administrator-only; changing a destination never silently reuses its previous credential.

This is **one organization per installation**, with private/shared collections inside that organization. It is not a complete multi-tenant commercial SaaS platform. Host operators can access their installation's files and backups. HTTPS certificates, account approval, document permissions, storage capacity and backup operations remain the operator's responsibility.

Default limits: 25 MB/file, 50 files/browser batch, 2 GB of uploaded originals, 4,000 characters/question, 15 questions/user/minute, 12-hour sessions. The document-storage limit can be changed using `LEGAL_PLATFORM_STORAGE_LIMIT_MB`. PDFs are limited to 500 OCR pages and bounded rendering dimensions. Documents interrupted by a restart are marked for retry instead of remaining stuck forever.

## Tests and Windows build

```sh
python -m pip install -r requirements-test.lock
python -m pytest --tb=short
# On Windows:
python -m pip install -r packaging/requirements-build.lock
python -m PyInstaller --noconfirm packaging/LegalLibrary.spec
dist/LegalLibrary/LegalLibrary.exe --self-check --data-dir ./build-check
```

The workflow tests clean checkouts on Windows and Linux and builds a Windows artifact. New HTTP journeys cover bootstrap protection, signup approval, password recovery, session invalidation, upload-to-answer processing, source versions, collection access revocation, request protections, and encrypted backup/restore. These are engineering tests, not a measured legal-accuracy benchmark.

## Before customer launch

Use this build for an organization pilot while completing:

- A reviewed, held-out Vietnamese legal benchmark with answerable and unanswerable cases, expected documents, exceptions, dates, OCR failures and prompt-injected documents. Parser evaluation without ground truth now reports not evaluated instead of passing.
- A clean-machine Windows service installation/reboot test, a restore exercise on the intended host, and code signing for distributed installers.
- Trusted HTTPS/domain setup, monitoring and alerting, operating/support ownership, a privacy/retention policy, and a review of third-party data-processing destinations.
- The repository owner's product-license decision and dependency-license review. PyMuPDF/MuPDF uses AGPL/commercial licensing; see [third-party notices](packaging/THIRD-PARTY-NOTICES.md). This change does not assign a license on the owner's behalf.

Authentication and storage changes do not automatically claim documents from the earlier username-only prototype. Back up any existing installation first; a host administrator must explicitly map legacy collection owners to verified accounts during migration. Do not treat an old owner string as proof of identity.

# Decision: usable single-organization LAN release

Status: implemented for the 0.2.0 pilot.

The prototype described an enterprise legal platform but did not provide a complete first-user journey or enforce real identity. This release prioritizes an inspectable workflow for one organization's documents and a Windows host that non-developers can start.

## Decisions

1. **One organization per installation.** Collections enforce document sharing. Do not claim multi-tenant SaaS isolation or subscription management from this architecture.
2. **Real persistent accounts.** Salted password hashes, stable UUIDs, expiring sessions, administrator approval/invitations and one-time recovery replace the arbitrary-username authentication stub. First administrator creation requires a random host-local code. Legacy owner strings are not automatically claimed by matching new usernames.
3. **Source quotations in the live answer path.** Retrieved evidence is mapped to contiguous text from the exact version's extraction. Optional AI selects evidence IDs and exact quotations in JSON. Verification and rendering happen on the server. Parser-added chunk headings and unsupported generated prose are not presented as source quotations. The app exposes uncertainty about relevance, extraction quality and legal applicability.
4. **Local mode by default.** No provider account or preconfigured remote endpoint is required. Local keyword search works immediately. Optional AI processing requires administrator configuration and destination approval. A destination change never silently reuses its prior key.
5. **Version-specific source references.** New versions become active for processing/search; historical citations retain immutable original-file references. A compatibility active-source table is kept, with a composite document/version table for history.
6. **Page-aware OCR.** Low-text pages in mixed PDFs must be read or reported as failures. Scans cannot be silently skipped. DOCX is extracted as logical text, with an explicit printed-layout limitation.
7. **Bounded WSGI service.** Cheroot and a shared WSGI boundary replace the development HTTP server for production entrypoints. Requests, rate limits, CSRF protection and authentication are handled before route dispatch. SQLite handles are per-thread, with WAL and explicit single-process data ownership.
8. **Windows host controls.** A PyInstaller onedir executable contains the application and desktop runtime. Service and private-LAN firewall changes are explicit elevated actions. Service code is installed under Program Files; data under ProgramData; the service uses Local Service.
9. **Recoverable operations.** Immutable source versions, visible retries, interrupted-job recovery, encrypted database/source backups and restore-to-empty behavior provide a practical recovery path. Archiving retains originals. Permanent document deletion is not part of this release unless separately approved and implemented.
10. **Honest verification.** Engineering regression tests cover user journeys and controls. Evaluation without expected assertions or parser ground truth no longer gets an automatic pass. Customer-facing accuracy claims require separate expert validation.

## Consequences

These decisions supersede earlier descriptions of stub authentication, first-run unauthenticated provider configuration, generated legal answers, confidence-as-correctness and the development HTTP server. Existing domain contracts remain where compatible; the live browser answer response intentionally hides the retrieval-derived confidence percentage and adds date/scope/source-mode information.

Moving to public multi-tenant hosting requires an explicit organization identity boundary, external operational controls, and commercial/privacy/license decisions. A pilot executable does not resolve those requirements. See `docs/MAINTAINER-GUIDE.md` for the implementation map and `docs/RELEASE-HANDOFF.md` for remaining validation.

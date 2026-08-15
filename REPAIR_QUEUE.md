# Repair Queue

Statuses: `SUSPECTED`, `CONFIRMED`, `IN_PROGRESS`, `FIXED`, `VERIFIED`, `DEFERRED`.

## P0

### TRACE-001 — Broken Document/Version ownership chain

- **Status:** VERIFIED
- **Symptom:** Evidence/citation `document_id` does not resolve; document-scoped artifact queries return zero.
- **Reproduction:** Upload/process a real DOCX, search, then GET `/documents/{evidence.document_id}` → 404.
- **Evidence:** `StructureAwareChunker` writes `tree.document_version_id` into both chunk `document_id` and `version_id`; all 447 live rows reproduce it.
- **Root cause:** Knowledge Tree only carries version identity and chunking was never given the logical document ID.
- **Invariant:** Retrieval traceability and Chunk → exactly one Document Version while retaining logical Document ownership.
- **Dependencies:** none; blocks reprocessing, delete/archive cleanup, citations, source navigation.
- **Subsystem:** chunking → embedding → index → retrieval → citation.
- **Repair:** `StructureAwareChunker` and `ChunkingService` now require the authoritative logical document ID while preserving the tree's version ID. New collections, embeddings, and index entries keep both identities distinct. Legacy derived rows will be rebuilt under `STATE-001`/`PROCESS-001`; canonical trees remain untouched.
- **Verification:** 84 focused chunk/embedding/index/retrieval tests pass. An isolated real DOCX reached READY with 16 chunks/vectors carrying the logical document ID; all five search evidence IDs resolved through `GET /v1/documents/{id}`; document and search survived restart.

### EMB-001 — Fake semantic embeddings

- **Status:** VERIFIED
- **Symptom:** semantic/hybrid scores are hash similarity, not meaning.
- **Reproduction:** inspect stored models and `PlaceholderEmbedder`; all live vectors are `placeholder/384`.
- **Evidence:** small real-corpus benchmark gives both live embedding models 6/6 R@1; BGE-M3 has the better legal-text context contract.
- **Root cause:** Task 007 placeholder remained the runtime default and setup config covers generation only.
- **Invariant:** embeddings are real, versioned, reproducible, and query/document engines match.
- **Dependencies:** TRACE-001.
- **Subsystem:** embedding/index/retrieval/config.
- **Repair:** the runtime now uses native Ollama `/api/embed`, verifies the live catalog and exact model digest, refuses truncation/dimension mismatch, stores model/digest/dimension, and filters semantic search by the same model contract. BGE-M3 is the default; Nomic is selectable through configuration. Placeholder vectors require explicit test injection only. Backend failures return a retryable 503 rather than a silent keyword downgrade.
- **Verification:** the live server returned BGE-M3 digest `790764642607…`, 1024 dimensions, and two vectors in 4.725 s. An isolated real DOCX reached READY with 16 BGE embeddings/index rows, HYBRID search returned five resolvable evidence items, and persisted metadata matched exactly. Legacy placeholder rows remain queued for a controlled rebuild under `STATE-001`/`PROCESS-001`.

### STATE-001 — READY does not guarantee required artifacts

- **Status:** VERIFIED
- **Symptom:** live READY documents have no searchable derived artifacts; parser/restore can set READY independently.
- **Reproduction:** read-only DB invariant query; four READY documents lack chunks/embeddings/index entries.
- **Evidence:** parser defaults `mark_ready=True`; restore unconditionally saves READY; old data predates the coordinator.
- **Root cause:** multiple owners of processing state and no readiness validator.
- **Invariant:** only the coordinator may mark READY after meaningful tree, chunks, complete embeddings, and active index entries exist.
- **Dependencies:** TRACE-001, EMB-001.
- **Subsystem:** registry/parser/pipeline/health.
- **Repair:** parser no longer marks READY by default. The runtime installs an artifact-backed validator covering source, OCR, latest tree/chunks, exact active model embeddings, and index coverage before READY or restore. Configured startup reconciliation changes invalid legacy READY rows to recoverable FAILED without touching source/canonical data.
- **Verification:** regressions prove a complete pipeline reaches READY and deletion of one persisted index row makes READY validation/process fail; reconciliation then records FAILED. Real BGE processing passed the full validator.

### AUTH-001 — Public API bypasses vault authorization

- **Status:** VERIFIED
- **Symptom:** any logged-in username can list/read/search/ask across all vaults.
- **Reproduction:** create personal vault/document as user A; log in as user B; list/search without vault filter.
- **Evidence:** router discards resolved user ID for read/query/admin handlers; handlers never call `check_permission`.
- **Root cause:** VaultService exists but was wired only into upload validation.
- **Invariant:** authorization precedes document access and retrieval; personal/department isolation.
- **Dependencies:** TRACE-001 for correct artifact ownership.
- **Subsystem:** auth/API/vault/retrieval/generation.
- **Repair:** the resolved user now flows through vault, document, upload, search, Ask, processing, and admin handlers. Vault membership is parsed exactly rather than matched with SQL substrings; document registration rechecks upload permission; retrieval/reranking/generation/index operations accept an explicit authorized-vault scope.
- **Verification:** the two-user regression and a fresh threaded HTTP server proved that an outsider sees zero documents and receives 403 for get, status, create, scoped keyword search, and delete in a personal vault, while the owner can read/search/archive. After the final restart, `admin` correctly saw no private `demo` vault and the `demo` owner saw all six curated documents. The final complete isolated suite passes 708 tests. MVP authentication still accepts any non-empty username/password and is documented as a deployment limitation; authorization boundaries are now enforced for the presented identity.

## P1

### UPLOAD-001 — Temp/invalid DOCX accepted

- **Status:** VERIFIED
- **Reproduction:** upload real `~$` file → HTTP 201 then FAILED.
- **Repair:** service rejects `~$` Office lock names before storage/registration and validates the ZIP, main Word XML, extractable text, corruption, and expansion bound. Folder UI skips lock files and reports the skipped count.
- **Verification:** two real DOCX files uploaded through multipart HTTP with their selected vault and returned 201/document IDs; the real adjacent `~$` file returned 400 with a clear lock-file message, persisted document total remained two, and no `'vault_id'` exception appeared. Unit regressions also prove malformed DOCX is rejected without a registry row.

### PROCESS-001 — Reprocessing controls are fake or destructive

- **Status:** VERIFIED
- **Reproduction:** call reembed/reparse → success with no DB change; document reindex → index rows removed.
- **Repair:** one audited coordinator now implements exact `reocr`, `reparse`, `reembed`, and `reindex` semantics. Prior embeddings become STALE before downstream rebuild; the active index is replaced; preserved immutable/history artifacts remain inspectable. API/admin controls report real completed/failure counts and include Re-OCR.
- **Verification:** unit regression and live HTTP/BGE run agree: initial 1 OCR/1 tree/1 chunk collection/16 active vectors; re-index changed no upstream counts; re-embed produced 16 new active vectors without OCR/tree/chunk work; re-parse added only a tree/chunk/downstream chain; re-OCR added OCR and all downstream artifacts. Every call returned one completed document, final state READY, search returned evidence.

### GEN-001 — Configured generation provider is bypassed

- **Status:** VERIFIED
- **Reproduction:** save/test provider, ask with evidence; metadata/model remains template and no provider call occurs.
- **Repair:** generation now resolves persisted setup configuration at request time, reloads a changed configuration, preserves explicit injected providers, and uses template output only when setup is genuinely incomplete. Empty provider responses and provider failures raise dependency errors; the Answer API returns a retryable 503 and exposes non-secret generation metadata.
- **Verification:** targeted generation/API/security tests pass. Live browser requests through the saved OpenAI-compatible configuration reached `qwen3.6:35b-a3b`, answered the source-grounded 01/07/2025 fact directly and by semantic paraphrase, reported that exact model (not `template`), and produced verified citations. The persisted `reasoning_effort: none` setting prevents hidden reasoning from consuming the visible-response budget.

### CIT-001 / SOURCE-001 — Citation and source inspection incomplete

- **Status:** VERIFIED
- **Reproduction:** Ask returns UUID-only citation; no route/control opens source; page anchor absent.
- **Repair:** citations now retain evidence identity and structured source anchors, are verified against the exact Knowledge Tree node/version/document, and are withheld if traceability fails. The authorized source endpoint returns canonical node/page text and optional original bytes without exposing physical paths. The UI opens source text and downloads the original.
- **Verification:** focused API tests prove outsider 403, canonical node/page resolution, and byte-identical original bytes. Browser acceptance opened the cited page supporting the 01/07/2025 answer and completed the original-download control.

### DELETE-001 — Normal UI physically deletes documents

- **Status:** VERIFIED
- **Reproduction:** click Xóa/DELETE endpoint; registry hard-deletes.
- **Repair:** normal DELETE now requires the vault DELETE permission, archives the registry record, and marks its index rows ARCHIVED. Physical purge is not exposed by the routine API/UI.
- **Verification:** fresh two-user HTTP proof returned 403 to an outsider, 200 to the owner, retained the database row with `ARCHIVED`, returned that truthful status afterward, and default retrieval filters it from active evidence.

### JOB-001 — Non-durable poller and stranded states

- **Status:** VERIFIED
- **Reproduction:** inspect worker; only `UPLOADED` rows are polled, no job/attempt lease or retry.
- **Repair:** uploads now create a durable SQLite pipeline job and return its ID; pending work is atomically claimed once; start/completion/failure/duration survive restart and are exposed through authorized job/status APIs. A restart changes abandoned RUNNING records to explicit FAILED records with a reprocessing instruction. Manual full/re-OCR/re-parse/re-embed/re-index operations also produce durable job history. The worker has a real stop lifecycle and no longer prints raw tracebacks.
- **Verification:** concurrent `ensure_pending_job` calls returned one ID and one claim; restart recovery converted a RUNNING job to FAILED with actionable recovery text; upload/admin regression sets pass. Exact stage reprocessing was already independently verified under PROCESS-001.

### STORAGE-001 — Hard-coded storage paths / unsafe test wiring

- **Status:** VERIFIED
- **Reproduction:** instantiate default `UploadService`; it writes to the real absolute project storage root.
- **Repair:** the runtime's configured data root remains authoritative and is injected into upload/pipeline services. Standalone services now default to isolated temporary storage, and legacy handler recovery reuses the injected upload backend instead of an absolute machine path.
- **Verification:** no backend/test reference to the old absolute project path remains. All 663 tests pass with `LEGAL_PLATFORM_DATA_DIR` set to a fresh temporary root; the root was moved to trash afterward and existing `storage/` was untouched.

### OCR-001 — Scanned OCR dependency unavailable

- **Status:** DEFERRED
- **Reproduction:** `tesseract` absent; scanned path raises a dependency error.
- **Repair:** install/document Tesseract + Vietnamese data or provide a supported configured OCR provider; verify on a real scanned PDF; keep clear failure/manual-review state.
- **Verification:** a real image-only PDF remained truthfully FAILED with `OCR extraction failed`; it was then archived through the UI without deleting its byte-identical source. Digital PDFs and DOCX files are fully supported. This is an environment/deployment limitation, not a false-success path.

### RETR-001 — Hybrid/reranker fabricated evidence confidence

- **Status:** VERIFIED
- **Reproduction:** Ask an unrelated World Cup 2030 question; common Vietnamese terms promoted legal chunks, returned SUCCESS/68%, and attached irrelevant citations.
- **Root cause:** keyword matching used substring/common terms on an incomparable score scale, the reranker rewarded *lack* of query overlap, and it discarded all but one provision per document.
- **Repair:** exact Unicode token matching with stopwords, comparable hybrid fusion, HYBRID retrieval for natural-language Ask, query-aware evidence filtering, separate content/title lexical scoring, validated document-identifier boosts, and exact-source rather than document-level deduplication.
- **Verification:** the unsupported browser query now returns `NO_EVIDENCE`, LOW 0%, no citations, and no generation call. A semantic paraphrase ranks the direct Điều 9/Khoản 1 source first and answers 01/07/2025 with HIGH confidence.

### CONCURRENCY-001 — Shared SQLite transaction ownership

- **Status:** VERIFIED
- **Reproduction:** two simultaneous processing claims formerly performed a read-then-write transition with no atomic predicate; HTTP requests and the worker shared one connection/transaction context; the in-memory vector map was iterated while mutable.
- **Repair:** the persistent runtime now owns one SQLite connection per thread behind a connection-compatible proxy, with WAL, foreign keys, and a 5-second busy timeout. State transitions use compare-and-set, full processing/reprocessing is locked per document, and vector-index mutation/search snapshots are synchronized.
- **Verification:** simultaneous state claims produce exactly one winner; duplicate full-pipeline calls yield one real process and one idempotent READY result; a real threaded HTTP stress run completed 90 concurrent operations (60 writes, 30 reads) with zero errors and persisted all 60 vaults in WAL mode.

## P2

### HEALTH-001 — Constant health/readiness

- **Status:** VERIFIED
- **Repair:** probes now check live DB queries, storage root, persisted index snapshot, worker liveness, embedding configuration, and generation configuration. Readiness returns 503 on an unhealthy required component. Conventional root probe paths and `/api` aliases are both supported.
- **Verification:** final demo runtime reports healthy DB/storage, 1,470 index entries, live worker, BGE-M3, and configured generation.

### DOCS-001 — Stale operational documentation

- **Status:** VERIFIED
- **Repair:** README and Vietnamese quick-start/config guides describe persistent storage, automatic processing, real embeddings/generation, setup, exact limitations, source citations, and the isolated regression gate.

### UI-001 — Misleading/dead controls and responsive workflow

- **Status:** VERIFIED
- **Repair:** hidden overlays no longer block the app; folder upload is reachable and reports lock-file skips; duplicate initialization is removed; processing state/error replaces lifecycle-only status; archive language is truthful; per-document reprocessing is explicit; jobs expose outcomes; citation source controls work; horizontally scrollable tables have accessible regions/mobile hints.
- **Verification:** browser workflow covered setup/auth, vault, single and folder upload, jobs/status, search, Ask, citations/source, re-index, archive, restart, and 390/820/1440px viewports with no console errors or body overflow.

### META-001 — Required labels/notes absent from the public document workflow

- **Status:** VERIFIED
- **Symptom:** `Metadata.tags` existed in the contract and registry but upload, document serialization, Search/Ask context, and the Web UI omitted it; old demo records had no labels and two templates had no notes.
- **Reproduction:** upload a document through the normal UI, then inspect list/detail/search/citation views; no tag control or serialized tag value exists.
- **Root cause:** metadata responsibility stopped at the registry boundary and was never wired through the public product contract.
- **Invariant:** CAP-003 document metadata includes tags; a normal user must be able to curate and later identify the corpus without a parallel tagging store.
- **Repair:** normalized tag validation now flows through create/upload/PATCH and API serialization; single and per-file batch upload require tags; details allow metadata edits; library/search/citations show tags; the library can filter by tag. Notes and original filename provenance are visible.
- **Verification:** the six real documents were uploaded through the UI with source-supported titles, mandatory labels, and notes. UI detail/source checks passed for every document; `Hàng hóa` selected only Mẫu 4A and `Đấu thầu qua mạng` selected the four applicable documents. API regressions cover persistence, mutation, validation, and provenance.

## Verification gates

Every item requires: deterministic reproduction → minimal repair → targeted regression → DB/storage invariant query → API/UI original reproduction → independent review. Major checkpoints additionally require full safe suite, several real documents, browser E2E, and restart persistence.

## Demo-readiness addendum — 2026-08-15

### RUNTIME-002 — Ollama reasoning output is empty or times out

- **Status:** VERIFIED
- **Symptom:** qwen3.6 can spend the response budget on hidden reasoning and return empty visible content.
- **Reproduction:** the same live prompt returned no content with default reasoning and a correct visible answer with `reasoning_effort: none`.
- **Root cause:** the coherent OpenAI-compatible provider abstraction did not expose the server's optional reasoning-control field.
- **Invariant:** a successfully configured generation role must produce observable answer content or an explicit dependency failure.
- **Repair:** added validated API/config/UI persistence and request forwarding for optional `reasoning_effort`; demo configuration uses `none`.
- **Verification:** live provider probe and 14-question Web UI Ask suite produced visible output; both insufficient-evidence questions normalized correctly.

### RETR-002 — Hybrid evidence attribution and identifier ranking

- **Status:** VERIFIED
- **Symptom:** natural Vietnamese/template queries could rank chunks from the wrong document; a 4A/5A comparison returned `NO_EVIDENCE` even though both documents were READY.
- **Reproduction:** ask `Mẫu 4A và Mẫu 5A khác nhau ở phạm vi áp dụng như thế nào?` through the UI. Before repair, 5A and 4A scored just below the answer floor.
- **Root cause:** Ask had previously been semantic-only; title and content matches were unioned; incidental numbers could look like identifiers; and the later identifier boost required *all* query identifiers to appear in one title, impossible for a two-document comparison. The moderate evidence gate then rejected each individually named source on generic term coverage.
- **Invariant:** query handling must retrieve evidence before generation, preserve document identity, and rank the supporting source ahead of decorative metadata matches.
- **Repair:** Ask uses HYBRID; title/content scores are separated; Vietnamese expansions and a wider semantic pool improve recall; identifier parsing ignores incidental single digits. Multi-document boosts are now proportional to the named identifiers present in each title, and score-eligible evidence matching any explicitly named document code survives the generic-overlap gate.
- **Verification:** the restarted UI answered the 4A/5A comparison from both real documents at MEDIUM 73%; its 5A citation/source/original opened. The full tagged-corpus matrix produced 12 PASS and 2 NO_EVIDENCE_CORRECT. Dedicated retrieval and generation regressions preserve the unrelated-generic-evidence rejection.

### GEN-002 — Model-declared no-evidence shown as SUCCESS

- **Status:** VERIFIED
- **Symptom:** the provider could state that the corpus lacked the requested rule while the API/UI still displayed SUCCESS and unrelated citations.
- **Reproduction:** ask for a cyberattack penalty absent from the procurement corpus.
- **Root cause:** post-generation status trusted pre-generation retrieval presence without interpreting the provider's explicit lack-of-evidence conclusion.
- **Invariant:** unsupported legal answers must not acquire confidence or citations merely because semantically adjacent chunks exist.
- **Repair:** explicit early no-evidence conclusions from the real provider normalize to `NO_EVIDENCE`, LOW, zero confidence, and no citations.
- **Verification:** both out-of-corpus questions returned honest no-evidence UI states after the final restart.

### SETUP-002 — First-run configuration and routing can strand the UI

- **Status:** VERIFIED
- **Symptom:** saved-but-incomplete setup state could bypass setup, fail to refresh embeddings, or ignore the first hash-navigation event.
- **Root cause:** setup completion was inferred from provider data, config recovery and embedding runtime ownership diverged, and the route listener was registered after an early return.
- **Invariant:** setup completion is explicit, secrets are write-only, and a successful setup immediately activates the configured runtime.
- **Repair:** added a setup-complete sentinel, safe config recovery, immediate embedding-engine refresh, and early hash-listener registration.
- **Verification:** clean first-run browser setup, refresh, login, ingestion, and restart all passed with persisted non-secret settings.

### UPLOAD-002 — Folder upload loses filename provenance

- **Status:** VERIFIED
- **Symptom:** folder uploads could store a relative folder path as the original filename and generate ugly display titles.
- **Root cause:** `webkitRelativePath` overrode the selected file's basename and the title normalization regex was incorrect.
- **Invariant:** original basename remains provenance; folders are selection context, not part of the legal document's name.
- **Repair:** explicit basenames win; title normalization was corrected; folder vault/metadata are explicit; Office locks remain skipped.
- **Verification:** final folder UI ingested two templates with correct filenames/titles and skipped one genuine `~$` file without a registry record.

### DEMO-001 — Clean human-usable corpus and release journey

- **Status:** VERIFIED
- **Symptom:** historical application data was cluttered and unsuitable for a normal-user demo.
- **Dependencies:** all items above.
- **Invariant:** final state contains only intentional real documents, truthful processing, functional Search/Ask/citations/source, and survives restart.
- **Repair:** preserved the old application state in `.backups/`, reset only application-managed artifacts, and uploaded six curated real documents through the actual UI with conservative metadata.
- **Verification:** the old corpus was archived through its visible UI controls and vanished from active Search. Six replacement documents with mandatory tags/notes reached READY with 1,470 real embeddings/index entries. Natural Search, 14 Ask checks, per-document source opening, original download, 390/768/1440px UI, and supported restart passed. Full isolated suite: 708 tests.

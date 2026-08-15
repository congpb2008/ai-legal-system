# Product Audit — Legal Knowledge Platform

**Audit date:** 2026-08-14; demo-readiness revalidation 2026-08-15 (Asia/Bangkok)  
**Workspace:** `/home/vostro/AI Legal Platform`

## Baseline and preservation

- Git top-level is `/home/vostro`, branch `master`, with no commits. The platform and other home files are untracked. There is no trustworthy commit baseline, so broad Git reset/clean/checkout operations are prohibited.
- The real corpus under `Luat-DT-QH15/` contains PDF, DOCX, ZIP, and two Office `~$` lock files. Originals were read only and remain untouched.
- Existing application data under `storage/` was inspected read-only. Runtime reproductions used a temporary isolated `LEGAL_PLATFORM_DATA_DIR`, which was moved to trash afterward.
- Python runtime is 3.12.3. The package starts with `python -m legal_platform`. Tesseract is not installed; `pdftoppm` is available.

## Authoritative behavior

The governing order is ADRs → contracts → architecture → implementation. Core invariants are:

1. Original sources and Knowledge Trees are canonical and immutable.
2. Full processing is source → extraction/OCR → parse → Knowledge Tree → chunks → real embeddings → index → READY.
3. READY means all required searchable artifacts exist.
4. Retrieval precedes generation; no evidence produces `NO_EVIDENCE`.
5. Evidence and citations trace to Knowledge Node → Knowledge Tree → Document Version → logical Document → original source.
6. Vault authorization is enforced before listing, retrieval, generation, and document/source access.
7. Normal document removal is archival, not physical deletion.
8. Reprocessing performs only the requested stage and required downstream invalidation/rebuild.

## Actual runtime map

- `PlatformAPI` creates one persistent SQLite graph at `$LEGAL_PLATFORM_DATA_DIR/db/legal_platform.db`, persistent files at `$LEGAL_PLATFORM_DATA_DIR/files`, then rebuilds the in-memory vector search map from persisted `vector_index` rows.
- A daemon thread polls `UPLOADED` documents every five seconds and runs `DocumentPipeline` synchronously per document.
- OCR/extraction, Knowledge Trees, chunk collections, embeddings, and index rows are persisted in the same SQLite database.
- The browser is a static SPA (`frontend/index.html`, `frontend/js/api.js`, `frontend/js/app.js`).
- Authentication is an in-memory token map accepting any non-empty username/password.

## Empirical baseline

- Live production-like DB: 22 documents, 12 vaults, 11 `FAILED`, 7 `OCR_COMPLETED`, 4 `READY`.
- All four existing `READY` documents have zero document-owned chunk collections, embeddings, and index rows. All 447 stored embeddings/index rows use model `placeholder`, dimension 384.
- Every persisted chunk/embedding/index `document_id` matches a Document Version ID, not a logical Document ID. Evidence document lookup therefore returns 404.
- Isolated upload of two real DOCX files succeeded and reached READY; hybrid search returned evidence and survived restart. The same traceability defect remained after restart.
- A real 162-byte Office `~$` lock file was accepted as a document, then failed asynchronously with a PDF-open error.
- Safe baseline suite initially passed 565 tests. The final isolated collection passes 708 tests against a disposable data root without touching demo application data.

## Confirmed findings

| ID | Severity | Finding | Evidence / impact |
|---|---|---|---|
| TRACE-001 | P0 | **VERIFIED repair:** chunk, embedding, and index ownership had stored a version UUID in both `document_id` and `version_id`. | Chunking now requires logical document identity separately. Focused tests pass; isolated real-DOCX evidence resolves through the document API and survives restart. Legacy derived rows still require the planned rebuild. |
| EMB-001 | P0 | **VERIFIED repair:** runtime semantic retrieval had used deterministic placeholder vectors. | Native Ollama embeddings now verify exact model digest/dimension; BGE-M3 is the selected default, placeholder use is explicit-test-only, and dependency failures are observable. |
| STATE-001 | P0 | **VERIFIED repair:** READY had not guaranteed searchable artifacts. | One coordinator now validates source, current OCR/tree/chunks, exact active embeddings, and index coverage; invalid legacy READY state reconciles to recoverable FAILED. |
| AUTH-001 | P0 | **VERIFIED repair:** public reads/queries had bypassed vault authorization. | Resolved user identity and explicit authorized-vault scope now cover read/search/Ask/admin/mutation paths. Fresh two-user HTTP proof returned zero/403 across the isolation boundary. |
| UPLOAD-001 | P1 | **VERIFIED repair:** Office lock/temp and malformed DOCX files entered ingestion. | Real multipart proof accepted two valid DOCX files with the selected vault and rejected the real `~$` file before persistence. |
| PROCESS-001 | P1 | **VERIFIED repair:** reprocessing controls were false or destructive. | Re-OCR/re-parse/re-embed/re-index now preserve the correct upstream stages, invalidate downstream artifacts, rebuild, and report actual counts. |
| GEN-001 | P1 | **VERIFIED repair:** saved provider configuration had been bypassed by normal answers. | Runtime generation now resolves/reloads saved configuration, never masks provider failure with template success, rejects empty output, and a live qwen3.6 proof returned the expected evidence-grounded legal date with correct model metadata. |
| CIT-001 | P1 | **VERIFIED repair:** citations had not been verified or inspectable. | Every citation now resolves evidence → node → tree/version → logical document/source; unauthorized source access is forbidden; browser source/page/original controls are proven. |
| DELETE-001 | P1 | **VERIFIED repair:** ordinary delete had physically removed registry rows. | It now requires vault permission, archives the record and index entries, and the fresh HTTP/DB proof retained a truthful `ARCHIVED` row. |
| JOB-001 | P1 | **VERIFIED repair:** background work had no durable observable job lifecycle. | Upload/manual operations now persist atomically claimed job IDs, timing, completion/failure, and restart recovery; authorized job/status APIs expose the durable record and exact-stage reprocessing provides recovery. |
| STORAGE-001 | P1 | **VERIFIED repair:** constructors/fallbacks hard-coded this machine's storage path. | Runtime storage is injected from its configured root; standalone/test wiring is isolated; no old absolute backend path remains. |
| OCR-001 | P1 | **DEFERRED deployment limitation:** scanned-PDF OCR is unavailable in this environment. | Tesseract and Vietnamese data are absent; a real image-only PDF failed observably. Digital PDF/DOCX extraction works and originals remain recoverable. |
| CONCURRENCY-001 | P1 | **VERIFIED repair:** HTTP threads and the worker shared one SQLite transaction context and raced processing state/index mutation. | Runtime DB ownership is per-thread with WAL/busy timeout, state claims use compare-and-set, pipeline work is per-document serialized, and a 90-request threaded stress proof completed with zero errors. |
| SOURCE-001 | P1 | **VERIFIED repair:** source lifecycle was opaque and uninspectable. | Rich source metadata, authorized node/page inspection, and optional immutable original retrieval are now implemented and proven byte-identical. |
| RETR-001 | P1 | **VERIFIED repair:** unrelated nearest-neighbour chunks could become SUCCESS citations. | Ask uses the same HYBRID path as Search, with query-aware filtering, separated title/content lexical scores, exact-source deduplication, and honest `NO_EVIDENCE`; semantic, identifier, numeric/date, and insufficient-evidence acceptance succeeds. |
| HEALTH-001 | P2 | **VERIFIED repair:** health/readiness were constants. | Live checks cover DB, storage, the final 1,470-entry index, worker, BGE-M3, and generation configuration; unhealthy readiness is 503. |
| DOCS-001 | P2 | **VERIFIED repair:** operations docs were stale. | Runtime, provider, persistence, OCR/auth limitations, setup, and current validation artifacts are aligned. |
| UI-001 | P2 | **VERIFIED repair:** controls/messages blocked or misrepresented workflows. | Browser acceptance covers reachable batch upload, truthful processing/jobs/archive, citations/source, recovery controls, and responsive layouts. |
| META-001 | P2 | **VERIFIED repair:** the document contract included tags but the public product omitted them. | Upload/update/API/list/detail/Search/Ask now use the existing tag model; all six curated documents have source-supported titles, required labels, notes, provenance, filtering, and UI verification. |

## Historical clues independently resolved

- The historical raw `KeyError: 'vault_id'` did not reproduce through the current isolated API path: three multipart uploads all carried a valid vault ID. It remains a browser regression target because the folder modal relies on a fallback vault lookup rather than an explicit selection.
- Persistent SQLite, persistent source storage, shared-thread connection setup, automatic processing, DOCX extraction, and restart index reload now exist in the main runtime graph.
- Historical READY and OCR-completed corruption remains in the real DB and current reprocessing controls cannot safely repair it.

## Embedding comparison

Six semantic Vietnamese legal queries and eight real-corpus excerpts were tested through native Ollama `/api/embed`.

| Model | Dim | Context | R@1 | R@3 | MRR | Cold wall time |
|---|---:|---:|---:|---:|---:|---:|
| `bge-m3:567m-fp16` | 1024 | 8192 | 1.00 | 1.00 | 1.00 | 4.74 s |
| `nomic-embed-text-v2-moe:latest` | 768 | 512 | 1.00 | 1.00 | 1.00 | 3.02 s |

Both passed the small benchmark. BGE-M3 is the preferred default because its 8192-token input contract better fits long legal chunks; Nomic is the faster fallback. Model/version/dimension changes must invalidate and rebuild embeddings/indexes.

## Audit conclusion

No unresolved P0 correctness, data-integrity, privacy, or security blocker remains in the supported MVP path. Real DOCX/digital-PDF ingestion, BGE-M3 retrieval, qwen3.6 generation, verified citations/source inspection, durable jobs, archive behavior, and restart persistence passed through the browser. Remaining limitations are production authentication and the absent system OCR dependency for scanned/image-only PDFs.

## Demo-readiness revalidation — 2026-08-15

The prior application-managed demo corpus was archived through the normal Web UI and became absent from active library/Search. It was replaced through the real Web UI with six real, non-duplicate procurement documents. The originals remain unchanged. All six received source-supported titles, required tags and notes, then reached artifact-backed READY with 1,470 BGE-M3 embeddings and active index records.

The revalidation confirmed and repaired seven additional integration defects:

1. first-run setup completion, safe configuration recovery, route wiring, and runtime embedding refresh were inconsistent;
2. folder upload could substitute a relative folder path for the source basename;
3. qwen hidden reasoning could consume the response budget without visible content;
4. Ask bypassed HYBRID retrieval and title/incidental-number matches could outrank supporting clauses;
5. a provider-declared lack of evidence could retain SUCCESS/citations from the candidate set;
6. the contract's existing tags were absent from upload/API/library/Search/Ask workflows;
7. comparison queries required every named document code in one title and discarded both real sources.

The fixes remain inside the existing setup/provider, document metadata, upload, retrieval, generation, and citation abstractions. No parallel Ollama, tagging, or source system was introduced. Final Web UI proof covered the labelled six-document library, tag filtering, natural Search, fourteen grounded/out-of-corpus Ask questions, citation/source/original opening, desktop/tablet/mobile states, and a supported restart. The final result was 12 PASS, 2 NO_EVIDENCE_CORRECT, and no PARTIAL/FAIL/SYSTEM_ERROR/UI_ERROR.

The supported demo path is therefore ready. Production identity, scanned-image OCR dependencies, exact DOCX page mapping, and horizontal scaling remain explicitly outside this MVP demo verdict.

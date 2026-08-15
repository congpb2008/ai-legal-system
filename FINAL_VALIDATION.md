# Final Validation — Demo Readiness

**Validation date:** 2026-08-15 (Asia/Bangkok)  
**Runtime:** supported `legal-platform` CLI on port 8080, persistent project `storage/` data root  
**Demo identity:** `demo`, owner of the curated vault `Pháp luật đấu thầu 2025`

## Baseline state

The pre-demo application contained an older six-document corpus without labels and with incomplete notes. Those records were archived one at a time using the visible **Lưu trữ** actions in the document library. Before replacement ingestion, the active library was empty and a representative query for the old corpus returned no results. The archive contract deliberately retains immutable historical rows, but their document/index status is `ARCHIVED`; they are absent from active library, Search, Ask, and source workflows.

No original under `Luat-DT-QH15/` was deleted, renamed, or modified. A recoverable pre-ingestion application backup remains under `.backups/`.

This pass also confirmed that the public document contract had persisted `Metadata.tags`, but upload serialization, API responses, Search/Ask context, and the Web UI did not expose it. The final multi-document Ask test additionally found that a query naming both `4A` and `5A` required both identifiers to appear in one document title, making a legitimate comparison fail as `NO_EVIDENCE`.

## Major problems, root causes, and fixes

- **Labels existed only inside the backend model.** The normal upload/update APIs and the UI now accept, validate, persist, serialize, display, and filter tags through the existing `Metadata.tags` field. No parallel categorization system was added.
- **Batch upload could not curate each file.** The real multi-file/folder modal now presents a per-file title, document number, labels, and note editor. It skips Office lock files and reports accepted, failed, and skipped counts truthfully.
- **Original filename provenance was not visible.** Document details and source panels now expose the immutable original basename while retaining a separate human display title.
- **Document notes and labels were absent from browsing/retrieval context.** The library shows notes and tag chips, provides a tag filter, and Search/Ask citations show source tags.
- **Cross-document identifiers were handled as an impossible all-in-one-title match.** Retrieval now gives each source a proportional boost for the named identifier it contains; the evidence gate accepts a score-eligible source that matches any explicitly named document code. Generic-overlap safeguards remain intact.
- **Normal CLI restart initially appeared empty under `admin`.** This was not data loss: the curated vault is correctly private to its `demo` owner. Logging in as that same identity after restart restored the six-document library, demonstrating both persistence and vault isolation.

## Demo corpus

Every source was read before upload. Titles, dates, authorities, labels, and notes below are transcribed or conservatively summarized from the originals. `INTERNAL_REGULATION` is the nearest existing type for the guide/templates because the authoritative enum has no `GUIDANCE` or `TEMPLATE` value; the mandatory tags provide the more precise categorization.

| Original file | Display title | Labels | Note | Processing | Searchable | Source opens |
| ------------- | ------------- | ------ | ---- | ---------- | ---------- | ------------ |
| `Luật-90-2025-QH15.docx` | Luật số 90/2025/QH15 – Sửa đổi, bổ sung một số luật về đấu thầu và đầu tư | Luật; Đấu thầu; Đầu tư; PPP; Quốc hội | Luật sửa đổi, bổ sung quy định của Luật Đấu thầu và các luật về PPP, hải quan, thuế, đầu tư, đầu tư công, quản lý tài sản công. | READY | PASS | PASS |
| `Nghị định-214-2025-NĐ-CP.docx` | Nghị định 214/2025/NĐ-CP – Quy định chi tiết Luật Đấu thầu về lựa chọn nhà thầu | Nghị định; Đấu thầu; Lựa chọn nhà thầu; Chính phủ; Hướng dẫn thi hành | Quy định chi tiết một số điều và biện pháp thi hành Luật Đấu thầu về lựa chọn nhà thầu. | READY | PASS | PASS |
| `0. Lời văn thông tư.docx` | Thông tư 79/2025/TT-BTC – Cung cấp, đăng tải thông tin và mẫu hồ sơ đấu thầu trên Hệ thống | Thông tư; Đấu thầu qua mạng; Hệ thống mạng đấu thầu quốc gia; Mẫu hồ sơ; Bộ Tài chính | Hướng dẫn việc cung cấp, đăng tải thông tin về đấu thầu và các mẫu hồ sơ đấu thầu trên Hệ thống mạng đấu thầu quốc gia. | READY | PASS | PASS |
| `HuongDan_ChuyenTiep_GoiThau_EGP_01072025_Luat90-2025QH15.pdf` | Hướng dẫn tổ chức lựa chọn nhà thầu qua mạng từ 01/07/2025 theo Luật 90/2025/QH15 | Hướng dẫn; Đấu thầu qua mạng; Chuyển tiếp; Hệ thống mạng đấu thầu quốc gia; Luật 90/2025/QH15 | Tài liệu hướng dẫn chủ đầu tư, nhà thầu, tổ chuyên gia và tổ thẩm định thực hiện lựa chọn nhà thầu trên Hệ thống từ 01/07/2025. | READY | PASS | PASS |
| `4. Mẫu số 4A E-HSMT hàng hóa 1 túi.docx` | Mẫu số 4A – E-HSMT mua sắm hàng hóa qua mạng, một giai đoạn một túi hồ sơ | Biểu mẫu; E-HSMT; Hàng hóa; Đấu thầu qua mạng; Một giai đoạn một túi hồ sơ | Biểu mẫu E-HSMT áp dụng cho gói thầu mua sắm hàng hóa qua mạng theo phương thức một giai đoạn một túi hồ sơ. | READY | PASS | PASS |
| `5. Mẫu số 5A E-HSMT Phi tư vấn 1 túi.docx` | Mẫu số 5A – E-HSMT dịch vụ phi tư vấn qua mạng, một giai đoạn một túi hồ sơ | Biểu mẫu; E-HSMT; Phi tư vấn; Đấu thầu qua mạng; Một giai đoạn một túi hồ sơ | Biểu mẫu E-HSMT áp dụng cho gói thầu dịch vụ phi tư vấn qua mạng theo phương thức một giai đoạn một túi hồ sơ. | READY | PASS | PASS |

The first four files were uploaded individually through the Web UI so their complete metadata could be inspected. The last two were uploaded through the visible multi-file workflow together with a genuine 162-byte `~$` Office lock file. The UI reported **2/2 successful, 0 failed, 1 lock file skipped**. No lock-file document exists.

Artifact-backed verification found 6 active sources, 6 current extraction/OCR records, 6 canonical Knowledge Trees, 1,470 active chunks, 1,470 BGE-M3 embeddings, and 1,470 active index rows. The UI's READY state therefore represents real completed work.

## AI runtime

- Ollama endpoint: `https://my-container-4vsbn24p-11434.serverless.fptcloud.jp`
- Generation surface: its OpenAI-compatible `/v1` endpoint
- Generation model: `qwen3.6:35b-a3b`, persisted with reasoning mode `none`
- Embedding model: `bge-m3:567m-fp16`, native Ollama embedding API, 1,024 dimensions
- Reranking: existing deterministic evidence/reranking architecture; no unavailable model is faked

Both native `/api/tags` and OpenAI-compatible `/v1/models` returned the same live eight-model catalog recorded in `MODEL_ROSTER.md`. Configuration, connectivity, generation, embeddings, and restart persistence were exercised through the product. No credential is included here.

## Search validation

Queries were entered through the visible Hybrid Search form after the tagged replacement corpus was READY.

| Query | Human-visible result | Result |
|---|---|---|
| `Tôi cần mẫu hồ sơ mời thầu mua sắm hàng hóa qua mạng theo phương thức một túi hồ sơ` | Mẫu 4A ranked first at 86%, with title, labels, supporting preamble, and source action | PASS |
| `Luật sửa đổi về đấu thầu bắt đầu áp dụng vào thời điểm nào?` | Correct Law 90 document ranked first; evidence included the implementation provision | PASS |
| `Đấu thầu bền vững quan tâm đến những yếu tố nào?` | Nghị định 214 ranked first with the environmental/social/economic provision | PASS |
| Label filter `Hàng hóa` | Only Mẫu 4A remained | PASS |
| Label filter `Đấu thầu qua mạng` | Circular, transition guide, Mẫu 4A, and Mẫu 5A remained | PASS |

Archived records were not returned. Every sampled result retained the correct document/vault identity, showed meaningful labels, and opened a real source.

## Ask validation

Expected facts were established directly from the originals before black-box mode. All questions below were then submitted only through the visible Ask form on the tagged corpus; after the 4A/5A defect was repaired, the Ask scenario was restarted.

| ID | Question | Classification | Evidence result |
|---|---|---|---|
| D1 | Luật 90/2025/QH15 có hiệu lực từ ngày nào? | PASS | 01-07-2025; HIGH 87%; implementation provision cited |
| D2 | Đấu thầu bền vững theo Nghị định 214 quan tâm những yếu tố nào? | PASS | Môi trường, xã hội, kinh tế; HIGH 82% |
| D3 | Thông tư 79 hướng dẫn những nội dung chính nào? | PASS | Publication of procurement information and system dossier templates; HIGH 82% |
| D4 | Trong Mẫu 4A, ngày được tính ra sao và Hệ thống dùng múi giờ nào? | PASS | Calendar days include weekends/holidays/Tết; GMT+7; MEDIUM 76% |
| D5 | Mẫu 5A áp dụng cho loại gói thầu và phương thức nào? | PASS | Non-consulting services, one-stage one-envelope; HIGH 82% |
| P1 | Sau 01-07-2025, gói thầu qua mạng chuyển tiếp được xử lý thế nào? | PASS | Correctly distinguished issue/opening dates and old/new-regime options; HIGH 86% |
| P2 | Kế hoạch đã duyệt nhưng chưa phát hành hồ sơ có thể điều chỉnh không? | PASS | Yes, with the not-yet-issued condition and transition sources; HIGH 83% |
| P3 | Sau khi phê duyệt kế hoạch tổng thể, trong bao lâu phải đăng tải? | PASS | Five working days; HIGH 83% |
| N1 | Ngày ban hành Thông tư 79 và ngày áp dụng chào giá trực tuyến xây lắp rút gọn? | PASS | 04-08-2025 and 01-09-2025; HIGH 86% |
| N2 | Nghị định 214 có hiệu lực từ ngày nào? | PASS | Signing date, 04-08-2025; HIGH 87% |
| M1 | Vai trò khác nhau của Luật 90, Nghị định 214, Thông tư 79? | PASS | Correct law / implementing decree / system-and-template circular roles; HIGH 84% |
| M2 | Mẫu 4A và Mẫu 5A khác nhau ở phạm vi áp dụng thế nào? | PASS | Goods versus non-consulting services; both real documents cited; MEDIUM 73% |
| I1 | Đội nào sẽ vô địch FIFA World Cup 2026? | NO_EVIDENCE_CORRECT | `NO_EVIDENCE`, LOW 0%, no citations |
| I2 | Mức phạt chính xác cho tấn công mạng vào hệ thống đấu thầu? | NO_EVIDENCE_CORRECT | `NO_EVIDENCE`, LOW 0%, no citations |

Final result: **12 PASS, 2 NO_EVIDENCE_CORRECT, 0 PARTIAL, 0 FAIL, 0 SYSTEM_ERROR, 0 UI_ERROR**.

## Citation validation

- The effective-date answer opened the Law 90 implementation citation, showing the human title, original filename, canonical clause text, and source tags.
- The repaired 4A/5A comparison displayed evidence from both named documents. The first 5A citation was expanded, **Xem nguồn** opened the correct 5A source, and **Tải bản gốc** fetched the authorized original DOCX with HTTP 200.
- Search and Ask use document/source IDs rather than developer filesystem paths. No `/home/...` path is rendered.
- DOCX inspection provides canonical extracted text plus original download. Exact rendered pagination/highlighting is not claimed where the source mapping cannot support it.

## Black-box UI validation

The UI-only journey covered login as the vault owner, active library, readable titles/notes/tags, tag filtering, document details, source opening, natural Search, all 14 Ask questions, citation expansion, source inspection, original download, navigation, and restart recovery. Implementation code, database queries, and private service calls were not used to decide black-box outcomes.

Responsive checks covered 1440×900 desktop, 768×1024 tablet, and 390×844 mobile. Mobile Search presents readable result cards with tags and reachable source actions. Mobile navigation collapses behind a labelled menu. The document table remains horizontally scrollable with an explicit user hint; this is usable but denser than a card-based mobile library. No final browser console/page errors were observed.

## Restart validation

The application was stopped cleanly and restarted with the documented CLI and the same project `storage/` root. Login tokens are intentionally in memory, so a fresh login was required. Logging in as `demo` (the curated vault owner) proved through the UI that:

- all six documents, titles, notes, labels, and READY states survived;
- the natural Mẫu 4A search still ranked the correct source first;
- effective-date, semantic, multi-document, and no-evidence Ask cases still worked;
- the 5A citation/source opened and the original download returned HTTP 200.

An `admin` login correctly saw no private `demo` vault; this confirms authorization rather than data loss.

## Tests executed

- Full isolated suite: **708 tests collected and passed**.
- Added regressions for tag creation/serialization/update/validation, upload provenance metadata, proportional multi-document identifier matching, and explicit named-document evidence retention.
- Focused retrieval/generation tests: passed.
- `node --check frontend/js/app.js` and `frontend/js/api.js`: passed.
- Python compile check: passed.
- Final browser console/page-error check: clean.

Tests use an isolated `LEGAL_PLATFORM_DATA_DIR` and do not pollute the curated demo corpus.

## Worker/model assignments and review

- `qwen3.6:35b-a3b` is the verified product generation model and worked well for grounded Vietnamese answers.
- `bge-m3:567m-fp16` remains the selected real embedding runtime after the Vietnamese legal comparison and complete six-document ingestion.
- Hermes/Qwen reports were treated as worker evidence only. Broad or self-certified claims were rejected unless reproduced by Codex through code, persistence, API, and browser checks.
- Codex retained single-writer architecture, implementation review, actual UI corpus preparation, black-box validation, and release ownership.

## Remaining limitations

- Authentication is an MVP identity stub accepting any non-empty username/password. Vault authorization works for the presented identity, but a production identity provider and durable sessions are required before multi-user deployment.
- Image-only PDF OCR requires Tesseract with Vietnamese language data, absent in this environment. The demo corpus uses supported DOCX and digitally extractable PDF sources; OCR dependency failures remain observable.
- The authoritative type enum has no `TEMPLATE` or `GUIDANCE` value. Those documents use `INTERNAL_REGULATION` plus precise mandatory tags.
- Mobile document browsing uses a horizontally scrollable table. It is functional and labelled, but less compact than a dedicated card layout.
- Citation lists can include more supporting evidence items than a minimal claim-by-claim view; sampled citations remained real and inspectable.
- DOCX rendered page precision is approximate; canonical text and the original file are provided instead of fabricated highlighting.
- SQLite/single-node runtime is suitable for this MVP demo, not horizontally scaled production.

## Verdict

READY FOR MVP DEMO

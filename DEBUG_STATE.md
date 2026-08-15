# Debug State

- **Phase:** Complete — demo runtime left active with the verified six-document corpus.
- **Verdict:** `READY FOR MVP DEMO`.
- **Runtime:** supported CLI, persistent project `storage/`, remote qwen3.6 generation (`reasoning_effort: none`), BGE-M3 embeddings.
- **Proof:** 6 READY sources/trees, 1,470 chunks/embeddings/index rows; every document has a human title, labels, note, provenance, Search/source proof; 12 Ask PASS and 2 honest NO_EVIDENCE; restart passed through the UI.
- **Regression gate:** 708 tests, JavaScript syntax, Python compile, and final browser page-error checks pass.
- **Preservation:** originals under `Luat-DT-QH15/` are untouched; pre-demo application data is recoverable under `.backups/`.
- **Current browser state:** logged in as the `demo` vault owner; curated six-document corpus remains active.
- **Known limits:** MVP identity stub; no scanned-PDF OCR dependency; template/guide use nearest type plus tags; mobile library is horizontally scrollable; DOCX pagination is approximate; SQLite is single-node.

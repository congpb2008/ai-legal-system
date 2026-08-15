# Task 031 — Document Pipeline Debug & State Machine Repair

## Objective

Fix the document-processing pipeline so that real uploaded documents can reliably move through:

Upload → OCR → Parse → Chunk → Embed → Index → Ready

The current application has a known pipeline/state-machine failure:

`ValueError: Document <id> is in state OCR_COMPLETED, expected OCR_PENDING`

This indicates that an already-completed OCR stage can incorrectly be invoked again as if it were pending.

Task 031 is strictly a debugging and correctness task.

Do NOT continue Task 029 or Task 030.
Do NOT add new UX features.
Do NOT redesign the architecture.
Do NOT add new providers.
Do NOT replace working components merely for convenience.

---

## 1. Read Before Editing

Read:

- this task completely
- architecture documentation
- processing pipeline documentation
- all relevant processing state definitions
- document contracts
- job contracts
- OCR implementation
- parser implementation
- chunking implementation
- embedding implementation
- indexing implementation
- document handlers
- job handlers
- background worker
- frontend code that invokes processing/reprocessing actions
- tests covering documents, processing, jobs, OCR, parsing, embedding and indexing

Identify the authoritative state machine before changing code.

Do not infer state transitions from the UI alone.

---

## 2. Establish the Actual State Machine

Document the current authoritative state transitions before modifying them.

The intended conceptual pipeline is:

UPLOAD
  ↓
OCR
  ↓
PARSE
  ↓
CHUNK
  ↓
EMBED
  ↓
INDEX
  ↓
READY

However, individual stages must also be independently repeatable when their prerequisites already exist.

Explicitly determine and document the valid behavior for:

### Full processing

```text
Upload
→ OCR
→ Parse
→ Chunk
→ Embed
→ Index
→ Ready

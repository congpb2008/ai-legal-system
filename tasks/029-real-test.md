# Task 029 — Real-World Autonomous UI Validation

## Objective

Validate the Legal Platform end-to-end using real documents already present
in the project workspace.

The agent must behave as a normal first-time user rather than as a developer
or test harness.

Do not rely exclusively on direct API calls or internal Python modules.
The primary validation interface is the Web UI.

---

## 1. Discover Real Documents

Before testing, inspect the project workspace for user-provided documents.

Identify supported documents such as:
- PDF
- supported text/document formats

Do not modify, delete, rename, or overwrite the source documents.

Build an internal test inventory containing:
- filename
- file type
- approximate size
- whether the document appears readable
- useful topics/entities detected from the document

The documents are real legal materials and must be treated as authoritative
test data.

---

## 2. Act as a New User

Start from a clean application state where practical.

Use the Web UI exactly as a normal user would.

The agent should:

1. Open the application.
2. Complete setup if required.
3. Navigate to document management.
4. Upload the discovered documents.
5. Fill required metadata automatically.
6. Wait for processing.
7. Observe processing status.
8. Trigger available indexing/embedding/parsing actions when appropriate.
9. Verify that the resulting document state actually changes.

Do not manually invent metadata when it can reasonably be inferred from
the document.

---

## 3. Validate the Processing Pipeline

For each uploaded document, verify:

Upload
→ parsing
→ extraction
→ embedding
→ indexing
→ searchable document
→ answer generation

The agent must distinguish between:

- button appears to work
- request succeeds
- backend state actually changes
- resulting data is actually usable

A successful HTTP response alone is insufficient.

---

## 4. Generate Questions From Real Documents

After processing, inspect the actual document contents.

Generate a test question set automatically.

Questions should include:

### Direct lookup
Questions whose answers explicitly exist in one document.

### Multi-document retrieval
Questions requiring information from multiple documents.

### Precise factual retrieval
Names, dates, article numbers, definitions, obligations, thresholds,
deadlines, monetary values, etc.

### Semantic retrieval
Questions where the wording differs significantly from the wording
used in the source document.

### Negative questions
Questions for which the documents do not contain sufficient evidence.

### Citation verification
Questions designed to determine whether the answer cites the correct
source document and relevant evidence.

Do not use questions based on general world knowledge when a document-derived
question can be constructed instead.

---

## 5. Use the UI to Search and Ask

For every generated question:

1. Enter it through the normal UI.
2. Submit it.
3. Wait for completion.
4. Inspect the displayed answer.
5. Inspect citations/evidence.
6. Compare the answer against the source documents.

The agent must not silently correct an incorrect answer using outside
knowledge.

---

## 6. Evaluate Answer Quality

Classify each result as:

- PASS — answer supported by source evidence
- PARTIAL — substantially correct but incomplete
- FAIL — incorrect or unsupported
- NO_EVIDENCE — correctly refuses/indicates insufficient evidence
- SYSTEM_ERROR — application failure
- UI_ERROR — user interaction failure

For every FAIL/PARTIAL result record:

- question
- expected answer/evidence
- actual answer
- cited document
- likely failure stage
- reproduction steps

---

## 7. Test UI Operations

While performing the workflow, actively test:

- navigation
- upload
- metadata forms
- processing buttons
- re-index
- re-embed
- re-parse
- search
- answer generation
- loading states
- empty states
- error states
- retry behavior
- document detail views
- delete operations
- responsive layout where practical

If a button appears clickable but produces no meaningful state change,
record it as a defect.

---

## 8. Test Failure Cases

Intentionally test reasonable failures:

- unsupported file
- malformed/empty input where practical
- duplicate upload
- missing required metadata
- unavailable provider
- empty search
- question with no supporting evidence
- interrupted/failed processing

Do not damage or delete the original workspace documents.

---

## 9. No Developer Privileges During Validation

During the user-flow portion, do not:

- call internal service methods directly
- bypass the UI
- modify database state manually
- modify application files to make a test pass
- fabricate API responses
- alter source documents

Direct API inspection may be used only afterward to diagnose a UI failure.

---

## 10. Produce a Validation Report

Create:

`docs/qa/task-029-real-world-validation.md`

Include:

### Environment
- application version
- model/provider
- processing configuration
- document count
- test date

### Documents Tested
Table containing:
- document
- type
- processing status
- searchable?
- answerable?

### Questions Tested
Table containing:
- question
- expected evidence
- actual result
- classification
- citation correctness

### Pipeline Results

| Stage | Status | Notes |
|---|---|---|
| Upload | | |
| Parsing | | |
| Embedding | | |
| Indexing | | |
| Retrieval | | |
| Generation | | |

### UI Defects

For every defect:

- severity
- location
- reproduction steps
- expected behavior
- actual behavior
- suspected cause

### Overall Assessment

Report:

- documents successfully processed
- questions tested
- PASS rate
- PARTIAL rate
- FAIL rate
- NO_EVIDENCE rate
- SYSTEM_ERROR count
- UI_ERROR count

Do not claim the application is production-ready merely because the test
suite passes.

---

## 11. Final Rule

This task is a real-world acceptance test.

The objective is not to make the tests green.

The objective is to discover whether a normal user can take real documents
from:

document on disk
→ upload
→ process
→ search
→ ask questions
→ receive evidence-backed answers

without developer intervention.

If something fails, report it honestly and do not modify unrelated code to
hide the failure.

Stop after producing the validation report.
Do not continue to Task 030.

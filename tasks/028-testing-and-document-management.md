# Task 028 – Real-Document UI Acceptance Test & Document Management

## Objective

Test the Legal Platform as a normal end user through the Web UI, using the real
documents currently present in the project directory as test data.

This task has two purposes:

1. Determine whether the application actually works end-to-end with real documents.
2. Add the missing document-management capabilities:
   - Delete documents
   - Upload an entire folder of documents

Do NOT assume that an operation works merely because its API endpoint returns
success. The primary acceptance criterion is observable behavior through the
Web UI.

Do not continue to later tasks.

---

## Part A — Discover the real test documents

Before modifying code:

1. Inspect the project directory for documents that were recently added by the
   project owner.
2. Identify supported document types and their filenames.
3. Do NOT modify, rename, delete, or move these source documents.
4. Use these documents as the real test dataset.

Record:
- filename
- type
- approximate size
- whether it is text-based or likely scanned/image-based
- any other useful characteristics

Do not invent document contents.

---

# Part B — Black-box UI acceptance test

Start the application using the documented normal-user startup procedure.

Use the Web UI as a normal client.

Do NOT use direct API calls as a substitute for UI interaction.

If browser automation is available, use it.
If browser automation is not available in the current environment, report this
as a blocker instead of pretending that the UI was tested.

Test the complete user journey:

1. Open the application.
2. Complete setup if necessary.
3. Log in.
4. Create/select an appropriate vault.
5. Upload one of the real documents through the UI.
6. Confirm that the UI reports successful upload.
7. Confirm that the document appears in the document list.
8. Inspect its metadata.
9. Run parsing from the UI.
10. Verify whether parsing actually changes document state/data.
11. Run embedding from the UI.
12. Verify whether embedding actually changes document state/data.
13. Run re-indexing from the UI.
14. Verify whether indexing actually changes document state/data.
15. Search for information that is known to exist in the uploaded document.
16. Ask questions whose answers require information from the uploaded document.
17. Verify that the returned answer actually uses the uploaded document.
18. Verify citations/evidence shown by the UI.
19. Repeat with at least one additional real document if available.

IMPORTANT:

A button returning SUCCESS is NOT sufficient.

For every processing operation, verify the resulting observable state.

For example:

    Upload
      ↓
    Parsing
      ↓
    Parsed content actually exists
      ↓
    Embedding
      ↓
    Embeddings actually exist
      ↓
    Indexing
      ↓
    Search can retrieve the document
      ↓
    Question answering can use the document

If one stage reports success but the next stage cannot observe its output,
identify it as a functional defect.

---

# Part C — Real information retrieval test

Use the actual contents of the uploaded documents to construct test queries.

Do not use generic questions such as "What is this document about?" unless
they are useful as an additional test.

Prefer questions that test:

- exact facts
- names
- dates
- numbers
- definitions
- relationships between sections
- information appearing in different parts of a document
- information requiring retrieval rather than simple metadata lookup

For every question record:

- question
- expected evidence/document
- actual answer
- whether the answer is supported by the document
- citation/evidence shown by the application
- pass/fail

Do not use outside knowledge to decide whether an answer is correct.
The real documents are the source of truth.

---

# Part D — Diagnose the processing pipeline

Based on the UI tests, determine exactly which stages work.

Test independently:

- upload
- document registration
- parsing
- OCR if applicable
- chunking
- embedding
- indexing
- retrieval
- reranking if present
- LLM generation

If the UI says an operation succeeded but the expected downstream artifact
does not exist, inspect the implementation and identify the root cause.

Do not paper over the problem with a UI-only success state.

Fix only defects necessary to make the existing documented architecture
actually work.

Do not redesign the architecture or silently change contracts.

---

# Part E — Add Delete Document

Implement document deletion through the Web UI.

The user must be able to:

1. Select a document.
2. Click Delete.
3. See a confirmation step.
4. Confirm deletion.
5. See the document disappear from the UI.
6. Verify that its associated searchable/indexed state is removed.
7. Verify that searching for that document no longer returns it.
8. Verify that deletion does not corrupt unrelated documents.

Deletion must not leave orphaned processing/index records.

Handle errors clearly.

Do not allow accidental deletion through a single destructive click.

---

# Part F — Add Upload Folder

Add folder upload to the Web UI.

The user should be able to select a folder and upload its supported documents.

Requirements:

- recursively process files in the selected folder where appropriate
- preserve useful relative filename/path metadata
- reject unsupported file types cleanly
- enforce the existing file-size limits
- sanitize filenames/path information
- do not allow uploaded paths to escape the storage directory
- show upload progress/status
- show per-file success/failure
- one failed file must not cause the entire folder upload to silently fail
- prevent duplicate submissions where practical
- preserve the existing security model

The UI should make it obvious which files succeeded and which failed.

If browser limitations prevent true directory upload in the current frontend,
use the standard browser directory-upload mechanism rather than inventing a
custom client-side filesystem API.

---

# Part G — Regression testing

Add automated tests for:

### Delete

- successful deletion
- unauthorized deletion
- nonexistent document
- deletion of indexed document
- deletion does not affect another document
- cleanup of associated searchable state

### Folder upload

- multiple files
- nested directories if supported
- unsupported files
- oversized files
- malformed files
- partial failure
- filename/path sanitization
- authorization

### UI

Verify the new UI paths and JavaScript syntax.

Run the complete existing test suite.

The existing tests must remain green.

---

# Part H — Final report

At the end, report:

## Real-document test dataset

List every document used.

## UI test results

For each operation:

| Operation | UI result | Actual result | Pass/Fail |
|---|---|---|---|
| Upload | | | |
| Parse | | | |
| OCR | | | |
| Embed | | | |
| Index | | | |
| Search | | | |
| Ask | | | |
| Delete | | | |
| Folder upload | | | |

## Retrieval tests

List the actual questions asked and whether the application answered them
using the correct document evidence.

## Bugs discovered

For every defect:

- symptom
- reproduction steps
- root cause
- fix
- test added

## Important

Do not report "working" merely because an endpoint returned HTTP 200 or a UI
button displayed "success".

The acceptance criterion is that the resulting state and downstream behavior
actually work.

Do not consume external LLM/API credits unnecessarily.

Use local processing/provider wherever possible.

Stop after Task 028.

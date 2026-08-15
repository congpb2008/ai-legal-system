# Task 030 – Final Productization, UX Repair & Autonomous User Regression

## Objective

Turn the current Legal Platform MVP into a coherent, usable, responsive product
by fixing the actual problems discovered during the autonomous real-world
acceptance test.

This is the final productization task of the current development cycle.

Task 030 is NOT a cosmetic redesign.

The primary goal is:

    real documents
        ↓
    autonomous user uses the UI
        ↓
    failures / friction / broken controls identified
        ↓
    fix root causes
        ↓
    autonomous user repeats the workflow
        ↓
    verify that the real-world problems are actually resolved

Do not continue to Task 031 or any later task.

---

# 1. Read the Existing Evidence First

Before making changes, read:

- Task 025 – AI Runtime / Provider Integration
- Task 026 – Setup & Configuration Wizard
- Task 027 – Security & Production Configuration Hardening
- Task 028 – Autonomous Real-World User Acceptance Test
- Task 029 – Document Management / Bulk Ingestion
- Task 021 – Frontend Polish
- User Guide
- Admin Guide
- API Guide
- relevant architecture documents
- relevant contracts
- the autonomous acceptance-test report and artifacts

Task 028 is the primary source of truth for what is currently broken or
difficult to use.

Do not invent a new product workflow merely because it seems preferable.

Fix problems demonstrated by actual use first.

Do not silently modify contracts or architecture.

---

# 2. Treat the Application as a Real Product

The UI must be usable by a normal user who does NOT know:

- the backend architecture
- Python
- API endpoints
- vector databases
- embeddings
- OCR engines
- internal processing jobs
- filesystem paths
- provider implementation details

A user should not need to open a terminal merely to perform a normal
application operation.

The UI must communicate what is happening and what the user should do next.

---

# 3. Autonomous User Regression Is Mandatory

After making fixes, perform another autonomous real-world test.

The testing agent must behave as a normal user.

It must:

1. open the Web UI
2. navigate through the application visually
3. discover available functionality
4. upload real documents from the workspace
5. use the application's UI rather than directly calling backend APIs
6. process the documents
7. search them
8. ask questions
9. inspect citations/evidence
10. deliberately try difficult questions
11. test failure and empty states
12. delete documents where supported
13. retry failed operations
14. inspect whether the UI accurately reflects backend state

The testing agent must not assume that a button works merely because it exists.

A workflow is considered successful only when the visible result corresponds to
an actual backend state.

---

# 4. Fix Every Broken or Fake UI Control

Audit all visible interactive controls.

At minimum inspect:

- navigation
- login/logout
- setup wizard
- settings
- provider configuration
- vault creation
- vault selection
- document upload
- folder upload
- bulk upload
- document deletion
- document details
- parsing
- OCR
- embedding
- indexing
- re-parsing
- re-embedding
- re-indexing
- search
- Q&A
- refresh
- retry
- job status
- error recovery
- empty-state actions

For every visible control:

1. verify the frontend event handler
2. verify the API request
3. verify backend behavior
4. verify response handling
5. verify UI state update
6. verify loading state
7. verify error handling
8. verify the resulting state through the UI

There must be no knowingly fake buttons.

If functionality is unavailable:

- implement it if it is consistent with the existing architecture, or
- remove/hide the control and clearly document the limitation.

Never leave a button that appears functional but does nothing.

---

# 5. Processing Must Represent Actual State

Processing operations include:

- Parse
- OCR
- Embed
- Index
- Re-parse
- Re-embed
- Re-index

The UI must distinguish between:

- Not processed
- Queued
- Processing
- Completed
- Failed

A successful HTTP response must NOT automatically mean the operation is
complete if the operation is asynchronous.

Where supported, show:

- current status
- last execution time
- failure reason
- resulting state
- retry action

If a processing operation does not actually perform the expected work, fix the
root cause rather than changing the UI to claim success.

---

# 6. Document Ingestion Must Be Practical

The normal workflow should be:

    Select documents/folder
          ↓
    Upload
          ↓
    Documents appear
          ↓
    Metadata is populated sensibly
          ↓
    Processing begins or can be started
          ↓
    Processing status becomes visible
          ↓
    Documents become searchable
          ↓
    Documents become usable for Q&A

Do not require users to manually repeat identical metadata entry for every file
when the same metadata can safely be applied to a batch.

Support bulk/folder ingestion if Task 029 provides it.

Show per-file status during bulk operations.

Handle:

- success
- failure
- retry
- unsupported file type
- oversized file
- duplicate files
- partial batch failure

Existing upload security from Task 027 must remain intact.

---

# 7. Metadata UX

Metadata must be understandable to a normal user.

Use sensible defaults where safe.

Do not invent legal metadata.

If metadata is optional, do not unnecessarily make it mandatory.

If metadata is required, explain why.

If metadata can be automatically inferred from the document, use the existing
architecture to do so rather than forcing unnecessary manual entry.

The autonomous acceptance test should be used to determine whether the current
metadata workflow is actually practical.

---

# 8. Document Management

The document list must clearly expose:

- document name/title
- type
- relevant metadata
- processing status
- searchable/indexed status
- processing errors
- available actions

Destructive actions require confirmation.

Deletion must be real.

If a document is deleted, verify that associated searchable/indexed state is
also removed according to the application's architecture.

After deletion, the UI must immediately reflect the new state.

---

# 9. Search UX

Search must provide clear feedback.

Required states:

- idle
- searching
- results
- no results
- error

Results should expose useful information such as:

- result count where available
- document identity
- title
- relevant snippet/evidence
- citation/source information

An empty result must not look like a broken application.

Where possible distinguish between:

- no matching evidence
- documents not yet processed
- search failure
- temporary server failure

Do not expose internal implementation details.

---

# 10. Q&A UX

The Q&A interface must communicate that answers are evidence-grounded.

The user workflow should be:

    Ask question
        ↓
    Loading
        ↓
    Answer
        ↓
    Evidence / citations
        ↓
    Source document

The UI must clearly handle:

- successful answer
- insufficient evidence
- no relevant documents
- provider failure
- generation failure
- search failure
- timeout

Do not make an unsupported answer appear authoritative.

Do not hide uncertainty.

---

# 11. Evidence and Citation UX

When an answer contains evidence:

- identify the source document
- show the relevant evidence/snippet where supported
- make citations understandable
- allow the user to distinguish generated text from source material

The user should be able to verify an answer against the original document.

Do not fabricate citations.

Do not display a citation as valid merely because a document ID exists.

---

# 12. Setup and Settings

Review the setup wizard and settings as a non-technical user.

The UI should explain:

- Local provider
- Cloud provider
- endpoint
- API key
- model
- connection testing
- saving configuration

Do not use unnecessary vendor branding.

Never display the saved API key.

Never put credentials into:

- URLs
- frontend source
- logs
- error messages
- API responses

Existing security constraints from Task 027 remain mandatory.

---

# 13. Loading and Async UX

Every asynchronous operation must communicate activity.

At minimum:

- login
- provider connection test
- configuration save
- upload
- folder upload
- deletion
- parsing
- OCR
- embedding
- indexing
- search
- Q&A
- bulk operations

Prevent duplicate submissions.

Do not freeze unrelated parts of the UI.

Where operations are long-running, provide meaningful progress/status
information if the backend supports it.

---

# 14. Error UX

Errors must answer two questions:

1. What went wrong?
2. What can I do now?

Examples:

Instead of:

    500 Internal Server Error

prefer:

    "The document could not be processed.
     Try again. If the problem persists, check the server status."

Technical diagnostics remain available to operators/logs.

Never expose:

- stack traces
- API keys
- credentials
- internal filesystem paths
- sensitive exception details

---

# 15. Empty States

Every major empty state must provide context and an obvious next action.

Examples:

### No vaults

Explain how to create the first vault.

### No documents

Provide an upload action.

### No search results

Explain that no matching evidence was found.

### No processed documents

Explain that documents need processing before they can be searched.

### No Q&A evidence

Explain that the available documents do not contain enough evidence.

Avoid blank pages.

---

# 16. Responsive UI

Verify the entire application at:

- desktop
- laptop
- tablet
- mobile-width browser

Check:

- navigation
- sidebar
- forms
- upload interface
- document list
- document cards
- processing controls
- search
- Q&A
- setup wizard
- settings
- dialogs
- alerts

At narrow widths:

- avoid unnecessary horizontal scrolling
- stack controls
- preserve readable text
- ensure buttons remain usable
- ensure dialogs fit
- prevent overflowing tables/cards
- keep primary actions visible

Do not simply scale down the desktop layout.

---

# 17. Accessibility Pass

Verify:

- keyboard navigation
- visible focus
- form labels
- meaningful button names
- semantic headings
- readable contrast
- accessible error messages
- predictable dialogs
- no essential information conveyed only through color

Do not add unnecessary dependencies.

---

# 18. UX Consistency

Standardize:

- buttons
- status badges
- forms
- spacing
- typography
- cards
- alerts
- dialogs
- loading indicators
- navigation

Prefer clarity and consistency over decorative redesign.

Do not redesign the product into an unrelated visual identity.

---

# 19. Root-Cause Rule

When the autonomous user discovers a problem, determine whether the failure is:

- frontend
- API integration
- backend
- processing pipeline
- persistence
- state synchronization
- configuration
- provider integration

Fix the root cause at the correct layer.

Do NOT implement a frontend workaround for a backend failure.

Do NOT make the UI report success when the underlying operation failed.

---

# 20. Regression Against Real Documents

Use the same real documents and corpus used by Task 028.

The autonomous user must repeat meaningful workflows.

At minimum:

### Ingestion

- discover documents
- upload them through the UI
- verify they appear

### Processing

- parse
- OCR where applicable
- embed
- index
- re-run processing where supported

### Retrieval

- search for information known to exist
- search using paraphrased queries
- search for numbers/names/legal terms
- verify results against the original documents

### Q&A

Ask questions generated from the actual document contents.

Include:

- simple factual questions
- cross-document questions
- paraphrased questions
- questions involving numbers/dates
- questions requiring evidence comparison
- questions whose answers are NOT present

### Negative tests

Ask questions for which the corpus has no evidence.

The system should avoid inventing unsupported answers.

---

# 21. Autonomous Test Generation

The testing agent must not rely exclusively on a hard-coded question list.

It should:

1. inspect the real corpus
2. understand the documents sufficiently to construct testable claims
3. generate questions from those claims
4. use the UI to ask those questions
5. compare the application's answer/evidence against the source documents

The agent may use the source documents as ground truth, but must not inject
the expected answer directly into the application's request.

This distinction is mandatory:

    Source documents
        ↓
    Ground-truth understanding

versus

    Web UI
        ↓
    Actual application behavior

The application must earn the answer.

---

# 22. Adversarial AI Testing

The autonomous user should deliberately test difficult cases.

Examples:

- paraphrased questions
- vague but reasonable questions
- cross-document questions
- numeric questions
- questions about exceptions
- questions where two documents appear related
- questions with misleading wording
- questions for information absent from the corpus
- questions likely to trigger hallucination

Evaluate:

- retrieval quality
- answer correctness
- evidence quality
- citation correctness
- refusal/uncertainty behavior

---

# 23. Final Autonomous Regression

After all fixes:

Run the complete workflow from a clean user perspective.

The agent should NOT rely on implementation knowledge.

It should discover the workflow through the UI.

Record:

- every click/action
- visible result
- expected result
- actual result
- failures
- recovery attempts

The test is successful only when the visible UI and actual application state
agree.

---

# 24. Automated Tests

Add or update regression tests for meaningful fixes.

At minimum:

- frontend JavaScript syntax
- API regressions
- upload regressions
- deletion regressions
- processing-state regressions
- search regressions
- Q&A regressions
- setup/settings regressions
- relevant security regressions

Run the complete existing test suite.

Do not weaken existing tests.

---

# 25. Final Acceptance Report

Produce a concise but evidence-based report.

## A. Broken controls fixed

List every previously non-functional control that was fixed.

## B. Workflow improvements

Describe the before/after user experience.

## C. Real-document ingestion

Report whether real documents can be:

- uploaded
- bulk uploaded
- processed
- reprocessed
- deleted

## D. Retrieval

Report:

- search success rate
- important failures
- evidence quality
- citation quality

Do not invent numerical metrics if insufficient test cases exist.

## E. Q&A

Report:

- factual answers
- cross-document answers
- unsupported questions
- hallucinations
- evidence/citation failures

## F. Responsive testing

Report desktop/tablet/mobile results.

## G. Accessibility

Report checks performed.

## H. Remaining limitations

List every known limitation honestly.

## I. Final verdict

Choose exactly one:

### READY FOR MVP DEMO

Core workflows are functional and coherent.

### USABLE MVP WITH LIMITATIONS

Core workflows work but known limitations remain.

### NOT READY

Important workflows remain broken.

---

# Constraints

- Do not continue to Task 031 or any later task.
- Do not redesign the architecture.
- Do not silently change contracts.
- Do not invent unsupported providers.
- Do not introduce vendor-specific integrations.
- Do not expose secrets.
- Do not weaken security.
- Do not fabricate successful behavior.
- Do not mark an operation successful merely because an HTTP request returned
  200.
- Do not remove functionality merely to make tests pass.
- Do not use backend shortcuts when performing the autonomous UI acceptance test.
- Prefer root-cause fixes.
- Preserve existing working functionality.

Stop when Task 030 is complete.

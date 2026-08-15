Implement Task 023 — End-to-End QA.

You are implementing exactly Task 023.
Do not continue to Task 024 or any later task.

This task is primarily a validation and QA task.

Do NOT begin by changing code.

==================================================
ROLE
==================================================

You are no longer the project author.

Act as a completely new user/operator who has never seen this project before.

You must evaluate whether the current project can actually be used from a clean environment using only:

- the repository;
- the published documentation;
- the documented configuration;
- the documented startup procedure;
- the Web UI.

Do not rely on knowledge from previous tasks.

Do not assume undocumented behavior.

Do not inspect source code merely because it is easier.

If you need to inspect source code to understand or bypass something, record that as a QA finding.

==================================================
AUTHORITATIVE SOURCES
==================================================

Before testing, read:

1. .project_context.md
2. Task 023 specification
3. README
4. User Guide
5. Admin Guide
6. API Guide where relevant
7. Task 020 packaging/startup documentation
8. Task 021 frontend documentation/implementation
9. Relevant deployment documentation

Do not modify these documents before the initial QA run.

==================================================
CLEAN ENVIRONMENT
==================================================

Where practical, perform the test from a clean environment.

Prefer:

- a fresh virtual environment;
- a clean working directory;
- a fresh database/storage state;
- no undocumented environment variables;
- no manually configured PYTHONPATH.

Do not reuse hidden setup from previous development sessions.

If a completely isolated environment is impossible, clearly document what was reused.

==================================================
PHASE 1 — INSTALLATION
==================================================

Follow the installation documentation literally.

Verify:

- prerequisites;
- installation;
- dependency installation;
- package installation;
- configuration;
- initialization.

Do not invent missing commands.

If a documented command fails:

1. record the exact failure;
2. record the documented step;
3. determine whether the failure is caused by the software or documentation;
4. only then attempt a reasonable diagnostic.

Do not silently work around failures.

==================================================
PHASE 2 — STARTUP
==================================================

Follow the canonical startup procedure from Task 020.

Verify:

- application starts;
- no PYTHONPATH is required;
- startup command is reproducible;
- expected port is used;
- health endpoint works if documented;
- Web UI is reachable;
- startup errors are understandable.

Verify that the documented stop procedure works.

Test startup from outside the backend source directory where applicable.

==================================================
PHASE 3 — WEB UI
==================================================

Open the application through the browser.

Do not use the API as a substitute for the Web UI unless the documentation explicitly requires it.

Verify:

- login;
- initial page;
- navigation;
- vault management;
- document management;
- upload;
- document status;
- search;
- question answering;
- citations;
- logout/session behavior.

For each flow verify:

- happy path;
- loading state;
- empty state;
- validation failure;
- server/API failure where reasonably testable.

Record anything that is confusing or requires undocumented knowledge.

==================================================
PHASE 4 — REALISTIC USER FLOW
==================================================

Use a small realistic sample dataset.

At minimum:

- one valid document;
- one document that exercises a meaningful edge case if supported;
- realistic metadata.

Follow the documented workflow exactly.

Perform:

    Login
      ↓
    Create/select vault
      ↓
    Upload document
      ↓
    Observe document state
      ↓
    Search
      ↓
    Ask a question
      ↓
    Inspect answer
      ↓
    Inspect citations
      ↓
    Return to document
      ↓
    Logout

Do not claim that a pipeline works merely because an endpoint exists.

Verify actual behavior.

If the MVP intentionally does not automate part of the pipeline, verify that the UI and documentation communicate this accurately.

==================================================
PHASE 5 — DOCUMENTATION FIDELITY
==================================================

For every important workflow compare:

DOCUMENTATION

against

ACTUAL APPLICATION BEHAVIOR.

Record:

- incorrect instructions;
- missing steps;
- incorrect URLs;
- incorrect commands;
- incorrect UI labels;
- missing prerequisites;
- misleading descriptions;
- undocumented limitations;
- undocumented errors.

The documentation must not require the user to inspect source code.

==================================================
PHASE 6 — RESPONSIVE UI
==================================================

Check the Web UI at:

- desktop;
- laptop;
- tablet/narrow viewport;
- mobile/narrow browser viewport.

Look for:

- horizontal overflow;
- clipped controls;
- unreadable text;
- broken navigation;
- unusable forms;
- overflowing tables;
- inaccessible buttons.

Record defects.

==================================================
PHASE 7 — ERROR HANDLING
==================================================

Intentionally test reasonable failures.

Examples:

- invalid login;
- missing required field;
- invalid upload;
- duplicate action;
- unavailable backend;
- malformed request where accessible through the UI;
- empty search;
- question with no available evidence.

Verify that the user receives an understandable response.

The UI must not expose:

- stack traces;
- Python exceptions;
- internal filesystem paths;
- internal module names;
- secrets;
- raw database errors.

==================================================
PHASE 8 — DATA INTEGRITY
==================================================

Verify that normal user operations do not unexpectedly:

- duplicate documents;
- lose documents;
- lose vault associations;
- lose metadata;
- produce inconsistent states.

Do not perform destructive tests unless the specification explicitly permits them.

==================================================
PHASE 9 — TEST SUITE
==================================================

Run the complete automated test suite.

Record:

- total tests;
- passed;
- failed;
- skipped;
- errors.

If failures exist, determine whether they are:

- pre-existing;
- caused by recent tasks;
- environment-specific;
- genuine regressions.

Do not modify tests merely to make the suite pass.

==================================================
BUG CLASSIFICATION
==================================================

Classify every finding.

BLOCKER
---------
The user cannot install, start, authenticate, or perform a core workflow.

CRITICAL
--------
A core workflow is technically possible but seriously broken or data integrity/security is at risk.

MAJOR
------
A significant user workflow is broken or misleading, but a workaround exists.

MINOR
-----
Cosmetic, usability, or documentation issue that does not block normal use.

TRIVIAL
-------
Low-impact polish issue.

For every bug provide:

- ID
- severity
- reproduction steps
- expected behavior
- actual behavior
- evidence
- likely cause
- recommended owner/task

Do not invent root causes when the evidence does not establish them.

==================================================
FIX POLICY
==================================================

Do NOT automatically fix every problem you discover.

First complete the QA pass.

Then determine whether a fix is explicitly within Task 023 scope.

Task 023 may fix small, clearly isolated regressions discovered during QA if doing so does not change architecture, contracts, or product behavior.

For larger issues:

- record them;
- do not redesign the system;
- do not implement Task 024;
- do not silently expand scope.

If a problem requires specification or architecture changes, stop and report it.

==================================================
REGRESSION TESTS
==================================================

For every fixed bug:

1. reproduce the bug;
2. apply the minimal fix;
3. add a regression test where appropriate;
4. rerun the relevant test;
5. rerun the full test suite.

Do not weaken existing tests.

==================================================
FINAL QA REPORT
==================================================

Create a dedicated QA report.

Use a clear location such as:

docs/qa/task-023-e2e-report.md

The report must contain:

# Task 023 — End-to-End QA Report

## Environment

- OS
- Python version
- browser
- installation method
- deployment/startup method

## Test Scope

Describe exactly what was tested.

## Installation Result

PASS / FAIL

## Startup Result

PASS / FAIL

## Web UI Result

PASS / FAIL

## Core User Flow

For each step:

- Login
- Vault
- Upload
- Document state
- Search
- Question answering
- Citations
- Logout

record PASS / FAIL and notes.

## Responsive UI

PASS / FAIL

## Error Handling

PASS / FAIL

## Documentation Fidelity

PASS / FAIL

## Automated Tests

Record exact results.

## Bugs

Provide a severity-classified table.

## Fixes Made

List only changes actually made during Task 023.

## Remaining Issues

List all unresolved issues.

## Release Readiness

Give one of:

NOT READY
READY WITH BLOCKERS
READY WITH MINOR ISSUES
READY

Do not declare READY if a core user workflow is broken.

==================================================
FINAL VERIFICATION
==================================================

After any permitted fixes:

1. Run the complete test suite.
2. Repeat every previously failing workflow.
3. Verify the Web UI again.
4. Verify installation/startup again if packaging was affected.
5. Confirm no regressions were introduced.

At the end, report:

- total E2E scenarios;
- passed;
- failed;
- blockers;
- critical issues;
- major issues;
- minor issues;
- fixes made;
- remaining issues;
- release-readiness status.

Do not continue to Task 024.

Stop when Task 023 is complete.

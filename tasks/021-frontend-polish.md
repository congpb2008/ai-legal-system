Implement Task 021 — Frontend Polish.

You are implementing exactly Task 021.
Do not continue to Task 022 or any later task.

==================================================
BEFORE MAKING CHANGES
==================================================

Read:

1. .project_context.md
2. The Task 021 specification
3. All relevant architecture documents
4. Relevant ADRs
5. Relevant contracts
6. The existing Web UI implementation
7. The API implementation that the Web UI consumes
8. Existing frontend tests
9. Existing UI/UX-related documentation and examples
10. The result of the previous documentation/first-user audit

The repository specifications are authoritative.

Do NOT redesign the product.
Do NOT invent new user workflows.
Do NOT replace the Web UI with a CLI.
Do NOT introduce a desktop application.
Do NOT change backend contracts merely to make the frontend easier to implement.

The intended product is a browser-based Web UI for normal users.

==================================================
TASK 021 — FRONTEND POLISH
==================================================

The goal is to make the existing Web UI usable as a normal client.

This is a polish and completion task, not a product redesign.

Inspect the current UI first and determine what is already implemented.

Then ensure that the existing intended user flows work coherently from the browser.

At minimum, verify the flows that are actually supported by the current backend:

- opening the application;
- authentication/login;
- navigating the application;
- viewing/managing available vaults;
- creating a vault where supported;
- uploading a document;
- viewing document state;
- searching;
- asking a question;
- viewing an answer;
- viewing citations where supported;
- handling unavailable/empty results.

Do not add functionality that is not supported by the backend.

==================================================
UI STATES
==================================================

Every existing user-facing operation should have appropriate states.

Implement or fix:

1. Loading states

Users must understand that an operation is in progress.

Avoid frozen-looking interfaces.

2. Empty states

When there are no:

- documents;
- vaults;
- search results;
- answers/results;

show a clear explanation and, where appropriate, the next useful action.

3. Error states

API failures, authentication failures, invalid input, unavailable services, and failed operations must produce understandable messages.

Do not expose raw Python exceptions, stack traces, or internal implementation details to normal users.

4. Success states

Successful operations should provide clear confirmation and update the relevant UI state.

5. Disabled states

Buttons should not allow duplicate submissions while an operation is already running.

==================================================
USER EXPERIENCE
==================================================

Keep the interface simple.

The primary audience is a normal user, not a developer.

Users should not need to know:

- Python;
- FastAPI;
- REST;
- database internals;
- vector indexes;
- embeddings;
- chunking;
- backend module names.

Do not expose implementation details unless they are genuinely useful to the user.

Use terminology already established by the project specifications.

Do not rename domain concepts merely for stylistic reasons.

==================================================
NAVIGATION
==================================================

Review the current navigation structure.

Ensure that:

- every visible navigation item leads somewhere meaningful;
- there are no dead links;
- the current page/state is understandable;
- users can return to the relevant previous context;
- authentication state is handled consistently.

Do not create a large navigation system if the existing application does not require one.

Keep the UI focused on the actual product workflows.

==================================================
FORMS
==================================================

Review all existing forms.

Ensure:

- required fields are obvious;
- invalid input is explained;
- validation happens before submission where appropriate;
- server-side validation errors are displayed clearly;
- successful submission does not leave stale form state;
- duplicate submissions are prevented.

Do not invent validation rules that contradict the backend contracts.

==================================================
SEARCH AND ANSWERING
==================================================

Pay particular attention to the two primary user workflows:

Search:

    User enters query
        ↓
    Search
        ↓
    Loading state
        ↓
    Results / empty state / error

Question answering:

    User asks question
        ↓
    Loading state
        ↓
    Answer
        ↓
    Citations / supporting information
        ↓
    Error or empty state when applicable

The UI must accurately represent what the backend actually returns.

Do not fabricate citations, confidence scores, processing states, or answer metadata.

==================================================
DOCUMENT PROCESSING
==================================================

The current MVP may not automatically execute the complete processing pipeline after upload.

Respect the actual backend behavior.

If a document is uploaded but not yet searchable because processing is incomplete or not automated:

- make that state understandable to the user;
- do not imply that indexing has completed;
- do not pretend search should already return the document.

Use the actual processing/status information exposed by the backend.

==================================================
RESPONSIVE DESIGN
==================================================

Make the existing Web UI usable at:

- desktop width;
- laptop width;
- tablet width;
- narrow/mobile browser width.

Do not redesign the application specifically as a mobile app.

Prioritize usability and readable content.

Avoid:

- horizontal overflow;
- clipped buttons;
- unusably narrow forms;
- overflowing tables;
- inaccessible navigation.

==================================================
ACCESSIBILITY
==================================================

Where practical, improve basic accessibility:

- semantic elements;
- labels for form controls;
- keyboard-accessible controls;
- visible focus states;
- meaningful button text;
- readable contrast;
- appropriate aria attributes where necessary.

Do not introduce an accessibility framework unless the existing project already uses one.

==================================================
VISUAL CONSISTENCY
==================================================

Review the existing UI for:

- inconsistent spacing;
- inconsistent typography;
- inconsistent button styles;
- inconsistent form controls;
- inconsistent status indicators;
- duplicated styling;
- obvious layout defects.

Prefer the project's existing design language.

Do not introduce a completely new visual identity.

Do not spend this task creating elaborate animations or decorative effects.

The objective is clarity and reliability.

==================================================
API INTEGRATION
==================================================

Inspect the actual API contracts before changing frontend requests.

Ensure the frontend:

- sends the correct request shape;
- handles authentication correctly;
- handles API errors correctly;
- handles loading states;
- handles empty responses;
- does not assume fields that the API does not provide.

Do not change API contracts unless an existing specification explicitly requires it.

If an API mismatch is discovered:

1. determine whether the frontend or backend is incorrect according to the specification;
2. fix the implementation that violates the specification;
3. do not silently redefine the contract.

==================================================
TESTING
==================================================

Before changes:

- run the existing test suite;
- inspect existing frontend tests;
- record the baseline.

After changes:

- run all existing tests;
- add appropriate frontend tests;
- test the primary user flows;
- test loading states;
- test empty states;
- test error states;
- test form validation;
- test responsive layouts where the existing test setup supports it.

Do not remove or weaken tests to make them pass.

If browser/e2e testing infrastructure exists, use it.

If it does not exist, do not spend the entire task building a new testing framework unless required by the specifications.

==================================================
SCOPE CONTROL
==================================================

Do NOT:

- implement Task 022 Documentation;
- implement Task 023 End-to-End QA;
- implement Task 024 Release;
- redesign the backend architecture;
- replace the Web UI with CLI;
- add desktop application support;
- add unrelated features;
- change contracts merely for convenience.

Task 021 is specifically about making the existing browser UI a coherent, usable client.

==================================================
FINAL VERIFICATION
==================================================

At the end, report:

1. Existing frontend state before implementation.
2. What UI components/pages were changed.
3. What user flows were verified.
4. Loading states implemented/fixed.
5. Empty states implemented/fixed.
6. Error states implemented/fixed.
7. Responsive issues fixed.
8. Accessibility improvements made.
9. Tests before implementation.
10. Tests after implementation.
11. Any backend limitations that still affect the UI.
12. Any issues that should be handled by Task 022 or Task 023.

Do not continue to another task.

Stop when Task 021 is complete.

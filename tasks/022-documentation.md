Implement Task 022 — Documentation.

You are implementing exactly Task 022.
Do not continue to Task 023 or any later task.

==================================================
BEFORE WRITING
==================================================

Read the repository first.

Read:

1. .project_context.md
2. The Task 022 specification
3. All relevant ADRs
4. Architecture documents
5. Contracts
6. Module specifications
7. Current backend implementation
8. Current frontend implementation
9. Task 020 implementation and startup/packaging changes
10. Task 021 implementation and current Web UI
11. Existing README and documentation
12. The previous documentation audit / first-user QA report
13. Existing API routes and their actual request/response behavior

The repository and specifications are authoritative.

Documentation must describe the software that actually exists.

Do NOT invent functionality.

Do NOT document planned features as implemented.

Do NOT redesign the architecture.

Do NOT modify backend or frontend behavior merely to make documentation easier to write.

If documentation conflicts with implementation:

1. Check the specifications/contracts first.
2. Determine which implementation behavior is authoritative.
3. If the implementation violates the specification, report it.
4. Do not silently redefine the specification.

==================================================
TASK 022 — DOCUMENTATION
==================================================

Produce a complete documentation set for the current v0.1 candidate.

The documentation must serve four audiences:

1. New users
2. Administrators/operators
3. API consumers
4. Developers

Create/update:

docs/user-guide/en/
docs/user-guide/vi/

docs/admin-guide/en/
docs/admin-guide/vi/

docs/api-guide/en/
docs/api-guide/vi/

docs/developer-guide/en/
docs/developer-guide/vi/

Also update the repository README where necessary.

Keep the existing developer documentation/specification documents intact unless they are explicitly intended to be user-facing documentation.

==================================================
1. README
==================================================

The README is the project's entry point.

It should explain:

- what the project is;
- what problem it solves;
- the intended users;
- the high-level capabilities currently implemented;
- current project status;
- prerequisites;
- installation;
- canonical startup method;
- how to open the Web UI;
- where to find detailed documentation;
- known MVP limitations.

The README must not advertise features that are not implemented.

Keep the README concise.

Do not turn it into the full User Guide.

==================================================
2. USER GUIDE
==================================================

The User Guide is for a normal person using the application through a browser.

Do NOT assume the user is a developer.

Cover the actual implemented workflows.

At minimum, document where applicable:

- first-time access;
- login/authentication;
- navigating the Web UI;
- vault/document organization;
- creating or selecting a vault;
- uploading documents;
- viewing document status;
- searching;
- asking questions;
- reading answers;
- understanding citations;
- empty states;
- processing states;
- errors;
- logout/session behavior.

For every major workflow explain:

1. What it does.
2. When to use it.
3. Steps to perform it.
4. What the user should see.
5. What can go wrong.
6. What to do if it fails.

Use terminology from the existing UI.

Do not expose internal implementation terminology unless necessary.

Do not tell normal users to use curl, Python, PYTHONPATH, SQLite, or internal modules unless the operation genuinely requires it.

==================================================
3. ADMIN GUIDE
==================================================

The Admin Guide is for the person responsible for operating the deployment.

Document only capabilities that actually exist.

Cover:

- installation;
- configuration;
- environment variables;
- starting the service;
- stopping the service;
- service health;
- logs;
- storage;
- data locations;
- backup considerations;
- restore considerations;
- updating the application;
- authentication configuration;
- operational limitations;
- troubleshooting;
- known MVP limitations.

Clearly distinguish:

IMPLEMENTED

from:

NOT YET IMPLEMENTED

Do not invent production-grade operational features.

If backup/restore is not implemented, document what currently exists and explicitly state the limitation.

==================================================
4. API GUIDE
==================================================

Document the actual API exposed by the current implementation.

For each public endpoint include:

- HTTP method;
- path;
- purpose;
- authentication requirements;
- request headers;
- request body;
- parameters;
- response body;
- important response fields;
- error responses;
- example request;
- example response.

Use examples that can actually be executed against the current implementation.

Do not invent endpoints.

Do not document internal Python functions as public API.

Clearly separate:

- public API;
- internal implementation interfaces.

If an endpoint is experimental or incomplete, state that.

==================================================
5. DEVELOPER GUIDE
==================================================

Create developer-facing documentation for someone who wants to work on the existing project.

Cover:

- repository structure;
- development environment;
- installation;
- running tests;
- running the application;
- frontend development;
- backend development;
- API structure;
- module boundaries;
- contracts;
- adding/changing modules;
- configuration;
- debugging;
- test conventions;
- packaging;
- common development problems.

Respect the existing architecture.

Do not replace or contradict the existing developer-guide.md.

Where an existing specification already provides authoritative architectural information, link/reference it rather than duplicating large amounts of content.

==================================================
6. QUICK START
==================================================

Create a genuinely usable Quick Start.

A new user should be able to:

1. install the project;
2. start it;
3. open the Web UI;
4. authenticate;
5. perform the first meaningful operation.

Do not use undocumented commands.

Do not require manual PYTHONPATH manipulation.

Use the canonical startup procedure established by Task 020.

If the current MVP cannot complete a full document → retrieval → answer pipeline automatically, explain that explicitly.

Do not pretend that a feature works merely because an API endpoint exists.

==================================================
7. TROUBLESHOOTING
==================================================

Create practical troubleshooting sections.

Cover actual problems discovered during the previous first-user audit, including where applicable:

- Python environment problems;
- missing dependencies;
- installation failures;
- startup failures;
- port conflicts;
- authentication problems;
- upload failures;
- empty search results;
- unavailable processing;
- API errors;
- frontend loading failures.

For each issue:

Symptoms
→ Cause
→ Resolution

Do not document speculative problems as known problems.

==================================================
8. LANGUAGE
==================================================

Produce both English and Vietnamese documentation.

The two versions must describe the same behavior.

Do not mechanically translate technical terms.

Preserve established technical terminology where appropriate, for example:

- API
- Backend
- Frontend
- Vault
- Document
- OCR
- Parser
- Embedding
- Retrieval
- Reranker
- Citation
- Vector Index

Use natural Vietnamese around those terms.

Do not translate domain terminology in a way that changes its meaning.

==================================================
9. SCREENSHOTS / VISUALS
==================================================

If screenshots already exist, use them where appropriate.

If screenshots are required but cannot be generated in the current environment:

- add clearly marked screenshot placeholders;
- specify exactly which screen/state should be captured;
- do not fabricate screenshots.

Prioritize useful screenshots of:

- login;
- main navigation;
- vault/document management;
- upload;
- search;
- answer/citations.

==================================================
10. DOCUMENTATION QUALITY
==================================================

Every command shown in documentation must be checked against the current repository.

Every API example must match the actual API.

Every UI instruction must match the current UI.

Every feature claim must be supported by the implementation.

Avoid statements such as:

"the system will..."

when the feature is only planned.

Prefer:

"The current MVP..."

when behavior is intentionally limited.

==================================================
11. DOCUMENTATION AUDIT
==================================================

Before finishing, perform a final consistency audit.

Check:

- README vs implementation;
- User Guide vs Web UI;
- Admin Guide vs actual deployment;
- API Guide vs actual API;
- Developer Guide vs repository;
- English vs Vietnamese;
- documentation vs contracts;
- documentation vs ADRs;
- documentation vs Task 020;
- documentation vs Task 021.

Identify contradictions.

Fix documentation contradictions where the authoritative implementation/specification is clear.

If something cannot be resolved without changing code/specification:

STOP and report it instead of inventing an answer.

==================================================
12. TESTING
==================================================

Run the existing test suite before and after documentation changes.

Documentation changes must not break the software.

If the project has documentation linting or link checking, run it.

Check internal documentation links.

Check that referenced files and commands actually exist.

Do not modify tests merely to make them pass.

==================================================
SCOPE CONTROL
==================================================

Do NOT:

- implement Task 023;
- perform the final end-to-end QA;
- create the final release;
- create Docker release artifacts unless already required by Task 020;
- add new application features;
- redesign the UI;
- modify contracts;
- modify ADRs.

If you discover a software bug while writing documentation, report it separately.

Do not silently implement unrelated fixes.

==================================================
FINAL REPORT
==================================================

At the end report:

1. Documentation files created.
2. Documentation files updated.
3. README changes.
4. User Guide coverage.
5. Admin Guide coverage.
6. API Guide coverage.
7. Developer Guide coverage.
8. English/Vietnamese coverage.
9. Documentation inconsistencies discovered.
10. Any unresolved documentation gaps.
11. Tests run and results.
12. Any software issues discovered but intentionally left for Task 023 or later.

Do not continue to Task 023.

Stop when Task 022 is complete.

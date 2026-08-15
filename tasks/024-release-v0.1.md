Implement Task 024 — Release v0.1.

This is the final task in the current implementation roadmap.

Do not introduce new product features.
Do not redesign the architecture.
Do not continue to another task.

The objective is to package the current project into a coherent, reproducible v0.1 release.

==================================================
RELEASE PRINCIPLE
==================================================

This is a RELEASE task, not a development task.

The release must represent the software that actually exists.

Do not:

- invent features;
- add speculative functionality;
- redesign existing modules;
- change contracts for convenience;
- rewrite architecture;
- hide known limitations;
- modify QA results to make the release appear healthier.

If a release blocker is discovered, report it and stop rather than silently changing scope.

==================================================
BEFORE MAKING CHANGES
==================================================

Read:

1. .project_context.md
2. Task 024 specification
3. README
4. All relevant architecture documents
5. Relevant ADRs
6. Relevant contracts
7. Current implementation
8. Task 020 results
9. Task 021 results
10. Task 022 documentation
11. Task 023 E2E QA report
12. Current test suite
13. Existing packaging/deployment configuration
14. Existing version information
15. Existing Git state/history if available

Treat the Task 023 QA report as the primary release-readiness evidence.

==================================================
PHASE 1 — RELEASE GATE
==================================================

Before creating release artifacts, determine whether the project is actually releaseable.

Check the Task 023 report.

If it contains:

- unresolved BLOCKER issues;
- unresolved CRITICAL issues;
- broken installation;
- broken startup;
- broken authentication;
- broken core Web UI workflow;
- failing mandatory tests;

do NOT declare the project release-ready.

Do not hide these issues.

Produce a Release Blocker Report and stop if necessary.

Minor known issues may remain if Task 023 explicitly considers them acceptable for v0.1.

==================================================
PHASE 2 — VERSION
==================================================

Establish a single canonical version:

    0.1.0

Use the project's existing versioning mechanism.

Do not create multiple conflicting version sources.

Update version metadata only where the project's packaging architecture requires it.

Verify that the application reports the same version where applicable.

==================================================
PHASE 3 — CHANGELOG
==================================================

Create or update:

CHANGELOG.md

Document the v0.1.0 release.

Organize it into appropriate sections such as:

- Added
- Changed
- Fixed
- Known Limitations

Only document changes that actually exist.

Do not generate marketing claims.

Include the major implemented capabilities from the current roadmap, but keep the description factual.

Known limitations discovered during Task 023 must be explicitly listed.

==================================================
PHASE 4 — RELEASE NOTES
==================================================

Create:

docs/release-notes/v0.1.0.md

Include:

- release overview;
- what is included;
- major capabilities;
- installation;
- startup;
- Web UI access;
- basic first-use flow;
- known limitations;
- compatibility requirements;
- testing status;
- upgrade notes if relevant.

The release notes must be understandable without reading the entire repository.

Do not duplicate the entire User Guide.

Link to the relevant documentation where appropriate.

==================================================
PHASE 5 — DEMO DATASET
==================================================

Create a small, deterministic demo dataset suitable for demonstrating the application.

It should contain realistic but fictional/sample data.

Do NOT use:

- real personal information;
- confidential information;
- copyrighted proprietary documents;
- credentials;
- API keys;
- production data.

The dataset should demonstrate the core intended workflow.

Include enough sample data to make the application useful during a demo.

Where appropriate include:

- sample documents;
- realistic metadata;
- sample vault configuration;
- representative queries/questions.

Document exactly how to load or use the demo dataset.

If the current application cannot automatically import a dataset, document the manual procedure instead.

Do not implement a new import system merely for this task.

==================================================
PHASE 6 — SAMPLE DOCUMENTS
==================================================

Create sample documents appropriate for the legal-document use case.

They must be clearly fictional.

Use realistic structure such as:

- title;
- issuing authority;
- dates;
- articles/sections;
- clauses;
- metadata.

Make the documents useful for testing:

- upload;
- search;
- retrieval;
- citations;
- question answering;

to the extent those capabilities are actually implemented.

Do not claim that a sample demonstrates a pipeline stage that the current MVP does not execute.

==================================================
PHASE 7 — DOCKER / DISTRIBUTION
==================================================

Inspect the deployment architecture and Task 020 implementation.

If Docker is part of the specified distribution architecture:

- verify the Dockerfile;
- verify the build;
- verify the runtime entrypoint;
- verify required configuration;
- verify exposed ports;
- verify that the container starts successfully.

If Docker is NOT part of the specified architecture:

do not introduce Docker solely because this task mentions distribution.

The task must follow the existing deployment architecture.

If a Docker image is required by the project specification, build it using the canonical version/tag:

    <project-name>:0.1.0

and, where appropriate:

    <project-name>:latest

Do not push anything to a public registry unless explicitly authorized.

==================================================
PHASE 8 — CLEAN INSTALL TEST
==================================================

Perform a release-style installation from a clean environment.

Do not depend on:

- developer-specific PYTHONPATH;
- globally installed packages;
- previous generated state;
- undocumented configuration;
- hidden files outside the project.

Verify:

1. installation;
2. startup;
3. Web UI access;
4. authentication;
5. demo workflow;
6. shutdown.

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

Do not modify tests merely to make them pass.

If tests fail:

- determine whether the failure is a genuine release blocker;
- do not conceal it;
- fix only if the fix is clearly within release scope and does not change product architecture.

After any fix, rerun the entire suite.

==================================================
PHASE 10 — RELEASE SMOKE TEST
==================================================

Perform one final end-to-end smoke test using the release artifacts.

The flow should be:

    Install
      ↓
    Start
      ↓
    Open browser
      ↓
    Login
      ↓
    Create/select vault
      ↓
    Load/upload demo document
      ↓
    Perform supported search/query workflow
      ↓
    Inspect result/answer/citations where supported
      ↓
    Shutdown

Use the actual release installation.

Do not rely on the development environment.

==================================================
PHASE 11 — REPOSITORY CLEANLINESS
==================================================

Inspect the repository before finalizing.

Do not include:

- .venv;
- __pycache__;
- test databases;
- temporary files;
- API keys;
- credentials;
- session logs;
- generated secrets;
- personal paths;
- development artifacts.

Review .gitignore and update it if necessary.

Check for accidental secrets.

Do not commit secrets.

==================================================
PHASE 12 — RELEASE MANIFEST
==================================================

Create:

RELEASE_MANIFEST.md

It must contain:

- project name;
- version: 0.1.0;
- release date;
- installation method;
- startup method;
- required runtime;
- supported deployment method;
- test result;
- E2E QA status;
- included artifacts;
- demo dataset location;
- known limitations;
- release readiness status.

==================================================
PHASE 13 — GIT RELEASE
==================================================

If this repository is under Git:

inspect the current status and history.

Do not destroy existing user changes.

Do not reset or rewrite history.

Prepare the release commit/tag only if the repository workflow permits it.

Preferred tag:

    v0.1.0

If committing/tagging is not appropriate in the current environment, prepare the exact commands and report them instead of performing destructive Git operations.

Do not push to a remote unless explicitly authorized.

==================================================
FINAL RELEASE AUDIT
==================================================

Before declaring success, verify:

- version is consistently 0.1.0;
- README is current;
- CHANGELOG is current;
- release notes exist;
- User Guide exists;
- Admin Guide exists;
- API Guide exists;
- Developer Guide exists;
- packaging works;
- canonical startup works;
- Web UI works;
- demo data exists;
- sample documents exist;
- automated tests pass;
- E2E QA passed or has only explicitly accepted minor issues;
- no secrets are included;
- repository contains no accidental development artifacts.

==================================================
FINAL REPORT
==================================================

Produce a concise release report containing:

# v0.1.0 Release Report

## Release Status

READY
or
BLOCKED

## Version

0.1.0

## Included Features

List the actually implemented major capabilities.

## Packaging

Describe the canonical installation and startup method.

## Web UI

Describe the released user-facing interface.

## Documentation

List the completed documentation sets.

## Demo Dataset

List the included demo assets.

## Tests

Report exact automated test results.

## E2E QA

Summarize Task 023's result.

## Known Limitations

List them honestly.

## Release Artifacts

List every artifact created.

## Git

Report whether a release commit/tag was created.

## Remaining Issues

List anything intentionally left unresolved.

If the release is blocked, explain exactly why and do not claim v0.1.0 is ready.

Stop after Task 024.

Implement Task 020 — Packaging & Distribution.

You are implementing exactly Task 020.
Do not continue to Task 021 or any later task.

Before making changes:

1. Read .project_context.md.
2. Read the Task 020 specification.
3. Read all relevant architecture and module specifications.
4. Read relevant ADRs and contracts.
5. Inspect the current implementation and existing tests.
6. Inspect the current documentation, especially the documentation audit produced by the previous QA pass.
7. Determine the intended deployment and runtime model from the repository itself.

The repository specifications are authoritative.
Do not redesign the architecture.
Do not invent a new runtime model.
Do not add features that belong to later tasks.

==================================================
TASK 020 — PACKAGING & DISTRIBUTION
==================================================

Goals:

1. Create a proper application entrypoint.
2. Eliminate the need for users to manually set PYTHONPATH.
3. Standardize how the application is started.
4. Make the resulting startup procedure suitable for the intended deployment model.
5. Keep the existing application behavior unchanged.

The final user should NOT need to run fragile commands such as:

    PYTHONPATH=backend:$PYTHONPATH python3 -c "..."

The application must have a documented, reproducible startup path.

==================================================
ENTRYPOINT
==================================================

Inspect the current API/server implementation and determine the correct entrypoint from the existing architecture.

Prefer a standard Python application entrypoint where appropriate.

If the architecture specifies FastAPI/ASGI, provide the appropriate ASGI entrypoint and startup mechanism.

If a CLI entrypoint is appropriate according to the existing specifications, implement it.

If Docker is already part of the specified deployment architecture, ensure the container has a proper entrypoint as well.

Do NOT introduce a CLI merely because it is convenient if the product architecture does not require one.

Do NOT introduce Docker merely for the sake of this task if the specifications do not require it.

==================================================
PYTHON PACKAGING
==================================================

Make the Python project installable in a clean environment.

The user should be able to install the project without manually modifying PYTHONPATH.

Use the project's existing structure and dependencies.

Prefer standard Python packaging mechanisms.

Do not duplicate dependencies unnecessarily.

Do not silently change dependency versions unless required by the existing implementation.

Ensure that imports work after installation.

==================================================
STARTUP
==================================================

Provide one canonical startup method.

It should:

- work from a clean checkout;
- not require PYTHONPATH;
- not require undocumented environment hacks;
- have a predictable working directory;
- expose the configured application endpoint;
- fail clearly when required configuration is missing.

If multiple startup methods are genuinely required by the existing deployment architecture, document which one is the canonical method and why.

==================================================
TESTING
==================================================

Before changing anything, run the existing test suite and record the baseline.

After implementation:

1. Run all existing tests.
2. Add tests for packaging/entrypoint behavior where appropriate.
3. Verify that the package can be installed in a clean environment.
4. Verify that the application can be started using the canonical startup command.
5. Verify that the API is reachable.
6. Verify that the existing Web UI remains reachable if it is already implemented.
7. Verify that imports no longer depend on PYTHONPATH.
8. Verify that the canonical startup procedure works from outside the repository's backend directory.

Do not weaken or remove existing tests merely to make them pass.

==================================================
DOCUMENTATION
==================================================

Update only documentation that is directly necessary to describe the new packaging/startup behavior.

Do not perform the full Task 022 documentation rewrite yet.

The documentation must clearly state:

- prerequisites;
- installation;
- canonical startup command;
- default endpoint;
- how to stop the application;
- relevant configuration/environment variables;
- common startup failures.

If previous documentation contains obsolete startup instructions, replace those instructions with the new canonical method rather than leaving contradictory instructions.

==================================================
SCOPE CONTROL
==================================================

Do NOT:

- implement new UI features;
- redesign the Web UI;
- add new user workflows;
- implement the full User Guide;
- create the final release;
- create demo datasets;
- perform the full end-to-end QA;
- implement Task 021, 022, 023, or 024.

Those belong to later tasks.

==================================================
FINAL VERIFICATION
==================================================

At the end, report:

1. What was changed.
2. The canonical installation command.
3. The canonical startup command.
4. The canonical endpoint.
5. Whether PYTHONPATH is still required anywhere.
6. Tests before implementation.
7. Tests after implementation.
8. Any remaining packaging/deployment limitations.
9. Any documentation that still needs to be addressed by Task 022.

Stop after Task 020 is complete.

Do not continue to another task.

# Task 027 — Security & Production Configuration Hardening

## Objective

Harden the application configuration, authentication, secrets handling, API boundaries, and production runtime behavior now that the platform supports real AI providers and user-configurable settings.

This task prepares the application for safe normal use and release.

Do not introduce unrelated functionality.

---

## Scope

### 1. Authentication hardening

Review the existing authentication implementation against the architecture and API specifications.

Verify:

- authentication is required for protected APIs;
- invalid credentials are rejected;
- expired/invalid sessions are handled correctly;
- authentication state is not trusted solely from the frontend;
- privileged configuration endpoints require appropriate authorization.

Do not redesign authentication unless the existing implementation is insufficient.

If the current authentication model is intentionally MVP-level, preserve the architecture and document the remaining limitation rather than inventing a new authentication system.

---

## 2. Authorization

Review authorization boundaries for:

- documents;
- vaults;
- search;
- answers;
- AI configuration;
- provider credentials;
- administrative settings.

A normal user must not be able to access configuration belonging to another user/organization where the architecture defines isolation.

Do not bypass the existing Vault/Organization boundaries.

---

## 3. Secret handling

Audit every place where secrets can enter or leave the application.

Secrets include:

- API keys;
- authentication tokens;
- passwords;
- provider credentials;
- secret configuration values.

Ensure secrets are never:

- logged;
- returned by normal API responses;
- embedded into frontend source;
- exposed through error messages;
- included in URLs;
- written into generated documentation;
- committed to version control.

Use masking/redaction where configuration values must be displayed.

---

## 4. Configuration storage

Review the configuration storage introduced by Task 025/026.

Verify that:

- configuration persists correctly;
- secrets are stored according to the supported security model;
- non-secret settings remain inspectable;
- configuration survives restart;
- incomplete configuration is handled safely;
- corrupted configuration fails safely.

Do not invent a new configuration system.

---

## 5. API security

Audit API endpoints for:

- authentication;
- authorization;
- input validation;
- malformed JSON;
- oversized requests;
- invalid file uploads;
- path traversal;
- unsafe filenames;
- unexpected content types;
- provider configuration injection;
- unsafe URLs.

The application must not allow arbitrary filesystem access through user-controlled paths.

Provider endpoint configuration must not create an unintended SSRF vulnerability.

Where appropriate, validate or restrict outbound provider URLs according to the architecture.

---

## 6. File upload security

Review document upload behavior.

Verify:

- filename handling;
- extension/content validation;
- file size limits;
- temporary file handling;
- path traversal protection;
- storage isolation;
- cleanup after failed uploads.

Uploaded documents must not be executable.

Do not trust client-provided MIME types as the sole validation mechanism.

Preserve the existing document/version contracts.

---

## 7. AI provider security

Review the provider integration introduced in Task 025.

Verify:

- API keys are transmitted only to the configured provider endpoint;
- credentials are not sent to unintended endpoints;
- provider errors do not expose credentials;
- provider responses are safely handled;
- arbitrary provider endpoints cannot be abused to access local services;
- model/provider configuration cannot inject arbitrary application behavior.

Do not add vendor-specific behavior.

---

## 8. Prompt and evidence boundaries

Review the Generation pipeline for prompt-injection risks.

Retrieved documents are untrusted content.

Ensure retrieved document content cannot override:

- the system prompt;
- application rules;
- citation requirements;
- security boundaries;
- tool permissions;
- configuration permissions.

The LLM must treat retrieved documents as evidence/context, not as trusted instructions.

Preserve the existing Retrieval → Reranking → Generation → Citation architecture.

---

## 9. Error handling

Audit application errors.

Errors shown to users should be actionable without exposing:

- stack traces;
- filesystem paths;
- API keys;
- authentication headers;
- internal credentials;
- database credentials;
- provider secrets.

Detailed diagnostic information may remain available to controlled server-side logs where appropriate.

---

## 10. Logging and observability

Review existing logging/observability from Task 016.

Ensure logs:

- contain useful operational information;
- do not contain secrets;
- identify provider/configuration failures;
- identify authentication failures;
- preserve useful request/error context;
- do not dump complete user documents or prompts unnecessarily.

If correlation/request IDs already exist, preserve them.

Do not create a second logging system.

---

## 11. Production configuration

Review production startup/configuration after Task 020 and Task 026.

Verify that:

- the application starts without manual PYTHONPATH manipulation;
- configuration is loaded consistently;
- development-only behavior is not accidentally enabled in production;
- default credentials/settings are not silently accepted in production;
- server errors are handled safely.

Do not introduce Docker-specific behavior unless already required by the release architecture.

---

## 12. Security headers and HTTP behavior

Review the Web UI/API HTTP behavior.

Where appropriate, configure standard security protections such as:

- appropriate content type handling;
- clickjacking protection;
- sensible cache behavior for authenticated responses;
- appropriate CORS behavior;
- security-related response headers.

Do not blindly add restrictive policies that break the existing Web UI.

Test the actual application after changes.

---

## 13. Dependency and repository audit

Review:

- Python dependencies;
- frontend dependencies if present;
- generated files;
- temporary files;
- credential files;
- `.env` files;
- build artifacts.

Ensure `.gitignore` covers sensitive/local artifacts.

Do not perform unnecessary dependency upgrades.

If a dependency has a security issue that requires an upgrade, document the reason and test the application afterward.

---

## 14. Security tests

Add automated tests covering the security boundaries relevant to the current implementation.

At minimum test:

- unauthenticated protected API access;
- unauthorized configuration access;
- secret masking;
- secret absence from API responses;
- secret absence from logs where practical;
- malicious filenames;
- path traversal attempts;
- invalid upload types;
- oversized upload handling;
- malformed configuration;
- provider endpoint validation;
- SSRF-sensitive endpoint behavior;
- prompt-injection/evidence boundary behavior;
- safe error responses.

Tests must not use real credentials or external services.

---

## 15. Documentation

Update the Admin Guide and relevant deployment documentation with:

- credential handling;
- provider configuration security;
- authentication limitations;
- production configuration;
- file upload considerations;
- backup/security considerations;
- known MVP limitations.

Do not document unsupported security guarantees.

---

## Constraints

- Preserve existing contracts.
- Preserve existing architecture.
- Do not redesign unrelated modules.
- Do not add vendor-specific integrations.
- Do not expose secrets.
- Do not use real API credentials in tests.
- Do not silently weaken security to make tests pass.
- Do not continue to Task 028 or later.

If an architectural security decision is required but not defined by the existing specifications, stop and report the decision instead of inventing one.

---

## Definition of Done

Task 027 is complete when:

1. Authentication and authorization boundaries have been audited and hardened where necessary.
2. Provider/API credentials are securely handled.
3. Configuration secrets cannot leak through APIs, logs, errors, or frontend code.
4. File uploads are protected against common filesystem and input attacks.
5. Provider configuration does not introduce an obvious SSRF/security boundary violation.
6. Retrieved documents remain untrusted evidence and cannot override system instructions.
7. Production startup/configuration is consistent.
8. HTTP/API behavior has appropriate security protections without breaking the UI.
9. Security-sensitive behavior is covered by automated tests.
10. Existing tests continue to pass.
11. Documentation accurately describes security behavior and remaining limitations.

Stop after completing Task 027.

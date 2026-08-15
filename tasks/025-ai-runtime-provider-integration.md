# Task 025 — AI Runtime & Provider Integration

## Objective

Replace the current template-only AI generation path with the provider-agnostic AI runtime defined by the architecture.

The application must be able to use a real configurable AI provider while preserving the existing contracts and module boundaries.

This task establishes the backend capability required by the future Setup Wizard.

The Setup Wizard itself is **not part of this task**.

---

## Scope

### 1. Generation provider abstraction

Implement the provider abstraction required by the Generation Service.

The Generation Service must depend on a replaceable provider interface rather than directly on a specific vendor.

The abstraction must support:

- system prompt;
- user query;
- retrieved evidence/context;
- model selection;
- configurable endpoint;
- authentication;
- timeout and provider errors.

The existing Generation and Answer contracts remain authoritative.

---

### 2. OpenAI-compatible remote provider

Implement support for an OpenAI-compatible API as the first remote provider.

Configuration must support:

- `base_url`;
- `api_key`;
- `model`;
- `timeout`.

Do not introduce vendor-specific assumptions or branding.

The implementation must be usable with any compatible endpoint, including self-hosted or third-party providers.

API credentials must never be hardcoded.

---

### 3. System prompt integration

Integrate the existing `system-prompt.md` into the Generation Service.

The existing system prompt is authoritative.

Do not create a replacement system prompt unless explicitly required by the existing specification.

Generation should conceptually receive:

1. system prompt;
2. retrieved evidence;
3. user question.

The LLM must operate within the existing retrieval/evidence boundary.

---

### 4. Application configuration

Introduce a coherent application-level configuration mechanism for AI providers.

It must support the provider configuration required by the Generation Service and must be designed so that the future Setup Wizard can use the same backend configuration mechanism.

The configuration must distinguish secret values from ordinary configuration where appropriate.

API keys must not be exposed through normal configuration/status responses.

Environment-variable configuration may be supported for deployment.

Do not create multiple competing configuration systems.

---

### 5. Provider connectivity

Provide a backend capability to test whether the configured provider is reachable and usable.

The connectivity check should detect and report appropriate failures, including:

- invalid endpoint;
- authentication failure;
- unavailable provider;
- timeout;
- rate limiting;
- invalid model;
- malformed provider response.

Errors should be actionable but must not expose credentials.

---

### 6. Generation integration

Connect the real provider to the existing generation pipeline:

```text
Question
    ↓
Retrieval
    ↓
Reranking
    ↓
Evidence
    ↓
Generation Provider
    ↓
Citation Builder
    ↓
Answer Contract
    ↓
Web UI

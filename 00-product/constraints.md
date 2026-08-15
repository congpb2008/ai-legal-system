# Constraints

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the architectural, business and technical constraints that govern the Banking Legal Platform.

Every implementation decision must satisfy these constraints unless an Architecture Decision Record (ADR) explicitly states otherwise.

These constraints are considered non-functional requirements and are expected to remain stable throughout the project's lifetime.

---

# Guiding Principles

The platform prioritizes:

1. Accuracy
2. Traceability
3. Reliability
4. Maintainability
5. Performance

When trade-offs exist, higher priority principles take precedence.

---

# Business Constraints

## BC-001 - Read-Only Knowledge Platform

The platform is a knowledge retrieval and research assistant.

It does not modify legal documents, provide legal advice or generate official legal interpretations.

---

## BC-002 - Human Decision Required

AI responses are decision support only.

Final legal or business decisions must always be made by human users.

---

## BC-003 - Official Documents Only

Only official documents are indexed.

Examples:

- Laws
- Decrees
- Circulars
- Decisions
- Internal banking regulations

User-generated notes are stored separately and are never merged into official documents.

---

## BC-004 - Immutable Source

Uploaded source documents are immutable.

The original PDF or DOCX must never be modified.

Every derived artifact must be traceable back to the original document.

---

# Functional Constraints

## FC-001 - Retrieval Before Generation

The LLM must answer using retrieved evidence.

Generation without retrieval is prohibited.

---

## FC-002 - Citation Required

Every factual statement generated from platform knowledge should include citations whenever possible.

At minimum, citations should reference:

- Document
- Article
- Clause
- Page (if available)

---

## FC-003 - Abstain on Insufficient Evidence

If sufficient evidence cannot be retrieved, the system must explicitly state uncertainty instead of generating speculative answers.

---

## FC-004 - Explainability

The system should expose the supporting evidence used to generate an answer.

Users should be able to inspect the retrieved document fragments.

---

## FC-005 - Version Awareness

When multiple versions of the same document exist, the retrieval system should distinguish between them.

The answer should indicate which version was used.

---

## FC-006 - OCR Transparency

OCR-derived text is considered machine-generated.

When OCR confidence is below an acceptable threshold, the system should flag the document for manual review.

---

# Data Constraints

## DC-001 - Knowledge Tree as Source of Truth

The Knowledge Tree is the canonical internal representation of a document.

Embeddings, chunks and search indexes are derived data.

---

## DC-002 - Derived Data Can Be Rebuilt

The following artifacts are disposable:

- OCR output
- Chunks
- Embeddings
- Search indexes

They must be reproducible from the original document.

---

## DC-003 - Metadata Separation

Document metadata must remain independent from document content.

Updating metadata must not require rebuilding document structure.

---

## DC-004 - Stable Document Identity

Each logical document has a persistent identifier.

Each document version has its own unique identifier.

---

# Security Constraints

## SC-001 - Vault Isolation

Documents are accessible only through their assigned vault.

Cross-vault retrieval is prohibited unless explicitly authorized.

---

## SC-002 - Principle of Least Privilege

Users may only access documents permitted by their role.

---

## SC-003 - Department Isolation

Department Vaults are logically isolated.

Documents belonging to one department must not appear in another department's search results.

---

## SC-004 - Personal Vault Privacy

Personal Vault documents are private by default.

---

# Performance Constraints

## PC-001 - Interactive Response

Typical queries should return within an acceptable interactive latency.

Target latency:

- Retrieval < 2 seconds
- Full answer < 10 seconds

---

## PC-002 - Incremental Indexing

Uploading new documents should not require rebuilding the entire knowledge base.

---

## PC-003 - Scalable Retrieval

Retrieval performance should degrade gracefully as document volume increases.

---

# AI Constraints

## AC-001 - No Hallucinated Citations

The system must never fabricate:

- Document names
- Article numbers
- Clause numbers
- Page numbers

---

## AC-002 - Preserve Original Meaning

Generated answers may summarize retrieved content.

They must never alter legal meaning.

---

## AC-003 - Evidence Before Reasoning

Reasoning must occur after evidence retrieval.

The LLM must not rely solely on its pre-trained knowledge.

---

## AC-004 - Semantic Search is Complementary

Semantic retrieval complements keyword retrieval.

Keyword search remains available for exact references.

---

## AC-005 - Human Language First

Answers should prioritize clarity for users while preserving legal precision.

---

# Operational Constraints

## OC-001 - Automatic Processing

Documents are automatically processed after upload.

Manual approval is required only when the system detects ambiguity or low confidence.

---

## OC-002 - Idempotent Processing

Reprocessing the same document should produce identical derived artifacts whenever possible.

---

## OC-003 - Auditability

Major system events must be recorded.

Examples include:

- Upload
- OCR
- Parsing
- Indexing
- Retrieval
- AI response generation

---

# Future Constraints

The architecture should allow future support for:

- Improved OCR engines
- Better embedding models
- Better reranking models
- Improved parsing algorithms

without requiring changes to the business domain model.

---

# Out of Scope

The platform currently does not provide:

- Automatic legal interpretation
- Legal risk assessment
- Automatic document drafting
- Workflow automation
- Approval management
- Electronic signatures

These capabilities may be considered in future versions.

---

# Architectural Philosophy

The system follows these principles:

1. Original documents are immutable.
2. Knowledge Tree is the canonical representation.
3. Derived artifacts are disposable.
4. Retrieval precedes generation.
5. Every answer should be explainable.
6. Every answer should be traceable.
7. Accuracy is preferred over completeness.
8. The system should abstain rather than hallucinate.
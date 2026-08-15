# Scope

**Project:** Banking Knowledge Platform

**Version:** 1.0

---

# 1. Purpose

This document defines the scope of the Minimum Viable Product (MVP) for the
Banking Legal Platform.

The goal is to establish a clear boundary for development, prevent feature
creep, and provide a stable reference for future architecture and
implementation decisions.

The MVP focuses on building a reliable enterprise knowledge platform capable
of indexing, searching, and answering questions about banking regulations and
internal documents with verifiable evidence.

---

# 2. Target Users

## Phase 1

- IT Department
- Procurement Department
- Infrastructure Team

## Phase 2

- Other internal departments

## Phase 3

- Organization-wide deployment

---

# 3. In Scope

## 3.1 Identity & Access

The system shall support:

- User authentication
- Department-based authorization
- Personal vaults
- Department vaults
- Role-based permissions

---

## 3.2 Document Management

The system shall support:

- Upload PDF documents
- Upload DOCX documents
- OCR scanned documents
- Parse digital documents
- Metadata extraction
- Document version management

---

## 3.3 Knowledge Tree

The system shall:

- Parse document hierarchy
- Preserve legal document structure
- Support:

    - Chapter
    - Section
    - Article
    - Clause
    - Point
    - Appendix

The Knowledge Tree shall be considered the source of truth.

---

## 3.4 Knowledge Registry

The system shall maintain:

- Logical Documents
- Document Versions
- Effective timeline
- Legal relationships
- Version history

The system should detect possible document updates during ingestion.

When confidence is low, the relationship shall be flagged instead of
automatically accepted.

---

## 3.5 Search & Retrieval

The MVP shall support:

- Keyword search
- Semantic search
- Hybrid retrieval
- Metadata filtering
- Citation retrieval

---

## 3.6 AI Question Answering

The system shall support:

- Natural language questions
- Evidence-based responses
- Citation generation
- Context explanation

When sufficient evidence cannot be found, the system must refuse to answer
instead of generating unsupported conclusions.

---

## 3.7 Security

The system shall support:

- Department isolation
- Personal vault isolation
- Audit logging

Documents uploaded to one vault shall never be accessible by unauthorized
users.

---

# 4. Out of Scope

The MVP will NOT include:

- Voice assistant
- Mobile application
- Internet search
- Automatic legal consultation
- Fine-tuned proprietary models
- Multi-agent workflows
- Knowledge Graph
- Handwriting OCR
- Automatic document drafting
- Workflow automation

These capabilities may be considered in future releases.

---

# 5. MVP Deliverables

At the end of MVP development, users shall be able to:

- Sign in
- Upload documents
- Organize documents into vaults
- Search documents
- Ask legal questions
- Receive answers with citations
- View supporting evidence
- Access document version history

---

# 6. Design Principles

The MVP follows the following priorities.

Priority 1

- Accuracy

Priority 2

- Explainability

Priority 3

- Maintainability

Priority 4

- Modularity

Performance optimization is secondary to correctness.

---

# 7. Non-Functional Expectations

The MVP should be:

- Modular
- Extensible
- Auditable
- Enterprise-ready
- Deployable on-premises

The architecture should allow future scaling without major redesign.

---

# 8. Acceptance Criteria

The MVP is considered complete when:

✓ Users can upload legal documents.

✓ OCR works for scanned PDFs.

✓ Documents are parsed into a Knowledge Tree.

✓ AI answers are supported by citations.

✓ Users can inspect evidence used to generate answers.

✓ Department permissions are enforced.

✓ Personal vaults are isolated.

✓ Document versions are tracked.

✓ Unknown answers are explicitly rejected instead of hallucinated.

---

# 9. Future Expansion

The architecture should reserve extension points for:

- Knowledge Graph
- Evaluation framework
- Agent workflows
- Workflow automation
- Advanced legal reasoning
- Model routing
- Additional retrieval strategies

These features are intentionally excluded from the MVP.
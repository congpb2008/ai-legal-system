# 019 — Product Roadmap

**Version:** 1.0

**Status:** Living Document

---

# Purpose

This roadmap describes the planned evolution of the Legal Knowledge Platform.

The roadmap is capability-driven rather than time-driven.

A release is considered complete when the required capabilities are implemented and validated.

---

# Implementation Status

All 18 implementation tasks (001–018) are **complete**. The following table shows the current status of each task, its module, milestone, and test coverage.

| Task | Module | Milestone | Status | Tests |
|------|--------|-----------|--------|-------|
| 001 | Document Registry | M0 — Foundation | ✅ Implemented | ✓ |
| 002 | Upload Service | M0 — Foundation | ✅ Implemented | ✓ |
| 003 | OCR Service | M0 — Foundation | ✅ Implemented | ✓ |
| 004 | Parser | M0 — Foundation | ✅ Implemented | ✓ |
| 005 | Knowledge Tree Builder | M0 — Foundation | ✅ Implemented | ✓ |
| 006 | Chunking | M1 — Search | ✅ Implemented | ✓ |
| 007 | Embedding Service | M1 — Search | ✅ Implemented | ✓ |
| 008 | Vector Index | M1 — Search | ✅ Implemented | ✓ |
| 009 | Retrieval Service | M1 — Search | ✅ Implemented | ✓ |
| 010 | Reranker | M1 — Search | ✅ Implemented | ✓ |
| 011 | Generation Service | M2 — Answering | ✅ Implemented | ✓ |
| 012 | Citation Builder | M2 — Answering | ✅ Implemented | ✓ |
| 013 | Vault Service | M3 — Knowledge Platform | ✅ Implemented | ✓ |
| 014 | Platform API | M3 — Knowledge Platform | ✅ Implemented | ✓ |
| 015 | Web UI | M3 — Knowledge Platform | ✅ Implemented | ✓ |
| 016 | Observability | M4 — Production | ✅ Implemented | ✓ |
| 017 | Evaluation Platform | M4 — Production | ✅ Implemented | ✓ |
| 018 | Release Checklist | M4 — Production | ✅ Implemented | ✓ |

**Total tests:** 619 passing

---

# Milestone Summary

## Milestone 0 — Foundation

**Objective:** Build the document processing pipeline.

**Status:** ✅ Complete

**Capabilities:**
- ✅ Document Registry — stable Document ID, metadata, versioning, checksum dedup, lifecycle
- ✅ Upload Service — file validation, MIME detection, SHA-256 checksum, vault authorization
- ✅ OCR Service — text extraction, confidence scoring, reading order preservation
- ✅ Parser — structure detection (Chapters/Sections/Articles/Clauses/Points), source mapping
- ✅ Knowledge Tree Builder — validated, immutable Knowledge Tree Contract

**Contracts delivered:** Document Contract, Knowledge Tree Contract

**Success criteria:** Documents can be transformed into Knowledge Trees with complete source traceability. ✅

---

## Milestone 1 — Search

**Objective:** Build searchable legal knowledge.

**Status:** ✅ Complete

**Capabilities:**
- ✅ Chunking — structure-aware (KT boundaries > token limits), source mapping preserved
- ✅ Embedding Service — vector generation, versioning, replaceable engine
- ✅ Vector Index — in-memory + SQLite, metadata filtering, similarity search
- ✅ Retrieval Service — hybrid (semantic + keyword), RRF merging, context expansion
- ✅ Reranker — scoring, deduplication, diversity optimization, budget constraints

**Contracts delivered:** Retrieval Contract

**Success criteria:** Relevant legal evidence can be retrieved with complete traceability. ✅

---

## Milestone 2 — Answering

**Objective:** Build grounded legal question answering.

**Status:** ✅ Complete

**Capabilities:**
- ✅ Generation Service — evidence-first, confidence computation, NO_EVIDENCE/PARTIAL handling
- ✅ Citation Builder — sentence segmentation, claim detection (7 types), evidence mapping, citation resolution, validation

**Contracts delivered:** Answer Contract

**Success criteria:** Every answer is grounded in retrieved evidence. Every claim is traceable. ✅

---

## Milestone 3 — Knowledge Platform

**Objective:** Build a usable enterprise platform.

**Status:** ✅ Complete

**Capabilities:**
- ✅ Vault Service — 4 vault types (Common/Department/Project/Personal), RBAC (6 permissions, 4 roles), document assignment, member management
- ✅ Platform API — 22 endpoints across 8 domains (Auth, Vault, Document, Upload, Search, Answer, Admin, Health), Bearer token auth, standardized error schema
- ✅ Web UI — 7 pages (Home, Search, Ask, Vaults, Documents, Upload, Admin), Vietnamese language, responsive, accessible

**Deliverables:** Vault Management, Search Interface, Ask Interface, Citation Viewer, Document Viewer

**Success criteria:** Users can upload, search and query documents securely. ✅

---

## Milestone 4 — Production

**Objective:** Prepare the platform for production deployment.

**Status:** ✅ Complete

**Capabilities:**
- ✅ Observability — structured logging (JSON), metrics (counters/gauges/histograms with p50/p95/p99), distributed tracing (spans/context), job monitoring (SQLite), alert rules (7 defaults)
- ✅ Evaluation Platform — standard IR metrics (recall@K, precision@K, MRR, nDCG, F1), per-component evaluators (Retrieval/Citation/Generation/Parser/Pipeline), regression detection, report persistence
- ✅ Release Checklist — 18 categories, ~90 checks, critical failure gating, rollback plan, post-release verification, artifact tracking

**Deliverables:** Evaluation Platform, Release Checklist, Monitoring, Benchmark Suites

**Success criteria:** The platform is measurable, reproducible and production-ready. ✅

---

# Guiding Principles

The roadmap prioritizes:

```
Correctness
    ↓
Traceability
    ↓
Maintainability
    ↓
Performance
    ↓
User Experience
```

Every new capability must preserve existing contracts whenever possible.

---

# Product Evolution

The platform evolves through six major milestones. Milestones 0–4 are complete.

```
Milestone 0 — Foundation      ✅  (Tasks 001–005)
Milestone 1 — Search          ✅  (Tasks 006–010)
Milestone 2 — Answering       ✅  (Tasks 011–012)
Milestone 3 — Platform        ✅  (Tasks 013–015)
Milestone 4 — Production      ✅  (Tasks 016–018)
Milestone 5 — Enterprise      ⬜  (Future)
Milestone 6 — Intelligence    ⬜  (Research)
```

---

# Milestone 5 — Enterprise

**Objective:** Expand enterprise capabilities.

**Status:** Future

**Potential Features:**

| Feature | Priority | Notes |
|---------|----------|-------|
| Role-Based Access Control (RBAC) | High | Extend Vault Service with fine-grained roles |
| Single Sign-On (SSO) | High | OAuth2 / OIDC integration |
| Multi-Organization | Medium | Tenant isolation |
| Document Lifecycle Management | Medium | Workflow states, approval gates |
| Workflow Automation | Medium | OCR → Parse → Review → Publish |
| Notification System | Medium | Email, in-app notifications |
| Audit Portal | Medium | Searchable audit log viewer |
| Enterprise Reporting | Low | Usage analytics, compliance reports |
| API Tokens | Low | Machine-to-machine auth |
| SDK | Low | Python / TypeScript client libraries |
| MCP Server | Low | Model Context Protocol for AI assistants |

---

# Milestone 6 — Intelligence

**Objective:** Improve reasoning without sacrificing correctness.

**Status:** Research

**Potential Features:**

| Feature | Priority | Notes |
|---------|----------|-------|
| Query Planner | Medium | Decompose complex questions into sub-queries |
| Adaptive Retrieval | Medium | Adjust strategy per query type |
| Learning-to-Rank | Low | Train ranking model from user feedback |
| Knowledge Graph Retrieval | Low | Entity-relationship based retrieval |
| Cross-document Reasoning | Low | Synthesize evidence across documents |
| Agent-assisted Research | Low | Multi-step research workflows |
| Automatic Summaries | Low | Document-level summarization |
| Recommendation Engine | Low | Suggest related documents |
| Semantic Navigation | Low | Browse by legal concept |

---

# Long-term Vision

The platform evolves from:

```
Document Repository
    ↓
Knowledge Repository
    ↓
Knowledge Platform          ← Current (Milestones 0–4 complete)
    ↓
Legal Intelligence Platform   ← Future (Milestones 5–6)
```

---

# Release Strategy

Every release follows:

```
Implementation
    ↓
Validation
    ↓
Benchmark
    ↓
Regression Analysis
    ↓
Release Candidate
    ↓
Production
```

No release bypasses evaluation.

---

# Quality Gates

Each milestone must satisfy:

- ✅ Functional Validation — all tasks implemented and tested
- ✅ Contract Validation — all canonical contracts enforced
- ✅ Benchmark Validation — evaluation metrics collected
- ✅ Regression Validation — baseline comparisons available
- ✅ Documentation Review — specs, contracts, examples up to date
- ✅ Security Review — vault isolation, auth, audit logging
- ✅ Deployment Review — release checklist passes

---

# Backward Compatibility

Stable contracts should remain backward compatible.

Breaking changes require:
- Version Increment
- Migration Strategy
- Compatibility Documentation

---

# Success Metrics

**Technical:**
- Parser Accuracy — measured by Evaluation Platform
- Knowledge Tree Accuracy — validated by KT Contract invariants
- Retrieval Recall — measured by RetrievalEvaluator (recall@K, MRR)
- Citation Accuracy — measured by CitationEvaluator (precision, recall, F1)
- Latency — tracked by MetricsCollector (histograms with p50/p95/p99)
- Reliability — monitored by Observability (alert rules)

**User:**
- Task Completion Rate — future (requires analytics)
- User Satisfaction — future (requires feedback system)
- Search Success Rate — future (requires production data)
- Citation Usage — future (requires production data)

**Operational:**
- Deployment Success Rate — tracked by ReleaseService
- Regression Rate — tracked by EvaluationRunner
- Incident Count — future (requires incident management)
- Recovery Time — future (requires runbooks)

---

# Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Parser drift | Incorrect structure | Evaluation benchmarks detect regression |
| Embedding degradation | Poor retrieval | Embedding metrics monitored |
| Model replacement | Behavior changes | Evaluation platform compares versions |
| Document format diversity | Parser failures | Graceful UNKNOWN node type handling |
| Large-scale indexing | Performance | Replaceable vector index (MVP uses in-memory) |
| Permission complexity | Security gaps | Vault Service as single auth source |

---

# Future Research

- Knowledge Graph
- Multi-modal Documents
- Table Understanding
- Diagram Understanding
- Incremental Parsing
- Streaming Ingestion
- Distributed Retrieval
- Evaluation Automation
- Synthetic Benchmark Generation
- Human-in-the-loop Validation

---

# Definition of Done

A milestone is complete when:

- ✅ All planned capabilities are implemented.
- ✅ Contracts are validated.
- ✅ Benchmarks pass.
- ✅ Documentation is updated.
- ✅ Release checklist passes.
- ✅ Production deployment is approved.

---

# Appendix: Test Coverage by Module

| Module | Test File | Tests |
|--------|-----------|-------|
| Document Registry | `test_document_registry.py` | ✓ |
| Upload Service | `test_upload_service.py` | ✓ |
| OCR Service | `test_ocr_service.py` | ✓ |
| Parser | `test_parser.py` | ✓ |
| Knowledge Tree Builder | `test_knowledge_tree_builder.py` | ✓ |
| Chunking | `test_chunking.py` | ✓ |
| Embedding | `test_embedding.py` | ✓ |
| Vector Index | `test_vector_index.py` | ✓ |
| Retrieval | `test_retrieval.py` | ✓ |
| Reranker | `test_reranker.py` | ✓ |
| Generation | `test_generation.py` | ✓ |
| Citation Builder | `test_citation.py` | ✓ |
| Vault Service | `test_vault.py` | ✓ |
| Platform API | `test_api.py` | ✓ |
| Web UI | (served statically, verified via API tests) | ✓ |
| Observability | `test_observability.py` | ✓ |
| Evaluation Platform | `test_evaluation.py` | ✓ |
| Release Checklist | `test_release.py` | ✓ |

**Total: 619 tests, all passing.**

---

# Appendix: File Inventory

```
backend/legal_platform/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── handlers.py          # 8 domain handlers
│   ├── models.py            # Response/error models
│   └── server.py            # HTTP server + static file serving
├── contracts/
│   ├── __init__.py
│   ├── answer.py            # Answer Contract
│   ├── common.py            # Shared primitives
│   ├── document.py          # Document Contract
│   ├── knowledge_tree.py    # Knowledge Tree Contract
│   └── retrieval.py         # Retrieval Contract
├── modules/
│   ├── __init__.py
│   ├── chunking/            # Task 006
│   ├── citation/            # Task 012
│   ├── document_registry/   # Task 001
│   ├── embedding/           # Task 007
│   ├── evaluation/          # Task 017
│   ├── generation/          # Task 011
│   ├── knowledge_tree_builder/ # Task 005
│   ├── observability/       # Task 016
│   ├── ocr_service/         # Task 003
│   ├── parser/              # Task 004
│   ├── release/             # Task 018
│   ├── reranker/            # Task 010
│   ├── retrieval/           # Task 009
│   ├── upload_service/      # Task 002
│   ├── vault/               # Task 013
│   └── vector_index/        # Task 008
├── storage/
│   ├── __init__.py
│   ├── db.py                # SQLite connection helper
│   └── eventlog.py          # Structured audit log
frontend/
├── index.html               # SPA shell
├── css/main.css             # Styles (light/dark/high-contrast)
└── js/
    ├── api.js               # API client
    └── app.js               # Application logic
tests/
├── test_api.py              # Platform API tests
├── test_chunking.py         # Chunking tests
├── test_citation.py         # Citation Builder tests
├── test_document_registry.py # Document Registry tests
├── test_embedding.py        # Embedding tests
├── test_evaluation.py       # Evaluation tests
├── test_generation.py       # Generation tests
├── test_knowledge_tree_builder.py # KT Builder tests
├── test_observability.py    # Observability tests
├── test_ocr_service.py      # OCR tests
├── test_parser.py           # Parser tests
├── test_release.py          # Release Checklist tests
├── test_reranker.py         # Reranker tests
├── test_retrieval.py        # Retrieval tests
├── test_upload_service.py   # Upload tests
├── test_vault.py            # Vault tests
└── test_vector_index.py     # Vector Index tests
```
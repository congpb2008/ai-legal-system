# Retrieval Contract

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the canonical output produced by the Retrieval Engine.

The Retrieval Contract represents the evidence selected by the system to answer a user query.

It serves as the boundary between Retrieval and Generation.

The Generation pipeline must consume this contract rather than interacting directly with vector databases, search engines or storage systems.

---

# Design Principles

The Retrieval Contract shall:

- represent evidence rather than storage artifacts
- remain independent from retrieval implementation
- preserve traceability
- preserve ranking information
- support multiple retrieval strategies
- remain deterministic for identical inputs

---

# Responsibilities

The Retrieval Contract is responsible for:

- carrying retrieved evidence
- preserving evidence ranking
- preserving citation information
- exposing retrieval metadata

The Retrieval Contract is NOT responsible for:

- AI reasoning
- answer generation
- summarization
- hallucination detection
- reranking by the LLM

---

# Ownership

```text
User Query

↓

Retrieval Engine

↓

Retrieval Contract

↓

Generation Pipeline
```

The Retrieval Contract exists only during query execution.

It is not a persistent business object.

---

# Contract

```yaml
RetrievalResult

query_id:
    UUID

strategy:
    RetrievalStrategy

generated_at:
    datetime

query:
    string

evidence:
    List<Evidence>

metadata:
    RetrievalMetadata
```

---

# Evidence Contract

Each retrieved evidence shall contain:

```yaml
Evidence

id:
    UUID

knowledge_node_id:
    UUID

document_id:
    UUID

document_version_id:
    UUID

score:
    float

rank:
    integer

text:
    string

source_anchor:
    SourceAnchor

reason:
    RetrievalReason
```

---

# Retrieval Strategy

Supported strategies include:

- Keyword Search
- Semantic Search
- Hybrid Search

The Retrieval Contract must not expose implementation-specific details.

Future retrieval methods may be introduced without changing the contract.

---

# Retrieval Reason

The retrieval engine may optionally provide a reason describing why an evidence item was selected.

Examples:

- keyword match
- semantic similarity
- hybrid ranking
- metadata filtering

This field is informational only.

The Generation Pipeline must never rely on it.

---

# Metadata

```yaml
RetrievalMetadata

strategy

latency_ms

candidate_count

returned_count

warnings[]
```

Metadata is intended for monitoring and debugging.

It shall never influence business logic.

---

# Ranking

Evidence items shall be ordered by descending relevance.

Rank 1 represents the highest-confidence evidence.

Ordering must remain stable for identical retrieval conditions.

---

# Evidence Requirements

Each evidence item shall:

- originate from exactly one Knowledge Node
- preserve original wording
- include source mapping
- remain immutable

The retrieval pipeline shall never modify the original document text.

---

# Traceability

Every Evidence item shall support the following chain:

```text
Evidence

↓

Knowledge Node

↓

Knowledge Tree

↓

Document Version

↓

Original Source File
```

Every answer produced by the system must remain traceable through this chain.

---

# Empty Retrieval

If no relevant evidence is found:

```yaml
evidence:
    []
```

shall be returned.

The Retrieval Engine shall never fabricate evidence.

---

# Invariants

## INV-001

Every Evidence item belongs to exactly one Knowledge Node.

---

## INV-002

Evidence text must match the original parsed content.

---

## INV-003

Evidence ranking is deterministic.

---

## INV-004

Evidence is immutable.

---

## INV-005

Retrieval never generates new knowledge.

---

## INV-006

Retrieval never modifies source wording.

---

## INV-007

Retrieval never performs legal interpretation.

---

## INV-008

An empty evidence list is a valid result.

---

# Extension Points

Future versions may introduce:

- reranking metadata
- diversity scores
- temporal ranking
- jurisdiction filters
- document-type filters
- vault-level filtering

These extensions must preserve backward compatibility.

---

# Relationships

```text
User Query

↓

Retrieval Engine

↓

Retrieval Contract

↓

Generation

↓

Answer Contract
```

The Retrieval Contract is the canonical interface between retrieval and answer generation.

---

# Architectural Notes

The Retrieval Contract abstracts retrieval implementation.

Whether evidence is produced by:

- BM25
- Vector Search
- Hybrid Search
- Graph Retrieval
- Future Retrieval Methods

is invisible to downstream components.

Generation consumes evidence, not search technology.
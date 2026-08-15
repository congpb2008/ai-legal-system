# Knowledge Tree Contract

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the canonical output produced by the parsing pipeline.

The Knowledge Tree Contract represents one fully parsed document in a normalized, implementation-independent format.

It is the primary contract consumed by downstream services including:

- Chunk Generator
- Retrieval Engine
- Citation Builder
- Evaluation Pipeline
- Future Knowledge Management Services

The Knowledge Tree Contract is immutable.

---

# Design Principles

The contract shall:

- preserve original legal wording
- preserve document hierarchy
- preserve reading order
- preserve traceability
- remain deterministic
- remain independent from storage technology
- remain independent from AI models

---

# Responsibilities

The Knowledge Tree Contract is responsible for:

- representing document structure
- representing legal hierarchy
- representing node relationships
- preserving source mapping
- exposing parsed metadata

The contract is NOT responsible for:

- chunking
- embeddings
- search
- AI reasoning
- summarization
- legal interpretation

---

# Ownership

```

```text
Document Version

↓

Knowledge Tree Contract

├── Metadata

├── Root Node

├── Node Registry

└── Statistics
```

The Knowledge Tree Contract belongs to exactly one Document Version.

---

# Contract

```yaml
KnowledgeTree

id:
    UUID

document_version_id:
    UUID

parser_version:
    string

created_at:
    datetime

root:
    NodeReference

nodes:
    List<Node>

statistics:
    TreeStatistics

metadata:
    TreeMetadata
```

---

# Root Node

Every Knowledge Tree contains exactly one Root Node.

The Root Node represents the complete logical document.

All structural nodes descend from the Root Node.

---

# Node Contract

Every node shall contain:

```yaml
Node

id:
    UUID

type:
    NodeType

title:
    string | null

text:
    string

parent:
    NodeReference | null

children:
    List<NodeReference>

order:
    integer

page_start:
    integer

page_end:
    integer

source:
    SourceLocation

metadata:
    NodeMetadata
```

---

# Node Types

Supported node types include:

Document

Chapter

Section

Article

Clause

Point

Paragraph

Appendix

Table

Figure

Unknown

Unknown shall be used whenever the parser cannot confidently classify a structure.

---

# Source Location

Every node shall maintain a reference to its original source.

```yaml
SourceLocation

page:
    integer

line_start:
    integer | null

line_end:
    integer | null

bbox:
    BoundingBox | null
```

The source location enables:

- precise citation
- PDF highlighting
- auditability

---

# Node Registry

The contract exposes a flat registry of all nodes.

Example:

```text
Knowledge Tree

↓

Node Registry

↓

Node 001

Node 002

Node 003
```

The registry exists to allow efficient traversal without recursively walking the tree.

The hierarchy remains authoritative.

---

# Metadata

Tree metadata includes:

```yaml
TreeMetadata

language

parser_confidence

ocr_confidence

warnings[]

processing_time
```

---

# Statistics

Statistics are informational only.

```yaml
TreeStatistics

node_count

depth

article_count

clause_count

appendix_count

page_count
```

Statistics shall never influence business logic.

---

# Ordering

Sibling nodes shall preserve original document order.

The parser shall never reorder content.

---

# Text Preservation

Original wording must remain unchanged.

No normalization.

No summarization.

No translation.

No AI correction.

---

# Traceability

Every node must satisfy:

Node

↓

Source Page

↓

Original PDF

The original document must always remain recoverable.

---

# Immutability

After creation, the Knowledge Tree Contract is immutable.

Changes to:

- parser
- OCR
- chunking
- embeddings

must generate a new Knowledge Tree Contract rather than modifying an existing one.

---

# Invariants

## INV-001

Exactly one Root Node exists.

---

## INV-002

Every node has exactly one parent except the Root Node.

---

## INV-003

Node identifiers are globally unique.

---

## INV-004

Sibling ordering is stable.

---

## INV-005

Every node belongs to exactly one Knowledge Tree.

---

## INV-006

Every node references exactly one source location.

---

## INV-007

Every character in the original document belongs to one and only one node.

---

## INV-008

Knowledge Trees never contain chunks.

---

## INV-009

Knowledge Trees never contain embeddings.

---

## INV-010

Knowledge Trees never contain AI-generated text.

---

# Extension Points

Future versions may introduce:

- Explicit References
- Legal Cross References
- Effective Dates
- Exception Relationships
- Applies-To Relationships
- Amendment Relationships

These extensions must preserve backward compatibility.

---

# Relationships

```

```text
Document

↓

Document Version

↓

Knowledge Tree Contract

↓

Node

↓

Chunk Contract

↓

Embedding

↓

Retrieval

↓

Answer
```

---

# Architectural Notes

The Knowledge Tree Contract is the canonical representation of legal knowledge.

All downstream processing must operate on this contract rather than directly on source files.

Destroying all retrieval artifacts must never affect the Knowledge Tree.

The Knowledge Tree is the permanent representation from which all derived artifacts can be reconstructed.
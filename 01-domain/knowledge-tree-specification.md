# Knowledge Tree Specification

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the canonical representation of legal documents inside the Banking Legal Platform.

Every legal document processed by the system SHALL be converted into a Knowledge Tree before any downstream processing.

The Knowledge Tree is the single source of truth for all derived artifacts including:

- Retrieval Chunks
- Embeddings
- Search Indexes
- Citations
- AI Context

Any derived representation may be rebuilt from the Knowledge Tree.

---

# Design Goals

The Knowledge Tree must:

- Preserve legal structure.
- Preserve original wording.
- Preserve document order.
- Support efficient retrieval.
- Support precise citations.
- Support future document versioning.
- Remain independent from any LLM or embedding model.

---

# Principles

## KT-001

The Knowledge Tree represents structure, not interpretation.

It should preserve what the document says.

It should never infer legal meaning.

---

## KT-002

Original wording is immutable.

No parser may rewrite, summarize or normalize legal text.

---

## KT-003

Every node must be traceable back to the original document.

---

## KT-004

The tree is deterministic.

Processing the same document twice should produce the same tree.

---

# Tree Structure

```

```
Document

├── Chapter

│      ├── Section

│      │      ├── Article

│      │      │      ├── Clause

│      │      │      │      ├── Point

│      │      │      │      └── Point

│      │      │      └── Clause

│      │      └── Article

│      └── Section

└── Appendix
```

The parser should preserve hierarchy whenever it exists.

If a hierarchy level does not exist, it should be omitted.

---

# Node Types

Supported node types include:

- Document
- Chapter
- Section
- Article
- Clause
- Point
- Appendix
- Table
- Figure
- Paragraph
- Unknown

Unknown nodes allow graceful handling of non-standard internal regulations.

---

# Node Definition

Every node shall contain the following fields.

```

```text
Node

id

type

title

text

parent_id

children[]

order

page_start

page_end

metadata
```

---

# Field Definitions

## id

Globally unique identifier.

Never changes after creation.

---

## type

Logical node type.

Examples:

Article

Clause

Appendix

---

## title

Original heading.

Examples:

Article 15

Clause 2

Appendix A

May be empty.

---

## text

Original text belonging to the node.

Text must remain unchanged.

---

## parent_id

Identifier of parent node.

Root document has no parent.

---

## children

Ordered list of child nodes.

---

## order

Position among siblings.

---

## page_start

First page containing the node.

---

## page_end

Last page containing the node.

---

## metadata

Parser-generated metadata.

Examples:

OCR confidence

Parser confidence

Language

Document source

---

# Node Identity

A node identity never changes.

If the document changes, a new Document Version produces a new tree.

Existing nodes remain immutable.

---

# Text Ownership

Every character belongs to exactly one node.

Nodes must never duplicate legal text.

Parent nodes reference children through hierarchy rather than copying text.

---

# Ordering

Sibling order is significant.

The original document order must be preserved.

---

# Parser Requirements

The parser shall:

Detect:

- Chapters
- Sections
- Articles
- Clauses
- Points

Preserve:

- Titles
- Numbering
- Order

Reject:

- Text rewriting
- Semantic interpretation
- AI-generated modifications

---

# Citation Support

Every node must be citable.

Minimum citation information:

- Document
- Article
- Clause
- Point
- Page

---

# Chunk Generation

Chunks are NOT stored inside the tree.

Chunks are projections generated from tree nodes.

Possible strategies include:

- Article-level chunk
- Clause-level chunk
- Parent-child merged chunk

Chunking strategy may evolve without modifying the tree.

---

# Embedding

Embeddings are generated from chunks.

Embeddings are disposable.

Changing embedding models must never require rebuilding the tree.

---

# Search

Search operates on derived indexes.

Search never modifies the tree.

---

# Versioning

Every Document Version owns an independent Knowledge Tree.

Trees from different versions are never merged.

Relationships between versions are managed outside the tree.

---

# Error Handling

If parser confidence is insufficient:

- Preserve original text.
- Create Unknown nodes.
- Record parser warnings.

Never discard text.

---

# Non Goals

The Knowledge Tree does NOT:

- Understand legal meaning.
- Detect legal conflicts.
- Interpret regulations.
- Compare document versions.
- Generate summaries.

These are downstream capabilities.

---

# Architectural Rules

1. Original Document is immutable.

2. Knowledge Tree is the canonical representation.

3. Nodes are immutable.

4. Chunks are derived artifacts.

5. Embeddings are derived artifacts.

6. Search indexes are derived artifacts.

7. Every Answer must ultimately reference Knowledge Tree nodes.

8. Destroying all chunks, embeddings and indexes must never destroy knowledge.

The system must always be able to reconstruct them from the Knowledge Tree.
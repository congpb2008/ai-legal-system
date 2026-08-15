# Task 005 — Knowledge Tree Builder

Status: Planned

Priority: Critical

Estimated Complexity: High

Dependencies

- Task 004 — Parser

Related Contracts

- knowledge-tree-contract.md

Related Specifications

- knowledge-tree-specification.md

Related Examples

- knowledge-tree-example.json

---

# Goal

Implement the Knowledge Tree Builder.

The Knowledge Tree Builder transforms parsed structural elements into a validated Knowledge Tree.

It is responsible for constructing the final hierarchical representation of a legal document.

The Builder does not perform parsing.

It consumes parser output only.

---

# Background

The Parser identifies document structure.

The Knowledge Tree Builder converts that structure into the canonical tree representation defined by the Knowledge Tree Contract.

Every downstream module depends on this tree.

---

# Responsibilities

The Knowledge Tree Builder shall

- Build Knowledge Nodes
- Construct parent-child relationships
- Generate Node IDs
- Generate canonical references
- Generate node paths
- Generate node depth
- Preserve ordering
- Validate tree integrity

The Builder shall NOT

- Perform OCR
- Parse raw text
- Rewrite content
- Generate embeddings
- Chunk documents
- Retrieve documents
- Generate answers

---

# Inputs

Input

↓

Parser Output

↓

Document Contract

Parser output contains

- Detected hierarchy
- Structural elements
- Source mapping
- Raw node content

---

# Outputs

Knowledge Tree Contract

↓

Validated Knowledge Tree

↓

Builder Metadata

---

# Processing Flow

Parser Output

↓

Node Construction

↓

Hierarchy Construction

↓

Path Generation

↓

Reference Generation

↓

Validation

↓

Knowledge Tree

---

# Node Construction

Create one Knowledge Node for every legal structural element.

Examples

Document

Chapter

Section

Article

Clause

Point

Appendix

Each node receives

- Node ID
- Node Type
- Content
- Metadata

---

# Parent-Child Construction

Assign exactly one parent to every node except the root.

The resulting structure must be a tree.

Example

Document

↓

Chapter

↓

Article

↓

Clause

↓

Point

---

# Path Generation

Generate deterministic paths.

Examples

1

1.2

1.2.3

1.2.3.a

Paths must remain stable across rebuilds when the source document is unchanged.

---

# Canonical References

Generate human-readable references.

Examples

Article 3

Article 3 Clause 2

Article 3 Clause 2 Point a

Canonical references are unique within a document.

---

# Node Ordering

Preserve the original document order.

Every sibling node shall contain

Node Order

Ordering is deterministic.

---

# Tree Validation

The generated tree must satisfy

One root node

No cycles

No orphan nodes

Unique Node IDs

Unique paths

Valid parent references

Valid canonical references

Nodes ordered correctly

Validation failures prevent publication.

---

# Metadata

Generate

Knowledge Tree Version

Builder Version

Creation Timestamp

Document ID

Node Count

Maximum Depth

---

# Error Handling

Possible failures

Duplicate Node IDs

↓

Broken hierarchy

↓

Invalid parent

↓

Invalid references

↓

Missing root

Return structured validation errors.

Never publish an invalid tree.

---

# Logging

Record

Builder Job ID

Document ID

Tree Version

Node Count

Maximum Depth

Validation Result

Execution Time

Warnings

Errors

---

# Performance

Tree construction should be deterministic.

Tree validation should execute in linear time relative to node count.

---

# Acceptance Criteria

The task is complete when

✓ Knowledge Tree Contract is produced.

✓ Tree validation passes.

✓ Parent-child relationships are correct.

✓ Canonical references are generated.

✓ Paths are generated.

✓ Node ordering is preserved.

✓ knowledge-tree-example.json is reproduced.

---

# Out of Scope

OCR

Parser

Chunking

Embedding

Retrieval

Generation

Citation

Legal reasoning

Cross-document relationships

---

# Future Improvements

Incremental tree updates

Tree diff generation

Tree compression

Relationship indexing

Node annotations

Semantic node classification

Confidence scoring

Knowledge Tree migration support
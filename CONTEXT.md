# Legal Library

A shared document library for one organization to ingest, structure, search, and verify Vietnamese legal and regulatory documents through evidence-grounded research.

## Language

**Collection**:
A shared or private organizational folder of documents with role-based member permissions (Viewer, Contributor, Manager, Owner).
_Avoid_: Vault, folder, workspace

**Document**:
A legal or internal regulatory document (Law, Decree, Circular, Decision, Policy) identified across its historical revisions.
_Avoid_: File, record, paper

**Document Version**:
An immutable revision of a Document corresponding to a specific uploaded original file and its canonical Knowledge Tree.
_Avoid_: Draft, update, revision

**Knowledge Tree**:
The canonical hierarchical structural representation (Document → Chapter → Section → Article → Clause → Point) of an extracted document version.
_Avoid_: Parse tree, document graph, AST

**Evidence**:
Verified Knowledge Tree nodes and passages selected by the retrieval and reranker pipeline to answer a query.
_Avoid_: Snippet, chunk, context

**Quotation**:
Contiguous excerpt text extracted from the exact cited document version, verified against source extraction for human inspection.
_Avoid_: Generated text, summary snippet, hallucination

**Citation**:
Structured reference metadata linking an answer claim through Knowledge Node and Document Version to the original source file.
_Avoid_: Hyperlink, source link, footnote

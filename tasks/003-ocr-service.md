# Task 003 — OCR Service

Status: Planned

Priority: High

Estimated Complexity: High

Dependencies

- Task 001 — Document Registry
- Task 002 — Upload Service

Related Contracts

- Document Contract

Related Examples

- examples/document/active-decision.json

---

# Goal

Implement the OCR Service.

The OCR Service converts uploaded documents into machine-readable text while preserving the original document as faithfully as possible.

The OCR Service is responsible only for text extraction.

It does not understand document structure.

It does not identify legal hierarchy.

It does not perform chunking.

---

# Background

Most legal documents received by the platform are scanned PDFs.

OCR is therefore a mandatory preprocessing stage before parsing.

The parser depends on OCR output.

OCR quality directly affects downstream retrieval accuracy.

---

# Responsibilities

The OCR Service shall

- Detect whether OCR is required
- Extract text from scanned pages
- Preserve reading order
- Preserve page boundaries
- Preserve line boundaries whenever possible
- Produce confidence scores
- Report OCR failures

The OCR Service shall NOT

- Build Knowledge Trees
- Detect Articles
- Detect Clauses
- Correct legal wording
- Rewrite text
- Summarize
- Translate

---

# Inputs

Input

↓

Document Contract

↓

Original PDF

Supported Inputs

- PDF (scanned)
- PDF (digital)

Future

- PNG
- JPG
- TIFF

---

# Outputs

OCR Result

↓

Page List

↓

Text

↓

Confidence

↓

Metadata

---

# OCR Output

Each OCR result shall contain

- Page Number
- Page Text
- Line Information
- Confidence Score

Example

Page 1

↓

Lines

↓

Raw Text

↓

Average Confidence

OCR output must remain independent from the Knowledge Tree.

---

# Processing Flow

Document

↓

Determine OCR Requirement

↓

Digital PDF

↓

Extract Embedded Text

OR

Scanned PDF

↓

Image OCR

↓

Normalize Encoding

↓

Store OCR Result

↓

Parser Queue

---

# OCR Modes

Digital Mode

Extract embedded text directly.

Image Mode

Run OCR engine.

Hybrid Mode

Automatically select the appropriate strategy.

---

# Fidelity Requirements

The OCR Service shall preserve

- Original wording
- Original punctuation
- Original numbering
- Original capitalization

OCR shall not

- Rewrite text
- Improve grammar
- Normalize legal terminology

The extracted text should be as close as possible to the source document.

---

# Page Preservation

Page boundaries must be retained.

Each page shall be individually identifiable.

Example

Page 1

↓

OCR Text

Page 2

↓

OCR Text

The parser may later combine pages if necessary.

---

# Line Preservation

Whenever possible

Original line order shall be preserved.

Original reading sequence shall remain unchanged.

Line numbers are optional but recommended.

---

# Confidence

Each page shall have

- Average confidence

Each line may additionally have

- Line confidence

Confidence values are intended for diagnostics.

Parser behavior must not depend solely on OCR confidence.

---

# Failure Handling

Possible failures

Unreadable page

↓

Low confidence

↓

Missing page

↓

Corrupted PDF

↓

Unsupported encoding

Every failure shall be reported.

No silent data loss is allowed.

---

# Reprocessing

OCR results may be regenerated.

Reasons include

- Improved OCR engine
- Better language model
- Higher quality scans

Reprocessing shall not overwrite historical versions.

---

# Storage

Store

Original Document

↓

OCR Result

↓

Processing Metadata

OCR output is immutable.

Later OCR versions create new OCR records.

---

# Logging

Record

- OCR Job ID
- Document ID
- OCR Engine
- Engine Version
- Processing Time
- Page Count
- Average Confidence
- Status

---

# Performance

OCR jobs execute asynchronously.

Multiple OCR workers may run concurrently.

Large documents should be processed page-by-page.

---

# Security

OCR operates only on documents the platform already owns.

OCR results inherit the same vault permissions as the original document.

---

# Acceptance Criteria

The task is complete when

✓ Digital PDFs are processed without OCR.

✓ Scanned PDFs produce readable text.

✓ Page boundaries are preserved.

✓ Original wording is preserved.

✓ OCR confidence is recorded.

✓ OCR results are stored independently.

✓ Parser receives OCR output.

---

# Out of Scope

Knowledge Tree

Parser

Chunking

Embedding

Retrieval

Generation

Citation

Legal interpretation

Metadata extraction

---

# Future Improvements

Multi-language OCR

Table detection

Signature detection

Stamp detection

Handwriting recognition

Layout detection

GPU acceleration

Incremental OCR

Automatic quality benchmarking
# Benchmark Dataset Specification

Version: 1.0

Status: Stable

Related Documents

- evaluation.md
- system-prompt.md
- retrieval-contract.md
- answer-contract.md

---

# Purpose

This document defines the structure, lifecycle and quality requirements of benchmark datasets used to evaluate the Legal Knowledge Platform.

A benchmark dataset provides reproducible measurements for retrieval, generation, citation and end-to-end system quality.

Benchmark datasets are immutable once published.

---

# Design Principles

A benchmark dataset shall be

Representative

Repeatable

Versioned

Traceable

Auditable

Extensible

Every benchmark sample shall have a clear expected outcome.

---

# Benchmark Hierarchy

Benchmark Suite

↓

Benchmark Dataset

↓

Benchmark Case

↓

Evaluation Result

---

# Dataset Types

The platform supports

Unit Dataset

Component Dataset

Regression Dataset

Release Dataset

Production Replay Dataset

Research Dataset

Each dataset serves a different evaluation purpose.

---

# Benchmark Case Structure

Every benchmark case contains

Case Metadata

↓

Input

↓

Expected Retrieval

↓

Expected Citations

↓

Expected Answer

↓

Evaluation Rules

---

# Benchmark Case

Example

```json
{
  "id": "LAW-000123",

  "version": "1.0",

  "title": "Server procurement requirements",

  "category": "procurement",

  "difficulty": "medium",

  "language": "vi",

  "vault": "common",

  "question":

  "Điều kiện mua sắm máy chủ là gì?",

  "expected_documents": [

      "Decision-123"

  ],

  "expected_nodes": [

      "article_5.clause_2.point_a"
  ],

  "expected_citations": [

      {
          "document":"Decision-123",
          "reference":"Điều 5 Khoản 2 Điểm a"
      }
  ],

  "expected_answer":

  "The answer should identify procurement requirements stated in Article 5 Clause 2.",

  "evaluation":

  {

      "retrieval":true,

      "citation":true,

      "generation":true

  }
}
```

---

# Metadata

Every benchmark case records

Case ID

Version

Language

Category

Difficulty

Vault

Author

Reviewer

Created Date

Last Updated

Status

Tags

---

# Difficulty Levels

Recommended

Easy

Medium

Hard

Expert

Difficulty reflects reasoning complexity rather than document length.

---

# Categories

Examples

Definitions

Requirements

Procedures

Exceptions

Comparisons

Thresholds

Responsibilities

Penalties

Document Navigation

Cross-document Questions

Multiple categories may be assigned.

---

# Question Types

Supported question types

Fact Lookup

Definition

Requirement

Procedure

Comparison

Exception

Calculation

Summary

Navigation

Cross-document Reasoning

Each benchmark should specify exactly one primary type.

---

# Expected Retrieval

Expected retrieval may specify

Expected Documents

Expected Knowledge Nodes

Expected Canonical References

Expected Evidence Count

Minimum Recall

Evaluation may tolerate additional relevant evidence.

---

# Expected Citations

Expected citations should include

Document

Canonical Reference

Knowledge Node

Page (optional)

Line (optional)

Citation precision should be preferred over document-level citations.

---

# Expected Answer

Expected answers should define

Required concepts

Required legal references

Required terminology

Forbidden statements

Evaluation should focus on correctness rather than wording.

---

# Evaluation Rules

Each benchmark case specifies

Retrieval Evaluation

Citation Evaluation

Generation Evaluation

Overall Evaluation

Individual modules may be evaluated independently.

---

# Failure Categories

Examples

Wrong Retrieval

Wrong Ranking

Wrong Citation

Wrong Generation

Parser Error

Hierarchy Error

Missing Evidence

Unsupported Claim

Permission Error

Timeout

Every failed benchmark should map to exactly one primary failure category.

---

# Gold Standard

Ground truth shall be reviewed by

Domain Expert

↓

Technical Reviewer

↓

Approval

Gold datasets should not be modified after publication.

Corrections require a new dataset version.

---

# Dataset Versioning

Every dataset records

Dataset ID

Version

Release

Document Version

Knowledge Tree Version

Evaluation Version

Historical versions remain available.

---

# Dataset Organization

Recommended layout

datasets/

    unit/

    parser/

    retrieval/

    generation/

    citation/

    regression/

    release/

    production/

---

# Dataset Size

Suggested minimum sizes

Parser

200 cases

Retrieval

500 cases

Generation

300 cases

Citation

300 cases

Regression

1000+ cases

Release

500+ cases

These numbers are recommendations only.

---

# Quality Requirements

A benchmark dataset should

Cover all supported document types.

Cover multiple difficulty levels.

Contain edge cases.

Contain failure cases.

Remain balanced across categories.

Avoid duplicated questions.

---

# Evaluation Output

Each execution produces

Execution ID

Dataset Version

System Version

Prompt Version

Model Version

Embedding Version

Parser Version

Retrieval Version

Metrics

Failure Report

Execution Time

---

# Reproducibility

Every benchmark execution shall record

Dataset Version

Prompt Version

Configuration

Model

Temperature

Random Seed (if supported)

System Version

The same configuration should produce comparable results.

---

# Maintenance

Datasets shall be periodically reviewed.

Deprecated legal documents should be replaced in new dataset versions.

Historical datasets remain available for regression testing.

---

# Acceptance Criteria

A benchmark dataset is accepted when

✓ Cases are reviewed.

✓ Ground truth is verified.

✓ Categories are balanced.

✓ Difficulty is assigned.

✓ Evaluation rules are complete.

✓ Dataset version is published.

---

# Future Improvements

Synthetic benchmark generation

Automatic hard-case discovery

Production replay datasets

Human evaluation integration

LLM-assisted benchmark review

Cross-language benchmarks

Adversarial benchmark suites
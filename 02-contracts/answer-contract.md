# Answer Contract

**Project:** Banking Legal Platform

**Version:** 1.0

---

# Purpose

This document defines the canonical output produced by the Generation Pipeline.

The Answer Contract represents the final response delivered to the user.

It is the only object exposed to client applications.

The Answer Contract separates user-facing responses from internal retrieval and generation implementations.

---

# Design Principles

The Answer Contract shall:

- remain evidence-driven
- remain explainable
- remain traceable
- distinguish facts from AI interpretation
- preserve legal citations
- expose confidence information
- gracefully represent uncertainty

---

# Responsibilities

The Answer Contract is responsible for:

- presenting the final answer
- presenting supporting evidence
- presenting citations
- communicating confidence
- explaining limitations

The Answer Contract is NOT responsible for:

- document retrieval
- search ranking
- OCR
- parsing
- embeddings
- legal decision making

---

# Ownership

```text
Retrieval Contract

↓

Generation Pipeline

↓

Answer Contract

↓

Client
```

The Answer Contract is transient.

It exists only for the lifetime of a request.

---

# Contract

```yaml
Answer

request_id:
    UUID

generated_at:
    datetime

status:
    SUCCESS
    PARTIAL
    NO_EVIDENCE
    ERROR

response:
    Response

citations:
    List<Citation>

evidence:
    List<EvidenceReference>

confidence:
    Confidence

limitations:
    List<Limitation>

metadata:
    AnswerMetadata
```

---

# Response

The Response contains the natural-language explanation presented to the user.

```yaml
Response

format:
    MARKDOWN

content:
    string
```

The response may explain, summarize or compare information.

The response shall never fabricate legal facts.

---

# Citation

Every factual statement should be traceable.

```yaml
Citation

id:
    UUID

document_id:
    UUID

document_version_id:
    UUID

knowledge_node_id:
    UUID

source_anchor:
    SourceAnchor

label:
    string
```

Example labels:

- Article 15
- Clause 2
- Point a
- Appendix I

---

# Evidence Reference

Generation does not duplicate evidence.

Instead it references evidence returned by the Retrieval Contract.

```yaml
EvidenceReference

evidence_id:
    UUID

usage:

    DIRECT

    SUPPORTING

    CONTEXT
```

---

# Confidence

Confidence reflects the reliability of the generated answer.

```yaml
Confidence

level:

    HIGH

    MEDIUM

    LOW

score:
    float

reason:
    string
```

Confidence is advisory only.

Users remain responsible for interpreting legal documents.

---

# Limitation

Generation should explicitly communicate important limitations.

Examples include:

- insufficient evidence
- conflicting documents
- ambiguous wording
- incomplete upload
- OCR uncertainty

Limitations improve transparency.

---

# Metadata

```yaml
AnswerMetadata

generation_model

generation_latency_ms

prompt_version

retrieval_strategy

token_usage
```

Metadata supports monitoring and debugging only.

---

# No Evidence

If Retrieval returns no evidence:

```yaml
status:
    NO_EVIDENCE
```

The system shall explain why an answer cannot be generated.

It shall never invent legal content.

---

# Partial Answer

If evidence exists but is incomplete:

```yaml
status:
    PARTIAL
```

The response shall clearly distinguish confirmed information from missing information.

---

# Invariants

## INV-001

Every factual claim shall be supported by at least one Citation.

---

## INV-002

The Answer Contract never contains fabricated citations.

---

## INV-003

Evidence references must originate from the Retrieval Contract.

---

## INV-004

Generation never modifies the wording of citations.

---

## INV-005

Confidence is never interpreted as legal certainty.

---

## INV-006

The Answer Contract never creates new legal knowledge.

---

## INV-007

Missing evidence is explicitly communicated.

---

## INV-008

The client receives exactly one Answer Contract per request.

---

# Extension Points

Future versions may introduce:

- multilingual responses
- structured comparison tables
- timeline visualizations
- legal reasoning chains
- interactive citations
- follow-up suggestions

These extensions must preserve backward compatibility.

---

# Relationships

```text
User Query

↓

Retrieval Contract

↓

Generation Pipeline

↓

Answer Contract

↓

Client Application
```

The Answer Contract is the final output of the Legal Knowledge Engine.

---

# Architectural Notes

The Answer Contract is presentation-oriented.

Internal implementation details such as:

- vector databases
- embedding models
- reranking algorithms
- LLM providers

shall never leak into this contract.

The contract represents what the user receives, not how the answer was produced.
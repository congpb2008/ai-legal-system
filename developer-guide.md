# Developer Guide

Project: Banking Legal Platform

Version: 1.0

---

# Purpose

This document explains how to work on the Banking Legal Platform.

It is intended for:

- Developers
- AI coding agents
- Technical reviewers
- Future maintainers

This document describes the engineering workflow, project conventions and implementation philosophy.

Business requirements are documented elsewhere.

---

# Before You Start

Do not begin implementing features immediately.

Read the following documents in order.

1. README.md
2. vision.md
3. scope.md
4. ADRs
5. architecture.md
6. processing-pipeline.md
7. module-specifications.md
8. Contracts
9. Examples

Only after understanding these documents should implementation begin.

---

# Engineering Philosophy

The platform prioritizes

Accuracy

↓

Correct Citation

↓

Maintainability

↓

Performance

Never sacrifice correctness for convenience.

---

# Single Source of Truth

Every engineering decision must originate from one of the following.

Business Vision

↓

Architecture

↓

ADR

↓

Contract

↓

Examples

Implementation must never become the source of truth.

Code follows documentation.

---

# Documentation Hierarchy

When conflicts exist, higher-level documents always win.

Priority

ADR

↓

Contracts

↓

Architecture

↓

Examples

↓

Implementation

---

# Development Workflow

Every implementation should follow the same workflow.

Understand the problem

↓

Read relevant contracts

↓

Read relevant examples

↓

Implement

↓

Test

↓

Review

↓

Merge

Do not skip documentation.

---

# Module Boundaries

Each module owns a single responsibility.

Gateway

- Request routing
- Authentication
- Authorization

Ingestion

- Upload
- OCR
- Parsing

Knowledge

- Knowledge Tree
- Versioning
- Relationships

Retrieval

- Search
- Ranking
- Evidence selection

Generation

- Answer generation
- Citation assembly

Modules communicate only through contracts.

---

# Contracts

Never invent new fields.

Never remove existing fields.

Never change field semantics.

Contract modifications require

ADR

↓

Contract Update

↓

Examples Update

↓

Implementation Update

---

# Examples

Examples represent expected system behavior.

They are executable documentation.

Every implementation should produce outputs compatible with examples.

Examples are not optional.

---

# Testing

Each module should have

Unit Tests

↓

Contract Validation

↓

Golden Example Validation

↓

Integration Tests

A feature is incomplete until all tests pass.

---

# AI Agent Workflow

Before implementing any task, an AI agent should

Read the task

↓

Read related ADR

↓

Read related contracts

↓

Read related examples

↓

Implement

↓

Run tests

↓

Validate contracts

↓

Return results

Agents should never redesign the architecture.

---

# Code Review Checklist

Before submitting code verify

- Contracts respected
- ADRs respected
- Module boundaries respected
- No duplicated logic
- Tests updated
- Examples still valid
- Documentation updated if required

---

# Error Handling

Errors should be

Observable

Recoverable

Traceable

Silent failures are unacceptable.

---

# Logging

Every important operation should produce logs.

Examples

Document Upload

OCR

Parser

Knowledge Tree

Retrieval

Generation

Logs should support debugging without exposing sensitive information.

---

# Versioning

Parser versions

Knowledge Tree versions

Embedding versions

Contracts

Examples

should all be versioned independently.

---

# Definition of Done

A task is considered complete only if

Implementation is finished

↓

Contracts remain valid

↓

Examples pass

↓

Tests pass

↓

Documentation updated

↓

Code reviewed

---

# Out of Scope

Developers should not

Modify architecture without ADR

Invent new contracts

Skip validation

Hardcode business rules

Bypass module boundaries

---

# Principles

Prefer simple solutions.

Prefer explicit contracts.

Prefer deterministic behavior.

Prefer traceability over cleverness.

The platform is designed to support long-term evolution.

Maintainability is more important than short-term optimization.

---

# Final Reminder

This project is documentation-driven.

Architecture defines the system.

Contracts define interfaces.

Examples define expected behavior.

Implementation follows all of them.
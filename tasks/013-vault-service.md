# Task 013 — Vault Service

Status: Planned

Priority: Critical

Estimated Complexity: High

Dependencies

- Task 001–012

Related Specifications

- architecture.md
- deployment-view.md

Related Contracts

- document-contract.md
- retrieval-contract.md

---

# Goal

Implement the Vault Service.

The Vault Service manages logical knowledge boundaries, document ownership and access control.

A Vault represents an isolated knowledge domain.

The Vault Service is the primary authorization layer for document access.

---

# Background

The platform stores documents from multiple sources.

Not every user may access every document.

Vaults provide

- Isolation
- Organization
- Security
- Retrieval Scope

Knowledge is indexed globally but access is enforced through Vault policies.

---

# Responsibilities

The Vault Service shall

- Create Vaults
- Update Vaults
- Archive Vaults
- Assign documents
- Assign users
- Resolve permissions
- Provide vault metadata

The Vault Service shall NOT

- Store documents
- Perform retrieval
- Generate embeddings
- Generate answers

---

# Vault Types

The platform supports

Common Vault

Department Vault

Project Vault

Personal Vault

Future vault types may be introduced.

---

# Common Vault

Contains shared knowledge.

Examples

Government Laws

Regulations

National Standards

Official Circulars

Readable by all authorized users.

---

# Department Vault

Contains department-specific knowledge.

Examples

IT

HR

Finance

Procurement

Compliance

Access is limited to department members.

---

# Project Vault

Contains project-specific documents.

Examples

Migration Project

Procurement Project

Audit Project

Access expires with project lifecycle when configured.

---

# Personal Vault

Contains user-owned documents.

Examples

Personal uploads

Draft notes

Working files

Private references

Only the owner (or explicitly delegated users) may access the vault.

---

# Vault Metadata

Each Vault shall contain

Vault ID

Vault Name

Vault Type

Owner

Description

Status

Creation Time

Last Updated

Document Count

Member Count

Retention Policy

---

# Document Assignment

Every document belongs to exactly one primary Vault.

Future versions may support shared references across vaults without duplicating documents.

---

# Permission Model

Permissions include

Read

Upload

Update

Delete

Share

Manage

Permissions are evaluated before retrieval begins.

---

# Retrieval Scope

Every retrieval request includes

Authorized Vault Set

↓

Vault Filtering

↓

Search Execution

↓

Evidence Collection

The Retrieval Service shall never search outside the authorized scope.

---

# Vault Isolation

Vaults are logically isolated.

Isolation applies to

Documents

Knowledge Trees

Chunks

Embeddings

Search Results

Generated Answers

Isolation shall remain consistent across the entire pipeline.

---

# Versioning

Vault membership changes do not modify documents.

Document versions remain independent from Vault metadata.

---

# Lifecycle

Supported operations

Create

Rename

Archive

Restore

Delete (implementation policy)

Member Management

Permission Updates

---

# Validation

Validate

Vault exists

↓

Vault active

↓

User authorized

↓

Document assignment valid

↓

Permission policy satisfied

---

# Logging

Record

Vault ID

Operation

User ID

Affected Documents

Execution Time

Warnings

Errors

---

# Performance

Permission resolution should be efficient.

Vault filtering should occur before retrieval whenever possible.

Vault metadata should be cacheable.

---

# Error Handling

Possible failures

Vault not found

↓

Permission denied

↓

Inactive vault

↓

Invalid assignment

↓

Policy conflict

Return structured authorization errors.

---

# Security

The Vault Service is the source of truth for access control.

Every downstream component shall trust Vault authorization.

No module shall bypass Vault validation.

---

# Acceptance Criteria

The task is complete when

✓ Vaults can be created.

✓ Documents are assigned correctly.

✓ Permissions are enforced.

✓ Retrieval respects vault boundaries.

✓ Personal Vault isolation functions correctly.

✓ Common Vault sharing functions correctly.

---

# Out of Scope

OCR

Parser

Knowledge Tree

Embedding

Retrieval Ranking

Answer Generation

Identity Provider

Single Sign-On

---

# Future Improvements

Hierarchical Vaults

Temporary Access

External Sharing

Attribute-Based Access Control (ABAC)

Organization Synchronization

Automatic Department Provisioning

Cross-Vault References

Vault Analytics
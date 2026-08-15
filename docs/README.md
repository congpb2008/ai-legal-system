# Documentation Index

This directory contains documentation for the Legal Knowledge Platform.

---

## User Guides

| Guide | English | Vietnamese |
|-------|---------|------------|
| Installation | [en/01-installation.md](user-guide/en/01-installation.md) | [vi/01-cai-dat.md](user-guide/vi/01-cai-dat.md) |
| Quick Start | [en/02-quick-start.md](user-guide/en/02-quick-start.md) | [vi/02-bat-dau-nhanh.md](user-guide/vi/02-bat-dau-nhanh.md) |
| Uploading Documents | [en/03-uploading-documents.md](user-guide/en/03-uploading-documents.md) | [vi/03-tai-lieu.md](user-guide/vi/03-tai-lieu.md) |
| Search and Retrieval | [en/04-search-and-retrieval.md](user-guide/en/04-search-and-retrieval.md) | [vi/04-tim-kiem.md](user-guide/vi/04-tim-kiem.md) |
| Question Answering | [en/05-question-answering.md](user-guide/en/05-question-answering.md) | [vi/05-hoi-dap.md](user-guide/vi/05-hoi-dap.md) |
| Document Management | [en/06-document-management.md](user-guide/en/06-document-management.md) | [vi/06-quan-ly-tai-lieu.md](user-guide/vi/06-quan-ly-tai-lieu.md) |
| Configuration | [en/07-configuration.md](user-guide/en/07-configuration.md) | [vi/07-cau-hinh.md](user-guide/vi/07-cau-hinh.md) |
| Troubleshooting | [en/08-troubleshooting.md](user-guide/en/08-troubleshooting.md) | [vi/08-khac-phuc-su-co.md](user-guide/vi/08-khac-phuc-su-co.md) |
| FAQ | [en/09-faq.md](user-guide/en/09-faq.md) | [vi/09-cau-hoi-thuong-gap.md](user-guide/vi/09-cau-hoi-thuong-gap.md) |

## Admin Guides

| Guide | English | Vietnamese |
|-------|---------|------------|
| Admin Guide | [admin-guide/en/](admin-guide/en/) | [admin-guide/vi/](admin-guide/vi/) |

## API Guides

| Guide | English | Vietnamese |
|-------|---------|------------|
| API Reference | [api-guide/en/](api-guide/en/) | [api-guide/vi/](api-guide/vi/) |

## Developer Guides

| Guide | English | Vietnamese |
|-------|---------|------------|
| Developer Guide | [developer-guide/en/](developer-guide/en/) | [developer-guide/vi/](developer-guide/vi/) |

---

## Specification Documents

The authoritative project specifications are in the repository root:

- `00-product/` — Vision, scope, constraints, glossary
- `01-domain/` — Domain model, knowledge tree specification
- `02-contracts/` — Four canonical contracts
- `03-architecture/` — Architecture, deployment, modules, pipeline
- `04-decisions/` — Architecture Decision Records (ADRs)
- `design/` — System prompt, benchmark dataset spec
- `tasks/` — Implementation task specifications
- `examples/` — Contract example files

### Reading Order

For new contributors:

1. `README.md` (repository root)
2. Vision (`00-product/`)
3. Architecture (`03-architecture/`)
4. Contracts (`02-contracts/`)
5. ADRs (`04-decisions/`)
6. Implementation Tasks (`tasks/`)
7. Design Documents (`design/`)

---

## Source of Truth

The specification documents in the repository root are the authoritative source for the project. Implementations should follow these documents unless an Architecture Decision Record (ADR) explicitly supersedes them.

Changes to contracts or architecture should be documented before implementation whenever practical.
# Release Manifest — v0.1.0

## Project

- **Project name:** Legal Knowledge Platform (Banking Legal Platform)
- **Version:** 0.1.0
- **Release date:** 2026-08-08
- **Release status:** READY WITH MINOR ISSUES

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For test tooling:

```bash
pip install -e ".[test]"
```

## Startup

```bash
legal-platform
```

Or:

```bash
python -m legal_platform
```

Default endpoint: `http://localhost:8080`

## Required Runtime

- Python 3.12+
- 2 GB RAM (4 GB recommended)
- 500 MB disk space
- (Optional) Tesseract OCR for scanned document processing

## Supported Deployment Method

- Local/single-server deployment via `pip install -e .` + `legal-platform`
- No Docker image (not part of the specified MVP architecture)
- No cloud deployment configuration (not part of the MVP)

## Test Result

- **Automated tests:** 632 passed, 0 failed, 0 skipped, 0 errors
- **E2E QA:** 12/12 scenarios passed
- **Release readiness:** READY WITH MINOR ISSUES

## E2E QA Status

Task 023 End-to-End QA completed. Two CRITICAL bugs (PaginatedResponse serialization, handler state isolation) and one MAJOR bug (VaultService thread-safety) were found and fixed. No unresolved BLOCKER or CRITICAL issues remain.

## Included Artifacts

| Artifact | Location |
|----------|----------|
| Source code | Repository root |
| Python package | `legal-platform==0.1.0` |
| Console script | `legal-platform` |
| Python module | `legal_platform` |
| User Guide (EN) | `docs/user-guide/en/` |
| User Guide (VI) | `docs/user-guide/vi/` |
| Admin Guide (EN) | `docs/admin-guide/en/` |
| Admin Guide (VI) | `docs/admin-guide/vi/` |
| API Guide (EN) | `docs/api-guide/en/` |
| API Guide (VI) | `docs/api-guide/vi/` |
| Developer Guide (EN) | `docs/developer-guide/en/` |
| Developer Guide (VI) | `docs/developer-guide/vi/` |
| Release Notes | `docs/release-notes/v0.1.0.md` |
| QA Report | `docs/qa/task-023-e2e-report.md` |
| Changelog | `CHANGELOG.md` |

## Demo Dataset

| Asset | Location |
|-------|----------|
| Sample document | `demo/sample-decision-15-2026.pdf` |
| Document generator | `demo/generate-sample-doc.py` |
| Load script | `demo/load-demo.sh` |
| Demo README | `demo/README.md` |

## Known Limitations

| Limitation | Impact |
|------------|--------|
| Automated processing pipeline not triggered after upload | Documents registered but not searchable until manually processed |
| In-memory storage by default | Data lost on restart |
| No LLM integration | Template-based answers |
| No conversation memory | Each question independent |
| Placeholder embedding engine | Limited semantic search quality |
| No real authentication | Any non-empty credentials accepted |
| No TLS/HTTPS | Plain HTTP traffic |
| No rate limiting | No abuse protection |
| No backup/restore automation | Manual file copying only |
| No `.gitignore` (now added) | Secret-commit risk mitigated |

## Release Readiness Status

**READY WITH MINOR ISSUES**

The release is functional and installable. Core workflows (install, start, login, vault, upload, list, search, ask) work end-to-end. Residual issues are minor (manual browser visual verification, persistent storage configuration) and do not block normal use.
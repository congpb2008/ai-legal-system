# Documentation

## Current release

- [Hosted HTTPS deployment](HOSTED-DEPLOYMENT.md): domain setup, isolated reverse proxy, Docker operation, command-line backups and host administrator recovery.

- [Windows quickstart](WINDOWS-QUICKSTART.md): installation, LAN access, first administrator, daily use, OCR, backup and recovery.
- [Maintainer guide](MAINTAINER-GUIDE.md): runtime/data map, security boundaries, API routes, source quotations, concurrency, packaging and testing.
- [Release handoff](RELEASE-HANDOFF.md): verified behavior, remaining release work and where to resume.
- [LAN-release decision](../04-decisions/adr-usable-lan-release.md): implementation decisions that supersede prototype assumptions.
- [Product README](../README.md): supported deployment shape and source/Docker commands.

The older `user-guide`, `admin-guide`, `api-guide` and `developer-guide` trees describe the earlier prototype and are retained as historical context. Their authentication, setup, UI and deployment details are superseded by the current-release documents above. Follow the implemented contracts and current guide when they differ from earlier proposals.

## Design history

`00-product/`, `01-domain/`, `02-contracts/`, `03-architecture/`, `04-decisions/`, `design/` and `tasks/` retain the original product/domain/architecture plans. Read the current release decision before treating an older feature description as implemented behavior.

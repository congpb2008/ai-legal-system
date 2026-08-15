"""Release Checklist (tasks/018-release-checklist.md, module Release).

Defines a standardized release validation process. Every release shall satisfy
functional, quality and operational requirements before deployment.

No production deployment should bypass this checklist.

The checklist covers:
    - Source Control
    - Contracts
    - Upload Pipeline
    - Retrieval Pipeline
    - Generation Pipeline
    - Vault
    - Platform API
    - Web UI
    - Performance
    - Evaluation
    - Regression
    - Security
    - Observability
    - Infrastructure
    - Documentation
    - Rollback Plan
    - Post-release Verification
    - Release Artifacts
"""

from legal_platform.modules.release.checklist import (
    ReleaseStage,
    CheckCategory,
    CheckItem,
    CheckResult,
    CheckStatus,
    ReleaseReport,
    RollbackPlan,
    PostReleaseVerification,
    ReleaseArtifact,
    create_standard_checklist,
)
from legal_platform.modules.release.service import ReleaseService

__all__ = [
    "ReleaseChecklist",
    "ReleaseStage",
    "CheckCategory",
    "CheckItem",
    "CheckResult",
    "CheckStatus",
    "ReleaseReport",
    "RollbackPlan",
    "PostReleaseVerification",
    "ReleaseArtifact",
    "ReleaseService",
]
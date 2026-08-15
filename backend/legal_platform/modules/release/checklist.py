"""Release checklist models (tasks/018-release-checklist.md).

Defines the release stages, check categories, check items, and result types
used to validate a release before deployment.

The checklist covers 18 categories with ~90 individual checks across:
    Development → Integration → Evaluation → Release Candidate → Production
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from legal_platform.contracts.common import now_utc, utc_iso


class ReleaseStage(str, Enum):
    """Stages of a release (tasks/018 #ReleaseStages)."""

    DEVELOPMENT = "DEVELOPMENT"
    INTEGRATION = "INTEGRATION"
    EVALUATION = "EVALUATION"
    RELEASE_CANDIDATE = "RELEASE_CANDIDATE"
    PRODUCTION = "PRODUCTION"


class CheckStatus(str, Enum):
    """Status of a single checklist item.

    - PASS: the check passed.
    - FAIL: the check failed (blocks release if critical).
    - SKIP: the check was skipped (not applicable).
    - PENDING: the check has not been run yet.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    PENDING = "PENDING"


class CheckCategory(str, Enum):
    """Categories of checklist items (tasks/018)."""

    SOURCE_CONTROL = "SOURCE_CONTROL"
    CONTRACTS = "CONTRACTS"
    UPLOAD_PIPELINE = "UPLOAD_PIPELINE"
    RETRIEVAL_PIPELINE = "RETRIEVAL_PIPELINE"
    GENERATION_PIPELINE = "GENERATION_PIPELINE"
    VAULT = "VAULT"
    PLATFORM_API = "PLATFORM_API"
    WEB_UI = "WEB_UI"
    PERFORMANCE = "PERFORMANCE"
    EVALUATION = "EVALUATION"
    REGRESSION = "REGRESSION"
    SECURITY = "SECURITY"
    OBSERVABILITY = "OBSERVABILITY"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    DOCUMENTATION = "DOCUMENTATION"
    ROLLBACK = "ROLLBACK"
    POST_RELEASE = "POST_RELEASE"
    ARTIFACTS = "ARTIFACTS"


@dataclass
class CheckItem:
    """A single item in the release checklist.

    Fields:
        id: unique identifier for this check.
        category: the check category.
        description: human-readable description.
        critical: whether failure blocks the release.
        status: current check status.
        detail: additional detail (e.g. error message).
        verified_by: who verified this check.
        verified_at: when the check was verified.
    """

    id: str
    category: CheckCategory
    description: str
    critical: bool = True
    status: CheckStatus = CheckStatus.PENDING
    detail: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None

    def pass_check(self, verified_by: str = "system", detail: Optional[str] = None) -> None:
        """Mark this check as passed."""
        self.status = CheckStatus.PASS
        self.verified_by = verified_by
        self.verified_at = utc_iso(now_utc())
        if detail:
            self.detail = detail

    def fail_check(self, verified_by: str = "system", detail: Optional[str] = None) -> None:
        """Mark this check as failed."""
        self.status = CheckStatus.FAIL
        self.verified_by = verified_by
        self.verified_at = utc_iso(now_utc())
        self.detail = detail or "Check failed"

    def skip_check(self, reason: str = "Not applicable") -> None:
        """Mark this check as skipped."""
        self.status = CheckStatus.SKIP
        self.detail = reason


@dataclass
class CheckResult:
    """Result of running a single check.

    Fields:
        check_id: the check item ID.
        passed: whether the check passed.
        detail: additional detail.
    """

    check_id: str
    passed: bool
    detail: Optional[str] = None


@dataclass
class RollbackPlan:
    """Rollback plan (tasks/018 #RollbackPlan).

    Fields:
        previous_release_available: whether the previous release is available.
        database_rollback_defined: whether DB rollback strategy is defined.
        index_rollback_defined: whether index rollback strategy is defined.
        config_rollback_verified: whether config rollback is verified.
        rollback_owner_assigned: whether a rollback owner is assigned.
        procedure_documented: whether the rollback procedure is documented.
    """

    previous_release_available: bool = False
    database_rollback_defined: bool = False
    index_rollback_defined: bool = False
    config_rollback_verified: bool = False
    rollback_owner_assigned: bool = False
    procedure_documented: bool = False

    @property
    def ready(self) -> bool:
        """True if all rollback requirements are met."""
        return all([
            self.previous_release_available,
            self.database_rollback_defined,
            self.index_rollback_defined,
            self.config_rollback_verified,
            self.rollback_owner_assigned,
            self.procedure_documented,
        ])


@dataclass
class PostReleaseVerification:
    """Post-release verification results (tasks/018 #Post-releaseVerification).

    Fields:
        health_endpoints: whether health endpoints respond.
        upload_workflow: whether upload workflow works.
        search_workflow: whether search workflow works.
        ask_workflow: whether ask workflow works.
        citation_integrity: whether citations are intact.
        error_rate_acceptable: whether error rate is acceptable.
        latency_acceptable: whether latency is acceptable.
        dashboards_updated: whether dashboards show data.
        alerts_configured: whether alerts are configured.
        user_smoke_test: whether user acceptance smoke test passed.
    """

    health_endpoints: bool = False
    upload_workflow: bool = False
    search_workflow: bool = False
    ask_workflow: bool = False
    citation_integrity: bool = False
    error_rate_acceptable: bool = False
    latency_acceptable: bool = False
    dashboards_updated: bool = False
    alerts_configured: bool = False
    user_smoke_test: bool = False

    @property
    def passed(self) -> bool:
        """True if all post-release checks pass."""
        return all([
            self.health_endpoints,
            self.upload_workflow,
            self.search_workflow,
            self.ask_workflow,
            self.citation_integrity,
            self.error_rate_acceptable,
            self.latency_acceptable,
        ])


@dataclass
class ReleaseArtifact:
    """A release artifact (tasks/018 #ReleaseArtifacts).

    Fields:
        name: artifact name.
        description: artifact description.
        produced: whether the artifact was produced.
        location: where the artifact is stored.
    """

    name: str
    description: str = ""
    produced: bool = False
    location: Optional[str] = None


@dataclass
class ReleaseReport:
    """Complete release report (tasks/018).

    Fields:
        report_id: unique identifier for this release report.
        release_version: the release version string.
        release_stage: the current release stage.
        created_at: when the report was created.
        completed_at: when the release was completed.
        checks: all checklist items.
        rollback_plan: the rollback plan.
        post_release: post-release verification.
        artifacts: release artifacts.
        approved_by: who approved the release.
        approved_at: when the release was approved.
        metadata: additional metadata.
    """

    report_id: str = field(default_factory=lambda: str(__import__("uuid").uuid4()))
    release_version: str = ""
    release_stage: ReleaseStage = ReleaseStage.DEVELOPMENT
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    completed_at: Optional[str] = None
    checks: list[CheckItem] = field(default_factory=list)
    rollback_plan: RollbackPlan = field(default_factory=RollbackPlan)
    post_release: PostReleaseVerification = field(default_factory=PostReleaseVerification)
    artifacts: list[ReleaseArtifact] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.PASS)

    @property
    def failed_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def skipped_checks(self) -> int:
        return sum(1 for c in self.checks if c.status == CheckStatus.SKIP)

    @property
    def critical_failures(self) -> list[CheckItem]:
        """Critical checks that failed."""
        return [c for c in self.checks if c.status == CheckStatus.FAIL and c.critical]

    @property
    def can_release(self) -> bool:
        """True if the release can proceed.

        Per tasks/018 #ProductionReadiness:
            ✓ All critical checklist items pass.
            ✓ No unresolved critical failures exist.
        """
        return len(self.critical_failures) == 0

    @property
    def pass_rate(self) -> float:
        """Fraction of non-skipped checks that passed."""
        total = self.total_checks - self.skipped_checks
        if total == 0:
            return 1.0
        return self.passed_checks / total


# ---------------------------------------------------------------------------
# Standard checklist factory
# ---------------------------------------------------------------------------


def create_standard_checklist() -> list[CheckItem]:
    """Create the standard release checklist with all items from the spec.

    Returns:
        A list of CheckItem instances covering all 18 categories.
    """
    checks: list[CheckItem] = []

    # --- Source Control ---
    checks.extend([
        CheckItem(id="sc-001", category=CheckCategory.SOURCE_CONTROL,
                  description="All code committed", critical=True),
        CheckItem(id="sc-002", category=CheckCategory.SOURCE_CONTROL,
                  description="No unreviewed changes", critical=True),
        CheckItem(id="sc-003", category=CheckCategory.SOURCE_CONTROL,
                  description="Release tag created", critical=True),
        CheckItem(id="sc-004", category=CheckCategory.SOURCE_CONTROL,
                  description="Version number updated", critical=True),
        CheckItem(id="sc-005", category=CheckCategory.SOURCE_CONTROL,
                  description="Changelog completed", critical=False),
    ])

    # --- Contracts ---
    checks.extend([
        CheckItem(id="ct-001", category=CheckCategory.CONTRACTS,
                  description="Document Contract unchanged or versioned", critical=True),
        CheckItem(id="ct-002", category=CheckCategory.CONTRACTS,
                  description="Knowledge Tree Contract valid", critical=True),
        CheckItem(id="ct-003", category=CheckCategory.CONTRACTS,
                  description="Retrieval Contract valid", critical=True),
        CheckItem(id="ct-004", category=CheckCategory.CONTRACTS,
                  description="Answer Contract valid", critical=True),
        CheckItem(id="ct-005", category=CheckCategory.CONTRACTS,
                  description="Backward compatibility verified", critical=True),
    ])

    # --- Upload Pipeline ---
    checks.extend([
        CheckItem(id="up-001", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Upload Service operational", critical=True),
        CheckItem(id="up-002", category=CheckCategory.UPLOAD_PIPELINE,
                  description="OCR operational", critical=True),
        CheckItem(id="up-003", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Parser operational", critical=True),
        CheckItem(id="up-004", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Knowledge Tree Builder operational", critical=True),
        CheckItem(id="up-005", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Chunking operational", critical=True),
        CheckItem(id="up-006", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Embedding operational", critical=True),
        CheckItem(id="up-007", category=CheckCategory.UPLOAD_PIPELINE,
                  description="Vector Index operational", critical=True),
        CheckItem(id="up-008", category=CheckCategory.UPLOAD_PIPELINE,
                  description="End-to-end upload succeeds", critical=True),
    ])

    # --- Retrieval Pipeline ---
    checks.extend([
        # F10: Query Planner is not in MVP; mark as N/A
        CheckItem(id="rp-001", category=CheckCategory.RETRIEVAL_PIPELINE,
                  description="Query Planner operational (N/A for MVP)", critical=False),
        CheckItem(id="rp-002", category=CheckCategory.RETRIEVAL_PIPELINE,
                  description="Retrieval operational", critical=True),
        CheckItem(id="rp-003", category=CheckCategory.RETRIEVAL_PIPELINE,
                  description="Ranking operational", critical=True),
        CheckItem(id="rp-004", category=CheckCategory.RETRIEVAL_PIPELINE,
                  description="Evidence Package generated", critical=True),
        CheckItem(id="rp-005", category=CheckCategory.RETRIEVAL_PIPELINE,
                  description="Retrieval Contract validation passes", critical=True),
    ])

    # --- Generation Pipeline ---
    checks.extend([
        CheckItem(id="gp-001", category=CheckCategory.GENERATION_PIPELINE,
                  description="Generation operational", critical=True),
        CheckItem(id="gp-002", category=CheckCategory.GENERATION_PIPELINE,
                  description="Citation Builder operational", critical=True),
        CheckItem(id="gp-003", category=CheckCategory.GENERATION_PIPELINE,
                  description="Answer Contract validation passes", critical=True),
        CheckItem(id="gp-004", category=CheckCategory.GENERATION_PIPELINE,
                  description="Unsupported claims rejected", critical=True),
        CheckItem(id="gp-005", category=CheckCategory.GENERATION_PIPELINE,
                  description="Citation traceability verified", critical=True),
    ])

    # --- Vault ---
    checks.extend([
        CheckItem(id="vt-001", category=CheckCategory.VAULT,
                  description="Permission checks pass", critical=True),
        CheckItem(id="vt-002", category=CheckCategory.VAULT,
                  description="Vault isolation verified", critical=True),
        CheckItem(id="vt-003", category=CheckCategory.VAULT,
                  description="Cross-vault leakage absent", critical=True),
        CheckItem(id="vt-004", category=CheckCategory.VAULT,
                  description="Personal Vault isolation verified", critical=True),
    ])

    # --- Platform API ---
    checks.extend([
        CheckItem(id="api-001", category=CheckCategory.PLATFORM_API,
                  description="Authentication", critical=True),
        CheckItem(id="api-002", category=CheckCategory.PLATFORM_API,
                  description="Authorization", critical=True),
        CheckItem(id="api-003", category=CheckCategory.PLATFORM_API,
                  description="Upload API", critical=True),
        CheckItem(id="api-004", category=CheckCategory.PLATFORM_API,
                  description="Search API", critical=True),
        CheckItem(id="api-005", category=CheckCategory.PLATFORM_API,
                  description="Ask API", critical=True),
        CheckItem(id="api-006", category=CheckCategory.PLATFORM_API,
                  description="Health API", critical=True),
        CheckItem(id="api-007", category=CheckCategory.PLATFORM_API,
                  description="Error schema", critical=True),
    ])

    # --- Web UI ---
    checks.extend([
        CheckItem(id="ui-001", category=CheckCategory.WEB_UI,
                  description="Upload workflow", critical=True),
        CheckItem(id="ui-002", category=CheckCategory.WEB_UI,
                  description="Search workflow", critical=True),
        CheckItem(id="ui-003", category=CheckCategory.WEB_UI,
                  description="Ask workflow", critical=True),
        CheckItem(id="ui-004", category=CheckCategory.WEB_UI,
                  description="Citation viewer", critical=True),
        CheckItem(id="ui-005", category=CheckCategory.WEB_UI,
                  description="Document viewer", critical=False),
        CheckItem(id="ui-006", category=CheckCategory.WEB_UI,
                  description="Vault browser", critical=True),
        CheckItem(id="ui-007", category=CheckCategory.WEB_UI,
                  description="Responsive layout", critical=False),
    ])

    # --- Performance ---
    checks.extend([
        CheckItem(id="pf-001", category=CheckCategory.PERFORMANCE,
                  description="Upload latency acceptable", critical=False),
        CheckItem(id="pf-002", category=CheckCategory.PERFORMANCE,
                  description="OCR throughput acceptable", critical=False),
        CheckItem(id="pf-003", category=CheckCategory.PERFORMANCE,
                  description="Retrieval latency within SLA", critical=True),
        CheckItem(id="pf-004", category=CheckCategory.PERFORMANCE,
                  description="Generation latency acceptable", critical=True),
        CheckItem(id="pf-005", category=CheckCategory.PERFORMANCE,
                  description="API latency acceptable", critical=True),
        CheckItem(id="pf-006", category=CheckCategory.PERFORMANCE,
                  description="Large document processing verified", critical=False),
    ])

    # --- Evaluation ---
    checks.extend([
        CheckItem(id="ev-001", category=CheckCategory.EVALUATION,
                  description="Benchmark suite executed", critical=True),
        CheckItem(id="ev-002", category=CheckCategory.EVALUATION,
                  description="Retrieval metrics acceptable", critical=True),
        CheckItem(id="ev-003", category=CheckCategory.EVALUATION,
                  description="Ranking metrics acceptable", critical=True),
        CheckItem(id="ev-004", category=CheckCategory.EVALUATION,
                  description="Generation metrics acceptable", critical=True),
        CheckItem(id="ev-005", category=CheckCategory.EVALUATION,
                  description="Citation metrics acceptable", critical=True),
        CheckItem(id="ev-006", category=CheckCategory.EVALUATION,
                  description="End-to-end benchmark passed", critical=True),
    ])

    # --- Regression ---
    checks.extend([
        CheckItem(id="rg-001", category=CheckCategory.REGRESSION,
                  description="No critical regression", critical=True),
        CheckItem(id="rg-002", category=CheckCategory.REGRESSION,
                  description="Failure report reviewed", critical=True),
        CheckItem(id="rg-003", category=CheckCategory.REGRESSION,
                  description="New failures accepted or fixed", critical=True),
        CheckItem(id="rg-004", category=CheckCategory.REGRESSION,
                  description="Historical comparison completed", critical=True),
    ])

    # --- Security ---
    checks.extend([
        CheckItem(id="se-001", category=CheckCategory.SECURITY,
                  description="Authentication verified", critical=True),
        CheckItem(id="se-002", category=CheckCategory.SECURITY,
                  description="Authorization verified", critical=True),
        CheckItem(id="se-003", category=CheckCategory.SECURITY,
                  description="Input validation", critical=True),
        CheckItem(id="se-004", category=CheckCategory.SECURITY,
                  description="Audit logging", critical=True),
        CheckItem(id="se-005", category=CheckCategory.SECURITY,
                  description="Sensitive data protected", critical=True),
        CheckItem(id="se-006", category=CheckCategory.SECURITY,
                  description="Vault permissions enforced", critical=True),
    ])

    # --- Observability ---
    checks.extend([
        CheckItem(id="ob-001", category=CheckCategory.OBSERVABILITY,
                  description="Logs", critical=True),
        CheckItem(id="ob-002", category=CheckCategory.OBSERVABILITY,
                  description="Metrics", critical=True),
        CheckItem(id="ob-003", category=CheckCategory.OBSERVABILITY,
                  description="Traces", critical=False),
        CheckItem(id="ob-004", category=CheckCategory.OBSERVABILITY,
                  description="Dashboards", critical=False),
        CheckItem(id="ob-005", category=CheckCategory.OBSERVABILITY,
                  description="Alerts", critical=True),
        CheckItem(id="ob-006", category=CheckCategory.OBSERVABILITY,
                  description="Audit logs", critical=True),
    ])

    # --- Infrastructure ---
    checks.extend([
        CheckItem(id="in-001", category=CheckCategory.INFRASTRUCTURE,
                  description="Database migrations complete", critical=True),
        CheckItem(id="in-002", category=CheckCategory.INFRASTRUCTURE,
                  description="Vector index available", critical=True),
        CheckItem(id="in-003", category=CheckCategory.INFRASTRUCTURE,
                  description="Object storage available", critical=True),
        CheckItem(id="in-004", category=CheckCategory.INFRASTRUCTURE,
                  description="Backup completed", critical=True),
        CheckItem(id="in-005", category=CheckCategory.INFRASTRUCTURE,
                  description="Restore tested", critical=True),
        CheckItem(id="in-006", category=CheckCategory.INFRASTRUCTURE,
                  description="Health checks green", critical=True),
    ])

    # --- Documentation ---
    checks.extend([
        CheckItem(id="dc-001", category=CheckCategory.DOCUMENTATION,
                  description="Architecture updated", critical=False),
        CheckItem(id="dc-002", category=CheckCategory.DOCUMENTATION,
                  description="ADRs updated", critical=False),
        CheckItem(id="dc-003", category=CheckCategory.DOCUMENTATION,
                  description="API documentation updated", critical=True),
        CheckItem(id="dc-004", category=CheckCategory.DOCUMENTATION,
                  description="Release notes completed", critical=True),
        CheckItem(id="dc-005", category=CheckCategory.DOCUMENTATION,
                  description="Deployment guide updated", critical=True),
    ])

    # --- Rollback ---
    checks.extend([
        CheckItem(id="rb-001", category=CheckCategory.ROLLBACK,
                  description="Previous release available", critical=True),
        CheckItem(id="rb-002", category=CheckCategory.ROLLBACK,
                  description="Database rollback strategy defined", critical=True),
        CheckItem(id="rb-003", category=CheckCategory.ROLLBACK,
                  description="Index rollback strategy defined", critical=True),
        CheckItem(id="rb-004", category=CheckCategory.ROLLBACK,
                  description="Configuration rollback verified", critical=True),
        CheckItem(id="rb-005", category=CheckCategory.ROLLBACK,
                  description="Rollback owner assigned", critical=True),
        CheckItem(id="rb-006", category=CheckCategory.ROLLBACK,
                  description="Rollback procedure documented", critical=True),
    ])

    # --- Post-release ---
    checks.extend([
        CheckItem(id="pr-001", category=CheckCategory.POST_RELEASE,
                  description="Health endpoints", critical=True),
        CheckItem(id="pr-002", category=CheckCategory.POST_RELEASE,
                  description="Upload workflow", critical=True),
        CheckItem(id="pr-003", category=CheckCategory.POST_RELEASE,
                  description="Search workflow", critical=True),
        CheckItem(id="pr-004", category=CheckCategory.POST_RELEASE,
                  description="Ask workflow", critical=True),
        CheckItem(id="pr-005", category=CheckCategory.POST_RELEASE,
                  description="Citation integrity", critical=True),
        CheckItem(id="pr-006", category=CheckCategory.POST_RELEASE,
                  description="Error rate", critical=True),
        CheckItem(id="pr-007", category=CheckCategory.POST_RELEASE,
                  description="Latency", critical=True),
        CheckItem(id="pr-008", category=CheckCategory.POST_RELEASE,
                  description="Dashboards", critical=False),
        CheckItem(id="pr-009", category=CheckCategory.POST_RELEASE,
                  description="Alerts", critical=True),
        CheckItem(id="pr-010", category=CheckCategory.POST_RELEASE,
                  description="User acceptance smoke test", critical=True),
    ])

    # --- Artifacts ---
    checks.extend([
        CheckItem(id="ar-001", category=CheckCategory.ARTIFACTS,
                  description="Release version", critical=True),
        CheckItem(id="ar-002", category=CheckCategory.ARTIFACTS,
                  description="Release notes", critical=True),
        CheckItem(id="ar-003", category=CheckCategory.ARTIFACTS,
                  description="Evaluation report", critical=True),
        CheckItem(id="ar-004", category=CheckCategory.ARTIFACTS,
                  description="Failure report", critical=True),
        CheckItem(id="ar-005", category=CheckCategory.ARTIFACTS,
                  description="Deployment log", critical=True),
        CheckItem(id="ar-006", category=CheckCategory.ARTIFACTS,
                  description="Audit record", critical=True),
        CheckItem(id="ar-007", category=CheckCategory.ARTIFACTS,
                  description="Release approval", critical=True),
    ])

    return checks
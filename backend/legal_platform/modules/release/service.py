"""Release Service (tasks/018-release-checklist.md).

Orchestrates the release validation process. Creates release reports,
runs automated checks, manages rollback plans, and tracks release artifacts.

No production deployment should bypass this checklist.
"""

from __future__ import annotations

import json
import sqlite3
import time
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.modules.release.checklist import (
    CheckCategory,
    CheckItem,
    CheckResult,
    CheckStatus,
    PostReleaseVerification,
    ReleaseArtifact,
    ReleaseReport,
    ReleaseStage,
    RollbackPlan,
    create_standard_checklist,
)
from legal_platform.storage.db import in_memory


_RELEASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS release_reports (
    report_id       TEXT PRIMARY KEY,
    release_version TEXT NOT NULL,
    release_stage   TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT,
    approved_by     TEXT,
    approved_at     TEXT,
    can_release     INTEGER NOT NULL DEFAULT 0,
    pass_rate       REAL NOT NULL DEFAULT 0.0,
    total_checks    INTEGER NOT NULL DEFAULT 0,
    passed_checks   INTEGER NOT NULL DEFAULT 0,
    failed_checks   INTEGER NOT NULL DEFAULT 0,
    skipped_checks  INTEGER NOT NULL DEFAULT 0,
    report_json     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_release_version ON release_reports(release_version);
CREATE INDEX IF NOT EXISTS idx_release_stage   ON release_reports(release_stage);
"""


class ReleaseService:
    """The Release Service.

    Defines a standardized release validation process. Every release shall
    satisfy functional, quality and operational requirements before deployment.

    No production deployment should bypass this checklist.
    """

    def __init__(self, conn: "sqlite3.Connection | None" = None):
        self._conn = conn or in_memory()
        self._conn.executescript(_RELEASE_SCHEMA)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    # ------------------------------------------------------------------
    # Create release
    # ------------------------------------------------------------------

    def create_release(
        self,
        release_version: str,
        *,
        stage: "str | ReleaseStage" = ReleaseStage.DEVELOPMENT,
    ) -> ReleaseReport:
        """Create a new release report with the standard checklist.

        Args:
            release_version: the release version string.
            stage: the current release stage.

        Returns:
            A ReleaseReport with all standard checklist items.
        """
        if isinstance(stage, str):
            stage = ReleaseStage(stage.upper())

        checks = create_standard_checklist()
        report = ReleaseReport(
            release_version=release_version,
            release_stage=stage,
            checks=checks,
        )
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Update checks
    # ------------------------------------------------------------------

    def update_check(
        self,
        report_id: str,
        check_id: str,
        status: "str | CheckStatus",
        *,
        verified_by: str = "system",
        detail: "str | None" = None,
    ) -> ReleaseReport:
        """Update the status of a single checklist item.

        Args:
            report_id: the release report ID.
            check_id: the check item ID.
            status: PASS, FAIL, or SKIP.
            verified_by: who verified this check.
            detail: optional detail.

        Returns:
            The updated ReleaseReport.
        """
        if isinstance(status, str):
            status = CheckStatus(status.upper())

        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")

        for check in report.checks:
            if check.id == check_id:
                if status == CheckStatus.PASS:
                    check.pass_check(verified_by=verified_by, detail=detail)
                elif status == CheckStatus.FAIL:
                    check.fail_check(verified_by=verified_by, detail=detail)
                elif status == CheckStatus.SKIP:
                    check.skip_check(reason=detail or "Not applicable")
                break
        else:
            raise KeyError(f"Check {check_id} not found in report {report_id}")

        self._persist(report)
        return report

    def update_checks_bulk(
        self,
        report_id: str,
        results: list[CheckResult],
        *,
        verified_by: str = "system",
    ) -> ReleaseReport:
        """Update multiple checklist items at once.

        Args:
            report_id: the release report ID.
            results: list of check results.
            verified_by: who verified these checks.

        Returns:
            The updated ReleaseReport.
        """
        for result in results:
            status = CheckStatus.PASS if result.passed else CheckStatus.FAIL
            self.update_check(
                report_id, result.check_id, status,
                verified_by=verified_by, detail=result.detail,
            )
        return self.get_report(report_id)

    # ------------------------------------------------------------------
    # Rollback plan
    # ------------------------------------------------------------------

    def set_rollback_plan(
        self,
        report_id: str,
        plan: RollbackPlan,
    ) -> ReleaseReport:
        """Set the rollback plan for a release.

        Args:
            report_id: the release report ID.
            plan: the rollback plan.

        Returns:
            The updated ReleaseReport.
        """
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")
        report.rollback_plan = plan
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Post-release verification
    # ------------------------------------------------------------------

    def set_post_release(
        self,
        report_id: str,
        verification: PostReleaseVerification,
    ) -> ReleaseReport:
        """Set post-release verification results.

        Args:
            report_id: the release report ID.
            verification: the post-release verification.

        Returns:
            The updated ReleaseReport.
        """
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")
        report.post_release = verification
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def add_artifact(
        self,
        report_id: str,
        name: str,
        *,
        description: str = "",
        location: "str | None" = None,
    ) -> ReleaseReport:
        """Add a release artifact.

        Args:
            report_id: the release report ID.
            name: artifact name.
            description: artifact description.
            location: where the artifact is stored.

        Returns:
            The updated ReleaseReport.
        """
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")
        artifact = ReleaseArtifact(
            name=name,
            description=description,
            produced=True,
            location=location,
        )
        report.artifacts.append(artifact)
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Approval
    # ------------------------------------------------------------------

    def approve_release(
        self,
        report_id: str,
        approved_by: str,
    ) -> ReleaseReport:
        """Approve a release for deployment.

        Args:
            report_id: the release report ID.
            approved_by: who approved the release.

        Returns:
            The updated ReleaseReport.

        Raises:
            ValueError: if the release has critical failures.
        """
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")

        if not report.can_release:
            failures = [c.id for c in report.critical_failures]
            raise ValueError(
                f"Cannot approve release: critical failures exist: {failures}. "
                "All critical checks must pass before deployment."
            )

        report.approved_by = approved_by
        report.approved_at = utc_iso(now_utc())
        report.release_stage = ReleaseStage.PRODUCTION
        report.completed_at = utc_iso(now_utc())
        self._persist(report)
        return report

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_report(self, report_id: str) -> Optional[ReleaseReport]:
        """Retrieve a release report by ID."""
        row = self._conn.execute(
            "SELECT report_json FROM release_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        if row is None:
            return None
        return self._report_from_json(row["report_json"])

    def list_reports(
        self,
        *,
        release_version: "str | None" = None,
        stage: "str | ReleaseStage | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReleaseReport]:
        """List release reports."""
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if release_version is not None:
            clauses.append("release_version = :release_version")
            params["release_version"] = release_version
        if stage is not None:
            s = stage.value if isinstance(stage, ReleaseStage) else stage
            clauses.append("release_stage = :release_stage")
            params["release_stage"] = s
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT report_json FROM release_reports{where} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return [self._report_from_json(r["report_json"]) for r in rows]

    def delete_report(self, report_id: str) -> bool:
        """Delete a release report."""
        cur = self._conn.execute(
            "DELETE FROM release_reports WHERE report_id = ?",
            (report_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_summary(self, report_id: str) -> dict[str, Any]:
        """Get a human-readable summary of a release report.

        Args:
            report_id: the release report ID.

        Returns:
            A dict with summary information.
        """
        report = self.get_report(report_id)
        if report is None:
            raise KeyError(f"Release report {report_id} not found")

        return {
            "release_version": report.release_version,
            "stage": report.release_stage.value,
            "created_at": report.created_at,
            "completed_at": report.completed_at,
            "approved_by": report.approved_by,
            "approved_at": report.approved_at,
            "can_release": report.can_release,
            "pass_rate": round(report.pass_rate, 4),
            "total_checks": report.total_checks,
            "passed": report.passed_checks,
            "failed": report.failed_checks,
            "skipped": report.skipped_checks,
            "critical_failures": [
                {"id": c.id, "description": c.description, "detail": c.detail}
                for c in report.critical_failures
            ],
            "rollback_ready": report.rollback_plan.ready,
            "post_release_passed": report.post_release.passed,
            "artifact_count": len(report.artifacts),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self, report: ReleaseReport) -> None:
        """Persist a release report."""
        import dataclasses
        import json as _json

        def _serialize(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj):
                return {f.name: _serialize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            return obj

        report_json = _json.dumps(_serialize(report), ensure_ascii=False)

        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO release_reports
                    (report_id, release_version, release_stage, created_at,
                     completed_at, approved_by, approved_at, can_release,
                     pass_rate, total_checks, passed_checks, failed_checks,
                     skipped_checks, report_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.release_version,
                    report.release_stage.value if isinstance(report.release_stage, ReleaseStage) else report.release_stage,
                    report.created_at,
                    report.completed_at,
                    report.approved_by,
                    report.approved_at,
                    1 if report.can_release else 0,
                    report.pass_rate,
                    report.total_checks,
                    report.passed_checks,
                    report.failed_checks,
                    report.skipped_checks,
                    report_json,
                ),
            )

    @staticmethod
    def _report_from_json(json_str: str) -> ReleaseReport:
        """Reconstruct a ReleaseReport from JSON."""
        import dataclasses
        import json as _json

        data = _json.loads(json_str)

        def _deserialize_checks(items: list[dict]) -> list[CheckItem]:
            return [
                CheckItem(
                    id=item["id"],
                    category=CheckCategory(item["category"]),
                    description=item["description"],
                    critical=item.get("critical", True),
                    status=CheckStatus(item.get("status", "PENDING")),
                    detail=item.get("detail"),
                    verified_by=item.get("verified_by"),
                    verified_at=item.get("verified_at"),
                )
                for item in items
            ]

        def _deserialize_artifacts(items: list[dict]) -> list[ReleaseArtifact]:
            return [
                ReleaseArtifact(
                    name=item["name"],
                    description=item.get("description", ""),
                    produced=item.get("produced", False),
                    location=item.get("location"),
                )
                for item in items
            ]

        return ReleaseReport(
            report_id=data.get("report_id", ""),
            release_version=data.get("release_version", ""),
            release_stage=ReleaseStage(data.get("release_stage", "DEVELOPMENT")),
            created_at=data.get("created_at", ""),
            completed_at=data.get("completed_at"),
            checks=_deserialize_checks(data.get("checks", [])),
            rollback_plan=RollbackPlan(
                previous_release_available=data.get("rollback_plan", {}).get("previous_release_available", False),
                database_rollback_defined=data.get("rollback_plan", {}).get("database_rollback_defined", False),
                index_rollback_defined=data.get("rollback_plan", {}).get("index_rollback_defined", False),
                config_rollback_verified=data.get("rollback_plan", {}).get("config_rollback_verified", False),
                rollback_owner_assigned=data.get("rollback_plan", {}).get("rollback_owner_assigned", False),
                procedure_documented=data.get("rollback_plan", {}).get("procedure_documented", False),
            ),
            post_release=PostReleaseVerification(
                health_endpoints=data.get("post_release", {}).get("health_endpoints", False),
                upload_workflow=data.get("post_release", {}).get("upload_workflow", False),
                search_workflow=data.get("post_release", {}).get("search_workflow", False),
                ask_workflow=data.get("post_release", {}).get("ask_workflow", False),
                citation_integrity=data.get("post_release", {}).get("citation_integrity", False),
                error_rate_acceptable=data.get("post_release", {}).get("error_rate_acceptable", False),
                latency_acceptable=data.get("post_release", {}).get("latency_acceptable", False),
                dashboards_updated=data.get("post_release", {}).get("dashboards_updated", False),
                alerts_configured=data.get("post_release", {}).get("alerts_configured", False),
                user_smoke_test=data.get("post_release", {}).get("user_smoke_test", False),
            ),
            artifacts=_deserialize_artifacts(data.get("artifacts", [])),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            metadata=data.get("metadata", {}),
        )
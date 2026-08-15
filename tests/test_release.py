"""Tests for the Release Checklist (Task 018).

Covers:
    - Domain models (CheckItem, CheckStatus, ReleaseReport, RollbackPlan, etc.)
    - Standard checklist factory (all 18 categories, ~90 checks)
    - ReleaseService (create, update checks, rollback, post-release, artifacts, approval)
    - Release gating (critical failures block release)
    - Persistence (create, read, list, delete)

The authoritative source is the Release Checklist specification
(tasks/018-release-checklist.md).
"""

import pytest

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
from legal_platform.modules.release.service import ReleaseService


# ======================================================================
# 1. Domain Models
# ======================================================================


class TestDomainModels:
    """Release checklist domain models."""

    def test_check_item_defaults(self):
        item = CheckItem(id="sc-001", category=CheckCategory.SOURCE_CONTROL,
                         description="All code committed")
        assert item.status == CheckStatus.PENDING
        assert item.critical is True
        assert item.verified_by is None

    def test_check_item_pass(self):
        item = CheckItem(id="sc-001", category=CheckCategory.SOURCE_CONTROL,
                         description="Test")
        item.pass_check(verified_by="reviewer", detail="All good")
        assert item.status == CheckStatus.PASS
        assert item.verified_by == "reviewer"
        assert item.detail == "All good"

    def test_check_item_fail(self):
        item = CheckItem(id="sc-001", category=CheckCategory.SOURCE_CONTROL,
                         description="Test")
        item.fail_check(detail="Missing commit")
        assert item.status == CheckStatus.FAIL
        assert item.detail == "Missing commit"

    def test_check_item_skip(self):
        item = CheckItem(id="rp-001", category=CheckCategory.RETRIEVAL_PIPELINE,
                         description="Query Planner")
        item.skip_check(reason="N/A for MVP")
        assert item.status == CheckStatus.SKIP
        assert item.detail == "N/A for MVP"

    def test_release_stages(self):
        assert ReleaseStage.DEVELOPMENT.value == "DEVELOPMENT"
        assert ReleaseStage.PRODUCTION.value == "PRODUCTION"

    def test_check_status_values(self):
        assert CheckStatus.PASS.value == "PASS"
        assert CheckStatus.FAIL.value == "FAIL"
        assert CheckStatus.PENDING.value == "PENDING"

    def test_check_categories(self):
        assert CheckCategory.SOURCE_CONTROL.value == "SOURCE_CONTROL"
        assert CheckCategory.SECURITY.value == "SECURITY"
        assert CheckCategory.ROLLBACK.value == "ROLLBACK"

    def test_rollback_plan_defaults(self):
        plan = RollbackPlan()
        assert plan.ready is False
        assert plan.previous_release_available is False

    def test_rollback_plan_ready(self):
        plan = RollbackPlan(
            previous_release_available=True,
            database_rollback_defined=True,
            index_rollback_defined=True,
            config_rollback_verified=True,
            rollback_owner_assigned=True,
            procedure_documented=True,
        )
        assert plan.ready is True

    def test_post_release_defaults(self):
        pr = PostReleaseVerification()
        assert pr.passed is False

    def test_post_release_passed(self):
        pr = PostReleaseVerification(
            health_endpoints=True,
            upload_workflow=True,
            search_workflow=True,
            ask_workflow=True,
            citation_integrity=True,
            error_rate_acceptable=True,
            latency_acceptable=True,
        )
        assert pr.passed is True

    def test_release_artifact(self):
        art = ReleaseArtifact(name="Release Notes", description="v1.0 notes",
                              produced=True, location="./releases/v1.0/notes.md")
        assert art.name == "Release Notes"
        assert art.produced is True

    def test_release_report_defaults(self):
        report = ReleaseReport(release_version="v1.0.0")
        assert report.report_id is not None
        assert report.release_stage == ReleaseStage.DEVELOPMENT
        assert report.can_release is True  # no checks yet
        assert report.pass_rate == 1.0

    def test_release_report_counts(self):
        checks = [
            CheckItem(id="c1", category=CheckCategory.SOURCE_CONTROL, description="c1"),
            CheckItem(id="c2", category=CheckCategory.SOURCE_CONTROL, description="c2"),
        ]
        checks[0].pass_check()
        checks[1].fail_check()
        report = ReleaseReport(release_version="v1.0", checks=checks)
        assert report.total_checks == 2
        assert report.passed_checks == 1
        assert report.failed_checks == 1
        assert report.pass_rate == 0.5

    def test_critical_failures_block_release(self):
        checks = [
            CheckItem(id="c1", category=CheckCategory.SECURITY, description="Auth",
                      critical=True),
            CheckItem(id="c2", category=CheckCategory.SECURITY, description="Input validation",
                      critical=False),
        ]
        checks[0].fail_check(detail="Auth broken")
        checks[1].fail_check(detail="Minor issue")
        report = ReleaseReport(release_version="v1.0", checks=checks)
        assert len(report.critical_failures) == 1
        assert report.can_release is False

    def test_non_critical_failures_dont_block(self):
        checks = [
            CheckItem(id="c1", category=CheckCategory.DOCUMENTATION, description="Docs",
                      critical=False),
        ]
        checks[0].fail_check()
        report = ReleaseReport(release_version="v1.0", checks=checks)
        assert len(report.critical_failures) == 0
        assert report.can_release is True

    def test_check_result(self):
        result = CheckResult(check_id="sc-001", passed=True, detail="All committed")
        assert result.check_id == "sc-001"
        assert result.passed is True


# ======================================================================
# 2. Standard Checklist
# ======================================================================


class TestStandardChecklist:
    """Standard release checklist factory."""

    def test_all_categories_present(self):
        checks = create_standard_checklist()
        categories = {c.category for c in checks}
        assert CheckCategory.SOURCE_CONTROL in categories
        assert CheckCategory.CONTRACTS in categories
        assert CheckCategory.UPLOAD_PIPELINE in categories
        assert CheckCategory.RETRIEVAL_PIPELINE in categories
        assert CheckCategory.GENERATION_PIPELINE in categories
        assert CheckCategory.VAULT in categories
        assert CheckCategory.PLATFORM_API in categories
        assert CheckCategory.WEB_UI in categories
        assert CheckCategory.PERFORMANCE in categories
        assert CheckCategory.EVALUATION in categories
        assert CheckCategory.REGRESSION in categories
        assert CheckCategory.SECURITY in categories
        assert CheckCategory.OBSERVABILITY in categories
        assert CheckCategory.INFRASTRUCTURE in categories
        assert CheckCategory.DOCUMENTATION in categories
        assert CheckCategory.ROLLBACK in categories
        assert CheckCategory.POST_RELEASE in categories
        assert CheckCategory.ARTIFACTS in categories

    def test_check_count(self):
        checks = create_standard_checklist()
        assert len(checks) >= 85  # ~90 checks across 18 categories

    def test_query_planner_skippable(self):
        """F10: Query Planner is not in MVP; should be non-critical."""
        checks = create_standard_checklist()
        qp = [c for c in checks if c.id == "rp-001"]
        assert len(qp) == 1
        assert qp[0].critical is False  # N/A for MVP

    def test_all_checks_have_ids(self):
        checks = create_standard_checklist()
        for c in checks:
            assert c.id, f"Check missing ID: {c.description}"
            assert c.description, f"Check missing description: {c.id}"

    def test_unique_ids(self):
        checks = create_standard_checklist()
        ids = [c.id for c in checks]
        assert len(ids) == len(set(ids))


# ======================================================================
# 3. ReleaseService
# ======================================================================


class TestReleaseService:
    """ReleaseService operations."""

    def test_create_release(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        assert report.release_version == "v1.0.0"
        assert report.release_stage == ReleaseStage.DEVELOPMENT
        assert report.total_checks >= 85

    def test_create_release_with_stage(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0", stage="RELEASE_CANDIDATE")
        assert report.release_stage == ReleaseStage.RELEASE_CANDIDATE

    def test_get_report(self):
        svc = ReleaseService()
        created = svc.create_release("v1.0.0")
        fetched = svc.get_report(created.report_id)
        assert fetched is not None
        assert fetched.release_version == "v1.0.0"

    def test_get_nonexistent(self):
        svc = ReleaseService()
        assert svc.get_report("nonexistent") is None

    def test_update_check_pass(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        updated = svc.update_check(report.report_id, "sc-001", "PASS",
                                   verified_by="tester", detail="All committed")
        check = [c for c in updated.checks if c.id == "sc-001"][0]
        assert check.status == CheckStatus.PASS
        assert check.verified_by == "tester"

    def test_update_check_fail(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        updated = svc.update_check(report.report_id, "sc-001", "FAIL",
                                   detail="Missing commits")
        check = [c for c in updated.checks if c.id == "sc-001"][0]
        assert check.status == CheckStatus.FAIL
        assert check.detail == "Missing commits"

    def test_update_check_skip(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        updated = svc.update_check(report.report_id, "rp-001", "SKIP",
                                   detail="N/A for MVP")
        check = [c for c in updated.checks if c.id == "rp-001"][0]
        assert check.status == CheckStatus.SKIP

    def test_update_nonexistent_check(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        with pytest.raises(KeyError):
            svc.update_check(report.report_id, "nonexistent", "PASS")

    def test_update_nonexistent_report(self):
        svc = ReleaseService()
        with pytest.raises(KeyError):
            svc.update_check("nonexistent", "sc-001", "PASS")

    def test_bulk_update(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        results = [
            CheckResult(check_id="sc-001", passed=True, detail="OK"),
            CheckResult(check_id="sc-002", passed=True, detail="OK"),
            CheckResult(check_id="ct-001", passed=False, detail="Contract issue"),
        ]
        updated = svc.update_checks_bulk(report.report_id, results, verified_by="ci")
        assert updated.passed_checks >= 2
        assert updated.failed_checks >= 1

    def test_approve_release(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        # Pass all checks
        for check in report.checks:
            svc.update_check(report.report_id, check.id, "PASS", verified_by="tester")

        approved = svc.approve_release(report.report_id, "release-manager")
        assert approved.approved_by == "release-manager"
        assert approved.approved_at is not None
        assert approved.release_stage == ReleaseStage.PRODUCTION

    def test_approve_release_with_failures(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        # Fail a critical check
        svc.update_check(report.report_id, "sc-001", "FAIL", detail="Not committed")

        with pytest.raises(ValueError, match="critical failures"):
            svc.approve_release(report.report_id, "manager")

    def test_rollback_plan(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        plan = RollbackPlan(
            previous_release_available=True,
            database_rollback_defined=True,
            index_rollback_defined=True,
            config_rollback_verified=True,
            rollback_owner_assigned=True,
            procedure_documented=True,
        )
        updated = svc.set_rollback_plan(report.report_id, plan)
        assert updated.rollback_plan.ready is True

    def test_post_release(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        verification = PostReleaseVerification(
            health_endpoints=True,
            upload_workflow=True,
            search_workflow=True,
            ask_workflow=True,
            citation_integrity=True,
            error_rate_acceptable=True,
            latency_acceptable=True,
        )
        updated = svc.set_post_release(report.report_id, verification)
        assert updated.post_release.passed is True

    def test_add_artifact(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        updated = svc.add_artifact(
            report.report_id, "Release Notes",
            description="v1.0 release notes",
            location="./releases/v1.0/notes.md",
        )
        assert len(updated.artifacts) == 1
        assert updated.artifacts[0].name == "Release Notes"

    def test_list_reports(self):
        svc = ReleaseService()
        svc.create_release("v1.0.0")
        svc.create_release("v1.1.0")
        reports = svc.list_reports()
        assert len(reports) >= 2

    def test_list_by_version(self):
        svc = ReleaseService()
        svc.create_release("v2.0.0")
        reports = svc.list_reports(release_version="v2.0.0")
        assert all(r.release_version == "v2.0.0" for r in reports)

    def test_delete_report(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        assert svc.delete_report(report.report_id) is True
        assert svc.get_report(report.report_id) is None

    def test_get_summary(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0.0")
        summary = svc.get_summary(report.report_id)
        assert summary["release_version"] == "v1.0.0"
        assert "can_release" in summary
        assert "pass_rate" in summary
        assert "critical_failures" in summary


# ======================================================================
# 4. Edge Cases
# ======================================================================


class TestEdgeCases:
    """Edge cases."""

    def test_empty_report_pass_rate(self):
        report = ReleaseReport(release_version="v1.0")
        assert report.pass_rate == 1.0

    def test_all_skipped_pass_rate(self):
        checks = [CheckItem(id="c1", category=CheckCategory.SOURCE_CONTROL, description="c1")]
        checks[0].skip_check()
        report = ReleaseReport(release_version="v1.0", checks=checks)
        assert report.pass_rate == 1.0  # skipped don't count

    def test_release_stage_from_string(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0", stage="INTEGRATION")
        assert report.release_stage == ReleaseStage.INTEGRATION

    def test_check_status_from_string(self):
        svc = ReleaseService()
        report = svc.create_release("v1.0")
        updated = svc.update_check(report.report_id, "sc-001", "pass")
        check = [c for c in updated.checks if c.id == "sc-001"][0]
        assert check.status == CheckStatus.PASS
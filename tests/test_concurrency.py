"""Concurrency and durable-job regressions for the threaded MVP runtime."""

from concurrent.futures import ThreadPoolExecutor
import threading

from legal_platform.contracts.common import new_id
from legal_platform.modules.document_registry.processing import (
    InvalidTransition,
    ProcessingState,
)
from legal_platform.modules.document_registry.repository import SqliteDocumentRepository
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.observability.jobs import JobMonitor, JobStatus
from legal_platform.storage.db import connect_thread_local


def _persistent_registry(tmp_path):
    connection = connect_thread_local(tmp_path / "threaded.db")
    registry = DocumentRegistry(repo=SqliteDocumentRepository(conn=connection))
    document = registry.register_document(
        user_id="concurrency-test",
        document_type="INTERNAL_REGULATION",
        title="Concurrent document",
        issuing_authority="QA",
        vault_id=new_id(),
        organization_id=new_id(),
    )
    return connection, registry, document


def test_processing_transition_is_compare_and_set(tmp_path):
    connection, registry, document = _persistent_registry(tmp_path)
    barrier = threading.Barrier(2)

    def claim():
        barrier.wait()
        try:
            registry.transition_processing(
                document.id,
                ProcessingState.OCR_PENDING,
                user_id="worker",
            )
            return "claimed"
        except InvalidTransition:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: claim(), range(2)))

    assert sorted(outcomes) == ["claimed", "rejected"]
    assert registry.get_processing(document.id) == ProcessingState.OCR_PENDING
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    connection.close()


def test_active_pipeline_job_has_one_atomic_claim(tmp_path):
    connection = connect_thread_local(tmp_path / "jobs.db")
    jobs = JobMonitor(conn=connection)
    barrier = threading.Barrier(8)

    def ensure():
        barrier.wait()
        return jobs.ensure_pending_job("pipeline", "document-1").job_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        job_ids = list(pool.map(lambda _: ensure(), range(8)))

    assert len(set(job_ids)) == 1
    job = jobs.start_job(job_ids[0])
    assert job.status == JobStatus.RUNNING
    connection.close()


def test_restart_marks_running_job_recoverable_and_observable(tmp_path):
    connection = connect_thread_local(tmp_path / "recovery.db")
    jobs = JobMonitor(conn=connection)
    job = jobs.ensure_pending_job("pipeline", "document-1")
    jobs.start_job(job.job_id)

    assert jobs.recover_interrupted_jobs() == 1
    recovered = jobs.get_job(job.job_id)
    assert recovered.status == JobStatus.FAILED
    assert "reprocessing action" in recovered.error
    connection.close()

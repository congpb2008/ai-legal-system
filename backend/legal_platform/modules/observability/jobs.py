"""Job monitor (tasks/016-observability.md #JobMonitoring).

Tracks the status and history of long-running jobs:
    Upload Jobs, OCR Jobs, Parser Jobs, Embedding Jobs, Index Jobs, Reprocessing Jobs

Each job exposes current status. Job monitoring never affects business logic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.storage.db import in_memory


class JobStatus(str, Enum):
    """Status of a tracked job.

    - PENDING: job created but not started.
    - RUNNING: job is in progress.
    - COMPLETED: job finished successfully.
    - FAILED: job finished with an error.
    - CANCELLED: job was cancelled.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class JobRecord:
    """A record of a tracked job.

    Fields:
        job_id: unique identifier for the job.
        job_type: the type of job (upload, ocr, parse, embed, index, reprocess).
        document_id: the document being processed.
        status: current job status.
        created_at: when the job was created.
        started_at: when the job started (None if not started).
        completed_at: when the job completed (None if not completed).
        duration_ms: execution duration in milliseconds.
        error: error message if the job failed.
        metadata: additional job metadata.
    """

    job_id: str
    job_type: str
    document_id: str
    status: JobStatus = JobStatus.PENDING
    created_at: str = field(default_factory=lambda: utc_iso(now_utc()))
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS observability_jobs (
    job_id          TEXT PRIMARY KEY,
    job_type        TEXT NOT NULL,
    document_id     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT,
    duration_ms     REAL,
    error           TEXT,
    metadata        TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_obs_jobs_type   ON observability_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_obs_jobs_status ON observability_jobs(status);
CREATE INDEX IF NOT EXISTS idx_obs_jobs_doc    ON observability_jobs(document_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_jobs_active
ON observability_jobs(document_id, job_type)
WHERE status IN ('PENDING', 'RUNNING');
"""


class JobMonitor:
    """Tracks the status and history of long-running jobs.

    Usage::

        monitor = JobMonitor()
        job = monitor.create_job("ocr", str(doc_id))
        monitor.start_job(job.job_id)
        # ... do work ...
        monitor.complete_job(job.job_id)
        # or
        monitor.fail_job(job.job_id, "OCR engine unavailable")
    """

    def __init__(self, conn: "sqlite3.Connection | None" = None):
        self._conn = conn or in_memory()
        self._conn.executescript(_JOB_SCHEMA)
        self._conn.commit()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def create_job(
        self,
        job_type: str,
        document_id: str,
        *,
        metadata: "dict[str, Any] | None" = None,
    ) -> JobRecord:
        """Create a new job record.

        Args:
            job_type: the type of job (upload, ocr, parse, embed, index, reprocess).
            document_id: the document being processed.
            metadata: optional job metadata.

        Returns:
            The created JobRecord.
        """
        import uuid
        job_id = str(uuid.uuid4())
        now = utc_iso(now_utc())
        job = JobRecord(
            job_id=job_id,
            job_type=job_type,
            document_id=document_id,
            status=JobStatus.PENDING,
            created_at=now,
            metadata=metadata or {},
        )
        self._persist(job)
        return job

    def ensure_pending_job(
        self,
        job_type: str,
        document_id: str,
        *,
        metadata: "dict[str, Any] | None" = None,
    ) -> JobRecord:
        """Return an active job or atomically create one for the document."""
        row = self._conn.execute(
            """
            SELECT * FROM observability_jobs
            WHERE document_id = ? AND job_type = ?
              AND status IN ('PENDING', 'RUNNING')
            ORDER BY created_at DESC LIMIT 1
            """,
            (document_id, job_type),
        ).fetchone()
        if row:
            return self._row_to_job(row)
        try:
            return self.create_job(job_type, document_id, metadata=metadata)
        except sqlite3.IntegrityError:
            row = self._conn.execute(
                """
                SELECT * FROM observability_jobs
                WHERE document_id = ? AND job_type = ?
                  AND status IN ('PENDING', 'RUNNING')
                ORDER BY created_at DESC LIMIT 1
                """,
                (document_id, job_type),
            ).fetchone()
            if row is None:
                raise
            return self._row_to_job(row)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Get a job record by ID."""
        row = self._conn.execute(
            "SELECT * FROM observability_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(
        self,
        *,
        job_type: "str | None" = None,
        status: "JobStatus | None" = None,
        document_id: "str | None" = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobRecord]:
        """List job records with optional filtering."""
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if job_type is not None:
            clauses.append("job_type = :job_type")
            params["job_type"] = job_type
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status.value if isinstance(status, JobStatus) else status
        if document_id is not None:
            clauses.append("document_id = :document_id")
            params["document_id"] = document_id
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM observability_jobs{where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return [self._row_to_job(r) for r in rows]

    def start_job(self, job_id: str) -> JobRecord:
        """Mark a job as started."""
        started_at = utc_iso(now_utc())
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE observability_jobs
                SET status = 'RUNNING', started_at = ?, error = NULL
                WHERE job_id = ? AND status = 'PENDING'
                """,
                (started_at, job_id),
            )
        if cursor.rowcount != 1:
            existing = self.get_job(job_id)
            if existing is None:
                raise KeyError(f"Job {job_id} not found")
            raise ValueError(f"Job {job_id} is already {existing.status.value}")
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        return job

    def recover_interrupted_jobs(self) -> int:
        """Make restart-interrupted work observable instead of leaving RUNNING forever."""
        completed_at = utc_iso(now_utc())
        with self._conn:
            cursor = self._conn.execute(
                """
                UPDATE observability_jobs
                SET status = 'FAILED', completed_at = ?,
                    error = 'Processing was interrupted by application restart; use the appropriate reprocessing action.'
                WHERE status = 'RUNNING'
                """,
                (completed_at,),
            )
        return cursor.rowcount

    def complete_job(self, job_id: str) -> JobRecord:
        """Mark a job as completed successfully."""
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job.status = JobStatus.COMPLETED
        job.completed_at = utc_iso(now_utc())
        if job.started_at:
            start = datetime.fromisoformat(job.started_at)
            end = datetime.fromisoformat(job.completed_at)
            job.duration_ms = (end - start).total_seconds() * 1000
        self._persist(job)
        return job

    def fail_job(self, job_id: str, error: str) -> JobRecord:
        """Mark a job as failed."""
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job.status = JobStatus.FAILED
        job.completed_at = utc_iso(now_utc())
        job.error = error
        if job.started_at:
            start = datetime.fromisoformat(job.started_at)
            end = datetime.fromisoformat(job.completed_at)
            job.duration_ms = (end - start).total_seconds() * 1000
        self._persist(job)
        return job

    def cancel_job(self, job_id: str) -> JobRecord:
        """Cancel a job."""
        job = self.get_job(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found")
        job.status = JobStatus.CANCELLED
        job.completed_at = utc_iso(now_utc())
        self._persist(job)
        return job

    def _persist(self, job: JobRecord) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO observability_jobs
                    (job_id, job_type, document_id, status, created_at,
                     started_at, completed_at, duration_ms, error, metadata)
                VALUES
                    (:job_id, :job_type, :document_id, :status, :created_at,
                     :started_at, :completed_at, :duration_ms, :error, :metadata)
                ON CONFLICT(job_id) DO UPDATE SET
                    status=excluded.status, started_at=excluded.started_at,
                    completed_at=excluded.completed_at, duration_ms=excluded.duration_ms,
                    error=excluded.error, metadata=excluded.metadata
                """,
                {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "document_id": job.document_id,
                    "status": job.status.value if isinstance(job.status, JobStatus) else job.status,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "duration_ms": job.duration_ms,
                    "error": job.error,
                    "metadata": json.dumps(job.metadata, ensure_ascii=False),
                },
            )

    def _row_to_job(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            job_type=row["job_type"],
            document_id=row["document_id"],
            status=JobStatus(row["status"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            duration_ms=row["duration_ms"],
            error=row["error"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

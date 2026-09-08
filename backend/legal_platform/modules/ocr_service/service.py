"""OCR Service (tasks/003-ocr-service.md).

The OCR Service orchestrates the OCR pipeline:
    1. Receives a document ID (from the Registry).
    2. Retrieves the original file bytes (from the Upload Service's storage).
    3. Detects whether OCR is needed (digital vs. scanned).
    4. Runs the appropriate OCR engine.
    5. Stores the OCR result.
    6. Transitions the document's processing state.
    7. Returns the OCR result for downstream consumption (Parser, Task 004).

Per the spec:
    - The OCR Service is responsible only for text extraction.
    - It does NOT understand document structure.
    - It does NOT identify legal hierarchy.
    - It does NOT perform chunking.
    - Original files are never modified.
    - OCR output remains traceable to the source document.
    - OCR jobs execute asynchronously (deployment-view.md).
    - Multiple OCR workers may run concurrently.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from legal_platform.contracts.common import now_utc, utc_iso
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.ocr_service.engine import (
    AutoOcrEngine,
    OcrEngine,
    OcrEngineError,
    PyMuPdfDigitalExtractor,
)
from legal_platform.modules.ocr_service.models import OcrResult
from legal_platform.modules.upload_service.file_storage import FileStorage, LocalFileStorage
from legal_platform.storage.eventlog import init_audit_log, log_event


# ---------------------------------------------------------------------------
# OCR result storage (SQLite, disposable per ADR-003)
# ---------------------------------------------------------------------------

_OCR_RESULT_DDL = """
CREATE TABLE IF NOT EXISTS ocr_result (
    ocr_id          TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL,
    version_id      TEXT NOT NULL,
    ocr_mode        TEXT NOT NULL,
    engine          TEXT NOT NULL,
    engine_version  TEXT NOT NULL,
    total_pages     INTEGER NOT NULL,
    avg_confidence  REAL NOT NULL,
    min_confidence  REAL NOT NULL,
    created_at      TEXT NOT NULL,
    warnings        TEXT NOT NULL DEFAULT '[]',
    result_json     TEXT NOT NULL,   -- full OcrResult as JSON (immutable)
    FOREIGN KEY (document_id) REFERENCES document(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ocr_document ON ocr_result(document_id);
CREATE INDEX IF NOT EXISTS idx_ocr_version  ON ocr_result(version_id);
"""


# ---------------------------------------------------------------------------
# OCR Service
# ---------------------------------------------------------------------------


class OcrService:
    """The OCR Service.

    Orchestrates text extraction from uploaded documents. Integrates with:
        - DocumentRegistry (Task 001) for state transitions and audit logging.
        - FileStorage (Task 002) for retrieving original file bytes.
        - OcrEngine (replaceable) for the actual text extraction.

    OCR jobs execute asynchronously (deployment-view.md). The service is designed
    to be called by a background worker; it handles one document per call.
    """

    def __init__(
        self,
        registry: "DocumentRegistry | None" = None,
        file_storage: "FileStorage | None" = None,
        ocr_engine: "OcrEngine | None" = None,
    ):
        self.registry = registry or DocumentRegistry()
        self.storage = file_storage or LocalFileStorage()
        self.engine = ocr_engine or AutoOcrEngine(
            digital_engine=PyMuPdfDigitalExtractor(),
            image_engine=__import__('legal_platform.modules.ocr_service.engine', fromlist=['Pdf2ImageTesseractEngine']).Pdf2ImageTesseractEngine(),
        )
        # Ensure OCR result table + audit table exist
        init_audit_log(self.registry.repo.conn)
        self.registry.repo.conn.executescript(_OCR_RESULT_DDL)
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Process a document (full pipeline — requires job queue integration)
    # ------------------------------------------------------------------

    def process_document(
        self,
        document_id: UUID,
        *,
        user_id: str = "system",
        storage_ref: "str | None" = None,
    ) -> OcrResult:
        """Run OCR on a document.

        Full pipeline flow (per processing-pipeline.md #Stage2):
            1. Validate document exists and is in OCR_PENDING state.
            2. Retrieve original file bytes from storage (via ``storage_ref``).
            3. Extract text via the OCR engine.
            4. Store the OCR result.
            5. Transition to OCR_COMPLETED (or FAILED on error).
            6. Return the OCR result.

        Args:
            document_id: the document to process.
            user_id: for audit logging (defaults to "system" for background jobs).
            storage_ref: opaque reference to the stored original file (from
                the Upload Service). In production this is passed via the job
                queue (Task 014). If None, the method falls back to
                ``process_bytes`` and the caller must provide bytes directly.

        Returns:
            The ``OcrResult`` containing extracted text and confidence metadata.

        Raises:
            ValueError: if the document is not found or not in OCR_PENDING state.
            OcrEngineError: if OCR extraction fails.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        current_state = self.registry.get_processing(document_id)
        if current_state != ProcessingState.OCR_PENDING:
            raise ValueError(
                f"Document {document_id} is in state {current_state.value}, "
                f"expected OCR_PENDING"
            )

        if storage_ref is None:
            raise ValueError(
                f"Cannot process document {document_id}: no storage_ref provided. "
                "In production, the job queue (Task 014) passes the storage_ref. "
                "For direct testing, use process_bytes()."
            )

        # Retrieve file bytes from storage
        try:
            file_bytes = self.storage.retrieve(storage_ref)
        except Exception as e:
            self.registry.transition_processing(
                document_id, ProcessingState.FAILED,
                user_id=user_id,
                failure_reason=f"Failed to retrieve file: {e}",
            )
            raise OcrEngineError(f"Failed to retrieve file from storage: {e}") from e

        return self.process_bytes(
            document_id, file_bytes, user_id=user_id, version_id=doc.current_version.version_id,
        )

    # ------------------------------------------------------------------
    # Process a document with explicit file bytes (test convenience)
    # ------------------------------------------------------------------

    def process_bytes(
        self,
        document_id: UUID,
        file_bytes: bytes,
        *,
        user_id: str = "system",
        version_id: "UUID | None" = None,
    ) -> OcrResult:
        """Run OCR on a document using provided file bytes.

        This is a convenience method for testing and for use when the file
        bytes are already available (e.g., from the Upload Service's storage).

        The document must already be in OCR_PENDING state.
        """
        doc = self.registry.get_document(document_id)
        if doc is None:
            raise ValueError(f"Document {document_id} not found")

        current_state = self.registry.get_processing(document_id)
        if current_state != ProcessingState.OCR_PENDING:
            raise ValueError(
                f"Document {document_id} is in state {current_state.value}, "
                f"expected OCR_PENDING"
            )

        vid = version_id or doc.current_version.version_id

        # --- transition to OCR_RUNNING ---
        self.registry.transition_processing(
            document_id, ProcessingState.OCR_RUNNING, user_id=user_id,
        )

        # --- run OCR ---
        try:
            result = self.engine.extract(
                content=file_bytes,
                document_id=document_id,
                version_id=vid,
            )
        except OcrEngineError:
            self.registry.transition_processing(
                document_id, ProcessingState.FAILED,
                user_id=user_id,
                failure_reason="OCR extraction failed",
            )
            raise

        # --- store OCR result ---
        self._store_result(result)

        # --- transition to OCR_COMPLETED ---
        self.registry.transition_processing(
            document_id, ProcessingState.OCR_COMPLETED, user_id=user_id,
        )

        # --- audit ---
        log_event(
            self.registry.repo.conn,
            service="ocr-service",
            module="ocr",
            event="ocr.complete",
            entity_type="document",
            entity_id=document_id,
            severity="INFO",
            message=f"OCR completed for document {document_id}",
            metadata={
                "ocr_id": str(result.ocr_id),
                "pages": result.total_pages,
                "mode": result.ocr_mode,
                "engine": result.engine,
                "avg_confidence": result.confidence.page_average,
                "min_confidence": result.confidence.page_min,
            },
        )

        return result

    # ------------------------------------------------------------------
    # Internal storage
    # ------------------------------------------------------------------

    def _store_result(self, result: OcrResult) -> None:
        """Persist an OCR result (disposable per ADR-003)."""
        import dataclasses
        import json as _json

        def _serialize(obj: Any) -> Any:
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return utc_iso(obj)
            if dataclasses.is_dataclass(obj):
                return {f.name: _serialize(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            return obj

        self.registry.repo.conn.execute(
            """
            INSERT OR REPLACE INTO ocr_result
                (ocr_id, document_id, version_id, ocr_mode, engine,
                 engine_version, total_pages, avg_confidence, min_confidence,
                 created_at, warnings, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(result.ocr_id),
                str(result.document_id),
                str(result.version_id),
                result.ocr_mode,
                result.engine,
                result.engine_version,
                result.total_pages,
                result.confidence.page_average,
                result.confidence.page_min,
                utc_iso(result.created_at),
                _json.dumps(result.warnings, ensure_ascii=False),
                _json.dumps(_serialize(result), ensure_ascii=False, default=str),
            ),
        )
        self.registry.repo.conn.commit()

    # ------------------------------------------------------------------
    # Retrieve OCR results
    # ------------------------------------------------------------------

    def get_result(self, ocr_id: UUID) -> Optional[OcrResult]:
        """Retrieve a stored OCR result by its ID."""
        import dataclasses
        import json as _json
        from datetime import datetime

        row = self.registry.repo.conn.execute(
            "SELECT result_json FROM ocr_result WHERE ocr_id = ?",
            (str(ocr_id),),
        ).fetchone()
        if row is None:
            return None
        data = _json.loads(row["result_json"])
        return _ocr_result_from_dict(data)

    def get_results_for_document(self, document_id: UUID) -> list[OcrResult]:
        """Retrieve all OCR results for a document (newest first)."""
        import json as _json

        rows = self.registry.repo.conn.execute(
            "SELECT result_json FROM ocr_result WHERE document_id = ? ORDER BY created_at DESC",
            (str(document_id),),
        )
        results: list[OcrResult] = []
        for row in rows:
            data = _json.loads(row["result_json"])
            results.append(_ocr_result_from_dict(data))
        return results

    # ------------------------------------------------------------------
    # Determine OCR requirement
    # ------------------------------------------------------------------

    @staticmethod
    def requires_ocr(content: bytes) -> bool:
        """Determine whether a PDF requires OCR.

        A digital PDF has embedded text; a scanned PDF does not.
        This is a heuristic: try to extract text via PyMuPDF and check
        if the result has meaningful content.

        Returns True if the document appears to be scanned (requires OCR).
        """
        try:
            import pymupdf
            doc = pymupdf.open(stream=content, filetype="pdf")
            total_chars = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text().strip()
                total_chars += len(text)
            doc.close()
            # If very few characters, it's likely scanned
            return total_chars < 50
        except Exception:
            return True  # assume scanned on error


def _ocr_result_from_dict(data: dict) -> OcrResult:
    """Reconstruct an OcrResult from a JSON-deserialized dict."""
    import dataclasses
    import typing
    from datetime import datetime

    # Resolve string annotations (from __future__ import annotations) to real types
    hints = typing.get_type_hints(OcrResult)

    def _deserialize(obj: Any, target_type: Any) -> Any:
        # Resolve Optional[X] -> X, List[X] -> X, etc.
        origin = typing.get_origin(target_type)
        args = typing.get_args(target_type)

        if target_type is UUID or (origin is not None and UUID in args):
            if isinstance(obj, str):
                return UUID(obj)
            return obj
        if target_type is datetime or (origin is not None and datetime in args):
            if isinstance(obj, str):
                return datetime.fromisoformat(obj)
            return obj
        if origin is list and isinstance(obj, list):
            item_type = args[0] if args else Any
            return [_deserialize(item, item_type) for item in obj]
        if origin is dict and isinstance(obj, dict):
            val_type = args[1] if len(args) > 1 else Any
            return {k: _deserialize(v, val_type) for k, v in obj.items()}
        if dataclasses.is_dataclass(target_type) and isinstance(obj, dict):
            field_names = {f.name for f in dataclasses.fields(target_type)}
            field_types = typing.get_type_hints(target_type)
            kwargs = {}
            for fname in field_names:
                if fname in obj:
                    kwargs[fname] = _deserialize(obj[fname], field_types.get(fname, Any))
            return target_type(**kwargs)
        return obj

    return _deserialize(data, OcrResult)
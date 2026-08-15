"""Regression tests for artifact-backed processing readiness."""

import io
import zipfile
import base64
from concurrent.futures import ThreadPoolExecutor

import pytest

from legal_platform.contracts.common import new_id
from legal_platform.modules.chunking.service import ChunkingService
from legal_platform.api.handlers import DocumentHandler
from legal_platform.modules.citation.service import (
    CitationBuilderService,
    CitationTraceabilityError,
)
from legal_platform.modules.document_registry.pipeline import DocumentPipeline
from legal_platform.modules.document_registry.processing import ProcessingState
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.ocr_service.service import OcrService
from legal_platform.modules.parser.service import ParserService
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.upload_service.file_storage import LocalFileStorage
from legal_platform.modules.upload_service.service import UploadService
from legal_platform.modules.vector_index.service import VectorIndexService
from legal_platform.modules.vault.service import VaultService


def _docx_bytes() -> bytes:
    text = (
        "Điều 1. Phạm vi điều chỉnh. Quy định này áp dụng cho hoạt động "
        "lựa chọn nhà thầu và quản lý hợp đồng trong đơn vị."
    )
    document_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
    </w:document>"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr("[Content_Types].xml", "<Types />")
        package.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


@pytest.fixture
def processed_pipeline(tmp_path):
    registry = DocumentRegistry()
    vaults = VaultService(registry=registry, conn=registry.repo.conn)
    registry.vault = vaults
    vault = vaults.create_vault(
        name="Pipeline Test Vault",
        vault_type="PERSONAL",
        owner="pipeline-test",
    )
    storage = LocalFileStorage(tmp_path / "files")
    upload = UploadService(
        registry=registry,
        file_storage=storage,
        vault_resolver=vaults,
    )
    result = upload.upload(
        user_id="pipeline-test",
        content=_docx_bytes(),
        filename="legal.docx",
        document_type="INTERNAL_REGULATION",
        title="Pipeline readiness",
        issuing_authority="Test Authority",
        vault_id=vault.id,
        organization_id=vault.organization_id,
        visibility="PUBLIC",
    )
    ocr = OcrService(registry=registry, file_storage=storage)
    parser = ParserService(registry=registry, ocr_service=ocr)
    chunking = ChunkingService(registry=registry, parser_service=parser)
    embedding = EmbeddingService(
        registry=registry,
        engine=PlaceholderEmbedder(),
    )
    index = VectorIndexService(registry=registry)
    pipeline = DocumentPipeline(
        registry=registry,
        storage=storage,
        ocr=ocr,
        parser=parser,
        chunking=chunking,
        embedding=embedding,
        vector_index=index,
    )
    return pipeline, result.document_id


def test_ready_requires_complete_persisted_artifact_chain(processed_pipeline):
    pipeline, document_id = processed_pipeline

    indexed = pipeline.process(document_id, user_id="pipeline-test")

    assert indexed > 0
    assert pipeline.registry.get_processing(document_id) == ProcessingState.READY
    assert pipeline.validate_ready(document_id) == []


def test_duplicate_processing_attempts_are_serialized(processed_pipeline):
    pipeline, document_id = processed_pipeline
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: pipeline.process(document_id, user_id="pipeline-test"),
            range(2),
        ))

    assert sum(result > 0 for result in results) == 1
    assert sum(result == 0 for result in results) == 1
    assert pipeline.registry.get_processing(document_id) == ProcessingState.READY
    assert pipeline.validate_ready(document_id) == []


def test_ready_document_with_missing_index_is_not_false_success(processed_pipeline):
    pipeline, document_id = processed_pipeline
    pipeline.process(document_id, user_id="pipeline-test")
    connection = pipeline.registry.repo.conn
    entry_id = connection.execute(
        "SELECT entry_id FROM vector_index WHERE document_id = ? LIMIT 1",
        (str(document_id),),
    ).fetchone()[0]
    connection.execute("DELETE FROM vector_index WHERE entry_id = ?", (entry_id,))
    connection.commit()

    problems = pipeline.validate_ready(document_id)

    assert "active index does not cover every embedding" in problems
    with pytest.raises(ValueError, match="READY invariant failed"):
        pipeline.process(document_id, user_id="pipeline-test")

    invalid = pipeline.reconcile_ready_documents(user_id="pipeline-test")
    assert str(document_id) in invalid
    assert pipeline.registry.get_processing(document_id) == ProcessingState.FAILED


def test_citation_resolves_to_canonical_node_and_page(processed_pipeline):
    pipeline, document_id = processed_pipeline
    pipeline.process(document_id, user_id="pipeline-test")
    retrieval = RetrievalService(
        registry=pipeline.registry,
        vector_index=pipeline.vector_index,
        embedding_service=pipeline.embedding,
    )
    result = retrieval.search(
        "phạm vi điều chỉnh",
        document_id=document_id,
        strategy="KEYWORD",
    )
    assert result.evidence
    draft = GenerationService(registry=pipeline.registry).generate(
        "Phạm vi điều chỉnh là gì?",
        evidence=result.evidence,
    )
    verified, report = CitationBuilderService(
        registry=pipeline.registry,
        parser_service=pipeline.parser,
    ).verify_evidence_traceability(draft, result.evidence)

    assert report.status == "VALID"
    assert verified.citations[0].evidence_id == result.evidence[0].id
    assert verified.citations[0].source_anchor.page == 1
    tree = pipeline.parser.get_tree_for_version(
        verified.citations[0].document_version_id
    )
    assert tree.get_node(verified.citations[0].knowledge_node_id) is not None


def test_authorized_source_view_returns_node_page_and_original(processed_pipeline):
    pipeline, document_id = processed_pipeline
    pipeline.process(document_id, user_id="pipeline-test")
    entry = next(iter(pipeline.vector_index._entries.values()))
    handler = DocumentHandler(
        registry=pipeline.registry,
        vault_service=pipeline.registry.vault,
        vector_index=pipeline.vector_index,
        file_storage=pipeline.storage,
        ocr_service=pipeline.ocr,
        parser_service=pipeline.parser,
    )

    forbidden = handler.get_document_source(
        str(document_id), {"node_id": str(entry.knowledge_node_id)}, "outsider"
    )
    assert forbidden.status == 403

    response = handler.get_document_source(
        str(document_id),
        {
            "node_id": str(entry.knowledge_node_id),
            "page": str(entry.page_start),
            "include_original": "1",
        },
        "pipeline-test",
    )
    assert response.success is True
    assert response.data["filename"] == "legal.docx"
    assert response.data["node"]["id"] == str(entry.knowledge_node_id)
    assert response.data["page"]["number"] == entry.page_start
    assert "Phạm vi điều chỉnh" in response.data["node"]["text"]
    assert base64.b64decode(response.data["content_base64"]) == _docx_bytes()


def _artifact_counts(pipeline, document_id):
    connection = pipeline.registry.repo.conn
    version_id = str(pipeline.registry.get_document(document_id).versions[0].version_id)
    return {
        "ocr": connection.execute(
            "SELECT COUNT(*) FROM ocr_result WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()[0],
        "trees": connection.execute(
            "SELECT COUNT(*) FROM knowledge_tree WHERE document_version_id = ?",
            (version_id,),
        ).fetchone()[0],
        "chunks": connection.execute(
            "SELECT COUNT(*) FROM chunk_collection WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()[0],
        "embeddings": connection.execute(
            "SELECT COUNT(*) FROM embedding WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()[0],
        "active_embeddings": connection.execute(
            "SELECT COUNT(*) FROM embedding WHERE document_id = ? AND status = 'ACTIVE'",
            (str(document_id),),
        ).fetchone()[0],
        "index": connection.execute(
            "SELECT COUNT(*) FROM vector_index WHERE document_id = ?",
            (str(document_id),),
        ).fetchone()[0],
    }


def test_reprocessing_starts_at_requested_stage(processed_pipeline):
    pipeline, document_id = processed_pipeline
    pipeline.process(document_id, user_id="pipeline-test")
    initial = _artifact_counts(pipeline, document_id)

    pipeline.reprocess(
        document_id,
        from_stage="index",
        user_id="pipeline-test",
    )
    after_index = _artifact_counts(pipeline, document_id)
    assert after_index == initial

    pipeline.reprocess(
        document_id,
        from_stage="embed",
        user_id="pipeline-test",
    )
    after_embed = _artifact_counts(pipeline, document_id)
    assert after_embed["ocr"] == initial["ocr"]
    assert after_embed["trees"] == initial["trees"]
    assert after_embed["chunks"] == initial["chunks"]
    assert after_embed["embeddings"] == initial["embeddings"] * 2
    assert after_embed["active_embeddings"] == initial["active_embeddings"]
    assert after_embed["index"] == initial["index"]

    pipeline.reprocess(
        document_id,
        from_stage="parse",
        user_id="pipeline-test",
    )
    after_parse = _artifact_counts(pipeline, document_id)
    assert after_parse["ocr"] == after_embed["ocr"]
    assert after_parse["trees"] == after_embed["trees"] + 1
    assert after_parse["chunks"] == after_embed["chunks"] + 1
    assert after_parse["active_embeddings"] == after_embed["active_embeddings"]
    assert after_parse["index"] == after_embed["index"]

    pipeline.reprocess(
        document_id,
        from_stage="ocr",
        user_id="pipeline-test",
    )
    after_ocr = _artifact_counts(pipeline, document_id)
    assert after_ocr["ocr"] == after_parse["ocr"] + 1
    assert after_ocr["trees"] == after_parse["trees"] + 1
    assert after_ocr["chunks"] == after_parse["chunks"] + 1
    assert after_ocr["active_embeddings"] == after_parse["active_embeddings"]
    assert after_ocr["index"] == after_parse["index"]
    assert pipeline.validate_ready(document_id) == []
    assert pipeline.registry.get_processing(document_id) == ProcessingState.READY

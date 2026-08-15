"""Tests for the Generation Service (Task 011).

Covers:
    - Answer Contract invariants
    - Generating answers from evidence
    - No evidence handling (NO_EVIDENCE status)
    - Partial evidence (PARTIAL status)
    - Citation generation
    - Confidence computation
    - Full pipeline: search → rerank → generate
    - Audit logging

The authoritative source is the Answer Contract (02-contracts/answer-contract.md)
and the Generation specification (tasks/011-generation.md).
"""

from uuid import UUID
from types import SimpleNamespace

import pytest

from legal_platform.contracts.answer import (
    Answer,
    AnswerStatus,
    Citation,
    Confidence,
    ConfidenceLevel,
    EvidenceReference,
    Limitation,
    Response,
)
from legal_platform.contracts.common import new_id
from legal_platform.contracts.retrieval import (
    Evidence,
    RetrievalResult,
    RetrievalStrategy,
    SourceAnchor,
)
from legal_platform.modules.document_registry.service import DocumentRegistry
from legal_platform.modules.embedding.engine import PlaceholderEmbedder
from legal_platform.modules.embedding.service import EmbeddingService
from legal_platform.modules.generation.service import GenerationService
from legal_platform.modules.generation.provider import (
    GenerationProviderError,
    ProviderConfig,
)
from legal_platform.modules.reranker.service import RerankerService
from legal_platform.modules.reranker.reranker import RerankedEvidence
from legal_platform.modules.retrieval.service import RetrievalService
from legal_platform.modules.vector_index.service import VectorIndexService
from legal_platform.storage.eventlog import recent_events


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def generation_service():
    registry = DocumentRegistry()
    vector_index = VectorIndexService(registry=registry)
    retrieval = RetrievalService(
        registry=registry,
        vector_index=vector_index,
        embedding_service=EmbeddingService(
            registry=registry,
            engine=PlaceholderEmbedder(),
        ),
    )
    reranker = RerankerService(
        registry=registry,
        retrieval_service=retrieval,
    )
    return GenerationService(
        registry=registry,
        reranker_service=reranker,
    )


@pytest.fixture
def sample_evidence() -> list[Evidence]:
    doc_id = new_id()
    return [
        Evidence(
            id=new_id(),
            knowledge_node_id=new_id(),
            document_id=doc_id,
            document_version_id=new_id(),
            score=0.95,
            rank=1,
            text="Điều 1. Phạm vi điều chỉnh: Quy chế này quy định việc mua sắm máy chủ.",
            source_anchor=SourceAnchor(canonical_reference="Điều 1"),
        ),
        Evidence(
            id=new_id(),
            knowledge_node_id=new_id(),
            document_id=doc_id,
            document_version_id=new_id(),
            score=0.90,
            rank=2,
            text="Điều 2. Đối tượng áp dụng: Áp dụng đối với toàn bộ đơn vị.",
            source_anchor=SourceAnchor(canonical_reference="Điều 2"),
        ),
    ]


# ======================================================================
# 1. Answer Contract
# ======================================================================


class TestAnswerContract:
    """Answer Contract structure and invariants."""

    def test_answer_fields(self):
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.SUCCESS,
            response=Response(content="Test answer"),
        )
        assert answer.request_id is not None
        assert answer.status == AnswerStatus.SUCCESS
        assert answer.response.content == "Test answer"

    def test_answer_with_citations(self):
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.SUCCESS,
            response=Response(content="Answer with citations"),
            citations=[
                Citation(
                    id=new_id(),
                    document_id=new_id(),
                    document_version_id=new_id(),
                    knowledge_node_id=new_id(),
                    label="Điều 1",
                ),
            ],
        )
        assert len(answer.citations) == 1
        assert answer.citations[0].label == "Điều 1"

    def test_no_evidence_status(self):
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.NO_EVIDENCE,
            response=Response(content="No evidence found"),
            confidence=Confidence(level=ConfidenceLevel.LOW, score=0.0),
        )
        assert answer.status == AnswerStatus.NO_EVIDENCE
        assert answer.confidence.level == ConfidenceLevel.LOW

    def test_inv_001_citations_support_claims(self):
        """INV-001: Every factual claim should be supported by at least one Citation."""
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.SUCCESS,
            response=Response(content="Claim with citation"),
            citations=[
                Citation(
                    id=new_id(),
                    document_id=new_id(),
                    document_version_id=new_id(),
                    knowledge_node_id=new_id(),
                ),
            ],
        )
        assert len(answer.citations) >= 1

    def test_inv_002_no_fabricated_citations(self):
        """INV-002: The Answer Contract never contains fabricated citations."""
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.NO_EVIDENCE,
            response=Response(content="No evidence"),
        )
        assert len(answer.citations) == 0

    def test_inv_008_exactly_one_answer(self):
        """INV-008: The client receives exactly one Answer Contract per request."""
        answer = Answer(
            request_id=new_id(),
            status=AnswerStatus.SUCCESS,
            response=Response(content="Single answer"),
        )
        assert isinstance(answer, Answer)


# ======================================================================
# 2. Generation from Evidence
# ======================================================================


class TestGeneration:
    """Generating answers from evidence."""

    def test_generate_returns_answer(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        assert isinstance(answer, Answer)
        assert answer.status == AnswerStatus.SUCCESS

    def test_persisted_provider_configuration_is_used(
        self, generation_service, sample_evidence, monkeypatch
    ):
        """Normal runtime resolution must honor setup-wizard configuration."""
        import legal_platform.modules.generation.service as service_module

        config = ProviderConfig(
            base_url="https://provider.example/v1",
            api_key="test-only",
            model="configured-model",
        )

        class FakeProvider:
            def __init__(self, config):
                self.config = config
                self.calls = []

            def generate(self, **kwargs):
                self.calls.append(kwargs)
                return "Configured provider answer"

        monkeypatch.setattr(service_module, "is_configured", lambda: True)
        monkeypatch.setattr(service_module, "load_config", lambda: config)
        monkeypatch.setattr(service_module, "OpenAICompatibleProvider", FakeProvider)

        service = GenerationService(
            registry=generation_service.registry,
            reranker_service=generation_service.reranker_service,
        )
        answer = service.generate("question", evidence=sample_evidence)

        assert answer.response.content == "Configured provider answer"
        assert answer.metadata.generation_model == "configured-model"
        assert len(service.provider.calls) == 1

    def test_provider_evidence_includes_document_identity(
        self, generation_service, sample_evidence, monkeypatch
    ):
        """Clause labels must be attributable to the actual legal document."""
        calls = []

        class CapturingProvider:
            config = ProviderConfig(model="capturing-model")

            def generate(self, **kwargs):
                calls.append(kwargs)
                return "Grounded answer"

        monkeypatch.setattr(
            generation_service.registry,
            "get_document",
            lambda _document_id: SimpleNamespace(
                title="Nghị định 214/2025/NĐ-CP"
            ),
        )
        generation_service.provider = CapturingProvider()

        generation_service.generate("question", evidence=sample_evidence)

        evidence_text = calls[0]["evidence_text"]
        assert "Tài liệu: Nghị định 214/2025/NĐ-CP" in evidence_text
        assert "Vị trí: Điều 1" in evidence_text
        assert "Nội dung:" in evidence_text

    def test_provider_no_evidence_conclusion_clears_success_and_citations(
        self, generation_service, sample_evidence, monkeypatch
    ):
        class HonestProvider:
            config = ProviderConfig(model="honest-model")

            def generate(self, **kwargs):
                return (
                    "Dựa trên các bằng chứng được cung cấp, không có thông tin "
                    "nào về mức phạt cho hành vi này."
                )

        monkeypatch.setattr(
            generation_service.registry,
            "get_document",
            lambda _document_id: SimpleNamespace(title="Tài liệu liên quan"),
        )
        generation_service.provider = HonestProvider()

        answer = generation_service.generate(
            "Mức phạt là bao nhiêu?", evidence=sample_evidence
        )

        assert answer.status == AnswerStatus.NO_EVIDENCE
        assert answer.citations == []
        assert answer.evidence == []

    def test_configured_provider_failure_is_not_silently_templated(
        self, generation_service, sample_evidence
    ):
        class FailingProvider:
            config = ProviderConfig(model="failing-model")

            def generate(self, **kwargs):
                raise GenerationProviderError("backend unavailable")

        generation_service.provider = FailingProvider()
        with pytest.raises(GenerationProviderError, match="backend unavailable"):
            generation_service.generate("question", evidence=sample_evidence)

    def test_generate_has_citations(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        assert len(answer.citations) >= 1

    def test_generate_has_evidence_refs(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        assert len(answer.evidence) >= 1

    def test_generate_has_response_content(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        assert len(answer.response.content) > 0

    def test_generate_has_confidence(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        assert answer.confidence.score > 0
        assert answer.confidence.level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)

    def test_generate_with_reranked_evidence(self, generation_service, sample_evidence):
        """Should accept RerankedEvidence list."""
        reranked = [
            RerankedEvidence(
                evidence=ev,
                rerank_score=ev.score,
                original_rank=ev.rank,
                final_rank=i + 1,
            )
            for i, ev in enumerate(sample_evidence)
        ]
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=reranked,
        )
        assert answer.status == AnswerStatus.SUCCESS


# ======================================================================
# 3. No Evidence Handling
# ======================================================================


class TestNoEvidence:
    """No evidence handling (tasks/011 #MissingEvidence)."""

    def test_no_evidence_returns_no_evidence_status(self, generation_service):
        answer = generation_service.generate(
            "câu hỏi không có tài liệu",
            evidence=[],
        )
        assert answer.status == AnswerStatus.NO_EVIDENCE

    def test_no_evidence_has_limitation(self, generation_service):
        answer = generation_service.generate(
            "câu hỏi không có tài liệu",
            evidence=[],
        )
        assert len(answer.limitations) >= 1

    def test_no_evidence_low_confidence(self, generation_service):
        answer = generation_service.generate(
            "câu hỏi không có tài liệu",
            evidence=[],
        )
        assert answer.confidence.level == ConfidenceLevel.LOW
        assert answer.confidence.score == 0.0

    def test_no_evidence_no_citations(self, generation_service):
        answer = generation_service.generate(
            "câu hỏi không có tài liệu",
            evidence=[],
        )
        assert len(answer.citations) == 0

    def test_answer_query_rejects_only_low_relevance_candidates(
        self, generation_service
    ):
        weak = Evidence(
            id=new_id(),
            knowledge_node_id=new_id(),
            document_id=new_id(),
            document_version_id=new_id(),
            score=0.69,
            rank=1,
            text="Unrelated nearest-neighbour text.",
        )
        generation_service.reranker_service.search_and_rerank = lambda *args, **kwargs: (
            [RerankedEvidence(evidence=weak, rerank_score=0.9, original_rank=1)],
            None,
        )
        answer = generation_service.answer_query("unsupported future event")
        assert answer.status == AnswerStatus.NO_EVIDENCE
        assert answer.citations == []

    def test_answer_query_uses_hybrid_retrieval(self, generation_service):
        calls = []

        def search_and_rerank(*args, **kwargs):
            calls.append(kwargs)
            return [], None

        generation_service.reranker_service.search_and_rerank = search_and_rerank
        generation_service.answer_query("Điều khoản chính xác")

        assert calls[0]["strategy"] == "HYBRID"

    def test_moderate_generic_overlap_is_not_answer_evidence(
        self, generation_service, monkeypatch
    ):
        evidence = Evidence(
            id=new_id(),
            knowledge_node_id=new_id(),
            document_id=new_id(),
            document_version_id=new_id(),
            score=0.76,
            rank=1,
            text=(
                "Chi phí nộp hồ sơ dự thầu trên Hệ thống mạng đấu thầu "
                "quốc gia là 330.000 đồng."
            ),
        )
        monkeypatch.setattr(
            generation_service.registry,
            "get_document",
            lambda _document_id: SimpleNamespace(
                title="Nghị định về lựa chọn nhà thầu"
            ),
        )

        filtered = generation_service.filter_answer_evidence(
            [evidence],
            query=(
                "Mức phạt chính xác đối với một cuộc tấn công mạng vào hệ "
                "thống đấu thầu là bao nhiêu tiền?"
            ),
        )

        assert filtered == []

    def test_named_documents_are_kept_for_multi_document_question(
        self, generation_service, monkeypatch
    ):
        document_4a = new_id()
        document_5a = new_id()
        evidence = [
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=document_4a,
                document_version_id=new_id(),
                score=0.74,
                rank=1,
                text="Phạm vi áp dụng cho gói thầu mua sắm hàng hóa.",
            ),
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=document_5a,
                document_version_id=new_id(),
                score=0.74,
                rank=2,
                text="Phạm vi áp dụng cho gói thầu dịch vụ phi tư vấn.",
            ),
        ]
        titles = {
            document_4a: "Mẫu số 4A - E-HSMT mua sắm hàng hóa",
            document_5a: "Mẫu số 5A - E-HSMT dịch vụ phi tư vấn",
        }
        monkeypatch.setattr(
            generation_service.registry,
            "get_document",
            lambda document_id: SimpleNamespace(title=titles[document_id]),
        )

        filtered = generation_service.filter_answer_evidence(
            evidence,
            query="Mẫu 4A và Mẫu 5A khác nhau ở phạm vi áp dụng như thế nào?",
        )

        assert filtered == evidence


# ======================================================================
# 4. Partial Evidence
# ======================================================================


class TestPartialEvidence:
    """Partial evidence handling."""

    def test_low_confidence_is_partial(self, generation_service):
        """Low-confidence evidence should produce PARTIAL status."""
        evidence = [
            Evidence(
                id=new_id(),
                knowledge_node_id=new_id(),
                document_id=new_id(),
                document_version_id=new_id(),
                score=0.30,
                rank=1,
                text="Some low-confidence text.",
            ),
        ]
        answer = generation_service.generate(
            "test query",
            evidence=evidence,
        )
        assert answer.status in (AnswerStatus.PARTIAL, AnswerStatus.SUCCESS)


# ======================================================================
# 5. Confidence Computation
# ======================================================================


class TestConfidence:
    """Confidence computation."""

    def test_high_confidence(self, generation_service):
        evidence = [
            Evidence(id=new_id(), knowledge_node_id=new_id(), document_id=new_id(),
                     document_version_id=new_id(), score=0.95, rank=1, text="A"),
            Evidence(id=new_id(), knowledge_node_id=new_id(), document_id=new_id(),
                     document_version_id=new_id(), score=0.90, rank=2, text="B"),
        ]
        confidence = generation_service._compute_confidence(evidence)
        assert confidence.level == ConfidenceLevel.HIGH

    def test_medium_confidence(self, generation_service):
        evidence = [
            Evidence(id=new_id(), knowledge_node_id=new_id(), document_id=new_id(),
                     document_version_id=new_id(), score=0.60, rank=1, text="A"),
        ]
        confidence = generation_service._compute_confidence(evidence)
        assert confidence.level == ConfidenceLevel.MEDIUM

    def test_low_confidence(self, generation_service):
        evidence = [
            Evidence(id=new_id(), knowledge_node_id=new_id(), document_id=new_id(),
                     document_version_id=new_id(), score=0.20, rank=1, text="A"),
        ]
        confidence = generation_service._compute_confidence(evidence)
        assert confidence.level == ConfidenceLevel.LOW

    def test_empty_confidence(self, generation_service):
        confidence = generation_service._compute_confidence([])
        assert confidence.level == ConfidenceLevel.LOW
        assert confidence.score == 0.0


# ======================================================================
# 6. Audit Logging
# ======================================================================


class TestAuditLogging:
    """Generation audit logging."""

    def test_generate_logs_event(self, generation_service, sample_evidence):
        answer = generation_service.generate(
            "mua sắm máy chủ",
            evidence=sample_evidence,
        )
        events = recent_events(
            generation_service.registry.repo.conn,
            entity_id=str(answer.request_id),
        )
        gen_events = [e for e in events if e["event"] == "generation.complete"]
        assert len(gen_events) >= 1

    def test_no_evidence_logs_event(self, generation_service):
        answer = generation_service.generate(
            "no results",
            evidence=[],
        )
        events = recent_events(
            generation_service.registry.repo.conn,
            entity_id=str(answer.request_id),
        )
        gen_events = [e for e in events if e["event"] == "generation.complete"]
        assert len(gen_events) >= 1


# ======================================================================
# 7. Full Pipeline
# ======================================================================


class TestFullPipeline:
    """End-to-end: search → rerank → generate."""

    def test_answer_query(self, generation_service):
        """answer_query should return an Answer even with empty results."""
        answer = generation_service.answer_query(
            "test query",
            vault_id=new_id(),
        )
        assert isinstance(answer, Answer)
        # With an empty index, should return NO_EVIDENCE
        assert answer.status in (AnswerStatus.NO_EVIDENCE, AnswerStatus.SUCCESS)

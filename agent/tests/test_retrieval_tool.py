from agent.config import AgentSettings
from agent.schemas.query import QueryPlan
from agent.tools.retrieval.evidence_processor import EvidenceProcessor
from agent.tools.retrieval.ragflow_client import RagflowClient
from agent.tools.retrieval.tool import KnowledgeRetrievalTool


class FakeRagflowClient:
    def search(self, query_plan: QueryPlan):
        return (
            [
                {
                    "source_type": "paper",
                    "title": "多囊卵巢综合征中医治疗研究",
                    "file_uuid": "same-file",
                    "abstract": "研究摘要",
                },
                {
                    "source_type": "paper",
                    "title": "重复资料",
                    "file_uuid": "same-file",
                    "abstract": "重复摘要",
                },
            ],
            2,
        )


def test_retrieval_tool_processes_and_deduplicates_evidence():
    tool = KnowledgeRetrievalTool(
        ragflow_client=FakeRagflowClient(),
        evidence_processor=EvidenceProcessor(),
    )
    result = tool.run(
        QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="多囊卵巢综合征",
            search_type="literature",
            top_k=5,
        )
    )

    assert result.total == 2
    assert len(result.evidence) == 1
    assert result.evidence[0].file_uuid == "same-file"


def test_retrieval_tool_runs_stage_sub_queries():
    class MultiQueryClient:
        def __init__(self):
            self.questions = []

        def search(self, query_plan: QueryPlan):
            self.questions.append(query_plan.rewritten_query)
            return (
                [
                    {
                        "source_type": "paper",
                        "title": query_plan.rewritten_query,
                        "file_uuid": query_plan.rewritten_query,
                        "content": query_plan.rewritten_query,
                        "similarity": 0.8,
                    }
                ],
                1,
            )

    client = MultiQueryClient()
    tool = KnowledgeRetrievalTool(ragflow_client=client, evidence_processor=EvidenceProcessor())
    result = tool.run(
        QueryPlan(
            intent="clinical_decision_question",
            rewritten_query="四阶段",
            search_type="both",
            top_k=4,
            retrieval_strategy="multi_query",
            sub_queries=["降调阶段", "促排阶段", "移植阶段", "黄体支持阶段"],
        )
    )

    assert client.questions == ["降调阶段", "促排阶段", "移植阶段", "黄体支持阶段"]
    assert len(result.evidence) == 4


def test_retrieval_tool_skips_ragflow_for_source_only_route():
    class FailingClient:
        def search(self, query_plan):
            raise AssertionError("source-only route must not call RAGFlow")

    tool = KnowledgeRetrievalTool(ragflow_client=FailingClient())
    result = tool.run(
        QueryPlan(
            intent="general_medical_question",
            rewritten_query="依据1",
            search_type="both",
            retrieval_required=False,
            answer_mode="source_detail",
            retrieval_strategy="source_targeted",
        )
    )

    assert result.evidence_status == "source_only"
    assert result.evidence == []


def test_ragflow_client_posts_to_retrieval_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "content": "检索片段",
                            "document_id": "doc-1",
                            "kb_id": "lit-dataset",
                            "similarity": 0.88,
                        }
                    ],
                    "doc_aggs": [{"doc_id": "doc-1", "doc_name": "文献标题"}],
                    "total": 1,
                },
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("agent.tools.retrieval.ragflow_client.requests.post", fake_post)
    monkeypatch.setattr(
        "agent.tools.retrieval.ragflow_client.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )
    settings = AgentSettings(
        ragflow_base_url="http://ragflow.test",
        ragflow_api_key="secret",
        ragflow_literature_dataset_id="lit-dataset",
        ragflow_case_dataset_id="case-dataset",
        ragflow_guideline_dataset_id="guide-dataset",
    )

    rows, total = RagflowClient(settings=settings).search(
        QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="多囊卵巢综合征",
            search_type="literature",
            top_k=3,
        )
    )

    assert captured["url"] == "http://ragflow.test/api/v1/retrieval"
    assert captured["json"]["dataset_ids"] == ["lit-dataset"]
    assert captured["json"]["question"] == "多囊卵巢综合征"
    assert captured["json"]["page_size"] == 3
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert total == 1
    assert rows[0]["source_type"] == "paper"
    assert rows[0]["title"] == "文献标题"


def test_ragflow_client_keeps_file_uuid_from_meta_fields(monkeypatch):
    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "content": "检索片段",
                            "document_id": "doc-1",
                            "kb_id": "lit-dataset",
                            "similarity": 0.88,
                            "meta_fields": {
                                "file_uuid": "file-uuid-1",
                                "journal": "测试期刊",
                            },
                        }
                    ],
                    "total": 1,
                },
            }

    def fake_post(url, headers, json, timeout):
        return FakeResponse()

    monkeypatch.setattr("agent.tools.retrieval.ragflow_client.requests.post", fake_post)
    settings = AgentSettings(
        ragflow_base_url="http://ragflow.test",
        ragflow_literature_dataset_id="lit-dataset",
        ragflow_case_dataset_id="case-dataset",
        ragflow_guideline_dataset_id="guide-dataset",
    )

    rows, _ = RagflowClient(settings=settings).search(
        QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="DOR",
            search_type="literature",
            top_k=3,
        )
    )

    evidence = EvidenceProcessor().process(rows, max_items=3)

    assert rows[0]["file_uuid"] == "file-uuid-1"
    assert rows[0]["metadata"]["file_uuid"] == "file-uuid-1"
    assert evidence[0].file_uuid == "file-uuid-1"


def test_ragflow_client_keeps_file_uuid_from_json_meta_fields(monkeypatch):
    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "content": "检索片段",
                            "document_id": "doc-1",
                            "kb_id": "lit-dataset",
                            "similarity": 0.88,
                            "meta_fields": '{"fileUuid": "file-uuid-2", "journal": "测试期刊"}',
                        }
                    ],
                    "total": 1,
                },
            }

    def fake_post(url, headers, json, timeout):
        return FakeResponse()

    monkeypatch.setattr("agent.tools.retrieval.ragflow_client.requests.post", fake_post)
    settings = AgentSettings(
        ragflow_base_url="http://ragflow.test",
        ragflow_literature_dataset_id="lit-dataset",
        ragflow_case_dataset_id="case-dataset",
        ragflow_guideline_dataset_id="guide-dataset",
    )

    rows, _ = RagflowClient(settings=settings).search(
        QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="DOR",
            search_type="literature",
            top_k=3,
        )
    )

    evidence = EvidenceProcessor().process(rows, max_items=3)

    assert rows[0]["file_uuid"] == "file-uuid-2"
    assert rows[0]["metadata"]["file_uuid"] == "file-uuid-2"
    assert evidence[0].file_uuid == "file-uuid-2"


def test_ragflow_client_enriches_file_uuid_from_document_metadata(monkeypatch):
    class RetrievalResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "code": 0,
                "data": {
                    "chunks": [
                        {
                            "id": "chunk-1",
                            "content": "检索片段",
                            "document_id": "doc-1",
                            "dataset_id": "case-dataset",
                            "document_keyword": "case_测试病案.md",
                            "similarity": 0.88,
                        }
                    ],
                    "total": 1,
                },
            }

    class DocumentResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "code": 0,
                "data": {
                    "docs": [
                        {
                            "id": "doc-1",
                            "location": "case_测试病案.md",
                            "meta_fields": {
                                "file_uuid": "file-uuid-from-doc",
                                "literature_title": "测试病案",
                            },
                        }
                    ],
                    "total": 1,
                },
            }

    def fake_get(url, headers, params, timeout):
        assert params == {"id": "doc-1"}
        return DocumentResponse()

    monkeypatch.setattr("agent.tools.retrieval.ragflow_client.requests.post", lambda *args, **kwargs: RetrievalResponse())
    monkeypatch.setattr("agent.tools.retrieval.ragflow_client.requests.get", fake_get)
    settings = AgentSettings(
        ragflow_base_url="http://ragflow.test",
        ragflow_literature_dataset_id="lit-dataset",
        ragflow_case_dataset_id="case-dataset",
        ragflow_guideline_dataset_id="guide-dataset",
    )

    rows, _ = RagflowClient(settings=settings).search(
        QueryPlan(
            intent="case_question",
            source_type="record",
            rewritten_query="DOR",
            search_type="case",
            top_k=3,
        )
    )

    evidence = EvidenceProcessor().process(rows, max_items=3)

    assert rows[0]["file_uuid"] == "file-uuid-from-doc"
    assert rows[0]["metadata"]["file_uuid"] == "file-uuid-from-doc"
    assert evidence[0].file_uuid == "file-uuid-from-doc"

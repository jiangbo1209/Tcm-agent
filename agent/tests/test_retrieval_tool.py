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

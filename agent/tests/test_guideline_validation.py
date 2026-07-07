from agent.schemas.retrieval import Evidence
from agent.tools.validation.guideline_checker import GuidelineChecker
from agent.tools.validation.guideline_retriever import GuidelineRetriever
from agent.tools.validation.tool import GuidelineValidationTool


class FakeLLMClient:
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        return """
        {
          "issues": ["存在确定性疗效承诺"]
        }
        """


class FailingLLMClient:
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        raise RuntimeError("model unavailable")


class FakeRagflowClient:
    def __init__(self):
        self.query_plan = None

    def search(self, query_plan):
        self.query_plan = query_plan
        return (
            [
                {
                    "source_type": "guideline",
                    "title": "不孕症诊疗指南",
                    "file_uuid": "guide-1",
                    "chunk": "不应承诺治疗一定有效，应结合个体情况评估。",
                    "score": 0.91,
                }
            ],
            1,
        )


def test_guideline_checker_returns_simple_grounding_result():
    result = GuidelineChecker(llm_client=FakeLLMClient()).check(
        question="这个回答安全吗？",
        answer="这个方案保证有效。",
        guidelines=[],
        evidence=[Evidence(source_type="paper", title="文献", chunk="证据片段")],
    )

    assert result.grounded
    assert result.message == "回答基于知识库检索结果生成。"
    assert result.issues == ["存在确定性疗效承诺"]


def test_guideline_checker_falls_back_to_risk_terms():
    result = GuidelineChecker(llm_client=FailingLLMClient()).check(
        question="这个回答安全吗？",
        answer="这个方案保证有效，无需就医。",
        guidelines=[],
        evidence=[],
    )

    assert not result.grounded
    assert "普通医学知识" in result.message
    assert result.issues


def test_guideline_retriever_uses_guideline_query_plan():
    fake_ragflow = FakeRagflowClient()
    retriever = GuidelineRetriever(ragflow_client=fake_ragflow, top_k=3)

    evidence = retriever.retrieve(
        question="这个回答安全吗？",
        answer="这个方案保证有效。",
    )

    assert fake_ragflow.query_plan.search_type == "guideline"
    assert fake_ragflow.query_plan.source_type == "guideline"
    assert fake_ragflow.query_plan.top_k == 3
    assert "这个回答安全吗" in fake_ragflow.query_plan.rewritten_query
    assert "保证有效" in fake_ragflow.query_plan.rewritten_query
    assert evidence[0].source_type == "guideline"


def test_guideline_validation_tool_retrieves_guidelines_when_enabled():
    fake_ragflow = FakeRagflowClient()
    retriever = GuidelineRetriever(ragflow_client=fake_ragflow, top_k=2)
    checker = GuidelineChecker(llm_client=FakeLLMClient())
    tool = GuidelineValidationTool(
        guideline_retriever=retriever,
        guideline_checker=checker,
        enabled=True,
    )

    result = tool.run(
        question="这个回答安全吗？",
        answer="这个方案保证有效。",
        evidence=[Evidence(source_type="paper", title="文献", chunk="证据片段")],
    )

    assert fake_ragflow.query_plan.search_type == "guideline"
    assert result.grounded
    assert result.issues == ["存在确定性疗效承诺"]

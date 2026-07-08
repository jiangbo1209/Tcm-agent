from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence
from agent.services.answer_generator import AnswerGenerator


class FakeLLMClient:
    def __init__(self):
        self.prompt = ""
        self.system_prompt = ""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompt = prompt
        self.system_prompt = system_prompt or ""
        return "这是模型生成的回答。[1]"


class FailingLLMClient:
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        raise RuntimeError("model unavailable")


def test_answer_generator_uses_llm_with_grounded_prompt():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    result = generator.generate(
        question="多囊卵巢综合征有哪些文献证据？",
        query_plan=QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="多囊卵巢综合征 文献证据",
            search_type="literature",
            top_k=3,
        ),
        evidence=[
            Evidence(
                source_type="paper",
                title="多囊卵巢综合征中医治疗研究",
                file_uuid="file-1",
                chunk="研究显示中医治疗可能改善相关症状。",
                score=0.87,
            )
        ],
        total=1,
    )

    assert result.answer == "这是模型生成的回答。[1]"
    assert result.sources == ["[1] 文献：多囊卵巢综合征中医治疗研究（UUID：file-1）"]
    assert result.references[0].file_uuid == "file-1"
    assert "RAGFlow 检索证据" in fake_llm.prompt
    assert "file-1" in fake_llm.prompt


def test_answer_generator_falls_back_when_llm_fails():
    generator = AnswerGenerator(llm_client=FailingLLMClient())

    result = generator.generate(
        question="不孕症有哪些病案治疗思路？",
        query_plan=QueryPlan(
            intent="case_question",
            source_type="record",
            rewritten_query="不孕症 病案 治疗",
            search_type="case",
            top_k=3,
        ),
        evidence=[],
        total=0,
    )

    assert "当前知识库没有检索到足够相关" in result.answer
    assert result.warnings

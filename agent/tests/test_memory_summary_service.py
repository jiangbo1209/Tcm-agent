from agent.memory.schemas import MemoryMessage
from agent.memory.summary_service import MemorySummaryService


class FakeLLMClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.prompt = ""

    def generate(self, prompt, system_prompt=None):
        self.prompt = prompt
        if self.error:
            raise self.error
        return self.response


def test_memory_summary_service_uses_llm_to_merge_previous_summary_and_archived_messages():
    llm = FakeLLMClient(response="患者已讨论多囊促排，待补充 AMH。")
    service = MemorySummaryService(llm_client=llm, max_summary_chars=200)

    summary = service.summarize(
        "前文讨论不孕治疗。",
        [MemoryMessage(role="user", content="患者 AMH 0.8，想了解促排方案。")],
    )

    assert summary == "患者已讨论多囊促排，待补充 AMH。"
    assert "前文讨论不孕治疗" in llm.prompt
    assert "AMH 0.8" in llm.prompt


def test_memory_summary_service_uses_deterministic_fallback_when_llm_fails():
    service = MemorySummaryService(
        llm_client=FakeLLMClient(error=RuntimeError("model unavailable")),
        max_summary_chars=200,
    )

    summary = service.summarize(
        "旧摘要",
        [MemoryMessage(role="user", content="需要继续讨论促排监测。")],
    )

    assert "旧摘要" in summary
    assert "需要继续讨论促排监测" in summary

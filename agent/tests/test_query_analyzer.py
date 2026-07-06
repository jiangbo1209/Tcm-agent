from agent.analyzers.query_analyzer import QueryAnalyzer


class FakeLLMClient:
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        return """
        {
          "intent": "literature_question",
          "search_type": "literature",
          "source_type": "paper",
          "rewritten_query": "多囊卵巢综合征 文献证据",
          "top_k": 4,
          "filters": {}
        }
        """


def test_query_analyzer_classifies_case_question():
    plan = QueryAnalyzer().analyze("不孕症有哪些病案治疗思路？")

    assert plan.intent == "case_question"
    assert plan.source_type == "record"
    assert plan.search_type == "case"


def test_query_analyzer_classifies_literature_question():
    plan = QueryAnalyzer().analyze("多囊卵巢综合征有哪些文献证据？")

    assert plan.intent == "literature_question"
    assert plan.source_type == "paper"
    assert plan.search_type == "literature"


def test_query_analyzer_can_use_llm_json_plan():
    plan = QueryAnalyzer(llm_client=FakeLLMClient()).analyze(
        "多囊卵巢综合征有哪些文献证据？",
        top_k=2,
    )

    assert plan.intent == "literature_question"
    assert plan.rewritten_query == "多囊卵巢综合征 文献证据"
    assert plan.top_k == 2

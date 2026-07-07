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
    plan = QueryAnalyzer().analyze("有没有类似不孕症病案可以参考？")

    assert plan.intent == "case_question"
    assert plan.source_type == "record"
    assert plan.search_type == "case"


def test_query_analyzer_classifies_literature_question():
    plan = QueryAnalyzer().analyze("多囊卵巢综合征有哪些文献证据？")

    assert plan.intent == "literature_question"
    assert plan.source_type == "paper"
    assert plan.search_type == "literature"


def test_query_analyzer_classifies_clinical_decision_question():
    plan = QueryAnalyzer().analyze("胖多囊和瘦多囊的中医辨证分型及治疗方案怎么选择？")

    assert plan.intent == "clinical_decision_question"
    assert plan.source_type is None
    assert plan.search_type == "both"


def test_query_analyzer_classifies_patient_education_question():
    plan = QueryAnalyzer().analyze("试管移植后饮食和作息有哪些注意事项？")

    assert plan.intent == "patient_education_question"
    assert plan.source_type is None
    assert plan.search_type == "both"


def test_query_analyzer_classifies_report_interpretation_question():
    plan = QueryAnalyzer().analyze("帮我解释一下AMH和性激素检查结果对怀孕有什么影响")

    assert plan.intent == "clinical_decision_question"
    assert plan.search_type == "both"


def test_query_analyzer_classifies_guideline_question():
    plan = QueryAnalyzer().analyze("备孕期间哪些中药禁忌或慎用？")

    assert plan.intent == "guideline_validation_question"
    assert plan.source_type == "guideline"
    assert plan.search_type == "guideline"


def test_query_analyzer_can_use_llm_json_plan():
    plan = QueryAnalyzer(llm_client=FakeLLMClient()).analyze(
        "多囊卵巢综合征有哪些文献证据？",
        top_k=2,
    )

    assert plan.intent == "literature_question"
    assert plan.rewritten_query == "多囊卵巢综合征 文献证据"
    assert plan.top_k == 2

from agent.analyzers.query_analyzer import QueryAnalyzer
from agent.memory.schemas import MemoryContext, MemoryMessage, UserContext


class FakeLLMClient:
    def __init__(self):
        self.prompt = ""

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompt = prompt
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
    assert plan.task_type == "option_comparison"
    assert plan.answer_mode == "option_comparison"
    assert plan.retrieval_strategy == "literature_case_mix"


def test_query_analyzer_classifies_patient_education_question():
    plan = QueryAnalyzer().analyze("试管移植后饮食和作息有哪些注意事项？")

    assert plan.intent == "patient_education_question"
    assert plan.source_type is None
    assert plan.search_type == "both"


def test_query_analyzer_classifies_report_interpretation_question():
    plan = QueryAnalyzer().analyze("帮我解释一下AMH和性激素检查结果对怀孕有什么影响")

    assert plan.intent == "clinical_decision_question"
    assert plan.search_type == "both"
    assert plan.task_type == "report_interpretation"
    assert plan.answer_mode == "report_interpretation"
    assert plan.risk_level == "high"


def test_query_analyzer_routes_assisted_reproduction_stages():
    plan = QueryAnalyzer().analyze("试管婴儿术前降调、促排、移植、黄体支持分别需要注意什么？")

    assert plan.task_type == "assisted_reproduction_stages"
    assert plan.answer_mode == "phase_guidance"
    assert plan.retrieval_strategy == "multi_query"
    assert len(plan.sub_queries) == 4
    assert plan.risk_level == "high"


def test_query_analyzer_routes_safety_question():
    plan = QueryAnalyzer().analyze("促排期间出现腹胀，什么情况需要立即就医？")

    assert plan.task_type == "safety_risk"
    assert plan.answer_mode == "safety_risk"
    assert plan.retrieval_strategy == "guideline_first"
    assert plan.risk_level == "high"


def test_query_analyzer_routes_literature_and_case_tasks():
    literature_plan = QueryAnalyzer().analyze("多囊卵巢综合征有哪些文献证据？")
    case_plan = QueryAnalyzer().analyze("有没有类似不孕症病案可以参考？")

    assert literature_plan.task_type == "literature_evidence"
    assert literature_plan.answer_mode == "evidence_summary"
    assert case_plan.task_type == "case_review"
    assert case_plan.answer_mode == "case_review"


def test_query_analyzer_classifies_guideline_question():
    plan = QueryAnalyzer(guideline_retrieval_enabled=True).analyze("备孕期间哪些中药禁忌或慎用？")

    assert plan.intent == "guideline_validation_question"
    assert plan.source_type == "guideline"
    assert plan.search_type == "guideline"


def test_query_analyzer_can_disable_guideline_retrieval():
    plan = QueryAnalyzer(guideline_retrieval_enabled=False).analyze("备孕期间哪些中药禁忌或慎用？")

    assert plan.source_type is None
    assert plan.search_type == "both"


def test_query_analyzer_can_use_llm_json_plan():
    fake_llm = FakeLLMClient()
    plan = QueryAnalyzer(llm_client=fake_llm).analyze(
        "多囊卵巢综合征有哪些文献证据？",
        top_k=2,
        user_context=UserContext(active_role="clinician", detail_level="detailed"),
    )

    assert plan.intent == "literature_question"
    assert plan.rewritten_query == "多囊卵巢综合征 文献证据"
    assert plan.top_k == 2
    assert '"active_role": "clinician"' in fake_llm.prompt
    assert '"detail_level": "detailed"' in fake_llm.prompt


def test_query_analyzer_uses_memory_for_contextual_followup():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="多囊患者促排方案怎么选？"),
            MemoryMessage(
                role="assistant",
                content="可参考来源中的病案经验。",
                references=[
                    {
                        "index": 1,
                        "source_type": "record",
                        "title": "case_多囊卵巢综合征促排治疗病案.md",
                        "file_uuid": "file-1",
                    }
                ],
            ),
        ],
        referenced_sources=[
            {
                "index": 1,
                "source_type": "record",
                "title": "case_多囊卵巢综合征促排治疗病案.md",
                "file_uuid": "file-1",
            }
        ],
    )

    plan = QueryAnalyzer().analyze("这种方法有什么依据？", memory_context=memory)

    assert "这种方法有什么依据" in plan.rewritten_query
    assert "多囊卵巢综合征促排治疗病案" in plan.rewritten_query


def test_query_analyzer_resolves_numbered_citation_followup():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="促排卵泡发育异常，如何快速调整用药剂量与检测计划"),
            MemoryMessage(
                role="assistant",
                content="当前检索证据未提供具体操作路径，依据见[1]。",
                references=[
                    {
                        "index": 1,
                        "source_type": "paper",
                        "title": "超排卵常用于不孕症妇女进行辅助生殖技术",
                        "file_uuid": "file-1",
                        "snippet": "文献提到超排卵用于辅助生殖，但未说明卵泡发育异常时的剂量调整。",
                    },
                    {
                        "index": 2,
                        "source_type": "record",
                        "title": "case_多囊促排病案.md",
                        "file_uuid": "file-2",
                    },
                ],
            ),
        ],
        referenced_sources=[],
    )

    plan = QueryAnalyzer().analyze("展开说一下依据1", memory_context=memory)

    assert "依据1" in plan.rewritten_query
    assert "超排卵常用于不孕症妇女" in plan.rewritten_query
    assert "促排卵泡发育异常" in plan.rewritten_query
    assert plan.answer_mode == "source_detail"
    assert plan.retrieval_required is False


def test_query_analyzer_resolves_literature_numbered_followup_without_retrieval():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="多囊卵巢综合征有哪些文献证据？"),
            MemoryMessage(
                role="assistant",
                content="文献见[1]。",
                references=[
                    {
                        "index": 1,
                        "source_type": "paper",
                        "title": "多囊卵巢综合征研究",
                        "file_uuid": "file-1",
                    }
                ],
            ),
        ]
    )

    plan = QueryAnalyzer().analyze("说一说文献1", memory_context=memory)

    assert plan.answer_mode == "source_detail"
    assert plan.retrieval_required is False
    assert "多囊卵巢综合征研究" in plan.rewritten_query


def test_query_analyzer_resolves_all_citation_followup_without_retrieval():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="多囊卵巢综合征有哪些文献证据？"),
            MemoryMessage(
                role="assistant",
                content="本轮有两条来源。",
                references=[
                    {"index": 1, "source_type": "paper", "title": "研究一", "file_uuid": "file-1"},
                    {"index": 2, "source_type": "paper", "title": "研究二", "file_uuid": "file-2"},
                ],
            ),
        ]
    )

    plan = QueryAnalyzer().analyze("把所有引用来源都说一下", memory_context=memory)

    assert plan.answer_mode == "source_detail"
    assert plan.retrieval_required is False


def test_query_analyzer_contextualizes_short_followup_without_citation_number():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="促排卵泡发育异常，如何快速调整用药剂量与检测计划"),
            MemoryMessage(role="assistant", content="需要结合卵泡大小、激素水平和既往反应动态评估。"),
        ],
    )

    plan = QueryAnalyzer().analyze("那监测频次呢？", memory_context=memory)

    assert "那监测频次呢" in plan.rewritten_query
    assert "促排卵泡发育异常" in plan.rewritten_query


def test_query_analyzer_does_not_append_memory_to_standalone_question():
    memory = MemoryContext(
        recent_messages=[
            MemoryMessage(role="user", content="促排卵泡发育异常，如何快速调整用药剂量与检测计划"),
        ],
    )

    plan = QueryAnalyzer().analyze("多囊卵巢综合征有哪些文献证据？", memory_context=memory)

    assert "上下文" not in plan.rewritten_query

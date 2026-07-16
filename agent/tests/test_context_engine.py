from agent.memory.context_engine import ContextEngine
from agent.memory.schemas import MemoryContext, MemoryMessage, UserContext


def test_context_engine_selects_case_facts_and_user_preferences():
    pack = ContextEngine().build(
        question="这个病例下一步方案怎么比较？",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(role="user", content="患者年龄28岁，AMH为0.8，诊断为DOR。"),
                MemoryMessage(role="assistant", content="可以从监测和证据两方面分析。"),
            ]
        ),
        user_context=UserContext(
            active_role="clinician",
            technical_level="professional",
            detail_level="detailed",
        ),
    )

    assert pack.context_plan.mode == "case_analysis"
    assert pack.current_case.facts["age"] == "28"
    assert pack.current_case.facts["amh"] == "0.8"
    assert pack.current_case.facts["diagnosis"] == "DOR"
    assert pack.user_context.active_role == "clinician"
    assert pack.user_context.detail_level == "detailed"


def test_context_engine_resolves_previous_citation_target():
    pack = ContextEngine().build(
        question="展开一下依据1",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(role="user", content="多囊促排方案怎么选？"),
                MemoryMessage(
                    role="assistant",
                    content="依据见[1]。",
                    references=[
                        {
                            "index": 1,
                            "title": "多囊促排病案",
                            "file_uuid": "file-1",
                        }
                    ],
                ),
            ]
        ),
    )

    assert pack.context_plan.mode == "citation_follow_up"
    assert pack.context_plan.use_citation_context is True
    assert pack.citation_context["previous_references"][0]["file_uuid"] == "file-1"


def test_context_engine_keeps_only_requested_reference_in_citation_followup():
    pack = ContextEngine().build(
        question="说一说文献1",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(
                    role="assistant",
                    content="上一轮有多条来源。",
                    references=[
                        {"index": 1, "title": "文献一", "file_uuid": "file-1"},
                        {"index": 2, "title": "文献二", "file_uuid": "file-2"},
                    ],
                )
            ]
        ),
    )

    assert pack.citation_context["requested_reference_index"] == 1
    assert pack.citation_context["previous_references"] == [
        {"index": 1, "title": "文献一", "file_uuid": "file-1"}
    ]
    assistant_history = next(item for item in pack.relevant_history if item["role"] == "assistant")
    assert assistant_history["references"] == [
        {"index": 1, "title": "文献一", "file_uuid": "file-1"}
    ]

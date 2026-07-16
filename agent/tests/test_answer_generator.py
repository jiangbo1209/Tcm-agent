from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence
from agent.schemas.answer import AnswerResult
from agent.memory.schemas import MemoryContext, MemoryMessage, UserContext
from agent.services.answer_generator import AnswerGenerator, sanitize_answer_text


class FakeLLMClient:
    def __init__(self):
        self.prompt = ""
        self.system_prompt = ""

    def stream_generate(self, prompt: str, system_prompt: str | None = None):
        self.prompt = prompt
        self.system_prompt = system_prompt or ""
        return iter(["这是模型生成的回答。[1]"])


class FailingLLMClient:
    def stream_generate(self, prompt: str, system_prompt: str | None = None):
        raise RuntimeError("model unavailable")


def stream_result(generator: AnswerGenerator, **kwargs) -> AnswerResult:
    chunks, sources, references, warnings = generator.stream_generate(**kwargs)
    return AnswerResult(
        answer="".join(chunks),
        sources=sources,
        references=references,
        warnings=warnings,
    )


def test_answer_generator_uses_llm_with_grounded_prompt():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    result = stream_result(
        generator,
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


def test_answer_prompt_contains_ordered_context_pack():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    stream_result(
        generator,
        question="这个病例应该重点关注什么？",
        query_plan=QueryPlan(
            intent="clinical_decision_question",
            source_type=None,
            rewritten_query="病例 重点关注",
            search_type="both",
            top_k=3,
        ),
        evidence=[],
        total=0,
        memory_context=MemoryContext(
            recent_messages=[],
            summary="前文讨论患者的多囊和AMH情况。",
        ),
        user_context=UserContext(
            active_role="clinician",
            technical_level="professional",
            detail_level="detailed",
            response_style="comparison",
        ),
    )

    prompt = fake_llm.prompt
    sections = [
        '"current_question"',
        '"context_plan"',
        '"user_context"',
        '"current_case"',
        '"retrieval_evidence"',
        '"citation_context"',
        '"relevant_history"',
        '"answer_constraints"',
        '"medical_safety"',
    ]
    positions = [prompt.index(section) for section in sections]
    assert positions == sorted(positions)
    assert '"active_role": "clinician"' in prompt
    assert '"response_style": "comparison"' in prompt


def test_answer_prompt_uses_route_specific_contract():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    stream_result(
        generator,
        question="试管婴儿术前降调、促排、移植、黄体支持分别需要注意什么？",
        query_plan=QueryPlan(
            intent="clinical_decision_question",
            rewritten_query="试管婴儿 四个阶段 注意事项",
            search_type="both",
            top_k=3,
            task_type="assisted_reproduction_stages",
            answer_mode="phase_guidance",
            retrieval_strategy="multi_query",
            risk_level="high",
        ),
        evidence=[],
        total=0,
    )

    assert '"answer_mode": "phase_guidance"' in fake_llm.prompt
    assert "按阶段分别说明" in fake_llm.prompt
    assert "不强制套用其他问题的固定标题" in fake_llm.prompt


def test_answer_generator_uses_general_fallback_for_weak_evidence():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    result = stream_result(
        generator,
        question="生化妊娠后多久可以再次备孕？",
        query_plan=QueryPlan(
            intent="general_medical_question",
            rewritten_query="生化妊娠 再次备孕 时间",
            search_type="both",
            top_k=3,
        ),
        evidence=[
            Evidence(
                source_type="paper",
                title="不孕症中医辨证治疗",
                file_uuid="weak-1",
                chunk="不孕症的中医治疗经验。",
            )
        ],
        total=1,
        evidence_status="weak_evidence",
    )

    assert result.references == []
    assert "当前 RAGFlow 知识库没有检索到足够相关的证据" in fake_llm.prompt


def test_answer_generator_reindexes_final_references():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)
    result = stream_result(
        generator,
        question="多囊有哪些文献证据？",
        query_plan=QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query="多囊 文献证据",
            search_type="literature",
            top_k=3,
        ),
        evidence=[
            Evidence(source_type="paper", title="来源一", file_uuid="one", citation_index=7),
            Evidence(source_type="paper", title="来源二", file_uuid="two", citation_index=7),
        ],
        total=2,
    )

    assert [ref.index for ref in result.references] == [1, 2]
    assert '"index": 1' in fake_llm.prompt


def test_answer_generator_uses_previous_source_without_new_evidence():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)
    result = stream_result(
        generator,
        question="展开一下依据1",
        query_plan=QueryPlan(
            intent="general_medical_question",
            rewritten_query="依据1 来源详情",
            search_type="both",
            answer_mode="source_detail",
            retrieval_strategy="source_targeted",
            retrieval_required=False,
        ),
        evidence=[],
        total=0,
        evidence_status="source_only",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(
                    role="assistant",
                    content="上一轮回答依据[1]。",
                    references=[
                        {
                            "index": 1,
                            "source_type": "paper",
                            "title": "来源一",
                            "file_uuid": "file-1",
                            "snippet": "来源片段",
                        }
                    ],
                )
            ]
        ),
    )

    assert result.references[0].index == 1
    assert result.references[0].file_uuid == "file-1"
    assert "来源详情回答 Prompt" in fake_llm.prompt


def test_source_detail_returns_only_the_requested_previous_reference():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)
    result = stream_result(
        generator,
        question="说一说文献1",
        query_plan=QueryPlan(
            intent="literature_question",
            rewritten_query="文献1 来源详情",
            search_type="literature",
            answer_mode="source_detail",
            retrieval_strategy="source_targeted",
            retrieval_required=False,
        ),
        evidence=[],
        total=0,
        evidence_status="source_only",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(
                    role="assistant",
                    content="上一轮有四条引用来源。",
                    references=[
                        {"index": 1, "source_type": "paper", "title": "文献一", "file_uuid": "file-1"},
                        {"index": 2, "source_type": "paper", "title": "文献二", "file_uuid": "file-2"},
                        {"index": 3, "source_type": "record", "title": "病案三", "file_uuid": "file-3"},
                        {"index": 4, "source_type": "record", "title": "病案四", "file_uuid": "file-4"},
                    ],
                )
            ]
        ),
    )

    assert [reference.index for reference in result.references] == [1]
    assert [reference.file_uuid for reference in result.references] == ["file-1"]
    assert result.sources == ["[1] 文献：文献一（UUID：file-1）"]
    assert "文献二" not in fake_llm.prompt
    assert "病案三" not in fake_llm.prompt


def test_source_detail_returns_all_previous_references_when_requested():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)
    result = stream_result(
        generator,
        question="把所有引用来源都说一下",
        query_plan=QueryPlan(
            intent="literature_question",
            rewritten_query="全部引用来源详情",
            search_type="literature",
            answer_mode="source_detail",
            retrieval_strategy="source_targeted",
            retrieval_required=False,
        ),
        evidence=[],
        total=0,
        evidence_status="source_only",
        memory_context=MemoryContext(
            recent_messages=[
                MemoryMessage(
                    role="assistant",
                    content="上一轮有两条引用来源。",
                    references=[
                        {"index": 1, "source_type": "paper", "title": "文献一", "file_uuid": "file-1"},
                        {"index": 2, "source_type": "paper", "title": "文献二", "file_uuid": "file-2"},
                    ],
                )
            ]
        ),
    )

    assert [reference.index for reference in result.references] == [1, 2]
    assert "文献一" in fake_llm.prompt
    assert "文献二" in fake_llm.prompt


def test_sanitize_answer_text_removes_internal_notes_and_markdown_decoration():
    text = "### 研究结论\n**内容**\n---\n（回答完毕，全部结论均源自本轮 retrieval_evidence）"

    cleaned = sanitize_answer_text(text)

    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "---" not in cleaned
    assert "回答完毕" not in cleaned
    assert "retrieval_evidence" not in cleaned


def test_answer_generator_general_prompt_answers_before_unhit_notice():
    fake_llm = FakeLLMClient()
    generator = AnswerGenerator(llm_client=fake_llm)

    stream_result(
        generator,
        question="多囊卵巢综合征有什么中医调理思路？",
        query_plan=QueryPlan(
            intent="general_medical_question",
            source_type=None,
            rewritten_query="多囊卵巢综合征 中医调理思路",
            search_type="both",
            top_k=3,
        ),
        evidence=[],
        total=0,
    )

    assert "先基于普通医学知识给出保守、实用的回答" in fake_llm.prompt
    assert "当前知识库未命中" in fake_llm.prompt


def test_answer_generator_falls_back_when_llm_fails():
    generator = AnswerGenerator(llm_client=FailingLLMClient())

    result = stream_result(
        generator,
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

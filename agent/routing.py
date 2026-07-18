"""Lightweight task routing shared by query analysis and answer generation."""

from __future__ import annotations

from typing import Any

from agent.memory.resolver import MemoryResolver
from agent.memory.schemas import MemoryContext, UserContext
from agent.routing_terms import (
    CASE_ROUTE_TERMS,
    COMPARE_TERMS,
    EDUCATION_TERMS,
    REPORT_INTERPRETATION_KEYWORDS,
    SAFETY_TERMS,
    STAGE_TERMS,
)
from agent.schemas.query import QueryPlan


def apply_route(
    question: str,
    plan: QueryPlan,
    memory_context: MemoryContext | None = None,
    preserve_model_route: bool = False,
) -> QueryPlan:
    """Apply the rule route or use rules as deterministic guardrails."""

    rule_values = _rule_route_values(question, plan, memory_context)
    if not preserve_model_route:
        return plan.model_copy(update=rule_values)

    return plan.model_copy(
        update=_guardrail_values(question, plan, memory_context, rule_values)
    )


def _rule_route_values(
    question: str,
    plan: QueryPlan,
    memory_context: MemoryContext | None = None,
) -> dict[str, Any]:
    """Build the deterministic route used when model analysis is unavailable."""

    text = question.lower()
    resolver = MemoryResolver()
    has_citation = (
        resolver.citation_reference_index(question) is not None
        or resolver.all_citations_requested(question)
    )
    history_needed = bool(memory_context and resolver.needs_context(question))
    stage_hits = [term for term in STAGE_TERMS if term.lower() in text]
    is_report = any(term.lower() in text for term in REPORT_INTERPRETATION_KEYWORDS)
    is_safety = any(term.lower() in text for term in SAFETY_TERMS)
    is_compare = any(term.lower() in text for term in COMPARE_TERMS)
    is_case = plan.intent == "case_question" or any(term in question for term in CASE_ROUTE_TERMS)
    is_literature = plan.intent == "literature_question"
    is_education = plan.intent == "patient_education_question" or any(term in text for term in EDUCATION_TERMS)

    if has_citation and memory_context:
        values = _route_values(
            task_type="source_detail",
            answer_mode="source_detail",
            retrieval_strategy="source_targeted",
            context_mode="citation_follow_up",
            risk_level="medium",
            retrieval_required=False,
        )
    elif is_report:
        values = _route_values(
            task_type="report_interpretation",
            answer_mode="report_interpretation",
            retrieval_strategy="report_evidence",
            context_mode="case_analysis" if history_needed else "new_question",
            risk_level="high",
            retrieval_required=True,
        )
    elif len(stage_hits) >= 2 or ("阶段" in question and stage_hits):
        values = _route_values(
            task_type="assisted_reproduction_stages",
            answer_mode="phase_guidance",
            retrieval_strategy="multi_query",
            context_mode="case_analysis" if history_needed else "new_question",
            risk_level="high",
            retrieval_required=True,
            sub_queries=_stage_sub_queries(question, stage_hits),
        )
    elif is_safety:
        values = _route_values(
            task_type="safety_risk",
            answer_mode="safety_risk",
            retrieval_strategy="guideline_first",
            context_mode="case_analysis" if history_needed else "new_question",
            risk_level="high",
            retrieval_required=True,
        )
    elif is_compare:
        values = _route_values(
            task_type="option_comparison",
            answer_mode="option_comparison",
            retrieval_strategy="literature_case_mix",
            context_mode="case_analysis" if history_needed or is_case else "new_question",
            risk_level="high" if plan.intent == "clinical_decision_question" else "medium",
            retrieval_required=True,
        )
    elif is_case:
        values = _route_values(
            task_type="case_analysis" if "患者" in question or "病史" in question or "个体化" in question else "case_review",
            answer_mode="case_analysis" if "患者" in question or "病史" in question or "个体化" in question else "case_review",
            retrieval_strategy="literature_case_mix" if plan.intent == "clinical_decision_question" else "case_first",
            context_mode="case_analysis",
            risk_level="high" if plan.intent == "clinical_decision_question" else "medium",
            retrieval_required=True,
        )
    elif is_literature:
        values = _route_values(
            task_type="literature_evidence",
            answer_mode="evidence_summary",
            retrieval_strategy="literature_first",
            context_mode="follow_up" if history_needed else "new_question",
            risk_level="medium",
            retrieval_required=True,
        )
    elif is_education:
        values = _route_values(
            task_type="patient_education",
            answer_mode="patient_education",
            retrieval_strategy="hybrid",
            context_mode="follow_up" if history_needed else "new_question",
            risk_level="medium",
            retrieval_required=True,
        )
    elif history_needed:
        values = _route_values(
            task_type="follow_up",
            answer_mode="follow_up",
            retrieval_strategy="single_query",
            context_mode="follow_up",
            risk_level="medium",
            retrieval_required=True,
        )
    else:
        values = _route_values(
            task_type="general_qa",
            answer_mode="general",
            retrieval_strategy="single_query",
            context_mode="new_question",
            risk_level="medium",
            retrieval_required=True,
        )

    return values


def _guardrail_values(
    question: str,
    plan: QueryPlan,
    memory_context: MemoryContext | None,
    rule_values: dict[str, Any],
) -> dict[str, Any]:
    """Keep valid model routing while enforcing deterministic safety boundaries."""

    text = question.lower()
    resolver = MemoryResolver()
    has_citation = (
        resolver.citation_reference_index(question) is not None
        or resolver.all_citations_requested(question)
    )
    history_needed = bool(memory_context and resolver.needs_context(question))
    stage_hits = [term for term in STAGE_TERMS if term.lower() in text]
    is_report = any(term.lower() in text for term in REPORT_INTERPRETATION_KEYWORDS)
    is_safety = any(term.lower() in text for term in SAFETY_TERMS)
    is_compare = any(term.lower() in text for term in COMPARE_TERMS)

    if has_citation and memory_context:
        return rule_values

    high_confidence_route = (
        is_report
        or is_safety
        or len(stage_hits) >= 2
        or ("阶段" in question and bool(stage_hits))
        or (is_compare and plan.intent == "clinical_decision_question")
    )
    if high_confidence_route:
        return rule_values

    overrides: dict[str, Any] = {
        "retrieval_required": True,
    }
    if rule_values.get("risk_level") == "high" or plan.risk_level == "high":
        overrides["risk_level"] = "high"
    if plan.answer_mode == "source_detail" and not (has_citation and memory_context):
        overrides.update(rule_values)
    if history_needed and plan.context_mode == "new_question":
        overrides["context_mode"] = "follow_up"
    return overrides


def route_contract(
    plan: QueryPlan,
    user_context: UserContext | None = None,
    evidence_status: str = "not_checked",
) -> dict[str, Any]:
    response_guidance = {
        "source_detail": {
            "primary_focus": ["来源基本信息", "资料明确说明的内容", "资料没有说明的内容"],
            "optional_focus": ["证据局限", "原文核查建议"],
        },
        "report_interpretation": {
            "primary_focus": ["指标或检查结果的含义", "与当前情况相关的影响因素"],
            "optional_focus": ["仍需补充的信息", "下一步就医或检查建议"],
        },
        "phase_guidance": {
            "primary_focus": ["用户提到的阶段", "阶段目标", "监测重点"],
            "optional_focus": ["常见风险", "证据不足的部分"],
        },
        "safety_risk": {
            "primary_focus": ["可能情况", "安全边界", "需要立即就医的信号"],
            "optional_focus": ["当前不能确定的部分", "监测或就医建议"],
        },
        "option_comparison": {
            "primary_focus": ["方案差异", "适用情况", "优点和局限"],
            "optional_focus": ["风险与监测", "证据强度", "决策限制"],
        },
        "case_analysis": {
            "primary_focus": ["病例已知信息", "关键问题", "证据支持的分析框架"],
            "optional_focus": ["缺失信息", "后续评估重点"],
        },
        "case_review": {
            "primary_focus": ["病案基本情况", "辨证和治疗思路"],
            "optional_focus": ["疗效与局限", "可借鉴内容"],
        },
        "evidence_summary": {
            "primary_focus": ["研究结论", "研究对象和干预", "主要结果"],
            "optional_focus": ["证据局限", "需要进一步核实的问题"],
        },
        "patient_education": {
            "primary_focus": ["先用通俗语言回答", "用户可以做什么"],
            "optional_focus": ["需要避免什么", "何时就医"],
        },
        "follow_up": {
            "primary_focus": ["承接上一轮问题", "直接补充当前追问"],
            "optional_focus": ["仍需结合的条件", "下一步方向"],
        },
        "general": {
            "primary_focus": ["直接回答问题", "必要的依据"],
            "optional_focus": ["风险提示", "补充说明"],
        },
    }
    user = user_context or UserContext()
    role_guidance = {
        "patient": "使用通俗易懂的中文，解释术语，不直接给出具体处方或剂量。",
        "clinician": "可以使用专业术语，突出证据等级、监测指标和决策节点，但不替医生下最终医嘱。",
        "institution_researcher": "优先说明数据来源、统计口径和证据局限，不把个案经验当作总体结论。",
    }.get(user.active_role, "使用清晰的中文回答，并根据用户问题控制专业程度。")
    return {
        "task_type": plan.task_type,
        "answer_mode": plan.answer_mode,
        "retrieval_strategy": plan.retrieval_strategy,
        "context_mode": plan.context_mode,
        "retrieval_required": plan.retrieval_required,
        "risk_level": plan.risk_level,
        "evidence_status": evidence_status,
        "response_guidance": response_guidance.get(plan.answer_mode, response_guidance["general"]),
        "role_guidance": role_guidance,
        "format_rule": "response_guidance 是软性建议，不是固定提纲；先回答用户最关心的问题，再按相关性选择补充角度，不必逐项覆盖；内部路由字段只用于控制回答，不要在正文中解释。",
    }


def _route_values(**values: Any) -> dict[str, Any]:
    return values


def _stage_sub_queries(question: str, stages: list[str]) -> list[str]:
    topic_terms = [
        term for term in ("试管婴儿", "辅助生殖", "不孕症", "DOR", "多囊", "子宫内膜异位症")
        if term.lower() in question.lower()
    ]
    topic = "、".join(topic_terms) or "辅助生殖"
    focus = {
        "降调": "成功进入促排周期的标准 FSH E2 AFC 卵泡和内膜",
        "促排": "启动和监测标准 卵泡 E2 LH 和内膜",
        "移植": "移植前内膜 胚胎和围移植管理",
        "黄体支持": "开始条件 监测重点和安全边界",
        "取卵": "取卵前准备和术后监测",
    }
    return [f"{topic} {stage} {focus.get(stage, '阶段目标、监测重点和安全边界')}" for stage in stages]

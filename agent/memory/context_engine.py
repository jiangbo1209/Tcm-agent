"""Lightweight context selection and ordering for the Agent prompts."""

from __future__ import annotations

import re
from typing import Any, Iterable

from agent.memory.schemas import (
    CaseContext,
    ContextPack,
    ContextPlan,
    MemoryContext,
    UserContext,
)
from agent.routing_terms import CASE_CONTEXT_TERMS, EXPLANATION_TERMS


class ContextEngine:
    """Builds a compact, task-aware context pack without adding another memory store."""

    _SAFETY_RULES = [
        "医学事实和结论必须以本轮检索证据或明确标注的一般医学知识为依据。",
        "不能把历史回答、模型摘要或单个病案经验当作普遍医学结论。",
        "涉及具体剂量、扳机时间、成功率、风险分级和用药调整时，只能提供判断框架并建议由医生结合检查决定。",
        "涉及孕期、备孕、移植后、合并症或药物安全时，应提醒遵医嘱并结合线下医生评估。",
        "不得保证疗效、妊娠或安全；出现急症风险时应提示及时就医。",
    ]
    _FIELD_PATTERNS = {
        "age": r"(?:年龄|岁数)\s*(?:为|是|[:：=])?\s*(\d{1,3})\s*岁?",
        "height": r"(?:身高)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:cm|厘米)?",
        "weight": r"(?:体重)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:kg|公斤|千克)?",
        "bmi": r"(?:BMI|bmi)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)",
        "amh": r"(?:AMH|amh)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)",
        "fsh": r"(?:FSH|fsh)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)",
        "lh": r"(?:LH|lh)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)",
        "e2": r"(?:E2|e2|雌二醇)\s*(?:为|是|[:：=])?\s*([0-9]+(?:\.[0-9]+)?)",
        "diagnosis": r"(?:诊断|疾病|病名)\s*(?:为|是|[:：=])?\s*([^，。；;\n]{1,60})",
        "syndrome": r"(?:证型|辨证)\s*(?:为|是|[:：=])?\s*([^，。；;\n]{1,60})",
        "comorbidities": r"(?:合并症|既往病史)\s*(?:为|有|包括|[:：=])?\s*([^，。；;\n]{1,80})",
    }

    def __init__(self) -> None:
        from agent.memory.resolver import MemoryResolver

        self._resolver = MemoryResolver()

    def build(
        self,
        *,
        question: str,
        memory_context: MemoryContext | None = None,
        user_context: UserContext | dict[str, Any] | None = None,
        query_plan: Any | None = None,
        evidence: Iterable[Any] | None = None,
        references: Iterable[Any] | None = None,
    ) -> ContextPack:
        normalized_question = " ".join(question.strip().split())
        user = self._normalize_user_context(user_context)
        plan = self._build_plan(normalized_question, memory_context, query_plan)
        messages = memory_context.recent_messages if memory_context else []
        requested_reference_index = self._resolver.citation_reference_index(normalized_question)
        relevant_history = self._select_history(normalized_question, messages, plan)
        if requested_reference_index is not None:
            relevant_history = self._limit_history_references(relevant_history, requested_reference_index)
        if memory_context and memory_context.summary and plan.use_history:
            relevant_history.insert(0, {"role": "summary", "content": memory_context.summary, "references": []})
        current_case = self._build_case_context(normalized_question, messages, plan)
        citation_context = self._build_citation_context(
            memory_context,
            references,
            requested_reference_index=requested_reference_index,
        )
        evidence_payload = self._serialize_items(evidence, limit=20)

        return ContextPack(
            current_question=normalized_question,
            context_plan=plan,
            user_context=user,
            current_case=current_case,
            retrieval_evidence=evidence_payload,
            citation_context=citation_context,
            relevant_history=relevant_history,
            answer_constraints={
                "language": "中文",
                "technical_level": user.technical_level,
                "detail_level": user.detail_level,
                "response_style": user.response_style,
                "evidence_preference": user.evidence_preference,
                "citation_rule": "只能引用本轮 evidence 中存在的 index",
                "do_not_write_reference_list": True,
            },
            medical_safety=list(self._SAFETY_RULES),
        )

    def _normalize_user_context(self, value: UserContext | dict[str, Any] | None) -> UserContext:
        if isinstance(value, UserContext):
            return value
        if isinstance(value, dict):
            allowed = set(UserContext.model_fields)
            return UserContext(**{key: item for key, item in value.items() if key in allowed})
        return UserContext()

    def _build_plan(
        self,
        question: str,
        memory_context: MemoryContext | None,
        query_plan: Any | None,
    ) -> ContextPlan:
        has_citation = (
            self._resolver.citation_reference_index(question) is not None
            or self._resolver.all_citations_requested(question)
        )
        needs_history = bool(memory_context and self._resolver.needs_context(question))
        is_case = any(term.lower() in question.lower() for term in CASE_CONTEXT_TERMS)
        is_explanation = any(term in question for term in EXPLANATION_TERMS)

        if has_citation:
            mode, reason = "citation_follow_up", "用户正在追问上一轮引用来源。"
        elif is_explanation and needs_history:
            mode, reason = "explanation", "用户要求对当前对话内容进行解释。"
        elif is_case:
            mode, reason = "case_analysis", "问题包含病例、检查或个体化治疗信息。"
        elif needs_history:
            mode, reason = "follow_up", "问题包含对前文的指代或追问语气。"
        else:
            mode, reason = "new_question", "当前问题可以独立理解。"

        query_plan_payload = self._serialize_item(query_plan) if query_plan is not None else None
        return ContextPlan(
            mode=mode,
            reason=reason,
            use_case_context=is_case or mode in {"case_analysis", "follow_up"},
            use_citation_context=has_citation,
            use_history=needs_history or has_citation or mode == "case_analysis",
            retrieval_required=True,
            query_plan=query_plan_payload,
        )

    def _select_history(self, question: str, messages: list[Any], plan: ContextPlan) -> list[dict[str, Any]]:
        if not messages:
            return []

        if plan.use_history:
            selected = messages[-4:]
        else:
            scored = sorted(
                ((self._relevance_score(question, message.content), index, message) for index, message in enumerate(messages)),
                key=lambda item: (item[0], item[1]),
                reverse=True,
            )
            selected = [item[2] for item in scored[:2] if item[0] > 0]
            selected.sort(key=lambda item: messages.index(item))

        payload = [item.model_dump(mode="json") for item in selected]
        return payload

    def _relevance_score(self, question: str, content: str) -> int:
        question_text = question.lower()
        content_text = (content or "").lower()
        score = sum(1 for term in CASE_CONTEXT_TERMS if term.lower() in question_text and term.lower() in content_text)
        question_bigrams = self._bigrams(question_text)
        content_bigrams = self._bigrams(content_text)
        score += min(3, len(question_bigrams & content_bigrams))
        return score

    def _bigrams(self, text: str) -> set[str]:
        return {text[index : index + 2] for index in range(len(text) - 1) if text[index : index + 2].strip()}

    def _build_case_context(self, question: str, messages: list[Any], plan: ContextPlan) -> CaseContext:
        if not plan.use_case_context:
            return CaseContext()

        source = "\n".join(message.content for message in messages if message.role == "user")
        source = f"{source}\n{question}"
        values: dict[str, list[str]] = {}
        for field, pattern in self._FIELD_PATTERNS.items():
            values[field] = [match.strip() for match in re.findall(pattern, source, flags=re.IGNORECASE)]

        facts: dict[str, str] = {}
        conflicts: list[str] = []
        for field, matches in values.items():
            unique = list(dict.fromkeys(item for item in matches if item))
            if unique:
                facts[field] = unique[-1]
            if len(unique) > 1:
                conflicts.append(f"{field}存在多个值：{'、'.join(unique)}")

        mentioned = [
            term for term in ("多囊卵巢综合征", "DOR", "不孕症", "子宫内膜异位症", "子宫腺肌症", "输卵管积水")
            if term.lower() in source.lower()
        ]
        if mentioned:
            facts["mentioned_conditions"] = "、".join(mentioned)

        missing = []
        if plan.mode == "case_analysis":
            for field in ("age", "diagnosis", "amh"):
                if field not in facts:
                    missing.append(field)
        return CaseContext(facts=facts, missing_fields=missing, conflicts=conflicts)

    def _build_citation_context(
        self,
        memory_context: MemoryContext | None,
        references: Iterable[Any] | None,
        requested_reference_index: int | None = None,
    ) -> dict[str, Any]:
        previous: list[dict[str, Any]] = []
        if memory_context:
            for message in reversed(memory_context.recent_messages):
                if message.role == "assistant" and message.references:
                    previous = list(message.references[:6])
                    break

        if requested_reference_index is not None:
            previous = self._references_with_index(previous, requested_reference_index)

        current = self._serialize_items(references, limit=8)
        return {
            "previous_references": previous,
            "current_references": current,
            "requested_reference_index": requested_reference_index,
            "numbering_note": "上一轮和本轮引用编号分别解释，不能混用；本轮回答只能引用本轮 evidence 的 index。",
        }

    def _limit_history_references(
        self,
        history: list[dict[str, Any]],
        requested_reference_index: int,
    ) -> list[dict[str, Any]]:
        for item in history:
            if item.get("role") == "assistant" and item.get("references"):
                item["references"] = self._references_with_index(
                    item["references"], requested_reference_index
                )
        return history

    def _references_with_index(
        self,
        references: Iterable[dict[str, Any]],
        requested_reference_index: int,
    ) -> list[dict[str, Any]]:
        return [
            reference
            for reference in references
            if self._reference_index(reference) == requested_reference_index
        ]

    def _reference_index(self, reference: dict[str, Any]) -> int | None:
        try:
            return int(reference.get("index"))
        except (TypeError, ValueError):
            return None

    def _serialize_items(self, items: Iterable[Any] | None, limit: int) -> list[dict[str, Any]]:
        if not items:
            return []
        return [self._serialize_item(item) for item in list(items)[:limit]]

    def _serialize_item(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return item
        if hasattr(item, "model_dump"):
            return item.model_dump(mode="json")
        return dict(item)

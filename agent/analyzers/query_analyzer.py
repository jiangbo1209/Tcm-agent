"""Question understanding and retrieval rewrite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.config import get_agent_settings
from agent.schemas.query import QueryPlan
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"

CASE_KEYWORDS = (
    "病例",
    "病案",
    "患者",
    "医案",
    "症状",
    "诊断",
    "证型",
    "方药",
    "处方",
    "治疗",
    "疗效",
    "不孕",
    "妊娠",
)

LITERATURE_KEYWORDS = (
    "文献",
    "论文",
    "研究",
    "指南",
    "共识",
    "综述",
    "证据",
    "机制",
    "Meta",
    "RCT",
)

GUIDELINE_KEYWORDS = (
    "指南",
    "共识",
    "规范",
    "校验",
    "风险",
    "是否符合",
    "是否越界",
)


class QueryAnalyzer:
    def __init__(self, default_top_k: int = 6, llm_client: LLMClient | None = None) -> None:
        self._default_top_k = default_top_k
        self._llm_client = llm_client
        self._use_llm = llm_client is not None or get_agent_settings().enable_llm_query_analysis

    def analyze(self, question: str, top_k: int | None = None) -> QueryPlan:
        safe_top_k = top_k or self._default_top_k
        if self._use_llm:
            try:
                plan = self._analyze_with_llm(question, safe_top_k)
            except Exception:
                plan = self._analyze_with_rules(question, safe_top_k)
        else:
            plan = self._analyze_with_rules(question, safe_top_k)

        if top_k:
            plan.top_k = top_k
        return plan

    def _analyze_with_llm(self, question: str, top_k: int) -> QueryPlan:
        prompt = self._render_prompt("query_analysis.md", question=question)
        llm_client = self._llm_client or LLMClient()
        raw = llm_client.generate(
            prompt=prompt,
            system_prompt="你是医疗 Agent 的问题理解模块，只输出合法 JSON。",
        )
        payload = self._extract_json(raw)
        if "top_k" not in payload or not payload["top_k"]:
            payload["top_k"] = top_k
        if "filters" not in payload or payload["filters"] is None:
            payload["filters"] = {}
        plan = QueryPlan(**payload)
        return self._normalize_plan(plan, fallback_question=question, fallback_top_k=top_k)

    def _analyze_with_rules(self, question: str, top_k: int) -> QueryPlan:
        case_hits = self._count_hits(question, CASE_KEYWORDS)
        literature_hits = self._count_hits(question, LITERATURE_KEYWORDS)
        guideline_hits = self._count_hits(question, GUIDELINE_KEYWORDS)

        if guideline_hits > max(case_hits, literature_hits) and guideline_hits > 0:
            return QueryPlan(
                intent="guideline_validation_question",
                source_type="guideline",
                rewritten_query=question,
                search_type="guideline",
                top_k=top_k,
            )

        if case_hits > literature_hits and case_hits > 0:
            return QueryPlan(
                intent="case_question",
                source_type="record",
                rewritten_query=question,
                search_type="case",
                top_k=top_k,
            )

        if literature_hits > case_hits and literature_hits > 0:
            return QueryPlan(
                intent="literature_question",
                source_type="paper",
                rewritten_query=question,
                search_type="literature",
                top_k=top_k,
            )

        return QueryPlan(
            intent="general_medical_question",
            source_type=None,
            rewritten_query=question,
            search_type="both",
            top_k=top_k,
        )

    def _normalize_plan(self, plan: QueryPlan, fallback_question: str, fallback_top_k: int) -> QueryPlan:
        valid_search_types = {"literature", "case", "both", "guideline"}
        valid_source_types = {"paper", "record", "guideline", None}

        if plan.search_type not in valid_search_types:
            plan.search_type = "both"
        if plan.source_type not in valid_source_types:
            plan.source_type = None
        if not plan.rewritten_query.strip():
            plan.rewritten_query = fallback_question
        if not plan.top_k:
            plan.top_k = fallback_top_k
        return plan

    def _render_prompt(self, filename: str, **values: str) -> str:
        template = (PROMPT_DIR / filename).read_text(encoding="utf-8")
        for key, value in values.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        return template

    def _extract_json(self, text: str) -> dict[str, Any]:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("LLM did not return JSON")
        return json.loads(stripped[start : end + 1])

    def _count_hits(self, text: str, keywords: tuple[str, ...]) -> int:
        lower_text = text.lower()
        return sum(1 for keyword in keywords if keyword.lower() in lower_text)

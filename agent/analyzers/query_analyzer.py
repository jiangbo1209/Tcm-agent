"""Question understanding and retrieval rewrite."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent.config import get_agent_settings
from agent.memory.prompt_context import build_context_pack, format_context_pack
from agent.memory.resolver import MemoryResolver
from agent.memory.schemas import MemoryContext, UserContext
from agent.routing_terms import (
    CASE_KEYWORDS,
    CLINICAL_DECISION_KEYWORDS,
    GUIDELINE_KEYWORDS,
    HARD_DECISION_KEYWORDS,
    LITERATURE_KEYWORDS,
    PATIENT_EDUCATION_KEYWORDS,
    REPORT_INTERPRETATION_KEYWORDS,
)
from agent.routing import apply_route
from agent.schemas.query import QueryPlan
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class QueryAnalyzer:
    def __init__(
        self,
        default_top_k: int = 6,
        llm_client: LLMClient | None = None,
        guideline_retrieval_enabled: bool | None = None,
    ) -> None:
        self._default_top_k = default_top_k
        self._llm_client = llm_client
        settings = get_agent_settings()
        self._use_llm = llm_client is not None or settings.enable_llm_query_analysis
        self._guideline_retrieval_enabled = (
            settings.enable_guideline_retrieval
            if guideline_retrieval_enabled is None
            else guideline_retrieval_enabled
        )
        self._memory_resolver = MemoryResolver()

    def analyze(
        self,
        question: str,
        top_k: int | None = None,
        memory_context: MemoryContext | None = None,
        user_context: UserContext | None = None,
    ) -> QueryPlan:
        safe_top_k = top_k or self._default_top_k
        if self._use_llm:
            try:
                plan = self._analyze_with_llm(question, safe_top_k, memory_context, user_context)
            except Exception:
                plan = self._analyze_with_rules(question, safe_top_k, memory_context)
        else:
            plan = self._analyze_with_rules(question, safe_top_k, memory_context)

        if top_k:
            plan.top_k = top_k
        return apply_route(question, plan, memory_context)

    def _analyze_with_llm(
        self,
        question: str,
        top_k: int,
        memory_context: MemoryContext | None = None,
        user_context: UserContext | None = None,
    ) -> QueryPlan:
        prompt = self._render_prompt(
            "query_analysis.md",
            question=question,
            context_pack=self._format_context_pack(question, memory_context, user_context),
        )
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

    def _analyze_with_rules(
        self,
        question: str,
        top_k: int,
        memory_context: MemoryContext | None = None,
        user_context: UserContext | None = None,
    ) -> QueryPlan:
        rewritten_query = self._rewrite_query(question, memory_context)
        case_hits = self._count_hits(question, CASE_KEYWORDS)
        literature_hits = self._count_hits(question, LITERATURE_KEYWORDS)
        guideline_hits = self._count_hits(question, GUIDELINE_KEYWORDS)
        decision_hits = self._count_hits(question, CLINICAL_DECISION_KEYWORDS)
        hard_decision_hits = self._count_hits(question, HARD_DECISION_KEYWORDS)
        education_hits = self._count_hits(question, PATIENT_EDUCATION_KEYWORDS)
        report_hits = self._count_hits(question, REPORT_INTERPRETATION_KEYWORDS)

        if (
            self._guideline_retrieval_enabled
            and guideline_hits > 0
            and guideline_hits >= max(case_hits, literature_hits, decision_hits)
        ):
            return QueryPlan(
                intent="guideline_validation_question",
                source_type="guideline",
                rewritten_query=rewritten_query,
                search_type="guideline",
                top_k=top_k,
            )

        if education_hits > 0 and hard_decision_hits == 0 and report_hits == 0:
            return QueryPlan(
                intent="patient_education_question",
                source_type=None,
                rewritten_query=rewritten_query,
                search_type="both",
                top_k=top_k,
            )

        if decision_hits > 0 or report_hits > 0:
            return QueryPlan(
                intent="clinical_decision_question",
                source_type=None,
                rewritten_query=rewritten_query,
                search_type="both",
                top_k=top_k,
            )

        if education_hits > 0:
            return QueryPlan(
                intent="patient_education_question",
                source_type=None,
                rewritten_query=rewritten_query,
                search_type="both",
                top_k=top_k,
            )

        if case_hits > literature_hits and case_hits > 0:
            return QueryPlan(
                intent="case_question",
                source_type="record",
                rewritten_query=rewritten_query,
                search_type="case",
                top_k=top_k,
            )

        if literature_hits > case_hits and literature_hits > 0:
            return QueryPlan(
                intent="literature_question",
                source_type="paper",
                rewritten_query=rewritten_query,
                search_type="literature",
                top_k=top_k,
            )

        return QueryPlan(
            intent="general_medical_question",
            source_type=None,
            rewritten_query=rewritten_query,
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
        if not self._guideline_retrieval_enabled and (
            plan.search_type == "guideline" or plan.source_type == "guideline"
        ):
            plan.search_type = "both"
            plan.source_type = None
            if plan.intent == "guideline_validation_question":
                plan.intent = "clinical_decision_question"
        if not plan.rewritten_query.strip():
            plan.rewritten_query = self._rewrite_query(fallback_question)
        if not plan.top_k:
            plan.top_k = fallback_top_k
        return plan

    def _rewrite_query(self, question: str, memory_context: MemoryContext | None = None) -> str:
        return self._memory_resolver.contextualize_query(question, memory_context)

    def _format_context_pack(
        self,
        question: str,
        memory_context: MemoryContext | None,
        user_context: UserContext | None,
    ) -> str:
        return format_context_pack(
            build_context_pack(
                question=question,
                memory_context=memory_context,
                user_context=user_context,
            )
        )

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

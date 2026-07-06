"""Guideline answer checker."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.schemas.retrieval import Evidence
from agent.schemas.validation import ValidationResult
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[2] / "prompts"


class GuidelineChecker:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def check(
        self,
        question: str,
        answer: str,
        guidelines: list[Evidence],
        evidence: list[Evidence],
    ) -> ValidationResult:
        try:
            prompt = self._render_prompt(
                "guideline_validation.md",
                question=question,
                answer=answer,
                guidelines=self._json([self._evidence_for_prompt(item, index) for index, item in enumerate(guidelines, 1)]),
            )
            raw = self._llm_client.generate(
                prompt=prompt,
                system_prompt="你是医疗回答安全校验模块，只输出合法 JSON。",
            )
            payload = self._extract_json(raw)
            return ValidationResult(**payload)
        except Exception:
            return self._rule_based_check(answer)

    def _rule_based_check(self, answer: str) -> ValidationResult:
        risk_terms = ("必须治愈", "一定有效", "保证", "无需就医")
        issues = [f"回答中存在风险表达：{term}" for term in risk_terms if term in answer]
        return ValidationResult(
            passed=not issues,
            risk_level="medium" if issues else "low",
            issues=issues,
            suggested_revision="建议删除确定性疗效承诺，并提示需结合医生诊疗。" if issues else "",
        )

    def _render_prompt(self, filename: str, **values: str) -> str:
        template = (PROMPT_DIR / filename).read_text(encoding="utf-8")
        for key, value in values.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        return template

    def _evidence_for_prompt(self, item: Evidence, index: int) -> dict[str, Any]:
        return {
            "index": index,
            "source_type": item.source_type,
            "title": item.title,
            "file_uuid": item.file_uuid,
            "chunk": item.chunk,
            "score": item.score,
            "metadata": item.metadata,
        }

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

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

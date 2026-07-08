"""Answer generation service."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.schemas.answer import AnswerResult
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence, ReferenceSource
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
SYSTEM_PROMPT = "你是严谨的医疗 Agent，只能基于给定资料作答，不能编造医学证据。"


class AnswerGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def generate(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        total: int,
    ) -> AnswerResult:
        references = self._build_references(evidence)
        sources = self._build_sources(references)
        prompt = self._build_prompt(question, query_plan, evidence, references)

        try:
            answer = self._llm_client.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            return AnswerResult(answer=answer, sources=sources, references=references)
        except Exception as exc:
            fallback = self._fallback_answer(query_plan, evidence, total, sources)
            warning = f"llm_generation_failed: {exc}"
            return AnswerResult(answer=fallback, warnings=[warning], sources=sources, references=references)

    def stream_generate(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        total: int,
    ) -> tuple[Iterable[str], list[str], list[ReferenceSource], list[str]]:
        references = self._build_references(evidence)
        sources = self._build_sources(references)
        prompt = self._build_prompt(question, query_plan, evidence, references)

        try:
            chunks = self._llm_client.stream_generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            return chunks, sources, references, []
        except Exception as exc:
            fallback = self._fallback_answer(query_plan, evidence, total, sources)
            return iter([fallback]), sources, references, [f"llm_generation_failed: {exc}"]

    def _build_prompt(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        references: list[ReferenceSource],
    ) -> str:
        prompt_name = "grounded_answer.md" if evidence else "general_answer.md"
        return self._render_prompt(
            prompt_name,
            question=question,
            query_plan=self._json(query_plan.model_dump()),
            evidence=self._json(
                [self._evidence_for_prompt(item, reference) for item, reference in zip(evidence, references)]
            ),
        )

    def _fallback_answer(
        self,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        total: int,
        sources: list[str],
    ) -> str:
        if not evidence:
            return (
                "当前知识库没有检索到足够相关的文献、病案或指南依据。\n\n"
                f"问题理解：{self._intent_label(query_plan)}。\n"
                "当前回答生成服务没有正常返回，因此暂时无法给出完整回答。"
                "建议稍后重试，或检查 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL 配置。"
            )

        lines = [
            "根据当前知识库检索结果，先给出基于资料的初步回答：",
            "",
            f"问题理解：{self._intent_label(query_plan)}；共检索到 {total} 条相关资料，本次选取 {len(evidence)} 条作为参考。",
            "",
            "要点总结：",
        ]
        for index, item in enumerate(evidence[:3], start=1):
            citation = item.citation_index or index
            lines.append(f"{index}. {self._summarize(item)} [{citation}]")

        lines.extend(["", "参考资料：", *sources])
        lines.extend(
            [
                "",
                "说明：以上内容来自知识库检索结果，不能替代医生诊疗意见。涉及具体诊疗方案时，需要结合患者完整病史、体征和检查结果。",
            ]
        )
        return "\n".join(lines)

    def _render_prompt(self, filename: str, **values: str) -> str:
        template = (PROMPT_DIR / filename).read_text(encoding="utf-8")
        for key, value in values.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        return template

    def _evidence_for_prompt(self, item: Evidence, reference: ReferenceSource) -> dict[str, Any]:
        return {
            "index": reference.index,
            "source_type": item.source_type,
            "title": item.title,
            "file_uuid": item.file_uuid,
            "document_id": item.document_id,
            "dataset_id": item.dataset_id,
            "chunk_id": item.chunk_id,
            "chunk": item.chunk,
            "score": item.score,
            "metadata": item.metadata,
        }

    def _build_references(self, evidence: list[Evidence]) -> list[ReferenceSource]:
        references: list[ReferenceSource] = []
        for index, item in enumerate(evidence, start=1):
            metadata = item.metadata
            references.append(
                ReferenceSource(
                    index=item.citation_index or index,
                    source_type=item.source_type,
                    title=item.title,
                    file_uuid=item.file_uuid,
                    document_id=item.document_id,
                    dataset_id=item.dataset_id,
                    chunk_id=item.chunk_id,
                    snippet=self._shorten(item.chunk, max_len=260) if item.chunk else None,
                    authors=self._metadata_text(metadata, "authors", "author"),
                    journal=self._metadata_text(metadata, "journal", "source"),
                    year=self._metadata_text(metadata, "pub_year", "publish_year", "year"),
                    source_site=self._metadata_text(metadata, "source_site"),
                    source_url=self._metadata_text(metadata, "source_url", "url"),
                )
            )
        return references

    def _build_sources(self, references: list[ReferenceSource]) -> list[str]:
        sources: list[str] = []
        for reference in references:
            label = self._source_type_label(reference.source_type)
            uuid_part = f"（UUID：{reference.file_uuid}）" if reference.file_uuid else ""
            sources.append(f"[{reference.index}] {label}：{reference.title}{uuid_part}")
        return sources

    def _summarize(self, item: Evidence) -> str:
        fields = [
            ("题名", item.title),
            ("内容", item.chunk),
            ("来源", item.metadata.get("journal")),
            ("年份", item.metadata.get("publish_year") or item.metadata.get("pub_year")),
            ("中医诊断", item.metadata.get("tcm_diagnosis")),
            ("西医诊断", item.metadata.get("western_diagnosis")),
            ("治疗原则", item.metadata.get("treatment_principle")),
            ("方药", item.metadata.get("prescription")),
            ("疗效", item.metadata.get("efficacy")),
        ]
        parts = [
            f"{label}：{self._shorten(value)}"
            for label, value in fields
            if self._has_value(value)
        ]
        return "；".join(parts) if parts else self._shorten(item.title)

    def _intent_label(self, query_plan: QueryPlan) -> str:
        labels = {
            "case_question": "病案/病例问题",
            "literature_question": "文献/指南证据问题",
            "clinical_decision_question": "临床方案/决策辅助问题",
            "patient_education_question": "患者宣教问题",
            "general_medical_question": "综合医学问题",
            "guideline_validation_question": "医学指南校验问题",
        }
        return labels.get(query_plan.intent, query_plan.intent)

    def _source_type_label(self, source_type: str) -> str:
        labels = {
            "paper": "文献",
            "literature": "文献",
            "record": "病案",
            "case": "病案",
            "guideline": "指南",
        }
        return labels.get(source_type, source_type or "资料")

    def _metadata_text(self, metadata: dict[str, Any], *names: str) -> str | None:
        for name in names:
            value = metadata.get(name)
            if self._has_value(value):
                return self._shorten(value, max_len=200)
        return None

    def _json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)

    def _shorten(self, value: Any, max_len: int = 160) -> str:
        if isinstance(value, (list, tuple, set)):
            text = "、".join(str(item) for item in value if self._has_value(item))
        elif isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, default=str)
        else:
            text = "" if value is None else str(value)
        text = " ".join(text.split())
        return text if len(text) <= max_len else f"{text[:max_len]}..."

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip()) and value.strip().upper() != "NULL"
        if isinstance(value, (list, tuple, set, dict)):
            return bool(value)
        return True

"""Answer generation service."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from agent.memory.prompt_context import build_context_pack, format_context_pack
from agent.memory.resolver import MemoryResolver
from agent.memory.schemas import MemoryContext, UserContext
from agent.routing import route_contract
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence, ReferenceSource
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
SYSTEM_PROMPT = "你是严谨的医疗 Agent。证据充分时基于本轮证据作答；证据不足时可以提供一般医学知识，但必须明确说明没有本地知识库直接支撑，不能编造文献、指南、数据或引用。"


class AnswerGenerator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def stream_generate(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        total: int,
        memory_context: MemoryContext | None = None,
        user_context: UserContext | None = None,
        evidence_status: str = "not_checked",
    ) -> tuple[Iterable[str], list[str], list[ReferenceSource], list[str]]:
        references = self._build_references(evidence)
        if evidence_status in {"no_direct_evidence", "weak_evidence"}:
            references = []
        if query_plan.answer_mode == "source_detail" and not references:
            references = self._build_memory_references(memory_context, question)
        sources = self._build_sources(references)
        prompt = self._build_prompt(
            question, query_plan, evidence, references, memory_context, user_context, evidence_status
        )

        try:
            chunks = self._llm_client.stream_generate(prompt=prompt, system_prompt=SYSTEM_PROMPT)
            return chunks, sources, references, []
        except Exception as exc:
            fallback = self._fallback_answer(query_plan, evidence, total, sources, evidence_status)
            return iter([fallback]), sources, references, [f"llm_generation_failed: {exc}"]

    def _build_prompt(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        references: list[ReferenceSource],
        memory_context: MemoryContext | None = None,
        user_context: UserContext | None = None,
        evidence_status: str = "not_checked",
    ) -> str:
        if query_plan.answer_mode == "source_detail":
            prompt_name = "source_detail.md"
        elif evidence_status in {"grounded", "not_checked"} and evidence:
            prompt_name = "grounded_answer.md"
        else:
            prompt_name = "general_answer.md"
        return self._render_prompt(
            prompt_name,
            question=question,
            context_pack=self._format_context_pack(
                question, query_plan, evidence, references, memory_context, user_context
            ),
            route_contract=self._json(route_contract(query_plan, user_context, evidence_status)),
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
        evidence_status: str,
    ) -> str:
        if evidence_status in {"no_direct_evidence", "weak_evidence"} or not evidence:
            return (
                "当前知识库没有检索到足够相关资料，无法直接支撑本问题。以下只能提供一般性医学说明，不代表本地知识库证据。\n\n"
                f"问题理解：{self._intent_label(query_plan)}。\n"
                "当前回答生成服务没有正常返回，因此暂时无法给出完整回答。"
                "建议稍后重试，或检查 AGENT_LLM_BASE_URL、AGENT_LLM_API_KEY、AGENT_LLM_MODEL 配置。"
            )

        lines = [
            "根据当前知识库检索结果，先给出基于资料的初步回答：",
            "",
            f"问题理解：{self._intent_label(query_plan)}；共检索到 {total} 条相关资料，本次选取 {len(evidence)} 条作为参考。",
            "",
            "要点总结：",
        ]
        for index, item in enumerate(evidence[:3], start=1):
            lines.append(f"{index}. {self._summarize(item)} [{index}]")

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
                    index=index,
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

    def _build_memory_references(
        self,
        memory_context: MemoryContext | None,
        question: str,
    ) -> list[ReferenceSource]:
        if not memory_context:
            return []
        raw_references: list[dict[str, Any]] = []
        for message in reversed(memory_context.recent_messages):
            if message.role == "assistant" and message.references:
                raw_references = message.references
                break
        if not raw_references:
            raw_references = memory_context.referenced_sources

        requested_reference_index = MemoryResolver().citation_reference_index(question)
        if requested_reference_index is not None:
            raw_references = [
                reference
                for reference in raw_references
                if self._reference_index(reference) == requested_reference_index
            ]

        references: list[ReferenceSource] = []
        for index, ref in enumerate(raw_references[:8], start=1):
            references.append(
                ReferenceSource(
                    index=ref.get("index") or index,
                    source_type=ref.get("source_type") or "unknown",
                    title=ref.get("title") or "未命名来源",
                    file_uuid=ref.get("file_uuid"),
                    document_id=ref.get("document_id"),
                    dataset_id=ref.get("dataset_id"),
                    chunk_id=ref.get("chunk_id"),
                    snippet=self._shorten(ref.get("snippet"), 260) if ref.get("snippet") else None,
                )
            )
        return references

    def _reference_index(self, reference: dict[str, Any]) -> int | None:
        try:
            return int(reference.get("index"))
        except (TypeError, ValueError):
            return None

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

    def _format_context_pack(
        self,
        question: str,
        query_plan: QueryPlan,
        evidence: list[Evidence],
        references: list[ReferenceSource],
        memory_context: MemoryContext | None,
        user_context: UserContext | None,
    ) -> str:
        return format_context_pack(
            build_context_pack(
                question=question,
                memory_context=memory_context,
                user_context=user_context,
                query_plan=query_plan,
                evidence=evidence,
                references=references,
            )
        )

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


def sanitize_answer_text(text: str) -> str:
    """Remove internal notes and Markdown decoration before the answer is saved."""

    lines = []
    for line in str(text or "").splitlines():
        if "回答完毕" in line or "retrieval_evidence" in line or "evidence_status" in line:
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = cleaned.replace("***", "").replace("**", "")
    cleaned = re.sub(r"(?m)^\s*#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", cleaned)
    cleaned = re.sub(r"`([^`\n]+)`", r"\1", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

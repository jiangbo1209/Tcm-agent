"""KnowledgeRetrievalTool entry."""

from __future__ import annotations

from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence, RetrievalResult
from agent.routing_terms import MEDICAL_EVIDENCE_ANCHORS
from agent.tools.base import AgentTool
from agent.tools.retrieval.evidence_processor import EvidenceProcessor
from agent.tools.retrieval.ragflow_client import RagflowClient


class KnowledgeRetrievalTool(AgentTool[QueryPlan, RetrievalResult]):
    name = "knowledge_retrieval"

    def __init__(
        self,
        ragflow_client: RagflowClient | None = None,
        evidence_processor: EvidenceProcessor | None = None,
        default_top_k: int = 6,
    ) -> None:
        self._ragflow_client = ragflow_client or RagflowClient()
        self._evidence_processor = evidence_processor or EvidenceProcessor()
        self._default_top_k = default_top_k

    def run(self, payload: QueryPlan) -> RetrievalResult:
        if not payload.retrieval_required:
            return RetrievalResult(evidence=[], total=0, evidence_status="source_only")
        if payload.retrieval_strategy == "multi_query" and payload.sub_queries:
            return self._run_multi_query(payload)
        return self._run_single(payload)

    def _run_single(self, payload: QueryPlan) -> RetrievalResult:
        try:
            raw_items, total = self._ragflow_client.search(payload)
        except Exception as exc:
            return RetrievalResult(
                evidence=[],
                total=0,
                evidence_status="no_direct_evidence",
                warnings=[f"知识库检索失败：{exc}"],
            )

        evidence = self._evidence_processor.process(raw_items, max_items=payload.top_k or self._default_top_k)
        return RetrievalResult(
            evidence=evidence,
            total=total,
            evidence_status=self._evidence_status(payload, evidence),
        )

    def _run_multi_query(self, payload: QueryPlan) -> RetrievalResult:
        max_items = min(20, max(payload.top_k or self._default_top_k, len(payload.sub_queries) * 2))
        merged: dict[str, object] = {}
        total = 0
        warnings: list[str] = []

        for sub_query in payload.sub_queries:
            sub_plan = payload.model_copy(
                update={
                    "rewritten_query": sub_query,
                    "retrieval_strategy": "single_query",
                    "sub_queries": [],
                    "top_k": max_items,
                }
            )
            result = self._run_single(sub_plan)
            total += result.total
            warnings.extend(result.warnings)
            for item in result.evidence:
                key = item.file_uuid or item.chunk_id or f"{item.source_type}:{item.title}:{item.chunk}"
                current = merged.get(str(key))
                if current is None or (item.score or 0) > (current.score or 0):
                    merged[str(key)] = item

        evidence = sorted(
            merged.values(),
            key=lambda item: item.score or 0,
            reverse=True,
        )[:max_items]
        for index, item in enumerate(evidence, start=1):
            item.citation_index = index
        return RetrievalResult(
            evidence=list(evidence),
            total=total,
            evidence_status=self._evidence_status(payload, list(evidence)),
            warnings=list(dict.fromkeys(warnings)),
        )

    def _evidence_status(self, payload: QueryPlan, evidence: list[Evidence]) -> str:
        if not evidence:
            return "no_direct_evidence"

        query_text = " ".join([payload.rewritten_query, *payload.sub_queries]).lower()
        anchors = self._medical_anchors(query_text)
        if not anchors:
            return "weak_evidence"

        for item in evidence:
            source_text = " ".join(
                [item.title, item.chunk or "", str(item.metadata.get("title") or "")]
            ).lower()
            if any(anchor in source_text for anchor in anchors):
                return "grounded"
        return "weak_evidence"

    def _medical_anchors(self, text: str) -> set[str]:
        return {term.lower() for term in MEDICAL_EVIDENCE_ANCHORS if term.lower() in text}

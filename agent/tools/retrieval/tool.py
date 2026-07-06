"""KnowledgeRetrievalTool entry."""

from __future__ import annotations

from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import RetrievalResult
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
        try:
            raw_items, total = self._ragflow_client.search(payload)
        except Exception as exc:
            return RetrievalResult(evidence=[], total=0, warnings=[f"知识库检索失败：{exc}"])

        evidence = self._evidence_processor.process(raw_items, max_items=payload.top_k or self._default_top_k)
        return RetrievalResult(evidence=evidence, total=total)

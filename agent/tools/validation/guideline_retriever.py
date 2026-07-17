"""Guideline retrieval module."""

from __future__ import annotations

from agent.config import get_agent_settings
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence
from agent.tools.retrieval.evidence_processor import EvidenceProcessor
from agent.tools.retrieval.ragflow_client import RagflowClient


class GuidelineRetriever:
    """Retrieve guideline evidence from the RAGFlow guideline dataset."""

    def __init__(
        self,
        ragflow_client: RagflowClient | None = None,
        evidence_processor: EvidenceProcessor | None = None,
        top_k: int | None = None,
    ) -> None:
        self._ragflow_client = ragflow_client or RagflowClient()
        self._evidence_processor = evidence_processor or EvidenceProcessor()
        self._top_k = top_k or get_agent_settings().default_top_k

    def retrieve(self, question: str, answer: str | None = None) -> list[Evidence]:
        query = self._build_guideline_query(question, answer)
        query_plan = QueryPlan(
            intent="guideline_validation_question",
            source_type="guideline",
            rewritten_query=query,
            search_type="guideline",
            top_k=self._top_k,
        )
        raw_items, _ = self._ragflow_client.search(query_plan)
        return self._evidence_processor.process(raw_items, max_items=self._top_k)

    def _build_guideline_query(self, question: str, answer: str | None) -> str:
        normalized_question = " ".join(question.strip().split())
        if not answer:
            return normalized_question

        normalized_answer = " ".join(answer.strip().split())
        if len(normalized_answer) > 500:
            normalized_answer = normalized_answer[:500]
        return f"{normalized_question}\n{normalized_answer}"

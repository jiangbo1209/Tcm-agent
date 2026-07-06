"""Dependency factories for the Agent package."""

from __future__ import annotations

from agent.analyzers.query_analyzer import QueryAnalyzer
from agent.config import get_agent_settings
from agent.orchestrator.agent import MedicalAgent
from agent.orchestrator.response_builder import ResponseBuilder
from agent.services.answer_generator import AnswerGenerator
from agent.tools.retrieval.evidence_processor import EvidenceProcessor
from agent.tools.retrieval.tool import KnowledgeRetrievalTool
from agent.tools.validation.tool import GuidelineValidationTool


def build_agent() -> MedicalAgent:
    settings = get_agent_settings()
    retrieval_tool = KnowledgeRetrievalTool(
        evidence_processor=EvidenceProcessor(),
        default_top_k=settings.default_top_k,
    )
    validation_tool = GuidelineValidationTool(enabled=settings.enable_guideline_validation)
    return MedicalAgent(
        query_analyzer=QueryAnalyzer(default_top_k=settings.default_top_k),
        retrieval_tool=retrieval_tool,
        answer_generator=AnswerGenerator(),
        validation_tool=validation_tool,
        response_builder=ResponseBuilder(),
    )


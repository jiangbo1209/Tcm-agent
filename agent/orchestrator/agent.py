"""Agent core workflow entry."""

from __future__ import annotations

from agent.analyzers.query_analyzer import QueryAnalyzer
from agent.orchestrator.response_builder import ResponseBuilder
from agent.schemas.chat import ChatRequest, ChatResponse
from agent.services.answer_generator import AnswerGenerator
from agent.tools.retrieval.tool import KnowledgeRetrievalTool
from agent.tools.validation.tool import GuidelineValidationTool


class MedicalAgent:
    """Question understanding -> retrieval -> answer -> validation -> response."""

    def __init__(
        self,
        query_analyzer: QueryAnalyzer,
        retrieval_tool: KnowledgeRetrievalTool,
        answer_generator: AnswerGenerator,
        validation_tool: GuidelineValidationTool,
        response_builder: ResponseBuilder,
    ) -> None:
        self._query_analyzer = query_analyzer
        self._retrieval_tool = retrieval_tool
        self._answer_generator = answer_generator
        self._validation_tool = validation_tool
        self._response_builder = response_builder

    def run(self, request: ChatRequest) -> ChatResponse:
        question = " ".join(request.question.strip().split())
        if not question:
            raise ValueError("问题不能为空")

        query_plan = self._query_analyzer.analyze(question, top_k=request.top_k)
        retrieval_result = self._retrieval_tool.run(query_plan)
        answer_result = self._answer_generator.generate(
            question=question,
            query_plan=query_plan,
            evidence=retrieval_result.evidence,
            total=retrieval_result.total,
        )
        validation_result = self._validation_tool.run(
            question=question,
            answer=answer_result.answer,
            evidence=retrieval_result.evidence,
        )

        return self._response_builder.build(
            query_plan=query_plan,
            retrieval_result=retrieval_result,
            answer_result=answer_result,
            validation_result=validation_result,
        )


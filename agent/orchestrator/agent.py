"""Agent core workflow entry."""

from __future__ import annotations

from collections.abc import Iterable

from agent.analyzers.query_analyzer import QueryAnalyzer
from agent.orchestrator.response_builder import ResponseBuilder
from agent.schemas.answer import AnswerResult
from agent.schemas.chat import ChatRequest
from agent.schemas.stream import StreamEvent
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

    def run_stream(self, request: ChatRequest) -> Iterable[StreamEvent]:
        question = self._normalize_question(request.question)
        yield StreamEvent(event="started", data={"question": question})

        query_plan = self._query_analyzer.analyze(
            question,
            top_k=request.top_k,
            memory_context=request.memory_context,
            user_context=request.user_context,
        )
        yield StreamEvent(event="query_plan", data=query_plan.model_dump(mode="json"))

        retrieval_result = self._retrieval_tool.run(query_plan)
        chunks, sources, references, answer_warnings = self._answer_generator.stream_generate(
            question=question,
            query_plan=query_plan,
            evidence=retrieval_result.evidence,
            total=retrieval_result.total,
            memory_context=request.memory_context,
            user_context=request.user_context,
            evidence_status=retrieval_result.evidence_status,
        )
        yield StreamEvent(
            event="retrieval_done",
            data={
                "total": retrieval_result.total,
                "evidence_status": retrieval_result.evidence_status,
                "references": [item.model_dump(mode="json") for item in references],
                "warnings": retrieval_result.warnings,
            },
        )

        answer_parts: list[str] = []
        try:
            for chunk in chunks:
                if not chunk:
                    continue
                answer_parts.append(chunk)
                yield StreamEvent(event="answer_delta", data={"content": chunk})
        except Exception as exc:
            answer_warnings.append(f"llm_stream_failed: {exc}")
            yield StreamEvent(event="error", data={"phase": "llm", "message": str(exc)})

        answer = "".join(answer_parts)
        answer_result = AnswerResult(
            answer=answer,
            warnings=answer_warnings,
            sources=sources,
            references=references,
        )
        yield StreamEvent(event="answer_done", data={"answer": answer})

        validation_result = self._validation_tool.run(
            question=question,
            answer=answer_result.answer,
            evidence=retrieval_result.evidence,
            evidence_status=retrieval_result.evidence_status,
        )
        if getattr(self._validation_tool, "enabled", True):
            yield StreamEvent(event="validation_done", data=validation_result.model_dump(mode="json"))

        response = self._response_builder.build(
            query_plan=query_plan,
            retrieval_result=retrieval_result,
            answer_result=answer_result,
            validation_result=validation_result,
        )
        yield StreamEvent(event="done", data=response.model_dump(mode="json"))

    def _normalize_question(self, question: str) -> str:
        normalized = " ".join(question.strip().split())
        if not normalized:
            raise ValueError("问题不能为空")
        return normalized

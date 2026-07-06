"""Final response assembly."""

from __future__ import annotations

from agent.schemas.answer import AnswerResult
from agent.schemas.chat import ChatResponse
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import RetrievalResult
from agent.schemas.validation import ValidationResult


class ResponseBuilder:
    def build(
        self,
        query_plan: QueryPlan,
        retrieval_result: RetrievalResult,
        answer_result: AnswerResult,
        validation_result: ValidationResult,
    ) -> ChatResponse:
        warnings = [
            *retrieval_result.warnings,
            *answer_result.warnings,
            *validation_result.issues,
        ]
        return ChatResponse(
            answer=answer_result.answer,
            query_plan=query_plan,
            evidence=retrieval_result.evidence,
            references=answer_result.references,
            total=retrieval_result.total,
            answer_result=answer_result,
            validation=validation_result,
            warnings=warnings,
        )

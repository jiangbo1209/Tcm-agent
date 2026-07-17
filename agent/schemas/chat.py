"""Chat request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent.schemas.answer import AnswerResult
from agent.memory.schemas import MemoryContext, UserContext
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import Evidence, ReferenceSource
from agent.schemas.validation import ValidationResult


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    user_id: int | None = None
    conversation_id: int | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    memory_context: MemoryContext | None = None
    user_context: UserContext = Field(default_factory=UserContext)


class ChatResponse(BaseModel):
    answer: str
    query_plan: QueryPlan
    evidence: list[Evidence]
    references: list[ReferenceSource] = Field(default_factory=list)
    total: int
    evidence_status: str = "not_checked"
    answer_result: AnswerResult
    validation: ValidationResult
    warnings: list[str] = Field(default_factory=list)

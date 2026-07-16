"""Answer generation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agent.schemas.retrieval import ReferenceSource


class AnswerResult(BaseModel):
    answer: str
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    references: list[ReferenceSource] = Field(default_factory=list)

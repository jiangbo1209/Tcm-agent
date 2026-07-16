"""Memory data structures used by the Agent workflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MemoryMessage(BaseModel):
    role: str
    content: str
    references: list[dict[str, Any]] = Field(default_factory=list)


class MemoryContext(BaseModel):
    summary: str | None = None
    recent_messages: list[MemoryMessage] = Field(default_factory=list)
    referenced_sources: list[dict[str, Any]] = Field(default_factory=list)


class UserContext(BaseModel):
    """User role and response preferences used by context engineering."""

    active_role: str = "patient"
    technical_level: str = "standard"
    detail_level: str = "standard"
    response_style: str = "structured"
    evidence_preference: str = "show"


class ContextPlan(BaseModel):
    """Small routing decision describing which context is relevant this turn."""

    mode: str = "new_question"
    reason: str = ""
    use_case_context: bool = False
    use_citation_context: bool = False
    use_history: bool = False
    retrieval_required: bool = True
    query_plan: dict[str, Any] | None = None


class CaseContext(BaseModel):
    facts: dict[str, str] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class ContextPack(BaseModel):
    """The nine ordered context sections sent to query/answer prompts."""

    current_question: str
    context_plan: ContextPlan
    user_context: UserContext
    current_case: CaseContext
    retrieval_evidence: list[dict[str, Any]] = Field(default_factory=list)
    citation_context: dict[str, Any] = Field(default_factory=dict)
    relevant_history: list[dict[str, Any]] = Field(default_factory=list)
    answer_constraints: dict[str, Any] = Field(default_factory=dict)
    medical_safety: list[str] = Field(default_factory=list)

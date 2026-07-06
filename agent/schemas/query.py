"""Question understanding schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryPlan(BaseModel):
    intent: str
    source_type: str | None = None
    rewritten_query: str
    search_type: str
    top_k: int = Field(default=6, ge=1, le=20)
    filters: dict[str, list[str]] = Field(default_factory=dict)

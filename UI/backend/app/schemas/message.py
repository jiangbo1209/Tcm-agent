"""Pydantic schemas for message."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str
    user_context: dict[str, Any] | None = None


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime
    intent: str | None = None
    retrieval_query: str | None = None
    retrieval_used: bool = False
    retrieval_total: int | None = None
    query_plan: dict[str, Any] | None = None
    references: list[dict[str, Any]] | None = None
    validation_result: dict[str, Any] | None = None
    warnings: list[str] | None = None

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int

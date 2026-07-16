"""Medical guideline validation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    grounded: bool = True
    message: str = "回答基于知识库检索结果生成。"
    issues: list[str] = Field(default_factory=list)

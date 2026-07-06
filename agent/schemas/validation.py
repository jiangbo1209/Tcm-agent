"""Medical guideline validation schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    passed: bool = True
    risk_level: str = "low"
    issues: list[str] = Field(default_factory=list)
    suggested_revision: str = ""

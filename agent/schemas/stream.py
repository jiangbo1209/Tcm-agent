"""SSE stream event schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)

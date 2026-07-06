"""SSE stream event schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StreamEvent(BaseModel):
    event: str
    data: dict[str, Any] = {}


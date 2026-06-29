"""Result schemas for guideline metadata synchronization."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GuidelineSyncItem(BaseModel):
    file_uuid: str
    original_name: str
    success: bool
    error: str | None = None


class GuidelineSyncSummary(BaseModel):
    total: int = 0
    synced: int = 0
    failed: int = 0
    results: list[GuidelineSyncItem] = Field(default_factory=list)

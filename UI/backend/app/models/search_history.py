"""Search history ORM model."""

from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base
from enum import Enum

class SearchBackendMode(str, Enum):
    """Search strategy modes.

    auto: Prefer FULLTEXT when indexes are ready, fallback to LIKE.
    fulltext: Force FULLTEXT strategy first; fallback to LIKE on SQL errors.
    like: Always use LIKE strategy.
    """

    AUTO = "auto"
    FULLTEXT = "fulltext"
    LIKE = "like"

class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    search_type: Mapped[str] = mapped_column(String(20), nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

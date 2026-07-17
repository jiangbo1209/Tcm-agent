"""Database access for conversation memory."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.memory.models import ACTIVE, SESSION_SUMMARY


class MemoryMessageRow(Protocol):
    id: int
    role: str
    content: str
    references: list[dict[str, Any]] | None


class MemorySummaryRow(Protocol):
    content: str
    referenced_sources_summary: list[dict[str, Any]] | None
    covered_message_id: int | None


class ConversationMemoryRepository:
    """Reads memory data from UI backend ORM models without owning them."""

    def __init__(self, db: Session, message_model: Any, memory_model: Any) -> None:
        self._db = db
        self._message_model = message_model
        self._memory_model = memory_model

    def get_active_summary(self, conversation_id: int) -> str | None:
        row = self.get_active_summary_record(conversation_id)
        return row.content if row else None

    def get_active_summary_record(self, conversation_id: int) -> MemorySummaryRow | None:
        model = self._memory_model
        row = (
            self._db.query(model)
            .filter(
                model.conversation_id == conversation_id,
                model.memory_type == SESSION_SUMMARY,
                model.status == ACTIVE,
            )
            .order_by(model.updated_at.desc())
            .first()
        )
        return row

    def get_recent_messages(self, conversation_id: int, limit: int) -> list[MemoryMessageRow]:
        model = self._message_model
        rows = (
            self._db.query(model)
            .filter(model.conversation_id == conversation_id)
            .order_by(model.created_at.desc(), model.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(rows))

    def get_messages_outside_recent_window(
        self,
        conversation_id: int,
        recent_message_limit: int,
        after_message_id: int = 0,
    ) -> list[MemoryMessageRow]:
        """Return newly archived messages while keeping the latest window untouched."""

        model = self._message_model
        recent_ids = (
            self._db.query(model.id)
            .filter(model.conversation_id == conversation_id)
            .order_by(model.created_at.desc(), model.id.desc())
            .limit(recent_message_limit)
            .subquery()
        )
        rows = (
            self._db.query(model)
            .filter(
                model.conversation_id == conversation_id,
                model.id > after_message_id,
                model.id.not_in(select(recent_ids.c.id)),
            )
            .order_by(model.created_at.asc(), model.id.asc())
            .all()
        )
        return rows

    def save_active_summary(
        self,
        conversation_id: int,
        content: str,
        referenced_sources_summary: list[dict[str, Any]],
        covered_message_id: int,
    ) -> None:
        row = self.get_active_summary_record(conversation_id)
        if row:
            row.content = content
            row.referenced_sources_summary = referenced_sources_summary
            row.covered_message_id = covered_message_id
            return

        self._db.add(
            self._memory_model(
                conversation_id=conversation_id,
                memory_type=SESSION_SUMMARY,
                content=content,
                referenced_sources_summary=referenced_sources_summary,
                status=ACTIVE,
                covered_message_id=covered_message_id,
            )
        )

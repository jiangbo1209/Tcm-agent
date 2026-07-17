"""Adapter from UI backend ORM models to the Agent memory package."""

from __future__ import annotations

from sqlalchemy.orm import Session

from agent.config import get_agent_settings
from agent.memory.repository import ConversationMemoryRepository
from agent.memory.service import MemoryService
from app.models.conversation_memory import ConversationMemory
from app.models.message import Message


class AgentMemoryAdapter:
    def __init__(self, db: Session, recent_message_limit: int | None = None) -> None:
        settings = get_agent_settings()
        repository = ConversationMemoryRepository(
            db=db,
            message_model=Message,
            memory_model=ConversationMemory,
        )
        self._memory_service = MemoryService(
            repository=repository,
            recent_message_limit=recent_message_limit or settings.memory_recent_message_limit,
        )

    def build_context(self, conversation_id: int) -> dict:
        return self._memory_service.build_context(conversation_id).model_dump(mode="json")

    def refresh_summary(self, conversation_id: int) -> bool:
        return self._memory_service.refresh_summary(conversation_id)

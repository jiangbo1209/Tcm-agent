"""Memory service entry point."""

from __future__ import annotations

from agent.memory.context_builder import MemoryContextBuilder
from agent.memory.repository import ConversationMemoryRepository, MemorySummaryRow
from agent.memory.schemas import MemoryContext
from agent.memory.summary_service import MemorySummaryService


class MemoryService:
    def __init__(
        self,
        repository: ConversationMemoryRepository,
        context_builder: MemoryContextBuilder | None = None,
        summary_service: MemorySummaryService | None = None,
        recent_message_limit: int = 8,
    ) -> None:
        self._repository = repository
        self._context_builder = context_builder or MemoryContextBuilder()
        self._summary_service = summary_service or MemorySummaryService()
        self._recent_message_limit = recent_message_limit

    def build_context(self, conversation_id: int) -> MemoryContext:
        summary_record = self._repository.get_active_summary_record(conversation_id)
        messages = self._repository.get_recent_messages(
            conversation_id=conversation_id,
            limit=self._recent_message_limit,
        )
        context = self._context_builder.build(
            summary=summary_record.content if summary_record else None,
            recent_messages=messages,
        )
        if summary_record:
            context.referenced_sources = self._merge_references(
                summary_record.referenced_sources_summary or [],
                context.referenced_sources,
            )
        return context

    def refresh_summary(self, conversation_id: int) -> bool:
        """Archive messages outside the short-term window into one rolling summary."""

        summary_record = self._repository.get_active_summary_record(conversation_id)
        covered_message_id = self._covered_message_id(summary_record)
        archived_rows = self._repository.get_messages_outside_recent_window(
            conversation_id=conversation_id,
            recent_message_limit=self._recent_message_limit,
            after_message_id=covered_message_id,
        )
        if not archived_rows:
            return False

        archived_context = self._context_builder.build(summary=None, recent_messages=archived_rows)
        summary = self._summary_service.summarize(
            summary_record.content if summary_record else None,
            archived_context.recent_messages,
        )
        references = self._merge_references(
            summary_record.referenced_sources_summary if summary_record else [],
            archived_context.referenced_sources,
        )
        self._repository.save_active_summary(
            conversation_id=conversation_id,
            content=summary,
            referenced_sources_summary=references,
            covered_message_id=archived_rows[-1].id,
        )
        return True

    @staticmethod
    def _covered_message_id(summary_record: MemorySummaryRow | None) -> int:
        if not summary_record or summary_record.covered_message_id is None:
            return 0
        return summary_record.covered_message_id

    @staticmethod
    def _merge_references(
        previous: list[dict] | None,
        current: list[dict] | None,
        limit: int = 12,
    ) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for reference in [*(current or []), *(previous or [])]:
            key = str(
                reference.get("file_uuid")
                or reference.get("document_id")
                or reference.get("title")
                or ""
            )
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(reference)
            if len(merged) >= limit:
                break
        return merged

"""Build compact memory context for query analysis and answer generation."""

from __future__ import annotations

from typing import Any, Iterable

from agent.memory.schemas import MemoryContext, MemoryMessage
from agent.memory.repository import MemoryMessageRow


class MemoryContextBuilder:
    def build(
        self,
        *,
        summary: str | None,
        recent_messages: Iterable[MemoryMessageRow],
    ) -> MemoryContext:
        messages = [self._message_from_row(row) for row in recent_messages]
        return MemoryContext(
            summary=summary,
            recent_messages=messages,
            referenced_sources=self._collect_referenced_sources(messages),
        )

    def _message_from_row(self, row: MemoryMessageRow) -> MemoryMessage:
        return MemoryMessage(
            role=row.role,
            content=self._shorten(row.content, 900),
            references=self._reference_summary(row.references or []),
        )

    def _collect_referenced_sources(self, messages: list[MemoryMessage]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for message in reversed(messages):
            for ref in message.references:
                key = str(ref.get("file_uuid") or ref.get("document_id") or ref.get("title") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(ref)
                if len(collected) >= 8:
                    return collected
        return collected

    def _reference_summary(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summary: list[dict[str, Any]] = []
        for ref in references[:6]:
            summary.append(
                {
                    "index": ref.get("index"),
                    "source_type": ref.get("source_type"),
                    "title": self._shorten(ref.get("title"), 160),
                    "file_uuid": ref.get("file_uuid"),
                    "document_id": ref.get("document_id"),
                    "snippet": self._shorten(ref.get("snippet"), 220),
                }
            )
        return summary

    def _shorten(self, value: Any, max_len: int) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= max_len else f"{text[:max_len].rstrip()}..."

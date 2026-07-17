"""Rolling conversation summary generation for long-running sessions."""

from __future__ import annotations

import json
from pathlib import Path

from agent.config import get_agent_settings
from agent.memory.schemas import MemoryMessage
from agent.services.llm_client import LLMClient


PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class MemorySummaryService:
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        max_summary_chars: int | None = None,
    ) -> None:
        settings = get_agent_settings()
        self._llm_client = llm_client or LLMClient(settings)
        self._max_summary_chars = max_summary_chars or settings.memory_summary_max_chars

    def summarize(
        self,
        previous_summary: str | None,
        archived_messages: list[MemoryMessage],
    ) -> str:
        if not archived_messages:
            return self._shorten(previous_summary or "", self._max_summary_chars)

        prompt = self._render_prompt(
            previous_summary=self._shorten(previous_summary or "无", self._max_summary_chars),
            archived_messages=json.dumps(
                [self._message_payload(message) for message in archived_messages],
                ensure_ascii=False,
                indent=2,
            ),
        )
        try:
            summary = self._llm_client.generate(
                prompt=prompt,
                system_prompt="你是医疗会话记忆压缩模块，只输出可直接进入后续上下文的中文摘要。",
            )
            return self._shorten(summary, self._max_summary_chars)
        except Exception:
            return self._fallback_summary(previous_summary, archived_messages)

    def _render_prompt(self, **values: str) -> str:
        template = (PROMPT_DIR / "memory_summary.md").read_text(encoding="utf-8")
        for key, value in values.items():
            template = template.replace(f"{{{{{key}}}}}", value)
        return template

    def _message_payload(self, message: MemoryMessage) -> dict[str, object]:
        return {
            "role": message.role,
            "content": self._shorten(message.content, 1200),
            "references": message.references[:3],
        }

    def _fallback_summary(
        self,
        previous_summary: str | None,
        archived_messages: list[MemoryMessage],
    ) -> str:
        parts = [previous_summary] if previous_summary else []
        for message in archived_messages:
            role = "用户" if message.role == "user" else "助手"
            parts.append(f"{role}：{self._shorten(message.content, 500)}")
        return self._shorten("\n".join(part for part in parts if part), self._max_summary_chars)

    @staticmethod
    def _shorten(value: str, max_len: int) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= max_len else f"{text[:max_len].rstrip()}..."

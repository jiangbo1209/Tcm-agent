"""Format memory context for prompts and retrieval rewrite hints."""

from __future__ import annotations

import json
from typing import Any

from agent.memory.context_engine import ContextEngine
from agent.memory.schemas import ContextPack, MemoryContext, UserContext


def build_context_pack(
    *,
    question: str,
    memory_context: MemoryContext | None = None,
    user_context: UserContext | dict[str, Any] | None = None,
    query_plan: Any | None = None,
    evidence: list[Any] | None = None,
    references: list[Any] | None = None,
) -> ContextPack:
    return ContextEngine().build(
        question=question,
        memory_context=memory_context,
        user_context=user_context,
        query_plan=query_plan,
        evidence=evidence,
        references=references,
    )


def format_context_pack(context_pack: ContextPack) -> str:
    return json.dumps(context_pack.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str)


def resolution_hints(memory_context: MemoryContext, max_len: int = 900) -> str:
    parts: list[str] = []
    if memory_context.summary:
        parts.append(f"会话摘要：{memory_context.summary}")

    parts.extend(citation_hints(memory_context))

    for message in memory_context.recent_messages[-4:]:
        if message.role == "user" and message.content:
            parts.append(f"用户前文：{message.content}")
    return "；".join(_shorten(item, 140) for item in parts if item)[:max_len]


def citation_hints(memory_context: MemoryContext) -> list[str]:
    hints: list[str] = []
    seen: set[str] = set()

    for message in reversed(memory_context.recent_messages):
        if message.role != "assistant":
            continue
        for ref in message.references:
            hint = _format_reference(ref)
            key = str(ref.get("index") or "") + "|" + str(ref.get("file_uuid") or ref.get("document_id") or ref.get("title") or "")
            if hint and key not in seen:
                seen.add(key)
                hints.append(hint)
        if hints:
            break

    if not hints:
        for ref in memory_context.referenced_sources[:6]:
            hint = _format_reference(ref)
            key = str(ref.get("file_uuid") or ref.get("document_id") or ref.get("title") or "")
            if hint and key not in seen:
                seen.add(key)
                hints.append(hint)
    return hints[:6]


def _format_reference(ref: dict[str, Any]) -> str:
    index = ref.get("index")
    title = ref.get("title")
    source_type = ref.get("source_type") or "来源"
    snippet = ref.get("snippet")
    if not title and not snippet:
        return ""
    label = f"引用[{index}]" if index is not None else "引用来源"
    parts = [f"{label}={source_type}：{title or ''}".strip()]
    if snippet:
        parts.append(f"片段：{_shorten(snippet, 180)}")
    return "，".join(parts)


def _shorten(value: Any, max_len: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= max_len else f"{text[:max_len].rstrip()}..."

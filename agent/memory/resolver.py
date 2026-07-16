"""Resolve contextual follow-up questions using conversation memory."""

from __future__ import annotations

import re

from agent.memory.prompt_context import resolution_hints
from agent.memory.schemas import MemoryContext
from agent.routing_terms import (
    DOMAIN_ANCHORS,
    FOLLOWUP_TERMS,
    SOURCE_ALL_SCOPE_TERMS,
    SOURCE_REFERENCE_TERMS,
)


class MemoryResolver:
    def citation_reference_index(self, question: str) -> int | None:
        """Return the reference number explicitly requested in a follow-up."""

        match = re.search(
            r"(?:依据|引用|来源|文献|角标)\s*(?:第\s*)?\[?\s*(\d+)\s*\]?(?:\s*(?:个|篇|条|项|号))?"
            r"|第\s*(\d+)\s*(?:个|篇|条|项|号|文献|来源|引用|依据)",
            question,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        value = next((item for item in match.groups() if item), None)
        return int(value) if value else None

    def all_citations_requested(self, question: str) -> bool:
        """Return whether a follow-up explicitly asks for all previous sources."""

        normalized = re.sub(r"\s+", "", question.lower())
        return any(term in normalized for term in SOURCE_REFERENCE_TERMS) and any(
            term in normalized for term in SOURCE_ALL_SCOPE_TERMS
        )

    def contextualize_query(self, question: str, memory_context: MemoryContext | None) -> str:
        text = re.sub(r"\s+", " ", question).strip()
        text = re.sub(r"[？?。！!]+$", "", text)
        if not memory_context or not self.needs_context(text):
            return text

        hints = resolution_hints(memory_context)
        if not hints:
            return text
        return f"{text} 上下文：{hints}"

    def needs_context(self, question: str) -> bool:
        normalized = question.strip().lower()
        if not normalized:
            return False
        if self._has_numbered_reference(normalized):
            return True
        if any(term in normalized for term in FOLLOWUP_TERMS):
            return True
        if len(normalized) <= 18 and (not self._has_domain_anchor(normalized) or self._has_followup_tone(normalized)):
            return True
        if len(normalized) <= 30 and not self._has_domain_anchor(normalized):
            return True
        return False

    def _has_numbered_reference(self, question: str) -> bool:
        return bool(
            re.search(
                r"(\[\s*\d+\s*\]|依据\s*\d+|引用\s*\d+|来源\s*\d+|文献\s*\d+|第\s*\d+\s*(个|条|篇|则)?)",
                question,
            )
        )

    def _has_domain_anchor(self, question: str) -> bool:
        return any(anchor in question for anchor in DOMAIN_ANCHORS)

    def _has_followup_tone(self, question: str) -> bool:
        return question.endswith(("呢", "吗", "么")) or any(term in question for term in ("怎么", "如何", "为什么"))

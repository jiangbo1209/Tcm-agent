"""Adapter between the UI backend chat API and the core Agent workflow."""

from __future__ import annotations

from pathlib import Path
import sys
from collections.abc import Iterable
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[4]
project_root_text = str(PROJECT_ROOT)
if project_root_text not in sys.path:
    sys.path.insert(0, project_root_text)

from agent.dependencies import build_agent  # noqa: E402
from agent.schemas.chat import ChatRequest  # noqa: E402
from agent.schemas.stream import StreamEvent  # noqa: E402


class AgentChatService:
    """Runs the core Agent and returns its stream events."""

    def stream(
        self,
        *,
        question: str,
        user_id: int,
        conversation_id: int,
        top_k: int | None = None,
        memory_context: dict[str, Any] | None = None,
        user_context: dict[str, Any] | None = None,
    ) -> Iterable[StreamEvent]:
        request = ChatRequest(
            question=question,
            user_id=user_id,
            conversation_id=conversation_id,
            top_k=top_k,
            memory_context=memory_context,
            user_context=user_context,
        )
        return build_agent().run_stream(request)

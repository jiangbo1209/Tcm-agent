"""SSE stream service."""

from __future__ import annotations

import json
from collections.abc import Iterable

from agent.schemas.stream import StreamEvent


class StreamService:
    def encode(self, events: Iterable[StreamEvent]) -> Iterable[str]:
        for event in events:
            payload = json.dumps(event.model_dump(), ensure_ascii=False)
            yield f"data: {payload}\n\n"


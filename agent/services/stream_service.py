"""SSE stream service."""

from __future__ import annotations

import json
from collections.abc import Iterable

from agent.schemas.stream import StreamEvent


class StreamService:
    def encode(self, events: Iterable[StreamEvent]) -> Iterable[str]:
        for event in events:
            payload = json.dumps(event.data, ensure_ascii=False)
            yield f"event: {event.event}\ndata: {payload}\n\n"

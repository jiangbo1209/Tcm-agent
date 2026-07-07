"""Chat routes for the standalone Agent service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent.dependencies import build_agent
from agent.schemas.chat import ChatRequest, ChatResponse
from agent.services.stream_service import StreamService

router = APIRouter(prefix="/api/agent", tags=["agent-chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    try:
        return build_agent().run(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat/stream")
def chat_stream(body: ChatRequest):
    try:
        events = build_agent().run_stream(body)
        return StreamingResponse(
            StreamService().encode(events),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

"""Chat routes for the standalone Agent service."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent.dependencies import build_agent
from agent.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/agent", tags=["agent-chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    try:
        return build_agent().run(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


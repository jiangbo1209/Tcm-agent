"""Agent service startup entry."""

from __future__ import annotations

from fastapi import FastAPI

from agent.api.routes_chat import router as chat_router

app = FastAPI(title="TCM Medical Agent", version="0.1.0")
app.include_router(chat_router)


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


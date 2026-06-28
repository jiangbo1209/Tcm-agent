"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(ROOT_DIR / ".env", override=False)

from app.auth.router import router as auth_router
from app.database import engine
from app.models.base import Base
from app.routers.chat import router as chat_router
from app.routers.graph import router as graph_router
from app.routers.history import router as history_router
from app.routers.search import router as search_router

Base.metadata.create_all(bind=engine)

from app.config import get_database_config, get_minio_config, get_search_config
from app.core.minio_utils import MinioClient
from app.repositories.graph_repository import GraphRepository
from app.services.graph_service import GraphService

app = FastAPI(title="TCM Agent API", version="2.0.0")


def _build_minio_client() -> MinioClient | None:
    config = get_minio_config()
    if not config.access_key or not config.secret_key:
        logging.warning("MinIO credentials are missing; file URL APIs will be unavailable")
        return None
    try:
        return MinioClient(config)
    except Exception:
        logging.exception("Failed to initialize MinIO client")
        return None


repository = GraphRepository(get_database_config(), get_search_config())
app.state.graph_service = GraphService(repository, _build_minio_client())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(search_router)
app.include_router(history_router)
app.include_router(graph_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.api.routes_graph import router as graph_router
from app.config import get_database_config, get_minio_config, get_search_config
from app.core.minio_utils import MinioClient
from app.repositories.graph_repository import GraphRepository
from app.services.graph_service import GraphService

logging.basicConfig(level=logging.INFO)

ROOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(ROOT_DIR / ".env", override=False)

app = FastAPI(title="TCM Graph API", version="1.0.0")


def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8080,http://localhost:8080")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

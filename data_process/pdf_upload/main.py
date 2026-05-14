"""FastAPI application entrypoint for the data-process service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .dependencies import dispose_engine, ensure_tables, init_dependencies

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_dependencies()
    await ensure_tables()
    yield
    # Shutdown
    await dispose_engine()


app = FastAPI(
    title="TCM Data Process API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "data_process.pdf_upload.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )

"""Graph API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from minio.error import S3Error
from psycopg2 import Error

from app.schemas.graph import (
    FileUrlResponse,
    GraphExpandResponse,
    NodeDetailResponse,
    SearchIndexStatusResponse,
    SearchResponse,
)
from app.services.graph_service import GraphService

LOGGER = logging.getLogger("graph_api")

router = APIRouter(prefix="/api/graph", tags=["graph"])


def _get_service(request: Request) -> GraphService:
    return request.app.state.graph_service


@router.get("/expand", response_model=GraphExpandResponse)
def get_graph_expand(
    request: Request,
    seed_id: str = Query(..., description="Center node id for BFS expansion"),
    limit: str | None = Query(None, description="Requested top-k edge count, [10, 20]"),
    depth: str | None = Query("1", description="BFS depth, [1, 3]"),
):
    normalized_seed = seed_id.strip()
    if not normalized_seed:
        raise HTTPException(status_code=400, detail="seed_id is required")

    service = _get_service(request)
    try:
        effective_limit = service.clamp_limit(limit)
        effective_depth = service.clamp_depth(depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="limit/depth must be integer") from exc

    try:
        return service.expand_graph(normalized_seed, effective_limit, effective_depth)
    except Error as exc:
        LOGGER.exception("Failed to expand graph for seed_id=%s", normalized_seed)
        raise HTTPException(status_code=500, detail="database query failed") from exc


@router.get("/node-detail", response_model=NodeDetailResponse)
def get_graph_node_detail(
    request: Request,
    node_id: str = Query(..., description="Selected node id for detail panel"),
):
    normalized_node_id = node_id.strip()
    if not normalized_node_id:
        raise HTTPException(status_code=400, detail="node_id is required")

    service = _get_service(request)
    try:
        payload = service.get_node_detail(normalized_node_id)
    except Error as exc:
        LOGGER.exception("Failed to query node detail for node_id=%s", normalized_node_id)
        raise HTTPException(status_code=500, detail="database query failed") from exc

    if not payload:
        raise HTTPException(status_code=404, detail="node not found")

    return payload


@router.get("/search", response_model=SearchResponse)
def search_graph(
    request: Request,
    q: str = Query(..., description="Search keyword"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=50, description="Page size"),
):
    service = _get_service(request)
    return service.search_graph(q, page, size)


@router.get("/search/index-status", response_model=SearchIndexStatusResponse)
def search_index_status(request: Request):
    service = _get_service(request)
    return service.get_search_index_status()


@router.get("/file-url/{node_id}", response_model=FileUrlResponse)
def get_graph_file_url(
    request: Request,
    node_id: str,
    mode: str = Query("view", description="view | download"),
):
    normalized_node_id = node_id.strip()
    if not normalized_node_id:
        raise HTTPException(status_code=400, detail="node_id is required")

    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"view", "download"}:
        raise HTTPException(status_code=400, detail="mode must be view or download")

    service = _get_service(request)
    try:
        return service.get_file_url(node_id=normalized_node_id, download=normalized_mode == "download")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except S3Error as exc:
        LOGGER.exception("Failed to generate MinIO presigned url for node_id=%s", normalized_node_id)
        raise HTTPException(status_code=502, detail=f"minio error: {exc.code}") from exc



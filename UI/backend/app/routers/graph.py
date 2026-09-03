"""Graph API routes (preserved from original, adapted to new structure)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.graph import (
    GraphExpandResponse,
    NodeDetailResponse,
    NodeSearchResponse,
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
    limit: int = Query(10, ge=10, le=20, description="Requested top-k edge count"),
    depth: int = Query(1, ge=1, le=3, description="BFS depth"),
):
    normalized_seed = seed_id.strip()
    if not normalized_seed:
        raise HTTPException(status_code=400, detail="seed_id is required")

    service = _get_service(request)
    try:
        return service.expand_graph(normalized_seed, limit, depth)
    except SQLAlchemyError as exc:
        LOGGER.exception("Failed to expand graph for seed_id=%s", normalized_seed)
        raise HTTPException(status_code=500, detail="database query failed") from exc


@router.get("/node-detail", response_model=NodeDetailResponse)
def get_graph_node_detail(
    request: Request,
    node_id: str = Query(None, description="Selected node id for detail panel"),
    file_uuid: str = Query(None, description="File UUID for direct detail lookup"),
    source_type: str = Query(None, description="Source type: paper | record"),
):
    normalized_node_id = (node_id or "").strip()
    normalized_file_uuid = (file_uuid or "").strip()
    normalized_source_type = (source_type or "").strip()

    if normalized_node_id:
        return _load_detail_by_node_id(request, normalized_node_id)
    if normalized_file_uuid and normalized_source_type in ("paper", "record"):
        return _load_detail_by_file_uuid(request, normalized_file_uuid, normalized_source_type)
    raise HTTPException(status_code=400, detail="node_id or (file_uuid + source_type) is required")


def _load_detail_by_node_id(request: Request, node_id: str):
    service = _get_service(request)
    try:
        payload = service.get_node_detail(node_id)
    except SQLAlchemyError as exc:
        LOGGER.exception("Failed to query node detail for node_id=%s", node_id)
        raise HTTPException(status_code=500, detail="database query failed") from exc
    if not payload:
        raise HTTPException(status_code=404, detail="node not found")
    return payload


def _load_detail_by_file_uuid(request: Request, file_uuid: str, source_type: str):
    service = _get_service(request)
    try:
        payload = service.get_detail_by_file_uuid(file_uuid, source_type)
    except SQLAlchemyError as exc:
        LOGGER.exception("Failed to query detail for file_uuid=%s type=%s", file_uuid, source_type)
        raise HTTPException(status_code=500, detail="database query failed") from exc
    if not payload:
        raise HTTPException(status_code=404, detail="detail not found")
    return payload


@router.get("/search", response_model=NodeSearchResponse)
def search_nodes(
    request: Request,
    q: str = Query(..., description="Search keyword"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=50, description="Page size"),
):
    rows = request.app.state.graph_repository.search_nodes(q, size)
    return NodeSearchResponse(items=rows, total=len(rows), page=page)

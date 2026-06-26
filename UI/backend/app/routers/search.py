"""Search routes: smart search and search history."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_professional
from app.database import get_db
from app.models.search_history import SearchHistory
from app.models.user import User
from app.repositories.graph_repository import GraphRepository
from app.schemas.search import (
    SearchHistoryResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_graph_repo() -> GraphRepository:
    from app.config import get_database_config, get_search_config

    return GraphRepository(get_database_config(), get_search_config())


@router.post("", response_model=SearchResponse)
def smart_search(
    body: SearchRequest,
    current_user: User = Depends(require_professional),
    db: Session = Depends(get_db),
):
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="搜索关键词不能为空")

    if body.search_type not in ("literature", "case", "both"):
        raise HTTPException(status_code=400, detail="search_type 必须为 literature、case 或 both")

    repo = _get_graph_repo()
    page = max(1, body.page)
    size = max(1, min(50, body.size))
    offset = (page - 1) * size

    items, total = repo.search_graph(query, size, offset)

    if body.search_type == "literature":
        items = [i for i in items if i.get("source_type") == "paper"]
    elif body.search_type == "case":
        items = [i for i in items if i.get("source_type") == "record"]

    result_items = []
    for item in items:
        result_items.append(
            SearchResultItem(
                source_type=item.get("source_type", ""),
                node_id=item.get("node_id"),
                title=item.get("title"),
                authors=item.get("authors"),
                publish_year=item.get("publish_year"),
                keywords=item.get("keywords"),
                abstract=item.get("abstract"),
                tcm_diagnosis=item.get("tcm_diagnosis"),
                western_diagnosis=item.get("western_diagnosis"),
                score=item.get("score"),
            )
        )

    total_filtered = len(result_items)
    total_pages = math.ceil(total_filtered / size) if size > 0 else 0

    history = SearchHistory(
        user_id=current_user.id,
        query=query,
        search_type=body.search_type,
        result_count=total_filtered,
    )
    db.add(history)
    db.commit()

    return SearchResponse(
        items=result_items,
        total=total_filtered,
        total_pages=total_pages,
        page=page,
        size=size,
    )


@router.get("/history", response_model=SearchHistoryResponse)
def get_search_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query_obj = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
    )
    total = query_obj.count()
    items = query_obj.offset((page - 1) * size).limit(size).all()
    return SearchHistoryResponse(items=items, total=total)

"""Search routes: smart search and search history."""

from __future__ import annotations

import math
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
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


def _format_list_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return "、".join(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return "、".join(str(item).strip() for item in parsed if str(item).strip()) or None
    return text or None


def _parse_year(value) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


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

    source_type = None
    if body.search_type == "literature":
        source_type = "paper"
    elif body.search_type == "case":
        source_type = "record"

    filters = body.filters.model_dump()
    items, total = repo.search_graph(query, size, offset, source_type=source_type, filters=filters)
    facets = repo.search_graph_facets(query, source_type=source_type, filters=filters)

    result_items = []
    for item in items:
        result_items.append(
            SearchResultItem(
                source_type=item.get("source_type", ""),
                node_id=item.get("node_id"),
                title=item.get("title"),
                authors=_format_list_text(item.get("authors")),
                publish_year=_parse_year(item.get("publish_year")),
                keywords=_format_list_text(item.get("keywords")),
                abstract=item.get("abstract"),
                tcm_diagnosis=item.get("tcm_diagnosis"),
                western_diagnosis=item.get("western_diagnosis"),
                score=item.get("score"),
            )
        )

    total_pages = math.ceil(total / size) if size > 0 else 0

    normalized_history_query = query.lower()
    history = (
        db.query(SearchHistory)
        .filter(
            SearchHistory.user_id == current_user.id,
            func.lower(SearchHistory.query) == normalized_history_query,
        )
        .order_by(SearchHistory.created_at.desc())
        .first()
    )
    if history:
        history.query = query
        history.search_type = body.search_type
        history.result_count = total
        history.created_at = func.now()
    else:
        history = SearchHistory(
            user_id=current_user.id,
            query=query,
            search_type=body.search_type,
            result_count=total,
        )
        db.add(history)
    db.commit()

    return SearchResponse(
        items=result_items,
        total=total,
        total_pages=total_pages,
        page=page,
        size=size,
        facets=facets,
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
    deduped = []
    seen_queries = set()
    for item in query_obj.all():
        key = item.query.strip().lower()
        if key in seen_queries:
            continue
        seen_queries.add(key)
        deduped.append(item)

    total = len(deduped)
    start = (page - 1) * size
    end = start + size
    return SearchHistoryResponse(items=deduped[start:end], total=total)

"""History routes: combined conversation and search history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.conversation import Conversation
from app.models.search_history import SearchHistory
from app.models.user import User

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def get_history(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
        .all()
    )
    conv_items = [
        {
            "type": "conversation",
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]

    search_items_raw = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(50)
        .all()
    )
    search_items = [
        {
            "type": "search",
            "id": s.id,
            "query": s.query,
            "search_type": s.search_type,
            "result_count": s.result_count,
            "created_at": s.created_at.isoformat(),
        }
        for s in search_items_raw
    ]

    all_items = conv_items + search_items
    all_items.sort(key=lambda x: x["created_at"], reverse=True)

    total = len(all_items)
    start = (page - 1) * size
    end = start + size
    paged = all_items[start:end]

    return {"items": paged, "total": total, "page": page, "size": size}

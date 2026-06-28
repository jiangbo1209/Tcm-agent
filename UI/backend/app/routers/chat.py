"""Chat routes: conversation CRUD and message streaming (placeholder)."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from UI.backend.app.core.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationListResponse, ConversationResponse
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return ConversationListResponse(items=items, total=len(items))


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def create_conversation(
    body: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = Conversation(user_id=current_user.id, title=body.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
def list_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    items = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return MessageListResponse(items=items, total=len(items))


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    user_msg = Message(conversation_id=conversation_id, role="user", content=body.content)
    db.add(user_msg)
    conv.updated_at = user_msg.created_at
    db.commit()

    def generate_sse():
        placeholder_reply = f"收到您的消息：「{body.content}」。Agent 对话功能即将上线，敬请期待。"
        for char in placeholder_reply:
            chunk = json.dumps({"content": char, "done": False}, ensure_ascii=False)
            yield f"data: {chunk}\n\n"
            time.sleep(0.03)
        done_chunk = json.dumps({"content": "", "done": True}, ensure_ascii=False)
        yield f"data: {done_chunk}\n\n"

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=placeholder_reply,
        )
        db.add(assistant_msg)
        db.commit()

    return StreamingResponse(generate_sse(), media_type="text/event-stream")


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()

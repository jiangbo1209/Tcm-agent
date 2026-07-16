"""Chat routes: conversation CRUD and Agent-backed message streaming."""

from __future__ import annotations

import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.models.agent_tool_run import AgentToolRun
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.conversation import ConversationCreate, ConversationListResponse, ConversationResponse
from app.schemas.message import MessageCreate, MessageListResponse, MessageResponse
from app.services.agent_chat_service import AgentChatService
from app.services.agent_memory_adapter import AgentMemoryAdapter

from agent.services.answer_generator import sanitize_answer_text

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _title_from_first_question(content: str, max_length: int = 40) -> str:
    title = " ".join((content or "").split())
    if not title:
        return "新对话"
    if len(title) <= max_length:
        return title
    return f"{title[:max_length].rstrip()}..."


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

    existing_message_count = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .count()
    )
    conversation_payload: dict | None = None
    if existing_message_count == 0 and conv.title == "新对话":
        conv.title = _title_from_first_question(body.content)
        db.flush()
        conversation_payload = ConversationResponse.model_validate(conv).model_dump(mode="json")

    memory_adapter = AgentMemoryAdapter(db)
    memory_context = memory_adapter.build_context(conversation_id)

    user_msg = Message(conversation_id=conversation_id, role="user", content=body.content)
    db.add(user_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()

    def generate_sse():
        answer_parts: list[str] = []
        final_payload: dict | None = None
        query_plan: dict | None = None
        retrieval_payload: dict | None = None
        validation_payload: dict | None = None
        warnings: list[str] = []
        tool_events: list[dict] = []
        started_at = time.perf_counter()

        def emit_event(name: str, payload: dict | None = None):
            chunk = json.dumps(
                {"event": name, "payload": payload or {}, "done": False},
                ensure_ascii=False,
            )
            return f"data: {chunk}\n\n"

        def compact_done_payload(payload: dict) -> dict:
            return {
                "answer": payload.get("answer"),
                "query_plan": payload.get("query_plan"),
                "references": payload.get("references") or [],
                "total": payload.get("total"),
                "evidence_status": payload.get("evidence_status") or "not_checked",
                "validation": payload.get("validation"),
                "warnings": payload.get("warnings") or [],
            }

        try:
            if conversation_payload:
                yield emit_event("conversation_updated", conversation_payload)

            events = AgentChatService().stream(
                question=body.content,
                user_id=current_user.id,
                conversation_id=conversation_id,
                memory_context=memory_context,
                user_context=_build_user_context(current_user.role, body.user_context),
            )
            for event in events:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                payload = event.data

                if event.event == "answer_delta":
                    content = str(event.data.get("content") or "")
                    if not content:
                        continue
                    answer_parts.append(content)
                    chunk = json.dumps(
                        {"content": content, "done": False},
                        ensure_ascii=False,
                    )
                    yield f"data: {chunk}\n\n"
                elif event.event == "started":
                    tool_events.append(
                        {
                            "tool_name": "agent_started",
                            "status": "success",
                            "input_payload": {"question": body.content},
                            "output_payload": payload,
                            "duration_ms": elapsed_ms,
                            "error_message": None,
                        }
                    )
                    yield emit_event("started", payload)
                elif event.event == "query_plan":
                    query_plan = payload
                    tool_events.append(
                        {
                            "tool_name": "query_analysis",
                            "status": "success",
                            "input_payload": {"question": body.content},
                            "output_payload": payload,
                            "duration_ms": elapsed_ms,
                            "error_message": None,
                        }
                    )
                    yield emit_event("query_plan", payload)
                elif event.event == "retrieval_done":
                    retrieval_payload = payload
                    warnings.extend(payload.get("warnings") or [])
                    tool_events.append(
                        {
                            "tool_name": "knowledge_retrieval",
                            "status": "success",
                            "input_payload": query_plan,
                            "output_payload": payload,
                            "duration_ms": elapsed_ms,
                            "error_message": None,
                        }
                    )
                    yield emit_event("retrieval_done", payload)
                elif event.event == "answer_done":
                    tool_events.append(
                        {
                            "tool_name": "answer_generation",
                            "status": "success",
                            "input_payload": {
                                "question": body.content,
                                "query_plan": query_plan,
                                "retrieval_total": (retrieval_payload or {}).get("total"),
                            },
                            "output_payload": payload,
                            "duration_ms": elapsed_ms,
                            "error_message": None,
                        }
                    )
                    yield emit_event("answer_done", payload)
                elif event.event == "validation_done":
                    validation_payload = payload
                    tool_events.append(
                        {
                            "tool_name": "guideline_validation",
                            "status": "success",
                            "input_payload": {
                                "question": body.content,
                                "answer": "".join(answer_parts),
                            },
                            "output_payload": payload,
                            "duration_ms": elapsed_ms,
                            "error_message": None,
                        }
                    )
                    yield emit_event("validation_done", payload)
                elif event.event == "done":
                    final_payload = event.data
                    warnings.extend(final_payload.get("warnings") or [])
                    yield emit_event("done", compact_done_payload(final_payload))
                elif event.event == "error":
                    message = str(event.data.get("message") or "Agent 调用失败")
                    error_text = f"\n\n[Agent 错误：{message}]"
                    answer_parts.append(error_text)
                    tool_events.append(
                        {
                            "tool_name": f"agent_{event.data.get('phase') or 'unknown'}",
                            "status": "failed",
                            "input_payload": {"question": body.content},
                            "output_payload": event.data,
                            "duration_ms": elapsed_ms,
                            "error_message": message,
                        }
                    )
                    yield emit_event("error", event.data)
                    chunk = json.dumps(
                        {"content": error_text, "done": False},
                        ensure_ascii=False,
                    )
                    yield f"data: {chunk}\n\n"
        except Exception as exc:
            error_text = f"\n\n[Agent 调用失败：{exc}]"
            answer_parts.append(error_text)
            tool_events.append(
                {
                    "tool_name": "agent_stream",
                    "status": "failed",
                    "input_payload": {"question": body.content},
                    "output_payload": None,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "error_message": str(exc),
                }
            )
            yield emit_event("error", {"message": str(exc)})
            chunk = json.dumps(
                {"content": error_text, "done": False},
                ensure_ascii=False,
            )
            yield f"data: {chunk}\n\n"

        if final_payload and not answer_parts:
            answer = str(final_payload.get("answer") or "")
            if answer:
                answer_parts.append(answer)
                chunk = json.dumps(
                    {"content": answer, "done": False},
                    ensure_ascii=False,
                )
                yield f"data: {chunk}\n\n"

        final_query_plan = final_payload.get("query_plan") if final_payload else query_plan
        final_evidence_status = (
            final_payload.get("evidence_status")
            if final_payload
            else (retrieval_payload or {}).get("evidence_status")
        ) or "not_checked"
        if final_query_plan:
            final_query_plan = {**final_query_plan, "evidence_status": final_evidence_status}
        final_validation = final_payload.get("validation") if final_payload else validation_payload
        final_references = (
            final_payload.get("references")
            if final_payload
            else (retrieval_payload or {}).get("references")
        )
        final_total = final_payload.get("total") if final_payload else (retrieval_payload or {}).get("total")
        final_warnings = list(dict.fromkeys(warnings))

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=sanitize_answer_text("".join(answer_parts)),
            intent=(final_query_plan or {}).get("intent"),
            retrieval_query=(final_query_plan or {}).get("rewritten_query"),
            retrieval_used=bool(final_references),
            retrieval_total=final_total,
            query_plan=final_query_plan,
            references=final_references,
            validation_result=final_validation,
            warnings=final_warnings,
        )
        db.add(assistant_msg)
        db.flush()

        try:
            memory_adapter.refresh_summary(conversation_id)
        except Exception as exc:
            summary_warning = f"memory_summary_failed: {exc}"
            final_warnings.append(summary_warning)
            assistant_msg.warnings = final_warnings

        for item in tool_events:
            db.add(
                AgentToolRun(
                    conversation_id=conversation_id,
                    message_id=assistant_msg.id,
                    tool_name=item["tool_name"],
                    status=item["status"],
                    input_payload=item["input_payload"],
                    output_payload=item["output_payload"],
                    duration_ms=item["duration_ms"],
                    error_message=item["error_message"],
                )
            )

        conv.updated_at = datetime.utcnow()
        db.commit()

        done_chunk = json.dumps(
            {
                "event": "message_saved",
                "done": True,
                "message": MessageResponse.model_validate(assistant_msg).model_dump(mode="json"),
                "conversation": ConversationResponse.model_validate(conv).model_dump(mode="json"),
            },
            ensure_ascii=False,
        )
        yield f"data: {done_chunk}\n\n"

    return StreamingResponse(generate_sse(), media_type="text/event-stream")


def _build_user_context(account_role: str, requested: dict | None) -> dict:
    role_defaults = {
        "professional": ("clinician", "professional"),
        "admin": ("institution_researcher", "professional"),
        "normal": ("patient", "standard"),
    }
    active_role, technical_level = role_defaults.get(account_role, ("patient", "standard"))
    context = {
        "active_role": active_role,
        "technical_level": technical_level,
        "detail_level": "standard",
        "response_style": "structured",
        "evidence_preference": "show",
    }
    if requested:
        for key in ("detail_level", "response_style", "evidence_preference"):
            value = requested.get(key)
            if value:
                context[key] = str(value)
    return context


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

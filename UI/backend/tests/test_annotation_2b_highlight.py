"""2b 锁测：空 proposed 审批 fast-path 不改核心表（annotation_service.approve_submission L1572）。

沿用 test_annotation_review 约定：裸 FastAPI + 真实依赖链。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    monkeypatch.setenv("ANNOTATION_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db():
    from tests.utils import make_db

    with make_db() as session:
        yield session


@pytest.fixture()
def client(db):
    from app.core.database import get_db
    from app.routers.annotation import router as annotation_router
    from app.routers.annotation_admin import router as annotation_admin_router

    app = FastAPI()
    app.include_router(annotation_router)
    app.include_router(annotation_admin_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def admin(db):
    return make_user(db, "review-admin-2b", role="admin")


def _seed_core_lit(db, n: int, *, prefix: str = "t2b") -> list[int]:
    from app.models import LitMetadata

    for i in range(1, n + 1):
        db.add(
            LitMetadata(
                file_uuid=f"{prefix}-u{i}",
                original_name=f"a{i}.pdf",
                storage_path=f"lit/{prefix}-u{i}/a{i}.pdf",
                cleaned_title=f"针灸研究{i}",
                title=f"针灸治疗不孕症研究{i}",
                authors=["张三"],
                keywords=["中医"],
                source_site="cnki",
                journal="中医杂志",
                pub_year="2024",
                matched_title=f"针灸研究{i}",
                crawl_status="success",
                created_at=CORE_TS,
                updated_at=CORE_TS,
            )
        )
    db.commit()
    ids = [
        r.id
        for r in db.query(LitMetadata)
        .filter(LitMetadata.file_uuid.like(f"{prefix}-%"))
        .order_by(LitMetadata.id)
        .all()
    ]
    assert len(ids) == n
    return ids


def _seed_pool_with_records(db, record_ids: list[int]):
    from app.models import AnnotationPool, AnnotationPoolItem

    pool = AnnotationPool(table_name="lit", filter_json={}, status="active", priority=0)
    db.add(pool)
    db.flush()
    db.add_all(
        [
            AnnotationPoolItem(
                pool_id=pool.id,
                table_name="lit",
                record_id=record_id,
                status="available",
            )
            for record_id in record_ids
        ]
    )
    db.commit()
    return pool


def _claim_task(client, annotator) -> int:
    resp = client.post("/api/annotation/tasks/claim", json={}, headers=auth_header(annotator))
    assert resp.status_code == 200
    return resp.json()["task_id"]


def _task_items(db, task_id: int):
    from app.models import AnnotationTaskItem

    return (
        db.query(AnnotationTaskItem)
        .filter(AnnotationTaskItem.task_id == task_id)
        .order_by(AnnotationTaskItem.id)
        .all()
    )


def _draft(client, annotator, item_id: int, proposed_fields: dict):
    return client.put(
        f"/api/annotation/items/{item_id}/draft",
        json={"proposed_fields": proposed_fields},
        headers=auth_header(annotator),
    )


def _submit_all(client, annotator, task_id: int):
    resp = client.post(f"/api/annotation/tasks/{task_id}/submit", headers=auth_header(annotator))
    assert resp.status_code == 200
    return resp.json()


def _pending_submissions(db, items):
    from app.models import AnnotationSubmission

    subs = []
    for it in items:
        sub = (
            db.query(AnnotationSubmission)
            .filter(AnnotationSubmission.item_id == it.id, AnnotationSubmission.status == "pending")
            .one()
        )
        subs.append(sub)
    return subs


def _approve(client, admin, submission_id: int):
    return client.post(
        f"/api/annotation/admin/review/{submission_id}/approve", headers=auth_header(admin)
    )


# --- 2b: 空 proposed fast-path 不落库 ---------------------------------------


def test_empty_proposed_approve_does_not_touch_core(client, db, admin):
    """无需修改提交 (proposed_fields={}) 通过后核心记录完全不变，status approved。"""
    from app.models import LitMetadata

    record_ids = _seed_core_lit(db, 1, prefix="2b-empty1")
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, "2b-annotator-empty1", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    assert len(items) == 1
    item = items[0]

    # draft 无需修改（空 proposed）
    assert _draft(client, annotator, item.id, {}).status_code == 200
    _submit_all(client, annotator, task_id)
    (sub,) = _pending_submissions(db, [item])
    assert sub.proposed_fields == {}

    before = db.get(LitMetadata, item.record_id)
    before_title = before.title
    before_journal = before.journal
    before_updated = before.updated_at

    resp = _approve(client, admin, sub.id)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["submission_id"] == sub.id
    assert resp.json()["item_id"] == item.id

    db.refresh(sub)
    assert sub.status == "approved"
    assert sub.reviewed_at is not None
    assert sub.reviewer_id == admin.id
    db.refresh(item)
    assert item.status == "approved"

    after = db.get(LitMetadata, item.record_id)
    assert after.title == before_title
    assert after.journal == before_journal
    assert after.updated_at == before_updated

    # 审计落 approve 且 old/new 为空
    from app.models import AnnotationLog

    log = (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == "approve", AnnotationLog.submission_id == sub.id)
        .one()
    )
    assert log.old_fields == {}
    assert log.new_fields == {}


def test_batch_approve_empty_proposed_keeps_core_unchanged(client, db, admin):
    """批量通过中空 proposed 条目同走 fast-path，不误触核心表。"""
    from app.models import LitMetadata

    record_ids = _seed_core_lit(db, 2, prefix="2b-batch")
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, "2b-annotator-batch", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)

    # item0: 空 proposed（无需修改），item1: 真差异
    assert _draft(client, annotator, items[0].id, {}).status_code == 200
    assert _draft(client, annotator, items[1].id, {"title": "改后标题"}).status_code == 200
    _submit_all(client, annotator, task_id)
    subs = _pending_submissions(db, items)

    before0 = db.get(LitMetadata, items[0].record_id)
    b0_title, b0_updated = before0.title, before0.updated_at

    resp = client.post(
        "/api/annotation/admin/review/batch-approve",
        json={"submission_ids": [s.id for s in subs]},
        headers=auth_header(admin),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 2
    assert all(r["status"] == "approved" for r in results)

    after0 = db.get(LitMetadata, items[0].record_id)
    assert after0.title == b0_title
    assert after0.updated_at == b0_updated

    after1 = db.get(LitMetadata, items[1].record_id)
    assert after1.title == "改后标题"

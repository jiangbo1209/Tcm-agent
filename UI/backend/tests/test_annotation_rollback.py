"""审计日志检索与一键回滚（plan todo #9）。

沿用 test_annotation_review 约定：本机无 PostgreSQL，main.py 顶层迁移直连 PG，
故把真实 annotation 路由与 annotation_admin 路由同时挂载到裸 FastAPI 宿主，
仅覆盖 get_db；require_annotator / require_admin 走真实依赖链（真实 JWT + DB 用户）。
approve/reject/expire 日志由 claim + draft + submit + 复核全流程自然产生。

核心记录（lit_metadata）的 server_default 是 text("NOW()")，SQLite 无此函数，
播种与 Core 层直改一律显式给 updated_at（见 test_annotation_review 先例）。
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_annotation_config, get_settings
from tests.utils import auth_header, make_user

CORE_TS = datetime(2026, 1, 15, 8, 0, 0)
NEWER_TS = datetime(2026, 8, 1, 8, 0, 0)
assert NEWER_TS > CORE_TS

LOGS_URL = "/api/annotation/admin/logs"

# AnnotationLog 全列快照（append-only 逐字段对照用）
_LOG_COLUMNS = (
    "id",
    "table_name",
    "record_id",
    "actor_id",
    "username",
    "action",
    "old_fields",
    "new_fields",
    "submission_id",
    "created_at",
)

_ITEM_KEYS = {
    "id",
    "table_name",
    "record_id",
    "actor_id",
    "username",
    "action",
    "old_fields",
    "new_fields",
    "submission_id",
    "created_at",
}


def _naive_utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- 基建（镜像 test_annotation_review.py）-----------------------------------


@pytest.fixture(autouse=True)
def _annotation_enabled(monkeypatch):
    """环境变量直读根 Settings，清空其缓存放行真实总闸。"""
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
    return make_user(db, "t9-admin", role="admin")


def _seed_core_lit(db, n: int, *, prefix: str = "t9") -> list[int]:
    """播种 n 条核心 lit 记录，返回且仅返回本次创建的 id（多次建池安全）。"""
    from app.models import LitMetadata

    rows = []
    for i in range(1, n + 1):
        row = LitMetadata(
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
        db.add(row)
        rows.append(row)
    db.commit()
    ids = [row.id for row in rows]
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
    assert resp.status_code == 200, resp.text
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


def _submit_batch(db, client, *, n: int, fields: list[dict], prefix: str = "t9"):
    """建池 -> 领取 -> 逐条暂存 -> 整批提交，返回 (annotator, task_id, items, submissions)。"""
    record_ids = _seed_core_lit(db, n, prefix=prefix)
    _seed_pool_with_records(db, record_ids)
    annotator = make_user(db, f"{prefix}-annotator", role="annotator")
    task_id = _claim_task(client, annotator)
    items = _task_items(db, task_id)
    for it, f in zip(items, fields):
        assert _draft(client, annotator, it.id, f).status_code == 200
    _submit_all(client, annotator, task_id)
    return annotator, task_id, items, _pending_submissions(db, items)


def _approve(client, admin, submission_id: int):
    return client.post(
        f"/api/annotation/admin/review/{submission_id}/approve", headers=auth_header(admin)
    )


def _reject(client, admin, submission_id: int, comment: str):
    return client.post(
        f"/api/annotation/admin/review/{submission_id}/reject",
        json={"comment": comment},
        headers=auth_header(admin),
    )


def _log_row(db, log_id: int) -> dict:
    """单条日志的全列快照，用于 append-only 逐字节对照。"""
    from app.models import AnnotationLog

    log = db.get(AnnotationLog, log_id)
    assert log is not None
    return {col: getattr(log, col) for col in _LOG_COLUMNS}


def _find_log_via_api(client, admin, **params) -> dict:
    """经 GET /logs 检索且必须恰好命中一条（顺带验证检索端点本身）。"""
    resp = client.get(LOGS_URL, params=params, headers=auth_header(admin))
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1, f"params={params} 应恰好命中一条日志，实际 {len(items)}"
    return items[0]


# --- (a) happy rollback：核心表还原 + 新增 rollback 行 + 原行逐字段不变 -------


def test_happy_rollback_restores_core_and_appends_new_log(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=1, fields=[{"title": "批准稿标题"}]
    )
    record_id = items[0].record_id
    assert _approve(client, admin, subs[0].id).json()["status"] == "approved"
    assert db.get(LitMetadata, record_id).title == "批准稿标题"

    approve_item = _find_log_via_api(client, admin, action="approve", record_id=record_id)
    assert approve_item["submission_id"] == subs[0].id
    assert approve_item["username"] == admin.username
    assert approve_item["old_fields"] == {"title": "针灸治疗不孕症研究1"}
    assert approve_item["new_fields"] == {"title": "批准稿标题"}
    before = _log_row(db, approve_item["id"])

    resp = client.post(
        f"{LOGS_URL}/{approve_item['id']}/rollback", headers=auth_header(admin)
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["table_name"] == "lit"
    assert body["record_id"] == record_id
    assert sorted(body["restored_fields"]) == ["title"]
    assert isinstance(body["log_id"], int) and body["log_id"] > approve_item["id"]

    core = db.get(LitMetadata, record_id)
    assert core.title == "针灸治疗不孕症研究1", "回滚必须把 old_fields 写回核心表"

    after = _log_row(db, approve_item["id"])
    assert after == before, "源日志必须原样保留（append-only 证明）"

    rb_page = client.get(LOGS_URL, params={"action": "rollback"}, headers=auth_header(admin)).json()
    assert rb_page["total"] == 1
    row = rb_page["items"][0]
    assert row["id"] == body["log_id"]
    assert row["table_name"] == "lit"
    assert row["record_id"] == record_id
    assert row["action"] == "rollback"
    assert row["old_fields"] == {"title": "批准稿标题"}, "rollback 行 old=回滚前现值"
    assert row["new_fields"] == {"title": "针灸治疗不孕症研究1"}, "rollback 行 new=被恢复旧值"
    assert row["actor_id"] == admin.id
    assert row["username"] == admin.username
    assert row["submission_id"] == subs[0].id
    assert isinstance(row["created_at"], str)


# --- (b) roundtrip：对 rollback 日志再回滚 -> 变更后的值又回来了 ---------------


def test_roundtrip_rollback_twice_restores_changed_value(client, db, admin):
    from app.models import LitMetadata

    _annotator, _task_id, items, subs = _submit_batch(
        db, client, n=1, fields=[{"journal": "新期刊"}], prefix="t9b"
    )
    record_id = items[0].record_id
    assert _approve(client, admin, subs[0].id).json()["status"] == "approved"

    approve_item = _find_log_via_api(client, admin, action="approve", record_id=record_id)
    first = client.post(f"{LOGS_URL}/{approve_item['id']}/rollback", headers=auth_header(admin))
    assert first.status_code == 200
    assert db.get(LitMetadata, record_id).journal == "中医杂志", "第一跳恢复原始值"

    rollback_log_id = first.json()["log_id"]
    second = client.post(f"{LOGS_URL}/{rollback_log_id}/rollback", headers=auth_header(admin))
    assert second.status_code == 200
    assert db.get(LitMetadata, record_id).journal == "新期刊", "对回滚日志再回滚应还原变更值"


# --- (c) 过滤条件 AND 组合 / 分页 / 参数校验 -----------------------------------


def _seed_logs(db):
    """直接播种 7 条跨表/跨人/跨动作/跨日期的审计行（只插入，不改不删）。"""
    from app.models import AnnotationLog

    u1 = make_user(db, "t9c-u1", role="admin")
    u2 = make_user(db, "t9c-u2", role="annotator")

    def seed(**kw):
        defaults = dict(
            table_name="lit",
            record_id=1,
            actor_id=u1.id,
            username=u1.username,
            action="draft",
            old_fields={"title": "旧"},
            new_fields={"title": "新"},
            created_at=datetime(2026, 5, 1, 12, 0, 0),
        )
        defaults.update(kw)
        entry = AnnotationLog(**defaults)
        db.add(entry)
        return entry

    rows = {
        "may_lit1_u1_draft": seed(),
        "lit1_u1_approve": seed(action="approve"),
        "lit2_u1_approve": seed(record_id=2, action="approve"),
        "lit1_u2_draft": seed(actor_id=u2.id, username=u2.username),
        "case_u1_reject": seed(table_name="case", action="reject"),
        "june_draft": seed(created_at=datetime(2026, 6, 15, 9, 30, 0)),
        "july_draft": seed(created_at=datetime(2026, 7, 31, 23, 59, 59)),
    }
    db.commit()
    return u1, u2, rows


def test_log_filters_combine_and_paginate(client, db, admin):
    u1, u2, rows = _seed_logs(db)

    def get(**params):
        resp = client.get(LOGS_URL, params=params, headers=auth_header(admin))
        assert resp.status_code == 200, resp.text
        return resp.json()

    unfiltered = get()
    assert set(unfiltered.keys()) == {"total", "page", "page_size", "items"}
    assert unfiltered["total"] == 7
    assert all(set(it.keys()) == _ITEM_KEYS for it in unfiltered["items"])

    # 单条件过滤
    assert get(action="draft")["total"] == 4
    assert get(table_name="case")["total"] == 1
    assert get(record_id=2)["total"] == 1
    assert get(actor_id=u2.id)["total"] == 1
    assert get(action="approve")["total"] == 2
    # 未命中
    assert get(table_name="guideline")["total"] == 0

    # AND 组合：逐个收窄
    combined = get(action="approve", table_name="lit", actor_id=u1.id)
    assert combined["total"] == 2
    narrowed = get(action="approve", table_name="lit", actor_id=u1.id, record_id=1)
    assert narrowed["total"] == 1
    assert narrowed["items"][0]["id"] == rows["lit1_u1_approve"].id

    # 日期区间含两端
    assert get(date_from="2026-06-01T00:00:00")["total"] == 2
    assert get(date_to="2026-05-31T23:59:59")["total"] == 5
    both = get(date_from="2026-05-01T12:00:00", date_to="2026-07-31T23:59:59")
    assert both["total"] == 7
    edge = get(date_from="2026-06-15T09:30:00", date_to="2026-06-15T09:30:00")
    assert [it["id"] for it in edge["items"]] == [rows["june_draft"].id]

    # 倒序 + 分页算术
    p1 = get(page=1, page_size=3)
    p2 = get(page=2, page_size=3)
    p3 = get(page=3, page_size=3)
    assert (p1["page"], p1["page_size"]) == (1, 3)
    assert len(p1["items"]) == 3 and len(p2["items"]) == 3 and len(p3["items"]) == 1
    all_ids = [it["id"] for it in p1["items"] + p2["items"] + p3["items"]]
    assert all_ids == sorted(all_ids, reverse=True), "必须按 id 倒序"
    empty = get(page=4, page_size=3)
    assert empty["total"] == 7 and empty["items"] == []

    # 参数校验 -> 400
    resp_zero = client.get(LOGS_URL, params={"page_size": 0}, headers=auth_header(admin))
    assert resp_zero.status_code == 400
    resp_over = client.get(LOGS_URL, params={"page_size": 101}, headers=auth_header(admin))
    assert resp_over.status_code == 400
    resp_page0 = client.get(LOGS_URL, params={"page": 0}, headers=auth_header(admin))
    assert resp_page0.status_code == 400
    resp_bad_date = client.get(LOGS_URL, params={"date_from": "not-a-date"}, headers=auth_header(admin))
    assert resp_bad_date.status_code == 400


# --- (d) 集成：复核流产生的 approve/reject/expire 日志天然可被检索 -------------


def test_t8_review_logs_flow_into_query(client, db, admin):
    from app.models import LitMetadata

    annotator, _task_id, items, subs = _submit_batch(
        db, client, n=2, fields=[{"title": "过期稿"}, {"title": "正常稿"}], prefix="t9d"
    )
    db.execute(
        sa.update(LitMetadata)
        .where(LitMetadata.id == items[0].record_id)
        .values(updated_at=NEWER_TS)
    )
    db.commit()
    assert _approve(client, admin, subs[0].id).json()["status"] == "expired"
    assert _approve(client, admin, subs[1].id).json()["status"] == "approved"

    rej_ann, _t2, _r_items, r_subs = _submit_batch(
        db, client, n=1, fields=[{"title": "驳回稿"}], prefix="t9d-rej"
    )
    assert _reject(client, admin, r_subs[0].id, "不合格").status_code == 200

    body = client.get(LOGS_URL, params={"page_size": 100}, headers=auth_header(admin)).json()
    by_action: dict[str, list[dict]] = {}
    for row in body["items"]:
        by_action.setdefault(row["action"], []).append(row)

    assert {"approve", "reject", "expire"} <= set(by_action), "T8 的三类复核日志必须可被检索"

    ok_approve = next(r for r in by_action["approve"] if r["submission_id"] == subs[1].id)
    assert ok_approve["old_fields"] == {"title": "针灸治疗不孕症研究2"}
    assert ok_approve["new_fields"] == {"title": "正常稿"}
    expire_row = next(r for r in by_action["expire"] if r["submission_id"] == subs[0].id)
    assert expire_row["new_fields"] == {"reason": "base_conflict"}
    reject_row = next(r for r in by_action["reject"] if r["submission_id"] == r_subs[0].id)
    assert reject_row["new_fields"] == {"comment": "不合格"}

    for row in ok_approve, expire_row, reject_row:
        assert row["username"] == admin.username, "复核动作的 username 快照必须是管理员"

    claim_rows = by_action.get("claim", [])
    assert claim_rows and all(r["username"] == annotator.username or r["username"].endswith("-annotator") for r in claim_rows)
    draft_rows = [r for r in by_action.get("draft", []) if r["record_id"] != 0]
    assert any(r["username"] == rej_ann.username for r in draft_rows)


# --- (e) 无 old_fields 的日志回滚 -> 400 ---------------------------------------


def test_rollback_rejects_logs_without_old_fields(client, db, admin):
    from app.models import AnnotationLog

    _ann, _task_id, _items, subs = _submit_batch(db, client, n=1, fields=[{"title": "占位"}])
    claim_log = db.query(AnnotationLog).filter(AnnotationLog.action == "claim").one()
    assert claim_log.old_fields is None

    resp = client.post(f"{LOGS_URL}/{claim_log.id}/rollback", headers=auth_header(admin))
    assert resp.status_code == 400
    assert "该日志不含可回滚的字段变更" in resp.json()["detail"]

    # old_fields={} 同样不可回滚：空 diff 批准日志
    _ann2, _t2, _i2, subs2 = _submit_batch(db, client, n=1, fields=[{}], prefix="t9e2")
    assert _approve(client, admin, subs2[0].id).json()["status"] == "approved"
    empty_log = (
        db.query(AnnotationLog)
        .filter(AnnotationLog.action == "approve", AnnotationLog.submission_id == subs2[0].id)
        .one()
    )
    assert empty_log.old_fields == {}
    resp2 = client.post(f"{LOGS_URL}/{empty_log.id}/rollback", headers=auth_header(admin))
    assert resp2.status_code == 400
    assert "该日志不含可回滚的字段变更" in resp2.json()["detail"]

    assert db.query(AnnotationLog).filter(AnnotationLog.action == "rollback").count() == 0


# --- (f) 乐观锁冲突：读到快照之后、写入之前核心行被人改动 -> 409 ----------------


def test_stale_rollback_conflict_409(client, db, admin, monkeypatch):
    from app.models import AnnotationLog, LitMetadata
    from app.repositories.admin_repo import AdminQueryRepository, _TABLE_MAP

    _ann, _task_id, items, subs = _submit_batch(
        db, client, n=1, fields=[{"title": "并发前标题"}], prefix="t9f"
    )
    record_id = items[0].record_id
    assert _approve(client, admin, subs[0].id).json()["status"] == "approved"
    approve_item = _find_log_via_api(client, admin, action="approve", record_id=record_id)

    original = AdminQueryRepository.update_record

    def bump_then_update(self, table, rec_id, fields, updated_at):
        """模拟并发窗口：服务已读取 updated_at 快照后、写入前，他人直改核心行。"""
        model = _TABLE_MAP[table]
        db.execute(sa.update(model).where(model.id == rec_id).values(updated_at=NEWER_TS))
        db.commit()
        return original(self, table, rec_id, fields, updated_at)

    monkeypatch.setattr(AdminQueryRepository, "update_record", bump_then_update)

    resp = client.post(f"{LOGS_URL}/{approve_item['id']}/rollback", headers=auth_header(admin))
    assert resp.status_code == 409
    assert "记录已被他人修改" in resp.json()["detail"]
    assert "无法回滚" in resp.json()["detail"]

    db.expire_all()
    core = db.get(LitMetadata, record_id)
    assert core.title == "并发前标题", "冲突时核心表绝不能被部分写入"
    assert db.query(AnnotationLog).filter(AnnotationLog.action == "rollback").count() == 0, (
        "失败回滚不得留下任何 rollback 审计行"
    )


# --- (g) 未知日志 id / 核心记录缺失 -> 404 --------------------------------------


def test_rollback_unknown_log_and_missing_core_404(client, db, admin):
    from app.models import AnnotationLog, LitMetadata

    resp = client.post(f"{LOGS_URL}/999999/rollback", headers=auth_header(admin))
    assert resp.status_code == 404
    assert "日志不存在" in resp.json()["detail"]

    record_ids = _seed_core_lit(db, 1, prefix="t9g")
    orphan_log = AnnotationLog(
        table_name="lit",
        record_id=record_ids[0],
        actor_id=None,
        username="system",
        action="draft",
        old_fields={"title": "孤儿旧值"},
        new_fields={"title": "孤儿新值"},
    )
    db.add(orphan_log)
    db.commit()
    # 核心行随后被删（核心表删除不受 append-only 约束；annotation_logs 不动）
    db.query(LitMetadata).filter(LitMetadata.id == record_ids[0]).delete()
    db.commit()

    resp2 = client.post(f"{LOGS_URL}/{orphan_log.id}/rollback", headers=auth_header(admin))
    assert resp2.status_code == 404
    assert "核心记录不存在" in resp2.json()["detail"]


# --- (h) 非管理员一律 403 -------------------------------------------------------


def test_non_admin_forbidden_on_log_endpoints(client, db, admin):
    plain = make_user(db, "plain-t9", role="normal")

    query_resp = client.get(LOGS_URL, headers=auth_header(plain))
    assert query_resp.status_code == 403

    rollback_resp = client.post(f"{LOGS_URL}/1/rollback", headers=auth_header(plain))
    assert rollback_resp.status_code == 403


# --- (i) F4-V1/G3：管理员直改必须落 save_direct 审计行（与标注总闸无关）--------


def test_admin_direct_edit_writes_save_direct_log_gate_independent(
    client, db, admin, monkeypatch
):
    from fastapi import FastAPI as _FastAPI

    from app.core.database import get_db
    from app.models import AnnotationLog, LitMetadata
    from app.routers.admin import router as admin_router

    # 总闸关闭（无 enabled 环境变量）：save_direct 审计不得依赖 ANNOTATION_ENABLED
    monkeypatch.delenv("ANNOTATION_ENABLED", raising=False)
    get_settings.cache_clear()
    assert get_annotation_config().enabled is False

    record_id = _seed_core_lit(db, 1, prefix="t9i")[0]

    app = _FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_db] = lambda: db
    try:
        admin_client = TestClient(app)
        resp = admin_client.put(
            f"/api/admin/lit/{record_id}",
            json={"fields": {"title": "管理员直改标题"}},
            headers=auth_header(admin),
        )
        assert resp.status_code == 200, resp.text
        assert db.get(LitMetadata, record_id).title == "管理员直改标题"
    finally:
        app.dependency_overrides.clear()

    log = (
        db.query(AnnotationLog)
        .filter(
            AnnotationLog.action == "save_direct",
            AnnotationLog.table_name == "lit",
            AnnotationLog.record_id == record_id,
        )
        .one()
    )
    assert log.username == admin.username
    assert log.actor_id == admin.id
    assert log.old_fields == {"title": "针灸治疗不孕症研究1"}
    assert log.new_fields == {"title": "管理员直改标题"}

    get_settings.cache_clear()

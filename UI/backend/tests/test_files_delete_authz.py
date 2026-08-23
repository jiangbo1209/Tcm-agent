"""Wave3 文件删除安全回归：authz 矩阵 + 409 引用阻止 + DB-first 提交顺序。

覆盖计划 security-p0p1-hardening todo 8/9/10：
- 单删 DELETE /api/files/{file_uuid} 与批删 POST /api/files/batch-delete 仅 admin 可达；
- 被引用文件 409 阻止（表名明细），批删任一被引用整批阻止；
- 单删固定五步：引用检查 → 读行 → 删行 → 显式 commit → S3（commit 先于 S3）；
- S3 故障不影响库内一致性（仍 200，行已提交删除）。
"""

from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.dependencies.files import get_upload_service
from app.models import (
    Base,
    CoreFile,
    GraphBase,
    GuidelineMetadata,
    LitMetadata,
    MedCase,
)
from app.models.conversation import Conversation  # noqa: F401 -- 注册 FK 目标表
from app.models.message import Message  # noqa: F401 -- 注册 FK 目标表
from app.models.user import User
from app.routers.files import router as files_router
from app.storage.repository import CoreFileRepository
from app.storage.service import UploadService

TS = datetime(2026, 1, 15, 8, 0, 0, tzinfo=timezone.utc)


# --- 打桩与夹具 ---------------------------------------------------------------


class RecordingS3:
    """记录调用序的 S3 桩；fail=True 时模拟对象存储抖动。"""

    def __init__(self, fail: bool = False, events: list | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.events = events if events is not None else []
        self.fail = fail

    async def remove_object_async(self, storage_path: str) -> None:
        self.calls.append(("s3.remove", storage_path))
        self.events.append(("s3.remove", storage_path))
        if self.fail:
            raise RuntimeError("simulated s3 outage")

    async def put_object_async(self, *, object_name: str, **_kwargs) -> None:
        self.calls.append(("s3.put", object_name))


class RecordingRepo(CoreFileRepository):
    """在真实仓储上记录 commit 调用序，用于断言 commit 先于 S3 删除。"""

    def __init__(self, session: AsyncSession, events: list) -> None:
        super().__init__(session)
        self.events = events

    async def commit(self) -> None:
        self.events.append(("db.commit", ""))
        await super().commit()


def _make_user(role: str) -> User:
    return User(
        id=1,
        username=f"u-{role}",
        email=f"{role}@tcm.test",
        hashed_password="x",
        role=role,
        is_active=True,
    )


@pytest_asyncio.fixture()
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(GraphBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _build_app(db_session: AsyncSession, *, s3: RecordingS3 | None = None):
    events: list[tuple[str, str]] = []
    s3 = s3 or RecordingS3(events=events)
    repository = RecordingRepo(db_session, events)
    service = UploadService(
        repository=repository,
        s3_client=s3,
        max_file_size_mb=100,
        allowed_extensions=(".pdf",),
        batch_concurrency=5,
    )

    app = FastAPI()
    app.include_router(files_router)
    app.dependency_overrides[get_upload_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _make_user("admin")
    return app, service, s3, events


def _client(app: FastAPI, *, token_role: str | None = "admin") -> httpx.AsyncClient:
    headers = {}
    if token_role is not None:
        headers["Authorization"] = f"Bearer fake-token-for-{token_role}"
    # get_current_user 已被 override，token 内容不参与校验；缺失 header 才走匿名分支。
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers=headers,
    )


async def _seed_core_file(session: AsyncSession, file_uuid: str = "u1") -> None:
    session.add(
        CoreFile(
            file_uuid=file_uuid,
            original_name="a.pdf",
            storage_path=f"literature/{file_uuid}/a.pdf",
            upload_time=TS,
        )
    )
    await session.commit()


async def _row_exists(session: AsyncSession, file_uuid: str) -> bool:
    row = await session.execute(
        select(CoreFile).where(CoreFile.file_uuid == file_uuid)
    )
    return row.scalar_one_or_none() is not None


# --- T8：删除端点 authz 矩阵 ----------------------------------------------------


@pytest.mark.asyncio
async def test_delete_file_anonymous_returns_401(db_session):
    app, *_ = _build_app(db_session)
    del app.dependency_overrides[get_current_user]  # 匿名走真实 HTTPBearer 链
    async with _client(app, token_role=None) as client:
        resp = await client.delete("/api/files/u1")
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["normal", "professional"])
async def test_delete_file_non_admin_returns_403(db_session, role):
    app, *_ = _build_app(db_session)
    app.dependency_overrides[get_current_user] = lambda: _make_user(role)
    await _seed_core_file(db_session)
    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")
    assert resp.status_code == 403
    assert await _row_exists(db_session, "u1")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["normal", "professional"])
async def test_batch_delete_non_admin_returns_403(db_session, role):
    app, *_ = _build_app(db_session)
    app.dependency_overrides[get_current_user] = lambda: _make_user(role)
    await _seed_core_file(db_session)
    async with _client(app) as client:
        resp = await client.post(
            "/api/files/batch-delete", json={"file_uuids": ["u1"]}
        )
    assert resp.status_code == 403
    assert await _row_exists(db_session, "u1")


@pytest.mark.asyncio
async def test_batch_delete_anonymous_returns_401(db_session):
    app, *_ = _build_app(db_session)
    del app.dependency_overrides[get_current_user]  # 匿名走真实 HTTPBearer 链
    async with _client(app, token_role=None) as client:
        resp = await client.post(
            "/api/files/batch-delete", json={"file_uuids": ["u1"]}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_file_admin_reaches_service_and_deletes(db_session):
    app, _, s3, _ = _build_app(db_session)
    await _seed_core_file(db_session)
    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "file_uuid": "u1"}
    assert ("s3.remove", "literature/u1/a.pdf") in s3.calls
    assert not await _row_exists(db_session, "u1")


@pytest.mark.asyncio
async def test_batch_delete_admin_success(db_session):
    app, _, s3, _ = _build_app(db_session)
    await _seed_core_file(db_session, "u1")
    await _seed_core_file(db_session, "u2")
    async with _client(app) as client:
        resp = await client.post(
            "/api/files/batch-delete", json={"file_uuids": ["u1", "u2"]}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted"] == 2
    assert {c[1] for c in s3.calls if c[0] == "s3.remove"} == {
        "literature/u1/a.pdf",
        "literature/u2/a.pdf",
    }


@pytest.mark.asyncio
async def test_get_file_detail_stays_login_only(db_session):
    """非删除端点保持 get_current_user：normal 用户仍可读详情（防过度收紧）。"""
    app, *_ = _build_app(db_session)
    app.dependency_overrides[get_current_user] = lambda: _make_user("normal")
    await _seed_core_file(db_session)
    async with _client(app) as client:
        resp = await client.get("/api/files/u1")
    assert resp.status_code == 200
    assert resp.json()["file_uuid"] == "u1"


# --- T9：引用检查 409 -----------------------------------------------------------


def _make_lit(file_uuid: str) -> LitMetadata:
    return LitMetadata(
        file_uuid=file_uuid,
        original_name="a.pdf",
        storage_path=f"literature/{file_uuid}/a.pdf",
        cleaned_title="T",
        title="T",
        authors=["张三"],
        keywords=["中医"],
        paper_type="期刊论文",
        source_site="cnki",
        journal="中医杂志",
        pub_year="2026",
        matched_title="T",
        is_exact_match=True,
        crawl_status="success",
        created_at=TS,
        updated_at=TS,
    )


@pytest.mark.asyncio
async def test_delete_file_referenced_by_lit_returns_409_with_table_detail(db_session):
    app, *_ = _build_app(db_session)
    await _seed_core_file(db_session)
    db_session.add(_make_lit("u1"))
    await db_session.commit()

    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")

    assert resp.status_code == 409
    assert "lit_metadata" in resp.json()["detail"]
    assert await _row_exists(db_session, "u1")


@pytest.mark.asyncio
async def test_delete_file_referenced_by_case_returns_409(db_session):
    app, *_ = _build_app(db_session)
    await _seed_core_file(db_session)
    db_session.add(MedCase(id=1, file_uuid="u1", created_at=TS, updated_at=TS))
    await db_session.commit()

    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")

    assert resp.status_code == 409
    assert "med_case" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_delete_file_referenced_by_guideline_returns_409(db_session):
    app, *_ = _build_app(db_session)
    await _seed_core_file(db_session)
    db_session.add(
        GuidelineMetadata(
            file_uuid="u1",
            original_name="a.pdf",
            storage_path="literature/u1/a.pdf",
            cleaned_title="T",
            title="T",
            authors=[],
            keywords=[],
            source_site="gov",
            matched_title="T",
            crawl_status="success",
            created_at=TS,
            updated_at=TS,
        )
    )
    await db_session.commit()

    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")

    assert resp.status_code == 409
    assert "guideline_metadata" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_batch_delete_any_referenced_blocks_whole_batch(db_session):
    app, _, s3, _ = _build_app(db_session)
    await _seed_core_file(db_session, "u1")
    await _seed_core_file(db_session, "u2")
    db_session.add(_make_lit("u2"))  # 仅 u2 被引用 → 整批 409，不做部分成功
    await db_session.commit()

    async with _client(app) as client:
        resp = await client.post(
            "/api/files/batch-delete", json={"file_uuids": ["u1", "u2"]}
        )

    assert resp.status_code == 409
    assert "lit_metadata" in resp.json()["detail"]
    # 整批未动：无 S3 调用、两行俱在
    assert s3.calls == []
    assert await _row_exists(db_session, "u1")
    assert await _row_exists(db_session, "u2")


@pytest.mark.asyncio
async def test_service_delete_file_referenced_raises_filerencerencederror(db_session):
    from app.storage.service import FileReferencedError  # 实现前 ImportError 即红

    _, service, _, _ = _build_app(db_session)
    await _seed_core_file(db_session)
    db_session.add(_make_lit("u1"))
    await db_session.commit()

    with pytest.raises(FileReferencedError) as exc_info:
        await service.delete_file("u1")
    assert exc_info.value.detail == {"lit_metadata": 1}


# --- T10：DB-first 五步 + commit 先于 S3 ----------------------------------------


@pytest.mark.asyncio
async def test_commit_happens_before_s3_removal(db_session):
    app, _, _, events = _build_app(db_session)
    await _seed_core_file(db_session)

    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")

    assert resp.status_code == 200
    commit_idx = next(i for i, e in enumerate(events) if e[0] == "db.commit")
    s3_idx = next(i for i, e in enumerate(events) if e[0] == "s3.remove")
    assert commit_idx < s3_idx


@pytest.mark.asyncio
async def test_s3_failure_still_200_and_row_committed_deleted(db_session):
    s3 = RecordingS3(fail=True)
    app, _, _, _ = _build_app(db_session, s3=s3)
    await _seed_core_file(db_session)

    async with _client(app) as client:
        resp = await client.delete("/api/files/u1")

    # 对象存储抖动不得破坏库内一致性：接口仍 200，行已提交删除（孤儿对象可接受）
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "file_uuid": "u1"}
    assert ("s3.remove", "literature/u1/a.pdf") in s3.calls
    fresh = AsyncSession(bind=db_session.bind)
    try:
        assert not await _row_exists(fresh, "u1")
    finally:
        await fresh.close()


@pytest.mark.asyncio
async def test_delete_missing_file_returns_404_without_s3_call(db_session):
    app, _, s3, _ = _build_app(db_session)

    async with _client(app) as client:
        resp = await client.delete("/api/files/nope")

    assert resp.status_code == 404
    assert s3.calls == []

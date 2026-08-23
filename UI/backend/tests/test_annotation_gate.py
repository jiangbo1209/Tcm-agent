"""ANNOTATION_ENABLED 功能总闸：路由级 503 门禁两分支。

Why not ``from main import app``：本机无 PostgreSQL，main.py 模块顶层的
``ensure_*`` 迁移会直连 PG（见 tests/utils.py、test_graph_authz.py）。
故按既有约定把真实标注路由挂载到裸 FastAPI 宿主上，保留真实的
``Depends(annotation_gate)`` 依赖链；门禁不依赖数据库。

T7 起标注路由追加了路由级 lazy_sweep_dep（每个放行的请求都会先跑一次
清扫、需要可用会话），因此与全部标注测试同约定仅覆盖 get_db 指向内存
SQLite；503 分支在门禁处即短路，仍不会触碰数据库。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_annotation_config


@pytest.fixture(autouse=True)
def _isolate_annotation_cache():
    """镜像 test_config_security.py：前后均清空 lru_cache，杜绝跨用例泄漏。"""
    get_annotation_config.cache_clear()
    yield
    get_annotation_config.cache_clear()


@pytest.fixture()
def db():
    from tests.utils import make_db

    with make_db() as session:
        yield session


def _build_client(db) -> TestClient:
    """把真实标注路由按 main.py 的方式挂到裸宿主（无认证；get_db -> 内存 SQLite）。"""
    from app.core.database import get_db

    from app.routers.annotation import router as annotation_router
    from app.routers.annotation_admin import router as annotation_admin_router

    app = FastAPI()
    app.include_router(annotation_router)
    app.include_router(annotation_admin_router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


# --- 分支 (a)：默认 ENABLED=false -> 503 数据标注功能未开启 ---


def test_health_returns_503_when_disabled_by_default(monkeypatch, db):
    monkeypatch.delenv("ANNOTATION_ENABLED", raising=False)
    resp = _build_client(db).get("/api/annotation/health")
    assert resp.status_code == 503
    assert "数据标注功能未开启" in resp.text


# --- 分支 (b)：cache_clear 后改写当前缓存实例 -> 放行并探活成功 ---


def test_health_returns_200_when_enabled_via_cached_instance(monkeypatch, db):
    monkeypatch.delenv("ANNOTATION_ENABLED", raising=False)
    get_annotation_config.cache_clear()
    # 刻意不走环境变量：直接改写“当前缓存实例”，证明门禁在请求期
    # 经真实 Depends 链读取的正是这份缓存配置（stale-state 对抗验证）。
    get_annotation_config().ENABLED = True

    resp = _build_client(db).get("/api/annotation/health")
    assert resp.status_code == 200
    assert resp.json() == {"enabled": True}


# --- 结构性证明：两个路由都挂了同一道总闸 ---


def test_both_routers_attach_the_same_gate():
    from app.routers.annotation import annotation_gate
    from app.routers.annotation import router as annotation_router
    from app.routers.annotation_admin import router as annotation_admin_router

    assert annotation_router.prefix == "/api/annotation"
    assert annotation_admin_router.prefix == "/api/annotation/admin"
    assert annotation_router.dependencies[0].dependency is annotation_gate
    assert annotation_admin_router.dependencies[0].dependency is annotation_gate

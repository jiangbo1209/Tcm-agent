"""Wave2 图谱 API 鉴权回归：四态矩阵（匿名/normal/professional/admin）× 三端点。

覆盖计划 security-p0p1-hardening todo 4/5：
- require_professional 放行 admin（P1-6）；
- graph 路由在 include_router 级挂 Depends(require_professional)（P0-1）。

本机无 PostgreSQL，无法在进程内 import main（模块顶层 ensure_* 迁移直连 PG，
见 test_config_security.py 注释），故按 tests/ 既有风格构建最小 app 复刻
main.py 的 graph 挂载方式；另以 wiring 守卫断言 main.py 源码中 graph_router
的 include 确实携带 dependencies=[Depends(require_professional)]——防止测试
自带依赖副本掩盖主应用漏挂（misleading_success）。
"""

from pathlib import Path

import pytest
from fastapi import Depends, FastAPI

from app.dependencies.auth import get_current_user, require_professional
from app.models.user import User
from app.routers.graph import router as graph_router
from app.schemas.graph import GraphExpandResponse, GraphNode, NodeDetailResponse

BACKEND_DIR = Path(__file__).resolve().parent.parent


# --- 打桩与夹具 ---------------------------------------------------------------


def _make_user(role: str) -> User:
    return User(
        id=1,
        username=f"u-{role}",
        email=f"{role}@tcm.test",
        hashed_password="x",
        role=role,
        is_active=True,
    )


def _node(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        node_type="paper",
        title="中医证候研究",
        metric_value=2026,
        top_k_value=0.9,
    )


class StubGraphService:
    """返回固定载荷的图谱服务桩，使 professional/admin 可达 200。"""

    def expand_graph(self, seed_id: str, limit: int, depth: int) -> GraphExpandResponse:
        return GraphExpandResponse(nodes=[_node(seed_id)], edges=[])

    def get_node_detail(self, node_id: str) -> NodeDetailResponse:
        return NodeDetailResponse(node=_node(node_id), detail_type="paper")


class StubGraphRepository:
    def search_nodes(self, keyword: str, size: int) -> list[dict]:
        return [{"node_id": "n1", "title": "中医证候研究", "source_type": "paper"}]


def _build_app() -> FastAPI:
    """复刻 main.py 对 graph_router 的挂载：include_router 级全局鉴权。"""
    app = FastAPI()
    app.include_router(
        graph_router, dependencies=[Depends(require_professional)]
    )
    app.state.graph_service = StubGraphService()
    app.state.graph_repository = StubGraphRepository()
    return app


def _client(app: FastAPI, role: str | None):
    from fastapi.testclient import TestClient

    if role is not None:
        # 仅替换身份来源；require_professional 判定逻辑真实执行。
        app.dependency_overrides[get_current_user] = lambda: _make_user(role)
    # 匿名不覆写：走真实 HTTPBearer → get_current_user 依赖链。
    return TestClient(app, raise_server_exceptions=False)


ENDPOINTS = [
    ("/api/graph/expand?seed_id=n1&limit=10&depth=1"),
    ("/api/graph/node-detail?node_id=n1"),
    ("/api/graph/search?q=%E8%AF%81%E5%80%99&page=1&size=10"),
]


# --- 四态矩阵 × 三端点 ----------------------------------------------------------


@pytest.mark.parametrize("path", ENDPOINTS)
def test_anonymous_gets_401(path):
    resp = _client(_build_app(), None).get(path)
    assert resp.status_code == 401


@pytest.mark.parametrize("path", ENDPOINTS)
def test_normal_gets_403(path):
    resp = _client(_build_app(), "normal").get(path)
    assert resp.status_code == 403


@pytest.mark.parametrize("path", ENDPOINTS)
def test_professional_gets_200(path):
    resp = _client(_build_app(), "professional").get(path)
    assert resp.status_code == 200


@pytest.mark.parametrize("path", ENDPOINTS)
def test_admin_gets_200(path):
    resp = _client(_build_app(), "admin").get(path)
    assert resp.status_code == 200


# --- wiring 守卫：main.py 的 graph include 必须自带鉴权 ---------------------------


def _extract_call(source: str) -> str:
    """定位 main.py 中 include_router(graph_router ...) 调用（容忍多行换行）。"""
    import re

    match = re.search(r"include_router\(\s*graph_router\b", source)
    if match is None:
        raise AssertionError("main.py 未找到 include_router(graph_router ...) 调用")
    open_paren = source.index("(", match.start())
    depth = 0
    for i in range(open_paren, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[match.start() : i + 1]
    raise AssertionError("unbalanced parens in include_router(graph_router ...)")


def test_main_py_graph_include_carries_professional_guard():
    """主应用漏挂时本套件的自带副本会假绿，故直接核对 main.py 挂载语句。"""
    source = (BACKEND_DIR / "main.py").read_text(encoding="utf-8")
    call = _extract_call(source)
    assert "dependencies=" in call
    assert "require_professional" in call

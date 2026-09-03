"""Wave3 搜索分离 — GraphRepository.search_nodes 真实查询测试（SQLite 内存）。"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.graph_node import Node
from app.repositories.graph_repo import GraphRepository


def test_search_nodes_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Node.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime.now()
    with Session() as session:
        session.add_all(
            [
                Node(
                    id="n1",
                    node_type="paper",
                    title="肺癌研究",
                    metric_value=2020,
                    top_k_value=1.0,
                    created_at=now,
                    updated_at=now,
                ),
                Node(
                    id="n2",
                    node_type="record",
                    title="肺癌病案",
                    metric_value=30,
                    top_k_value=1.0,
                    created_at=now,
                    updated_at=now,
                ),
                Node(
                    id="n3",
                    node_type="paper",
                    title="糖尿病研究",
                    metric_value=2019,
                    top_k_value=1.0,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = GraphRepository(SimpleNamespace(), SimpleNamespace())
    res = repo.search_nodes("肺癌")

    assert len(res) == 2
    expected_keys = {"node_id", "title", "source_type", "node_type"}
    titles = [item["title"] for item in res]
    assert titles == sorted(titles)
    assert "病案" in res[0]["title"]
    assert {item["node_id"] for item in res} == {"n1", "n2"}
    for item in res:
        assert set(item.keys()) == expected_keys
        assert item["source_type"] in ("paper", "record")


@pytest.mark.skip(reason="search_graph 需 PostgreSQL tsvector，本环境无 PG")
def test_search_graph_requires_postgres():
    """全文搜索（search_graph）依赖 PostgreSQL tsvector 全文索引，
    无法在 SQLite 上运行；待具备 PG 测试库后补集成测试。
    """
    raise NotImplementedError

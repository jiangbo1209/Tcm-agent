from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.graph_edge import Edge
from app.models.graph_node import Node
from app.repositories.graph_repo import GraphRepository


def make_graph_repository() -> GraphRepository:
    return GraphRepository(SimpleNamespace(), SimpleNamespace())


def test_search_nodes_empty_query_returns_empty_list():
    repo = make_graph_repository()
    assert repo.search_nodes("") == []


def test_search_nodes_whitespace_query_returns_empty_list():
    repo = make_graph_repository()
    assert repo.search_nodes("   ") == []


def test_fetch_nodes_by_ids_none_returns_empty_list():
    repo = make_graph_repository()
    assert repo.fetch_nodes_by_ids(None) == []


def test_fetch_nodes_by_ids_empty_list_returns_empty_list():
    repo = make_graph_repository()
    assert repo.fetch_nodes_by_ids([]) == []


def test_fetch_node_by_id_hit(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Node.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime.now()
    with Session() as session:
        session.add(
            Node(
                id="n1",
                node_type="paper",
                title="肺癌研究",
                metric_value=2020,
                top_k_value=0.95,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = make_graph_repository()
    res = repo.fetch_node_by_id("n1")

    assert res is not None
    assert set(res.keys()) == {"id", "node_type", "title", "metric_value", "top_k_value"}
    assert res["id"] == "n1"
    assert res["node_type"] == "paper"
    assert res["title"] == "肺癌研究"
    assert res["metric_value"] == 2020
    assert res["top_k_value"] == 0.95


def test_fetch_edges_by_seed_hit(monkeypatch):
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
                Edge(
                    id="e1",
                    source_id="n1",
                    target_id="n2",
                    edge_type="similar",
                    similarity_score=0.87,
                    raw_score=0.87123456,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr("app.core.database.SessionLocal", Session)

    repo = make_graph_repository()
    res = repo.fetch_edges_by_seed("n1", 10)

    assert isinstance(res, list)
    assert len(res) == 1
    edge = res[0]
    assert set(edge.keys()) == {
        "id",
        "source_id",
        "target_id",
        "edge_type",
        "similarity_score",
        "raw_score",
    }
    assert edge["id"] == "e1"
    assert edge["source_id"] == "n1"
    assert edge["target_id"] == "n2"
    assert edge["edge_type"] == "similar"
    assert edge["similarity_score"] == 0.87

"""Database IO helpers for graph building (SQLAlchemy based)."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    text,
)
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from .models import Edge, Node
from .processor import (
    extract_age,
    extract_year,
    join_text,
    normalize_list_value,
    stable_node_id,
    tokenize_text,
)

Error = SQLAlchemyError

_METADATA = MetaData()

_NODES_TABLE = Table(
    "nodes",
    _METADATA,
    Column("id", String(128), primary_key=True),
    Column("node_type", String(32), nullable=False),
    Column("title", String(512), nullable=False),
    Column("metric_value", Integer, nullable=True),
    Column("top_k_value", Numeric(10, 4), nullable=False, server_default=text("1.0000")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
)

Index("idx_nodes_type", _NODES_TABLE.c.node_type)
Index("idx_nodes_metric", _NODES_TABLE.c.metric_value)

_EDGES_TABLE = Table(
    "edges",
    _METADATA,
    Column("id", String(40), primary_key=True),
    Column(
        "source_id",
        String(128),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "target_id",
        String(128),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("edge_type", String(32), nullable=False),
    Column("similarity_score", Numeric(6, 4), nullable=False),
    Column("raw_score", Numeric(12, 8), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    CheckConstraint(
        "similarity_score >= 0.0000 AND similarity_score <= 1.0000",
        name="chk_edges_score_range",
    ),
    CheckConstraint(
        "edge_type IN ('paper-paper', 'record-record', 'ref')",
        name="chk_edges_type",
    ),
)

Index("uk_edges_type_pair", _EDGES_TABLE.c.edge_type, _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.target_id, unique=True)
Index("idx_edges_source_score", _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.similarity_score)
Index("idx_edges_target_score", _EDGES_TABLE.c.target_id, _EDGES_TABLE.c.similarity_score)
Index("idx_edges_seed_expand", _EDGES_TABLE.c.source_id, _EDGES_TABLE.c.target_id)


def connect_postgres(host: str, port: int, user: str, password: str, database: str) -> Engine:
    url = URL.create(
        "postgresql+psycopg2",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    return create_engine(url, pool_pre_ping=True)


def create_graph_schema(conn: Connection) -> None:
    _METADATA.create_all(conn)


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql_text.splitlines():
        if line.strip().startswith("--"):
            continue
        current.append(line)
        candidate = "\n".join(current).strip()
        if candidate.endswith(";"):
            statements.append(candidate[:-1].strip())
            current = []
    tail = "\n".join(current).strip()
    if tail:
        statements.append(tail)
    return [s for s in statements if s]


def build_nodes(conn: Connection) -> tuple[list[Node], list[Node], dict[str, Node], dict[str, Node]]:
    paper_sql = (
        "SELECT file_uuid, title, keywords, abstract, pub_year, original_name, cleaned_title, matched_title "
        "FROM lit_metadata"
    )
    paper_rows = conn.execute(text(paper_sql)).fetchall()

    record_sql = (
        "SELECT mc.file_uuid, mc.age, mc.western_diagnosis, mc.tcm_diagnosis, "
        "mc.treatment_principle, mc.prescription, mc.present_symptoms, mc.medical_history, "
        "mc.lab_tests, mc.ultrasound, mc.followup, mc.commentary, "
        "lm.title, lm.matched_title, lm.cleaned_title, lm.original_name "
        "FROM med_case mc "
        "LEFT JOIN lit_metadata lm ON lm.file_uuid = mc.file_uuid"
    )
    record_rows = conn.execute(text(record_sql)).fetchall()

    papers: list[Node] = []
    paper_by_uuid: dict[str, Node] = {}
    for row in paper_rows:
        file_uuid, title, keywords, abstract, pub_year, original_name, cleaned_title, matched_title = row
        display_title = (title or matched_title or cleaned_title or original_name or str(file_uuid or "")).strip()
        node_id = stable_node_id("paper", str(file_uuid or display_title))
        keyword_list = normalize_list_value(keywords)
        text_blob = join_text(
            [
                title,
                matched_title,
                cleaned_title,
                original_name,
                abstract,
                " ".join(keyword_list),
            ]
        )
        tokens = tokenize_text(text_blob)
        if not tokens:
            # Skip papers with no meaningful tokens.
            continue
        node = Node(
            node_id=node_id,
            node_type="paper",
            title=display_title,
            metric_value=extract_year(str(pub_year) if pub_year is not None else None),
            tokens=tokens,
            file_uuid=str(file_uuid) if file_uuid else None,
        )
        papers.append(node)
        if file_uuid:
            if file_uuid not in paper_by_uuid or not paper_by_uuid[file_uuid].title:
                paper_by_uuid[file_uuid] = node

    records: list[Node] = []
    record_by_uuid: dict[str, Node] = {}
    for row in record_rows:
        (
            file_uuid,
            age,
            western_diag,
            tcm_diag,
            therapy,
            formula,
            present_symptoms,
            medical_history,
            lab_tests,
            ultrasound,
            followup,
            notes,
            title,
            matched_title,
            cleaned_title,
            original_name,
        ) = row
        display_title = (title or matched_title or cleaned_title or original_name or str(file_uuid or "")).strip()
        node_id = stable_node_id("record", str(file_uuid or display_title or "record"))
        text_blob = join_text(
            [
                western_diag,
                tcm_diag,
                therapy,
                formula,
                present_symptoms,
                medical_history,
                lab_tests,
                ultrasound,
                followup,
                notes,
            ]
        )
        tokens = tokenize_text(text_blob)
        if not tokens:
            # Skip records with no meaningful tokens.
            continue
        node = Node(
            node_id=node_id,
            node_type="record",
            title=display_title,
            metric_value=extract_age(str(age) if age is not None else None),
            tokens=tokens,
            file_uuid=str(file_uuid) if file_uuid else None,
        )
        records.append(node)
        if file_uuid:
            if file_uuid not in record_by_uuid or not record_by_uuid[file_uuid].title:
                record_by_uuid[file_uuid] = node

    return papers, records, paper_by_uuid, record_by_uuid


def chunked(data: Iterable, size: int):
    batch = []
    for item in data:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def write_nodes(conn: Connection, nodes: list[Node], top_k_map: dict[str, float], strategy: str) -> int:
    if not nodes:
        return 0

    if strategy == "truncate":
        conn.exec_driver_sql("DELETE FROM edges")
        conn.exec_driver_sql("DELETE FROM nodes")

    sql_insert = (
        "INSERT INTO nodes (id, node_type, title, metric_value, top_k_value) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    sql_upsert = (
        "INSERT INTO nodes (id, node_type, title, metric_value, top_k_value) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET "
        "node_type=EXCLUDED.node_type, title=EXCLUDED.title, "
        "metric_value=EXCLUDED.metric_value, top_k_value=EXCLUDED.top_k_value, "
        "updated_at=NOW()"
    )
    sql = sql_insert if strategy == "truncate" else sql_upsert

    values = [
        (node.node_id, node.node_type, node.title, node.metric_value, top_k_map.get(node.node_id, 1.0))
        for node in nodes
    ]

    for batch in chunked(values, 500):
        conn.exec_driver_sql(sql, batch)

    return len(values)


def write_edges(conn: Connection, edges: list[Edge], strategy: str) -> int:
    if not edges:
        return 0

    sql_insert = (
        "INSERT INTO edges (id, source_id, target_id, edge_type, similarity_score, raw_score) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    sql_upsert = (
        "INSERT INTO edges (id, source_id, target_id, edge_type, similarity_score, raw_score) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET "
        "similarity_score=EXCLUDED.similarity_score, raw_score=EXCLUDED.raw_score, "
        "source_id=EXCLUDED.source_id, target_id=EXCLUDED.target_id, "
        "updated_at=NOW()"
    )
    sql = sql_insert if strategy == "truncate" else sql_upsert

    values = [
        (
            edge.edge_id,
            edge.source_id,
            edge.target_id,
            edge.edge_type,
            edge.similarity_score,
            edge.raw_score,
        )
        for edge in edges
    ]

    for batch in chunked(values, 500):
        conn.exec_driver_sql(sql, batch)

    return len(values)

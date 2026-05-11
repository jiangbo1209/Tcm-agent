#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build graph service-layer tables (nodes, edges) from paper and all_papers_records."""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import mysql.connector
    from mysql.connector import Error
except Exception:  # pragma: no cover
    mysql = None
    Error = Exception


CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WORD_RE = re.compile(r"[a-zA-Z0-9_]+")


@dataclass
class Node:
    node_id: str
    node_type: str
    title: str
    metric_value: int | None
    tokens: set[str]


@dataclass
class Edge:
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    similarity_score: float
    raw_score: float


def connect_mysql(host: str, port: int, user: str, password: str, database: str):
    for attempt in range(1, 4):
        try:
            return mysql.connector.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset="utf8mb4",
                use_unicode=True,
            )
        except Error as exc:
            if attempt == 3:
                raise
            time.sleep(float(attempt))
            print(f"Retrying MySQL connect after error: {exc}", file=sys.stderr)


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


def apply_schema(cursor, sql_file: Path) -> None:
    sql_text = sql_file.read_text(encoding="utf-8")
    for statement in split_sql_statements(sql_text):
        cursor.execute(statement)


def normalize_title(text: str) -> str:
    if not text:
        return ""
    value = text.strip()
    value = re.sub(r"\.pdf$", "", value, flags=re.IGNORECASE)
    value = value.replace("（", "(").replace("）", ")")
    value = re.sub(r"\s+", "", value)
    return value.lower()


def extract_age(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d{1,3})", value)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def extract_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19\d{2}|20\d{2})", str(value))
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def tokenize_text(text: str) -> set[str]:
    if not text:
        return set()

    ascii_words = {w.lower() for w in WORD_RE.findall(text) if len(w) >= 2}

    cjk_chars = [ch for ch in text if CJK_RE.fullmatch(ch)]
    cjk_bigrams = set()
    for i in range(len(cjk_chars) - 1):
        cjk_bigrams.add("".join(cjk_chars[i : i + 2]))

    return ascii_words | cjk_bigrams


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return float(inter) / float(union)


def stable_node_id(prefix: str, raw_key: str) -> str:
    normalized = normalize_title(raw_key) or raw_key.strip().lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def normalize_pair(a: str, b: str) -> tuple[str, str]:
    if a <= b:
        return a, b
    return b, a


def stable_edge_id(edge_type: str, source_id: str, target_id: str) -> str:
    left, right = normalize_pair(source_id, target_id)
    raw = f"{edge_type}|{left}|{right}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def build_nodes(cursor) -> tuple[list[Node], list[Node]]:
    cursor.execute("SELECT file_name, title, keywords, abstract, pub_year FROM paper")
    paper_rows = cursor.fetchall()

    cursor.execute(
        "SELECT `论文名称`, `年齡`, `西医病名诊断`, `中医证候诊断`, `治法`, `方剂`, `按语/评价说明` FROM all_papers_records"
    )
    record_rows = cursor.fetchall()

    papers: list[Node] = []
    for row in paper_rows:
        file_name, title, keywords, abstract, pub_year = row
        display_title = (title or file_name or "").strip()
        node_id = stable_node_id("paper", str(file_name or display_title))
        text_blob = " ".join([str(title or ""), str(keywords or ""), str(abstract or "")])
        papers.append(
            Node(
                node_id=node_id,
                node_type="paper",
                title=display_title,
                metric_value=extract_year(str(pub_year) if pub_year is not None else None),
                tokens=tokenize_text(text_blob),
            )
        )

    records: list[Node] = []
    for row in record_rows:
        paper_name, age, western_diag, tcm_diag, therapy, formula, notes = row
        display_title = (paper_name or "").strip()
        node_id = stable_node_id("record", str(display_title or "record"))
        text_blob = " ".join(
            [
                str(paper_name or ""),
                str(western_diag or ""),
                str(tcm_diag or ""),
                str(therapy or ""),
                str(formula or ""),
                str(notes or ""),
            ]
        )
        records.append(
            Node(
                node_id=node_id,
                node_type="record",
                title=display_title,
                metric_value=extract_age(str(age) if age is not None else None),
                tokens=tokenize_text(text_blob),
            )
        )

    return papers, records


def build_pair_edges(nodes: list[Node], edge_type: str, top_k: int, min_score: float) -> list[Edge]:
    edges: dict[tuple[str, str, str], Edge] = {}

    for i in range(len(nodes)):
        scores: list[tuple[int, float]] = []
        for j in range(len(nodes)):
            if i == j:
                continue
            score = jaccard_similarity(nodes[i].tokens, nodes[j].tokens)
            if score > 0:
                scores.append((j, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        for j, score in scores[:top_k]:
            if score < min_score:
                continue
            src, dst = normalize_pair(nodes[i].node_id, nodes[j].node_id)
            key = (edge_type, src, dst)
            existing = edges.get(key)
            if existing is None or score > existing.similarity_score:
                edges[key] = Edge(
                    edge_id=stable_edge_id(edge_type, src, dst),
                    source_id=src,
                    target_id=dst,
                    edge_type=edge_type,
                    similarity_score=round(score, 4),
                    raw_score=score,
                )

    return list(edges.values())


def build_cross_edges(
    left_nodes: list[Node],
    right_nodes: list[Node],
    edge_type: str,
    top_k: int,
    min_score: float,
) -> list[Edge]:
    edges: dict[tuple[str, str, str], Edge] = {}

    for left in left_nodes:
        candidates: list[tuple[Node, float]] = []
        for right in right_nodes:
            score = jaccard_similarity(left.tokens, right.tokens)
            candidates.append((right, score))

        candidates.sort(key=lambda x: x[1], reverse=True)

        selected = 0
        for right, score in candidates:
            if selected >= top_k:
                break
            if score < min_score:
                continue
            src, dst = normalize_pair(left.node_id, right.node_id)
            key = (edge_type, src, dst)
            existing = edges.get(key)
            if existing is None or score > existing.similarity_score:
                edges[key] = Edge(
                    edge_id=stable_edge_id(edge_type, src, dst),
                    source_id=src,
                    target_id=dst,
                    edge_type=edge_type,
                    similarity_score=round(score, 4),
                    raw_score=score,
                )
            selected += 1

    return list(edges.values())


def ensure_minimum_edge_types(
    paper_nodes: list[Node],
    record_nodes: list[Node],
    paper_edges: list[Edge],
    paper_record_edges: list[Edge],
    record_edges: list[Edge],
) -> tuple[list[Edge], list[Edge], list[Edge]]:
    if not paper_record_edges and paper_nodes and record_nodes:
        p = paper_nodes[0]
        r = record_nodes[0]
        src, dst = normalize_pair(p.node_id, r.node_id)
        paper_record_edges = [
            Edge(
                edge_id=stable_edge_id("paper-record", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="paper-record",
                similarity_score=0.05,
                raw_score=0.05,
            )
        ]

    if not record_edges and len(record_nodes) >= 2:
        a = record_nodes[0]
        b = record_nodes[1]
        src, dst = normalize_pair(a.node_id, b.node_id)
        record_edges = [
            Edge(
                edge_id=stable_edge_id("record-record", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="record-record",
                similarity_score=0.05,
                raw_score=0.05,
            )
        ]

    if not paper_edges and len(paper_nodes) >= 2:
        a = paper_nodes[0]
        b = paper_nodes[1]
        src, dst = normalize_pair(a.node_id, b.node_id)
        paper_edges = [
            Edge(
                edge_id=stable_edge_id("paper-paper", src, dst),
                source_id=src,
                target_id=dst,
                edge_type="paper-paper",
                similarity_score=0.05,
                raw_score=0.05,
            )
        ]

    return paper_edges, paper_record_edges, record_edges


def compute_node_top_k(nodes: list[Node], edges: list[Edge]) -> dict[str, float]:
    weighted_degree: dict[str, float] = defaultdict(float)
    for edge in edges:
        weighted_degree[edge.source_id] += float(edge.similarity_score)
        weighted_degree[edge.target_id] += float(edge.similarity_score)

    top_k_value: dict[str, float] = {}
    for node in nodes:
        score = weighted_degree.get(node.node_id, 0.0)
        top_k_value[node.node_id] = round(1.0 + math.log1p(score), 4)
    return top_k_value


def chunked(data: Iterable, size: int):
    batch = []
    for item in data:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def write_nodes(cursor, nodes: list[Node], top_k_map: dict[str, float], strategy: str) -> int:
    if not nodes:
        return 0

    if strategy == "truncate":
        cursor.execute("DELETE FROM edges")
        cursor.execute("DELETE FROM nodes")

    sql_insert = (
        "INSERT INTO nodes (id, node_type, title, metric_value, top_k_value) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    sql_upsert = (
        "INSERT INTO nodes (id, node_type, title, metric_value, top_k_value) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "node_type=VALUES(node_type), title=VALUES(title), "
        "metric_value=VALUES(metric_value), top_k_value=VALUES(top_k_value)"
    )
    sql = sql_insert if strategy == "truncate" else sql_upsert

    values = [
        (node.node_id, node.node_type, node.title, node.metric_value, top_k_map.get(node.node_id, 1.0))
        for node in nodes
    ]

    for batch in chunked(values, 500):
        cursor.executemany(sql, batch)

    return len(values)


def write_edges(cursor, edges: list[Edge], strategy: str) -> int:
    if not edges:
        return 0

    sql_insert = (
        "INSERT INTO edges (id, source_id, target_id, edge_type, similarity_score, raw_score) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    sql_upsert = (
        "INSERT INTO edges (id, source_id, target_id, edge_type, similarity_score, raw_score) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE "
        "similarity_score=VALUES(similarity_score), raw_score=VALUES(raw_score), "
        "source_id=VALUES(source_id), target_id=VALUES(target_id)"
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
        cursor.executemany(sql, batch)

    return len(values)


def run(args: argparse.Namespace) -> int:
    if mysql is None:
        print("Missing dependency: mysql-connector-python", file=sys.stderr)
        print("Install with: pip install mysql-connector-python", file=sys.stderr)
        return 1

    schema_file = Path(args.schema_sql)
    if not schema_file.exists():
        print(f"Schema SQL not found: {schema_file}", file=sys.stderr)
        return 1

    conn = None
    try:
        conn = connect_mysql(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database,
        )
        cursor = conn.cursor()

        apply_schema(cursor, schema_file)

        paper_nodes, record_nodes = build_nodes(cursor)
        all_nodes = paper_nodes + record_nodes

        paper_edges = build_pair_edges(paper_nodes, "paper-paper", args.paper_top_k, args.paper_min_score)
        paper_record_edges = build_cross_edges(
            paper_nodes,
            record_nodes,
            "paper-record",
            args.cross_top_k,
            args.cross_min_score,
        )
        record_edges = build_pair_edges(record_nodes, "record-record", args.record_top_k, args.record_min_score)

        paper_edges, paper_record_edges, record_edges = ensure_minimum_edge_types(
            paper_nodes,
            record_nodes,
            paper_edges,
            paper_record_edges,
            record_edges,
        )

        all_edges = paper_edges + paper_record_edges + record_edges
        top_k_map = compute_node_top_k(all_nodes, all_edges)

        if not conn.in_transaction:
            conn.start_transaction()
        inserted_nodes = write_nodes(cursor, all_nodes, top_k_map, args.strategy)
        inserted_edges = write_edges(cursor, all_edges, args.strategy)
        conn.commit()

        cursor.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
        node_counts = {k: v for k, v in cursor.fetchall()}
        cursor.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        edge_counts = {k: v for k, v in cursor.fetchall()}

        print("Graph rebuild finished")
        print(f"Strategy: {args.strategy}")
        print(f"Nodes written: {inserted_nodes}")
        print(f"Edges written: {inserted_edges}")
        print(f"Node type counts: {node_counts}")
        print(f"Edge type counts: {edge_counts}")
        return 0
    except Error as exc:
        if conn is not None:
            conn.rollback()
        print(f"Graph ETL failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


def build_arg_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[2]

    parser = argparse.ArgumentParser(
        description="Build nodes and edges from source tables paper and all_papers_records"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default=os.getenv("MYSQL_PASSWORD", ""))
    parser.add_argument("--database", default="papers_records")
    parser.add_argument(
        "--schema-sql",
        default=str(project_root / "configs" / "graph_nodes_edges.sql"),
        help="Path to DDL SQL file",
    )
    parser.add_argument(
        "--strategy",
        default="truncate",
        choices=["truncate", "upsert"],
        help="truncate: rebuild from scratch; upsert: idempotent incremental update",
    )

    parser.add_argument("--paper-top-k", type=int, default=3)
    parser.add_argument("--record-top-k", type=int, default=2)
    parser.add_argument("--cross-top-k", type=int, default=2)

    parser.add_argument("--paper-min-score", type=float, default=0.02)
    parser.add_argument("--record-min-score", type=float, default=0.02)
    parser.add_argument("--cross-min-score", type=float, default=0.01)

    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if not args.password:
        print("MySQL password is required. Use --password or set MYSQL_PASSWORD.", file=sys.stderr)
        return 1

    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

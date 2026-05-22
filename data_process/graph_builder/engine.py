"""Orchestrate graph building from metadata tables."""

from __future__ import annotations

import sys
from pathlib import Path

from .database import (
    Error,
    apply_schema,
    build_nodes,
    connect_postgres,
    psycopg2,
    write_edges,
    write_nodes,
)
from .models import BuildGraphOptions
from .processor import build_pair_edges, build_ref_edges, compute_node_top_k


def run(options: BuildGraphOptions) -> int:
    if psycopg2 is None:
        print("Missing dependency: psycopg2-binary", file=sys.stderr)
        print("Install with: pip install psycopg2-binary", file=sys.stderr)
        return 1

    schema_file = Path(options.schema_sql)
    if not schema_file.exists():
        print(f"Schema SQL not found: {schema_file}", file=sys.stderr)
        return 1

    conn = None
    try:
        conn = connect_postgres(
            host=options.host,
            port=options.port,
            user=options.user,
            password=options.password,
            database=options.database,
        )
        cursor = conn.cursor()

        apply_schema(cursor, schema_file)

        paper_nodes, record_nodes, paper_by_uuid, record_by_uuid = build_nodes(cursor)
        all_nodes = paper_nodes + record_nodes

        paper_edges = build_pair_edges(
            paper_nodes,
            "paper-paper",
            options.paper_top_k,
            options.paper_min_score,
        )
        ref_edges = build_ref_edges(paper_by_uuid, record_by_uuid)
        record_edges = build_pair_edges(
            record_nodes,
            "record-record",
            options.record_top_k,
            options.record_min_score,
        )

        all_edges = paper_edges + ref_edges + record_edges
        top_k_map = compute_node_top_k(all_nodes, all_edges)

        inserted_nodes = write_nodes(cursor, all_nodes, top_k_map, options.strategy)
        inserted_edges = write_edges(cursor, all_edges, options.strategy)
        conn.commit()

        cursor.execute("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type")
        node_counts = {k: v for k, v in cursor.fetchall()}
        cursor.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        edge_counts = {k: v for k, v in cursor.fetchall()}

        print("Graph rebuild finished")
        print(f"Strategy: {options.strategy}")
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

"""Orchestrate graph building from metadata tables."""

from __future__ import annotations

import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .database import (
    build_nodes,
    connect_postgres,
    create_graph_schema,
    write_edges,
    write_nodes,
)
from .models import BuildGraphOptions
from .processor import build_pair_edges, build_ref_edges, compute_node_top_k, is_cuda_available


def run(options: BuildGraphOptions) -> int:
    engine = connect_postgres(
        host=options.host,
        port=options.port,
        user=options.user,
        password=options.password,
        database=options.database,
    )

    try:
        with engine.begin() as conn:
            create_graph_schema(conn)

            paper_nodes, record_nodes, paper_by_uuid, record_by_uuid = build_nodes(conn)
            all_nodes = paper_nodes + record_nodes

            print(f"Nodes loaded: {len(paper_nodes)} papers, {len(record_nodes)} records")

            device = options.device
            if device == "auto":
                device = "cuda" if is_cuda_available() else "cpu"
            print(f"Pair-edge backend: {device}")

            paper_edges = build_pair_edges(
                paper_nodes,
                "paper-paper",
                options.paper_top_k,
                options.paper_min_score,
                device=device,
            )
            ref_edges = build_ref_edges(paper_by_uuid, record_by_uuid)
            record_edges = build_pair_edges(
                record_nodes,
                "record-record",
                options.record_top_k,
                options.record_min_score,
                device=device,
            )

            all_edges = paper_edges + ref_edges + record_edges
            top_k_map = compute_node_top_k(all_nodes, all_edges)

            inserted_nodes = write_nodes(conn, all_nodes, top_k_map, options.strategy)
            inserted_edges = write_edges(conn, all_edges, options.strategy)

            node_counts = {
                row[0]: row[1]
                for row in conn.execute(text("SELECT node_type, COUNT(*) FROM nodes GROUP BY node_type"))
            }
            edge_counts = {
                row[0]: row[1]
                for row in conn.execute(text("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"))
            }

        print("Graph rebuild finished")
        print(f"Strategy: {options.strategy}")
        print(f"Device: {options.device}")
        print(f"Nodes written: {inserted_nodes}")
        print(f"Edges written: {inserted_edges}")
        print(f"Node type counts: {node_counts}")
        print(f"Edge type counts: {edge_counts}")
        print(f"ref edges: {len(ref_edges)}")
        return 0
    except SQLAlchemyError as exc:
        print(f"Graph ETL failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
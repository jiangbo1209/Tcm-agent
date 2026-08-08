"""Graph node/edge queries."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_

from app.models import Edge, Node


class GraphRepoMixin:
    def fetch_edges_by_seed(self, seed_id: str, limit: int) -> list[dict[str, Any]]:
        with self._get_session() as session:
            rows = (
                session.query(Edge)
                .filter(or_(Edge.source_id == seed_id, Edge.target_id == seed_id))
                .order_by(Edge.similarity_score.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "edge_type": r.edge_type,
                    "similarity_score": float(r.similarity_score) if r.similarity_score is not None else None,
                    "raw_score": float(r.raw_score) if r.raw_score is not None else None,
                }
                for r in rows
            ]

    def fetch_nodes_by_ids(self, node_ids: list[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []
        with self._get_session() as session:
            rows = (
                session.query(Node)
                .filter(Node.id.in_(node_ids))
                .all()
            )
            return [
                {
                    "id": r.id,
                    "node_type": r.node_type,
                    "title": r.title,
                    "metric_value": r.metric_value,
                    "top_k_value": float(r.top_k_value) if r.top_k_value is not None else None,
                }
                for r in rows
            ]

    def fetch_node_by_id(self, node_id: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return None
            return {
                "id": node.id,
                "node_type": node.node_type,
                "title": node.title,
                "metric_value": node.metric_value,
                "top_k_value": float(node.top_k_value) if node.top_k_value is not None else None,
            }

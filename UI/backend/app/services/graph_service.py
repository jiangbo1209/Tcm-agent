"""Business service for BFS graph expansion and node detail composition."""

from __future__ import annotations

from collections import deque
from datetime import timedelta
from typing import Any
import math
from urllib.parse import quote

from app.core.minio_utils import MinioClient
from app.models.entities import PAPER_COLUMNS, RECORD_COLUMNS
from app.repositories.graph_repository import GraphRepository


class GraphService:
    def __init__(self, repository: GraphRepository, minio_client: MinioClient | None = None) -> None:
        self._repository = repository
        self._minio_client = minio_client

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def clamp_limit(raw_limit: str | None) -> int:
        if raw_limit is None or raw_limit.strip() == "":
            return 10
        requested = int(raw_limit)
        return max(10, min(20, requested))

    @staticmethod
    def clamp_depth(raw_depth: str | None) -> int:
        if raw_depth is None or raw_depth.strip() == "":
            return 1
        requested = int(raw_depth)
        return max(1, min(3, requested))

    def expand_graph(self, seed_id: str, limit: int, depth: int) -> dict[str, list[dict[str, Any]]]:
        visited_nodes = {seed_id}
        queued_nodes = {seed_id}
        queue = deque([(seed_id, 0)])

        edge_map: dict[str, dict[str, Any]] = {}

        while queue:
            current_node, level = queue.popleft()
            if level >= depth:
                continue

            edges = self._repository.fetch_edges_by_seed(current_node, limit)
            for edge in edges:
                edge_id = str(edge["id"])
                edge_map[edge_id] = {
                    "id": edge_id,
                    "source": str(edge["source_id"]),
                    "target": str(edge["target_id"]),
                    "edge_type": edge["edge_type"],
                    "similarity_score": self._to_float(edge.get("similarity_score")),
                    "raw_score": self._to_float(edge.get("raw_score")),
                }

                for nid in (str(edge["source_id"]), str(edge["target_id"])):
                    visited_nodes.add(nid)
                    if nid not in queued_nodes:
                        queued_nodes.add(nid)
                        queue.append((nid, level + 1))

        if not visited_nodes:
            return {"nodes": [], "edges": []}

        nodes = self._repository.fetch_nodes_by_ids(sorted(visited_nodes))
        node_payload = []
        for row in nodes:
            node_type = row["node_type"]
            metric_value = row["metric_value"]
            node_payload.append(
                {
                    "id": row["id"],
                    "node_type": node_type,
                    "title": row["title"],
                    "metric_value": metric_value,
                    "publish_year": metric_value if node_type == "paper" else None,
                    "age": metric_value if node_type == "record" else None,
                    "top_k_value": self._to_float(row["top_k_value"]),
                }
            )

        return {"nodes": node_payload, "edges": list(edge_map.values())}

    def get_node_detail(self, node_id: str) -> dict[str, Any] | None:
        node = self._repository.fetch_node_by_id(node_id)
        if not node:
            return None

        node_payload = {
            "id": node["id"],
            "node_type": node["node_type"],
            "title": node["title"],
            "metric_value": node["metric_value"],
            "publish_year": node["metric_value"] if node["node_type"] == "paper" else None,
            "age": node["metric_value"] if node["node_type"] == "record" else None,
            "top_k_value": self._to_float(node["top_k_value"]),
        }

        title = str(node.get("title") or "")
        if node.get("node_type") == "paper":
            paper = self._repository.fetch_paper_detail_by_title(title)
            paper_payload = None
            if paper:
                paper_payload = {col: paper.get(col) for col in PAPER_COLUMNS}
            return {
                "node": node_payload,
                "detail_type": "paper",
                "paper": paper_payload,
            }

        record = self._repository.fetch_record_detail_by_title(title)
        record_fields = []
        if record:
            record_fields = [{"name": col, "value": record.get(col)} for col in RECORD_COLUMNS]

        return {
            "node": node_payload,
            "detail_type": "record",
            "record_fields": record_fields,
        }

    def search_graph(self, keyword: str, page: int, size: int) -> dict[str, Any]:
        normalized = keyword.strip()
        if not normalized:
            return {
                "items": [],
                "total": 0,
                "total_pages": 0,
                "page": page,
                "size": size,
            }

        safe_page = max(1, int(page))
        safe_size = max(1, min(50, int(size)))
        offset = (safe_page - 1) * safe_size

        items, total = self._repository.search_graph(normalized, safe_size, offset)
        total_pages = int(math.ceil(total / safe_size)) if safe_size > 0 else 0

        return {
            "items": items,
            "total": total,
            "total_pages": total_pages,
            "page": safe_page,
            "size": safe_size,
        }

    def get_search_index_status(self) -> dict[str, Any]:
        return self._repository.get_search_index_status()

    def get_file_url(self, node_id: str, download: bool) -> dict[str, Any]:
        if not self._minio_client:
            raise RuntimeError("minio client is not configured")

        reference = self._repository.get_file_reference_by_node_id(node_id)
        if not reference:
            raise ValueError("node not found")

        node_type = str(reference.get("node_type") or "").strip().lower()
        if node_type != "paper":
            raise ValueError("only paper nodes can generate file url")

        file_key = str(reference.get("file_key") or "").strip()
        file_name = str(reference.get("file_name") or "").strip()
        node_title = str(reference.get("node_title") or "").strip()
        object_name = file_key or file_name
        if not object_name:
            raise ValueError("file key is missing for this literature")

        object_basename = object_name.split("/")[-1] if object_name else ""
        ext = ".pdf"
        if "." in object_basename:
            suffix = object_basename.rsplit(".", 1)[-1].strip().lower()
            if suffix:
                ext = f".{suffix}"

        base_name = node_title or file_name or object_basename.rsplit(".", 1)[0] or "document"
        if not base_name.lower().endswith(ext.lower()):
            download_name = f"{base_name}{ext}"
        else:
            download_name = base_name

        disposition_kind = "attachment" if download else "inline"
        encoded_name = quote(download_name)
        content_disposition = (
            f'{disposition_kind}; filename="document{ext}"; '
            f"filename*=UTF-8''{encoded_name}"
        )

        response_headers = {
            "response-content-type": "application/pdf",
            "response-content-disposition": content_disposition,
        }

        presigned_url = self._minio_client.presigned_get_object(
            object_name=object_name,
            expires=timedelta(hours=1),
            response_headers=response_headers,
        )

        return {
            "node_id": str(reference.get("node_id") or node_id),
            "node_type": node_type,
            "bucket": self._minio_client.bucket_name,
            "object_name": object_name,
            "file_name": download_name,
            "download": download,
            "url": presigned_url,
        }

"""Business service for BFS graph expansion and node detail composition."""

from __future__ import annotations

from collections import deque
from typing import Any

from app.core.formatting import format_list_field
from app.repositories import DetailRepository, GraphRepository

RECORD_COLUMNS = [
    "论文名称",
    "年齡",
    "BMI",
    "月经情况",
    "不孕情况",
    "生活习惯",
    "刻下症",
    "既往病史",
    "生化检查",
    "超声检查",
    "复诊情况",
    "西医病名诊断",
    "中医证候诊断",
    "治法",
    "方剂",
    "针刺选穴",
    "辅助生殖技术",
    "西药",
    "疔效评价",
    "不良反应",
    "按语/评价说明",
]


class GraphService:
    def __init__(
        self,
        graph_repository: GraphRepository,
        detail_repository: DetailRepository,
    ) -> None:
        self._graph_repository = graph_repository
        self._detail_repository = detail_repository

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _map_paper_detail(self, paper: dict[str, Any]) -> dict[str, Any]:
        authors = format_list_field(paper.get("authors"), sep=", ")
        keywords = format_list_field(paper.get("keywords"), sep=", ")
        return {
            "file_uuid": paper.get("file_uuid"),
            "file_name": paper.get("original_name"),
            "file_key": paper.get("storage_path"),
            "title": paper.get("title"),
            "authors": authors,
            "abstract": paper.get("abstract"),
            "keywords": keywords,
            "journal": paper.get("journal"),
            "pub_year": paper.get("pub_year"),
            "paper_type": paper.get("paper_type"),
            "created_at": paper.get("created_at"),
            "updated_at": paper.get("updated_at"),
            "source_site": paper.get("source_site"),
            "source_url": paper.get("source_url"),
            "matched_title": paper.get("matched_title"),
            "is_exact_match": paper.get("is_exact_match"),
            "crawl_status": paper.get("crawl_status"),
            "error_message": paper.get("error_message"),
        }

    @staticmethod
    def _build_record_fields(record: dict[str, Any] | None, fallback_title: str) -> list[dict[str, Any]]:
        if not record:
            return []
        title_value = record.get("literature_title") or fallback_title
        record_map = {
            "论文名称": title_value,
            "年齡": record.get("age"),
            "BMI": record.get("bmi"),
            "月经情况": record.get("menstruation"),
            "不孕情况": record.get("infertility"),
            "生活习惯": record.get("lifestyle"),
            "刻下症": record.get("present_symptoms"),
            "既往病史": record.get("medical_history"),
            "生化检查": record.get("lab_tests"),
            "超声检查": record.get("ultrasound"),
            "复诊情况": record.get("followup"),
            "西医病名诊断": record.get("western_diagnosis"),
            "中医证候诊断": record.get("tcm_diagnosis"),
            "治法": record.get("treatment_principle"),
            "方剂": record.get("prescription"),
            "针刺选穴": record.get("acupoints"),
            "辅助生殖技术": record.get("assisted_reproduction"),
            "西药": record.get("western_medicine"),
            "疔效评价": record.get("efficacy"),
            "不良反应": record.get("adverse_reactions"),
            "按语/评价说明": record.get("commentary"),
        }
        return [{"name": col, "value": record_map.get(col)} for col in RECORD_COLUMNS]

    def expand_graph(self, seed_id: str, limit: int, depth: int) -> dict[str, list[dict[str, Any]]]:
        visited_nodes = {seed_id}
        queued_nodes = {seed_id}
        queue = deque([(seed_id, 0)])

        edge_map: dict[str, dict[str, Any]] = {}

        while queue:
            current_node, level = queue.popleft()
            if level >= depth:
                continue

            edges = self._graph_repository.fetch_edges_by_seed(current_node, limit)
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

        nodes = self._graph_repository.fetch_nodes_by_ids(sorted(visited_nodes))
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
        node = self._graph_repository.fetch_node_by_id(node_id)
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
            paper = self._detail_repository.fetch_paper_detail_by_title(title)
            paper_payload = None
            if paper:
                paper_payload = self._map_paper_detail(paper)
            return {
                "node": node_payload,
                "detail_type": "paper",
                "paper": paper_payload,
            }

        record = self._detail_repository.fetch_record_detail_by_title(title)
        record_fields = self._build_record_fields(record, title)
        record_summary = None
        if record:
            record_summary = {
                "diagnosis": record.get("western_diagnosis"),
                "syndrome": record.get("tcm_diagnosis"),
                "treatment_principle": record.get("treatment_principle"),
                "prescription": record.get("prescription"),
            }

        return {
            "node": node_payload,
            "detail_type": "record",
            "record_fields": record_fields,
            "record": record_summary,
        }

    def get_detail_by_file_uuid(self, file_uuid: str, source_type: str) -> dict[str, Any] | None:
        if not file_uuid:
            return None
        node_payload = {"id": file_uuid, "node_type": source_type, "title": None,
                        "metric_value": None, "publish_year": None, "age": None, "top_k_value": None}
        if source_type == "paper":
            paper = self._detail_repository.fetch_paper_detail_by_file_uuid(file_uuid)
            paper_payload = self._map_paper_detail(paper) if paper else None
            if paper:
                title = paper.get("title") or paper.get("matched_title") or paper.get("cleaned_title") or paper.get("original_name")
                node_payload["title"] = title
                node_payload["publish_year"] = paper.get("pub_year")
            return {"node": node_payload, "detail_type": "paper", "paper": paper_payload}
        record = self._detail_repository.fetch_record_detail_by_file_uuid(file_uuid)
        if record:
            title = record.get("literature_title") or file_uuid
            node_payload["title"] = title
        record_fields = self._build_record_fields(record, node_payload.get("title") or "")
        record_summary = None
        if record:
            record_summary = {
                "diagnosis": record.get("western_diagnosis"),
                "syndrome": record.get("tcm_diagnosis"),
                "treatment_principle": record.get("treatment_principle"),
                "prescription": record.get("prescription"),
            }
        return {"node": node_payload, "detail_type": "record", "record_fields": record_fields, "record": record_summary}

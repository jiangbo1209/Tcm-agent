"""RAGFlow retrieval HTTP client."""

from __future__ import annotations

from typing import Any

import requests

from agent.config import AgentSettings, get_agent_settings
from agent.schemas.query import QueryPlan


class RagflowApiError(RuntimeError):
    """Raised when RAGFlow returns a failed response."""


class RagflowClient:
    """Client for RAGFlow `POST /api/v1/retrieval`."""

    def __init__(self, settings: AgentSettings | None = None) -> None:
        self._settings = settings or get_agent_settings()
        self._base_url = self._settings.ragflow_base_url.rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._settings.ragflow_api_key:
            headers["Authorization"] = f"Bearer {self._settings.ragflow_api_key}"
        return headers

    def search(self, query_plan: QueryPlan) -> tuple[list[dict[str, Any]], int]:
        dataset_ids = self._dataset_ids_for_plan(query_plan)
        body = self._build_retrieval_body(query_plan, dataset_ids)
        response = requests.post(
            f"{self._base_url}/api/v1/retrieval",
            headers=self._headers,
            json=body,
            timeout=self._settings.retrieval_timeout_seconds,
        )
        payload = self._unwrap(response)
        data = payload.get("data") or {}
        chunks = data.get("chunks") if isinstance(data, dict) else data
        if not isinstance(chunks, list):
            chunks = []

        doc_names = self._doc_names_by_id(data)
        normalized = [
            self._normalize_chunk(chunk, doc_names)
            for chunk in chunks
            if isinstance(chunk, dict)
        ]
        total = data.get("total") if isinstance(data, dict) else None
        return normalized, int(total if total is not None else len(normalized))

    def _build_retrieval_body(self, query_plan: QueryPlan, dataset_ids: list[str]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "question": query_plan.rewritten_query,
            "dataset_ids": dataset_ids,
            "page": 1,
            "page_size": query_plan.top_k,
            "similarity_threshold": self._settings.ragflow_similarity_threshold,
            "vector_similarity_weight": self._settings.ragflow_vector_similarity_weight,
            "top_k": self._settings.ragflow_top_k_candidates,
            "keyword": self._settings.ragflow_keyword,
            "highlight": self._settings.ragflow_highlight,
            "use_kg": self._settings.ragflow_use_kg,
            "toc_enhance": self._settings.ragflow_toc_enhance,
        }
        metadata_condition = self._metadata_condition(query_plan.filters)
        if metadata_condition:
            body["metadata_condition"] = metadata_condition
        return body

    def _dataset_ids_for_plan(self, query_plan: QueryPlan) -> list[str]:
        settings = self._settings
        if query_plan.search_type == "literature" or query_plan.source_type == "paper":
            dataset_ids = [settings.ragflow_literature_dataset_id]
        elif query_plan.search_type == "case" or query_plan.source_type == "record":
            dataset_ids = [settings.ragflow_case_dataset_id]
        elif query_plan.search_type == "guideline" or query_plan.source_type == "guideline":
            dataset_ids = [settings.ragflow_guideline_dataset_id]
        else:
            dataset_ids = [
                settings.ragflow_literature_dataset_id,
                settings.ragflow_case_dataset_id,
            ]

        cleaned = [dataset_id for dataset_id in dataset_ids if dataset_id]
        if not cleaned:
            raise RagflowApiError(f"Missing RAGFlow dataset id for search_type={query_plan.search_type}")
        return cleaned

    def _metadata_condition(self, filters: dict[str, list[str]]) -> dict[str, Any] | None:
        conditions = []
        for name, values in filters.items():
            for value in values:
                conditions.append(
                    {
                        "name": name,
                        "comparison_operator": "=",
                        "value": str(value),
                    }
                )
        if not conditions:
            return None
        return {"logic": "and", "conditions": conditions}

    def _normalize_chunk(self, chunk: dict[str, Any], doc_names: dict[str, str]) -> dict[str, Any]:
        chunk_metadata = self._chunk_metadata(chunk)
        document_id = chunk.get("document_id") or chunk.get("doc_id")
        dataset_id = chunk.get("kb_id") or chunk.get("dataset_id")
        chunk_id = chunk.get("id") or chunk.get("chunk_id")
        title = (
            chunk.get("document_keyword")
            or chunk.get("doc_name")
            or chunk.get("document_name")
            or chunk_metadata.get("title")
            or chunk_metadata.get("literature_title")
            or doc_names.get(str(document_id))
            or "Untitled source"
        )
        file_uuid = chunk.get("file_uuid") or chunk_metadata.get("file_uuid")
        source_type = self._source_type_for_dataset(str(dataset_id or ""))
        metadata = {
            **chunk_metadata,
            **chunk,
            "source_type": source_type,
            "title": title,
            "file_uuid": file_uuid,
            "document_id": document_id,
            "dataset_id": dataset_id,
            "chunk_id": chunk_id,
            "highlight": chunk.get("highlight"),
        }
        return {
            "source_type": source_type,
            "title": title,
            "file_uuid": file_uuid,
            "document_id": document_id,
            "dataset_id": dataset_id,
            "chunk_id": chunk_id,
            "chunk": chunk.get("content"),
            "score": chunk.get("similarity"),
            "metadata": metadata,
        }

    def _chunk_metadata(self, chunk: dict[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        for key in ("metadata", "document_metadata", "meta_fields"):
            value = chunk.get(key)
            if isinstance(value, dict):
                metadata.update(value)
        return metadata

    def _doc_names_by_id(self, data: Any) -> dict[str, str]:
        if not isinstance(data, dict):
            return {}
        doc_aggs = data.get("doc_aggs") or []
        if not isinstance(doc_aggs, list):
            return {}
        names = {}
        for item in doc_aggs:
            if not isinstance(item, dict):
                continue
            doc_id = item.get("doc_id") or item.get("document_id")
            doc_name = item.get("doc_name") or item.get("document_name")
            if doc_id and doc_name:
                names[str(doc_id)] = str(doc_name)
        return names

    def _source_type_for_dataset(self, dataset_id: str) -> str:
        settings = self._settings
        if dataset_id == settings.ragflow_literature_dataset_id:
            return "paper"
        if dataset_id == settings.ragflow_case_dataset_id:
            return "record"
        if dataset_id == settings.ragflow_guideline_dataset_id:
            return "guideline"
        return "unknown"

    @staticmethod
    def _unwrap(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RagflowApiError(f"RAGFlow returned non-JSON response: {response.text[:500]}") from exc

        if not response.ok:
            raise RagflowApiError(f"RAGFlow HTTP {response.status_code}: {payload}")

        code = payload.get("code")
        if code not in (None, 0, "0"):
            message = payload.get("message") or payload.get("msg") or payload
            raise RagflowApiError(f"RAGFlow API error: {message}")
        return payload

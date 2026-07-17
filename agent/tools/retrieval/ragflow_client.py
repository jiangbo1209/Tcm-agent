"""RAGFlow retrieval HTTP client."""

from __future__ import annotations

import json
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
        doc_metadata = self._doc_metadata_by_id(chunks)
        normalized = [
            self._normalize_chunk(chunk, doc_names, doc_metadata)
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

    def _normalize_chunk(
        self,
        chunk: dict[str, Any],
        doc_names: dict[str, str],
        doc_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        chunk_metadata = self._chunk_metadata(chunk)
        document_id = chunk.get("document_id") or chunk.get("doc_id")
        dataset_id = chunk.get("kb_id") or chunk.get("dataset_id")
        chunk_id = chunk.get("id") or chunk.get("chunk_id")
        document_metadata = ((doc_metadata or {}).get(str(document_id)) if document_id else {}) or {}
        title = (
            chunk.get("document_keyword")
            or chunk.get("doc_name")
            or chunk.get("document_name")
            or chunk_metadata.get("title")
            or chunk_metadata.get("literature_title")
            or document_metadata.get("title")
            or document_metadata.get("literature_title")
            or doc_names.get(str(document_id))
            or "Untitled source"
        )
        file_uuid = self._file_uuid_from(chunk, chunk_metadata, document_metadata)
        source_type = self._source_type_for_dataset(str(dataset_id or ""))
        metadata = {
            **document_metadata,
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
            elif isinstance(value, str):
                try:
                    parsed = json.loads(value)
                except ValueError:
                    parsed = None
                if isinstance(parsed, dict):
                    metadata.update(parsed)
        return metadata

    @staticmethod
    def _file_uuid_from(chunk: dict[str, Any], metadata: dict[str, Any], document_metadata: dict[str, Any] | None = None) -> Any:
        candidates = (
            "file_uuid",
            "fileUuid",
            "fileUUID",
            "file_id",
            "fileId",
            "fileID",
            "uuid",
        )
        for container in (chunk, metadata, document_metadata or {}):
            for key in candidates:
                value = container.get(key)
                if value:
                    return value

        for nested_key in ("core_file", "file", "source_file"):
            nested = metadata.get(nested_key) or chunk.get(nested_key) or (document_metadata or {}).get(nested_key)
            if isinstance(nested, dict):
                for key in candidates:
                    value = nested.get(key)
                    if value:
                        return value
        return None

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

    def _doc_metadata_by_id(self, chunks: list[Any]) -> dict[str, dict[str, Any]]:
        metadata_by_id: dict[str, dict[str, Any]] = {}
        seen: set[tuple[str, str]] = set()
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            if self._file_uuid_from(chunk, self._chunk_metadata(chunk)):
                continue
            document_id = chunk.get("document_id") or chunk.get("doc_id")
            dataset_id = chunk.get("kb_id") or chunk.get("dataset_id")
            if not document_id or not dataset_id:
                continue
            key = (str(dataset_id), str(document_id))
            if key in seen:
                continue
            seen.add(key)
            doc_metadata = self._fetch_document_metadata(key[0], key[1])
            if doc_metadata:
                metadata_by_id[key[1]] = doc_metadata
        return metadata_by_id

    def _fetch_document_metadata(self, dataset_id: str, document_id: str) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self._base_url}/api/v1/datasets/{dataset_id}/documents",
                headers=self._headers,
                params={"id": document_id},
                timeout=self._settings.retrieval_timeout_seconds,
            )
            payload = self._unwrap(response)
        except Exception:
            return {}

        data = payload.get("data") or {}
        docs = data.get("docs") if isinstance(data, dict) else None
        if not isinstance(docs, list):
            return {}

        for doc in docs:
            if not isinstance(doc, dict) or str(doc.get("id")) != document_id:
                continue
            raw_metadata = doc.get("meta_fields") or doc.get("metadata") or {}
            metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
            return {
                **metadata,
                "document_name": doc.get("name") or doc.get("location"),
                "document_location": doc.get("location"),
            }
        return {}

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

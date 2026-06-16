"""Small HTTP client for the RAGFlow dataset document API."""

from __future__ import annotations

from typing import Any

import requests


class RagflowApiError(RuntimeError):
    """Raised when RAGFlow returns a failed response."""


class RagflowClient:
    def __init__(self, base_url: str, api_key: str, dataset_id: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.dataset_id = dataset_id
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

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

    def upload_document(self, filename: str, content: bytes, content_type: str) -> str:
        url = self._url(f"/api/v1/datasets/{self.dataset_id}/documents")
        files = {"file": (filename, content, content_type)}
        response = requests.post(url, headers=self._headers, files=files, timeout=self.timeout)
        payload = self._unwrap(response)
        data = payload.get("data")

        if isinstance(data, list) and data:
            first = data[0]
            doc_id = first.get("id") or first.get("document_id")
        elif isinstance(data, dict):
            doc_id = data.get("id") or data.get("document_id")
        else:
            doc_id = None

        if not doc_id:
            raise RagflowApiError(f"Upload succeeded but document id was not found: {payload}")
        return str(doc_id)

    def update_document_metadata(self, document_id: str, meta_fields: dict[str, str]) -> None:
        url = self._url(f"/api/v1/datasets/{self.dataset_id}/documents/{document_id}")
        body = {"meta_fields": meta_fields}
        response = requests.put(
            url,
            headers={**self._headers, "Content-Type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        self._unwrap(response)

    def parse_documents(self, document_ids: list[str]) -> None:
        if not document_ids:
            return
        url = self._url(f"/api/v1/datasets/{self.dataset_id}/chunks")
        body = {"document_ids": document_ids}
        response = requests.post(
            url,
            headers={**self._headers, "Content-Type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        self._unwrap(response)


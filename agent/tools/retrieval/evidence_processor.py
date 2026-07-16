"""Evidence processor for retrieval results."""

from __future__ import annotations

from typing import Any

from agent.schemas.retrieval import Evidence


class EvidenceProcessor:
    def process(self, raw_items: list[dict[str, Any]], max_items: int) -> list[Evidence]:
        selected: list[Evidence] = []
        seen: set[str] = set()
        for item in raw_items:
            evidence = self._to_evidence(item)
            key = evidence.file_uuid or evidence.document_id or f"{evidence.source_type}:{evidence.title}:{evidence.chunk}"
            if key in seen:
                continue
            seen.add(key)
            evidence.citation_index = len(selected) + 1
            selected.append(evidence)
            if len(selected) >= max_items:
                break
        return selected

    def _to_evidence(self, item: dict[str, Any]) -> Evidence:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else dict(item)
        return Evidence(
            citation_index=item.get("citation_index") or metadata.get("citation_index"),
            source_type=item.get("source_type") or metadata.get("source_type") or "unknown",
            title=item.get("title") or metadata.get("title") or "Untitled source",
            file_uuid=self._file_uuid_from(item, metadata),
            document_id=item.get("document_id") or metadata.get("document_id"),
            dataset_id=item.get("dataset_id") or metadata.get("dataset_id"),
            chunk_id=item.get("chunk_id") or metadata.get("chunk_id"),
            chunk=item.get("chunk") or item.get("content") or item.get("abstract"),
            score=item.get("score"),
            metadata=metadata,
        )

    @staticmethod
    def _file_uuid_from(item: dict[str, Any], metadata: dict[str, Any]) -> Any:
        candidates = (
            "file_uuid",
            "fileUuid",
            "fileUUID",
            "file_id",
            "fileId",
            "fileID",
            "uuid",
        )
        for container in (item, metadata):
            for key in candidates:
                value = container.get(key)
                if value:
                    return value

        for nested_key in ("core_file", "file", "source_file"):
            nested = metadata.get(nested_key) or item.get(nested_key)
            if isinstance(nested, dict):
                for key in candidates:
                    value = nested.get(key)
                    if value:
                        return value
        return None

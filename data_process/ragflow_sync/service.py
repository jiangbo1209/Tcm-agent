"""Synchronization workflow from local data sources to RAGFlow."""

from __future__ import annotations

from typing import Literal

from .document_builder import (
    build_case_markdown,
    case_filename,
    case_metadata,
    content_hash,
    literature_filename,
    literature_metadata,
)
from .models import CaseSource, LiteratureSource, SyncResult

SyncSource = Literal["all", "literature", "case"]


class RagflowSyncService:
    def __init__(
        self,
        *,
        repository,
        object_store,
        ragflow_client,
        dataset_id: str,
        domain: str,
        parse_after_upload: bool = True,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.ragflow_client = ragflow_client
        self.dataset_id = dataset_id
        self.domain = domain
        self.parse_after_upload = parse_after_upload

    def sync(self, source: SyncSource, *, limit: int | None = None, dry_run: bool = False, force: bool = False) -> list[SyncResult]:
        self.repository.ensure_schema()
        results: list[SyncResult] = []
        if source in ("all", "literature"):
            for item in self.repository.fetch_literature(limit):
                results.append(self.sync_literature(item, dry_run=dry_run, force=force))
        if source in ("all", "case"):
            for item in self.repository.fetch_cases(limit):
                results.append(self.sync_case(item, dry_run=dry_run, force=force))
        return results

    def sync_literature(self, source: LiteratureSource, *, dry_run: bool, force: bool) -> SyncResult:
        meta = literature_metadata(source, self.domain)
        existing = self.repository.get_status("literature", source.file_uuid, self.dataset_id)
        if existing and existing.sync_status == "parsed" and not force:
            return SyncResult("literature", source.file_uuid, "skipped", existing.document_id, "already parsed")

        if dry_run:
            return SyncResult("literature", source.file_uuid, "would_upload", None, source.storage_path)

        document_id = existing.document_id if existing and force is False else None
        try:
            pdf_bytes = self.object_store.get_object(source.storage_path)
            current_hash = content_hash(pdf_bytes, meta)
            if existing and existing.content_hash == current_hash and existing.sync_status in {"uploaded", "parsed"} and not force:
                return SyncResult("literature", source.file_uuid, "skipped", existing.document_id, "content unchanged")

            document_id = self.ragflow_client.upload_document(
                filename=literature_filename(source),
                content=pdf_bytes,
                content_type="application/pdf",
            )
            self.ragflow_client.update_document_metadata(document_id, meta)
            status = "uploaded"
            if self.parse_after_upload:
                self.ragflow_client.parse_documents([document_id])
                status = "parsed"

            self.repository.upsert_status(
                source_type="literature",
                file_uuid=source.file_uuid,
                dataset_id=self.dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status=status,
            )
            return SyncResult("literature", source.file_uuid, status, document_id)
        except Exception as exc:
            self.repository.upsert_status(
                source_type="literature",
                file_uuid=source.file_uuid,
                dataset_id=self.dataset_id,
                document_id=document_id,
                content_hash=None,
                sync_status="failed",
                error_message=str(exc),
            )
            return SyncResult("literature", source.file_uuid, "failed", document_id, str(exc))

    def sync_case(self, source: CaseSource, *, dry_run: bool, force: bool) -> SyncResult:
        markdown = build_case_markdown(source)
        meta = case_metadata(source, self.domain)
        current_hash = content_hash(markdown, meta)
        existing = self.repository.get_status("case", source.file_uuid, self.dataset_id)
        if existing and existing.sync_status == "parsed" and existing.content_hash == current_hash and not force:
            return SyncResult("case", source.file_uuid, "skipped", existing.document_id, "content unchanged")

        if dry_run:
            return SyncResult("case", source.file_uuid, "would_upload", None, case_filename(source))

        document_id = existing.document_id if existing and force is False else None
        try:
            document_id = self.ragflow_client.upload_document(
                filename=case_filename(source),
                content=markdown.encode("utf-8"),
                content_type="text/markdown; charset=utf-8",
            )
            self.ragflow_client.update_document_metadata(document_id, meta)
            status = "uploaded"
            if self.parse_after_upload:
                self.ragflow_client.parse_documents([document_id])
                status = "parsed"

            self.repository.upsert_status(
                source_type="case",
                file_uuid=source.file_uuid,
                dataset_id=self.dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status=status,
            )
            return SyncResult("case", source.file_uuid, status, document_id)
        except Exception as exc:
            self.repository.upsert_status(
                source_type="case",
                file_uuid=source.file_uuid,
                dataset_id=self.dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status="failed",
                error_message=str(exc),
            )
            return SyncResult("case", source.file_uuid, "failed", document_id, str(exc))


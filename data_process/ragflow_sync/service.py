"""Synchronization workflow from local data sources to RAGFlow."""

from __future__ import annotations

from typing import Literal

from .document_builder import (
    build_case_markdown,
    case_filename,
    case_metadata,
    content_hash,
    guideline_filename,
    guideline_metadata,
    literature_filename,
    literature_metadata,
)
from .models import CaseSource, GuidelineSource, LiteratureSource, SyncResult

SyncSource = Literal["all", "literature", "case", "guideline"]
SYNC_SOURCES: tuple[Literal["literature", "case", "guideline"], ...] = (
    "literature",
    "case",
    "guideline",
)


class RagflowSyncService:
    def __init__(
        self,
        *,
        repository,
        object_store,
        ragflow_clients: dict[str, object],
        dataset_ids: dict[str, str],
        domain: str,
        parse_after_upload: bool = True,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.ragflow_clients = ragflow_clients
        self.dataset_ids = dataset_ids
        self.domain = domain
        self.parse_after_upload = parse_after_upload

    def sync(
        self,
        source: SyncSource,
        *,
        limit: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        only_failed: bool = False,
    ) -> list[SyncResult]:
        self.repository.ensure_schema()
        results: list[SyncResult] = []
        if source in ("all", "literature"):
            dataset_id = self._dataset_id("literature")
            for item in self.repository.fetch_literature(limit, only_failed=only_failed, dataset_id=dataset_id, force=force):
                results.append(self.sync_literature(item, dry_run=dry_run, force=force))
        if source in ("all", "case"):
            dataset_id = self._dataset_id("case")
            for item in self.repository.fetch_cases(limit, only_failed=only_failed, dataset_id=dataset_id, force=force):
                results.append(self.sync_case(item, dry_run=dry_run, force=force))
        if source == "guideline":
            dataset_id = self._dataset_id("guideline")
            for item in self.repository.fetch_guidelines(limit, only_failed=only_failed, dataset_id=dataset_id, force=force):
                results.append(self.sync_guideline(item, dry_run=dry_run, force=force))
        return results

    def sync_literature(self, source: LiteratureSource, *, dry_run: bool, force: bool) -> SyncResult:
        meta = literature_metadata(source, self.domain)
        dataset_id = self._dataset_id("literature")
        existing = self.repository.get_status("literature", source.file_uuid, dataset_id)
        if existing and existing.sync_status == "parsed" and not force:
            return SyncResult("literature", source.file_uuid, "skipped", existing.document_id, "already parsed", "precheck")

        if dry_run:
            return SyncResult("literature", source.file_uuid, "skipped", None, f"dry-run {source.storage_path}", "dry_run")

        document_id = existing.document_id if existing and force is False else None
        try:
            pdf_bytes = self.object_store.get_object(source.storage_path)
            self._validate_pdf_bytes(source.storage_path, pdf_bytes)
            current_hash = content_hash(pdf_bytes, meta)
            if existing and existing.content_hash == current_hash and existing.sync_status in {"uploaded", "parsed"} and not force:
                return SyncResult("literature", source.file_uuid, "skipped", existing.document_id, "content unchanged", "precheck")

            if not self._can_reuse_failed_document(existing):
                try:
                    document_id = self._ragflow_client("literature").upload_document(
                        filename=literature_filename(source),
                        content=pdf_bytes,
                        content_type="application/pdf",
                    )
                except Exception as exc:
                    raise RuntimeError(f"upload failed: {exc}") from exc

            if self._needs_metadata_retry(existing):
                try:
                    self._ragflow_client("literature").update_document_metadata(document_id, meta)
                except Exception as exc:
                    raise RuntimeError(f"metadata failed: {exc}") from exc

            status = "uploaded"
            stage = "metadata"
            if self.parse_after_upload:
                try:
                    self._ragflow_client("literature").parse_documents([document_id])
                except Exception as exc:
                    raise RuntimeError(f"parse failed: {exc}") from exc
                status = "parsed"
                stage = "parse"

            self.repository.upsert_status(
                source_type="literature",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status=status,
            )
            self.repository.mark_ragflow_done(source.file_uuid)
            return SyncResult("literature", source.file_uuid, status, document_id, stage=stage)
        except Exception as exc:
            self.repository.upsert_status(
                source_type="literature",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=None,
                sync_status="failed",
                error_message=str(exc),
            )
            return SyncResult("literature", source.file_uuid, "failed", document_id, str(exc), self._infer_stage(str(exc)))

    def sync_case(self, source: CaseSource, *, dry_run: bool, force: bool) -> SyncResult:
        markdown = build_case_markdown(source)
        meta = case_metadata(source, self.domain)
        current_hash = content_hash(markdown, meta)
        dataset_id = self._dataset_id("case")
        existing = self.repository.get_status("case", source.file_uuid, dataset_id)
        if existing and existing.sync_status == "parsed" and existing.content_hash == current_hash and not force:
            return SyncResult("case", source.file_uuid, "skipped", existing.document_id, "content unchanged", "precheck")

        if dry_run:
            return SyncResult("case", source.file_uuid, "skipped", None, f"dry-run {case_filename(source)}", "dry_run")

        document_id = existing.document_id if existing and force is False else None
        try:
            if not self._can_reuse_failed_document(existing):
                try:
                    document_id = self._ragflow_client("case").upload_document(
                        filename=case_filename(source),
                        content=markdown.encode("utf-8"),
                        content_type="text/markdown; charset=utf-8",
                    )
                except Exception as exc:
                    raise RuntimeError(f"upload failed: {exc}") from exc

            if self._needs_metadata_retry(existing):
                try:
                    self._ragflow_client("case").update_document_metadata(document_id, meta)
                except Exception as exc:
                    raise RuntimeError(f"metadata failed: {exc}") from exc

            status = "uploaded"
            stage = "metadata"
            if self.parse_after_upload:
                try:
                    self._ragflow_client("case").parse_documents([document_id])
                except Exception as exc:
                    raise RuntimeError(f"parse failed: {exc}") from exc
                status = "parsed"
                stage = "parse"

            self.repository.upsert_status(
                source_type="case",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status=status,
            )
            self.repository.mark_ragflow_done(source.file_uuid)
            return SyncResult("case", source.file_uuid, status, document_id, stage=stage)
        except Exception as exc:
            self.repository.upsert_status(
                source_type="case",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status="failed",
                error_message=str(exc),
            )
            return SyncResult("case", source.file_uuid, "failed", document_id, str(exc), self._infer_stage(str(exc)))

    def sync_guideline(self, source: GuidelineSource, *, dry_run: bool, force: bool) -> SyncResult:
        meta = guideline_metadata(source, self.domain)
        dataset_id = self._dataset_id("guideline")
        existing = self.repository.get_status("guideline", source.file_uuid, dataset_id)
        if existing and existing.sync_status == "parsed" and not force:
            return SyncResult("guideline", source.file_uuid, "skipped", existing.document_id, "already parsed", "precheck")

        if dry_run:
            return SyncResult("guideline", source.file_uuid, "skipped", None, f"dry-run {source.storage_path}", "dry_run")

        document_id = existing.document_id if existing and force is False else None
        try:
            pdf_bytes = self.object_store.get_object(source.storage_path)
            self._validate_pdf_bytes(source.storage_path, pdf_bytes)
            current_hash = content_hash(pdf_bytes, meta)
            if existing and existing.content_hash == current_hash and existing.sync_status in {"uploaded", "parsed"} and not force:
                return SyncResult("guideline", source.file_uuid, "skipped", existing.document_id, "content unchanged", "precheck")

            if not self._can_reuse_failed_document(existing):
                try:
                    document_id = self._ragflow_client("guideline").upload_document(
                        filename=guideline_filename(source),
                        content=pdf_bytes,
                        content_type="application/pdf",
                    )
                except Exception as exc:
                    raise RuntimeError(f"upload failed: {exc}") from exc

            if self._needs_metadata_retry(existing):
                try:
                    self._ragflow_client("guideline").update_document_metadata(document_id, meta)
                except Exception as exc:
                    raise RuntimeError(f"metadata failed: {exc}") from exc

            status = "uploaded"
            stage = "metadata"
            if self.parse_after_upload:
                try:
                    self._ragflow_client("guideline").parse_documents([document_id])
                except Exception as exc:
                    raise RuntimeError(f"parse failed: {exc}") from exc
                status = "parsed"
                stage = "parse"

            self.repository.upsert_status(
                source_type="guideline",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=current_hash,
                sync_status=status,
            )
            self.repository.mark_ragflow_done(source.file_uuid)
            return SyncResult("guideline", source.file_uuid, status, document_id, stage=stage)
        except Exception as exc:
            self.repository.upsert_status(
                source_type="guideline",
                file_uuid=source.file_uuid,
                dataset_id=dataset_id,
                document_id=document_id,
                content_hash=None,
                sync_status="failed",
                error_message=str(exc),
            )
            return SyncResult("guideline", source.file_uuid, "failed", document_id, str(exc), self._infer_stage(str(exc)))

    def _dataset_id(self, source_type: str) -> str:
        dataset_id = self.dataset_ids.get(source_type, "")
        if not dataset_id:
            raise ValueError(f"Dataset id is required for source={source_type}")
        return dataset_id

    def _ragflow_client(self, source_type: str):
        client = self.ragflow_clients.get(source_type)
        if client is None:
            raise ValueError(f"RAGFlow client is required for source={source_type}")
        return client

    @staticmethod
    def _infer_stage(message: str) -> str:
        if message.startswith("upload failed:"):
            return "upload"
        if message.startswith("metadata failed:"):
            return "metadata"
        if message.startswith("parse failed:"):
            return "parse"
        return "unknown"

    @staticmethod
    def _can_reuse_failed_document(existing) -> bool:
        if not existing or existing.sync_status != "failed" or not existing.document_id:
            return False
        message = existing.error_message or ""
        return message.startswith("metadata failed:") or message.startswith("parse failed:")

    @staticmethod
    def _needs_metadata_retry(existing) -> bool:
        if not existing:
            return True
        if existing.sync_status != "failed":
            return True
        message = existing.error_message or ""
        return not message.startswith("parse failed:")

    @staticmethod
    def _validate_pdf_bytes(storage_path: str, content: bytes) -> None:
        if not content:
            raise RuntimeError(f"upload failed: COS object is empty: {storage_path}")
        if not content.startswith(b"%PDF"):
            raise RuntimeError(f"upload failed: COS object is not a PDF file: {storage_path}")


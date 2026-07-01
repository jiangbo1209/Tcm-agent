"""Upload business logic: UUID generation, MinIO upload, DB insert."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from .minio_client import MinioClient
from .models import CoreFile
from .repository import CoreFileRepository

LOGGER = logging.getLogger("pdf_upload")

DOCUMENT_TYPE_PREFIX = {
    0: "literature",
    1: "case",
    2: "guideline",
}


class UploadService:
    def __init__(
        self,
        repository: CoreFileRepository,
        minio_client: MinioClient,
        max_file_size_mb: int = 100,
        allowed_extensions: tuple[str, ...] = (".pdf",),
        batch_concurrency: int = 5,
    ) -> None:
        self._repository = repository
        self._minio = minio_client
        self.max_file_size_mb = max_file_size_mb
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.allowed_extensions = allowed_extensions
        self.batch_concurrency = max(1, batch_concurrency)

    async def upload(self, original_name: str, content: bytes, document_type: int = 0) -> dict:
        if document_type not in DOCUMENT_TYPE_PREFIX:
            raise ValueError("Invalid document_type, expected 0, 1, or 2")

        # Reject duplicate filename
        if await self._repository.exists_by_original_name(original_name, document_type):
            raise ValueError(f"File already exists: {original_name}")

        file_uuid = str(uuid.uuid4())
        storage_path = f"{DOCUMENT_TYPE_PREFIX[document_type]}/{file_uuid}/{original_name}"

        # 1. Upload to MinIO first (more reliable; DB failure can be retried)
        await self._minio.put_object_async(
            object_name=storage_path,
            data=content,
            content_type="application/pdf",
        )

        # 2. Insert DB record
        core_file = CoreFile(
            file_uuid=file_uuid,
            original_name=original_name,
            storage_path=storage_path,
            file_type="pdf",
            upload_time=datetime.now(timezone.utc),
            status_metadata=False,
            status_case=False,
            document_type=document_type,
            status_guidelinemeta=False,
        )
        saved = await self._repository.insert(core_file)
        return self._to_response(saved)

    async def upload_many(
        self,
        files: list[tuple[str, bytes]],
        document_type: int = 0,
        *,
        concurrency: int | None = None,
    ) -> dict:
        if document_type not in DOCUMENT_TYPE_PREFIX:
            raise ValueError("Invalid document_type, expected 0, 1, or 2")
        if not files:
            return {"items": [], "total": 0, "uploaded": 0, "skipped": 0, "failed": 0}

        existing_names = await self._repository.existing_original_names(
            [name for name, _ in files],
            document_type,
        )
        seen_names: set[str] = set()
        results: list[dict | None] = [None] * len(files)
        pending: list[tuple[int, CoreFile, bytes]] = []

        for index, (original_name, content) in enumerate(files):
            if original_name in existing_names or original_name in seen_names:
                results[index] = {
                    "file_uuid": None,
                    "original_name": original_name,
                    "status": "skipped",
                    "detail": "File already exists",
                }
                continue

            seen_names.add(original_name)
            file_uuid = str(uuid.uuid4())
            storage_path = f"{DOCUMENT_TYPE_PREFIX[document_type]}/{file_uuid}/{original_name}"
            pending.append(
                (
                    index,
                    CoreFile(
                        file_uuid=file_uuid,
                        original_name=original_name,
                        storage_path=storage_path,
                        file_type="pdf",
                        upload_time=datetime.now(timezone.utc),
                        status_metadata=False,
                        status_case=False,
                        document_type=document_type,
                        status_guidelinemeta=False,
                    ),
                    content,
                )
            )

        effective_concurrency = self.batch_concurrency if concurrency is None else max(1, concurrency)
        semaphore = asyncio.Semaphore(effective_concurrency)

        async def upload_to_minio(index: int, core_file: CoreFile, content: bytes) -> tuple[int, CoreFile | None, str | None]:
            async with semaphore:
                try:
                    await self._minio.put_object_async(
                        object_name=core_file.storage_path,
                        data=content,
                        content_type="application/pdf",
                    )
                    return index, core_file, None
                except Exception as exc:
                    LOGGER.exception("Batch MinIO upload failed for %s", core_file.original_name)
                    return index, None, str(exc)

        uploaded_to_minio = await asyncio.gather(
            *(upload_to_minio(index, core_file, content) for index, core_file, content in pending)
        )

        core_files_to_insert: list[CoreFile] = []
        result_index_by_uuid: dict[str, int] = {}
        for index, core_file, error in uploaded_to_minio:
            if error or core_file is None:
                original_name = files[index][0]
                results[index] = {
                    "file_uuid": None,
                    "original_name": original_name,
                    "status": "failed",
                    "detail": "Internal upload error",
                }
                continue
            core_files_to_insert.append(core_file)
            result_index_by_uuid[core_file.file_uuid] = index

        saved_files = await self._repository.insert_many(core_files_to_insert)
        for saved in saved_files:
            index = result_index_by_uuid[saved.file_uuid]
            results[index] = {
                "file_uuid": saved.file_uuid,
                "original_name": saved.original_name,
                "status": "uploaded",
                "detail": None,
            }

        final_items = [item for item in results if item is not None]
        uploaded_count = sum(1 for item in final_items if item["status"] == "uploaded")
        skipped_count = sum(1 for item in final_items if item["status"] == "skipped")
        failed_count = sum(1 for item in final_items if item["status"] == "failed")
        return {
            "items": final_items,
            "total": len(final_items),
            "uploaded": uploaded_count,
            "skipped": skipped_count,
            "failed": failed_count,
        }

    async def get_file(self, file_uuid: str) -> dict | None:
        core_file = await self._repository.get_by_uuid(file_uuid)
        if not core_file:
            return None
        return self._to_response(core_file)

    async def list_files(self, page: int = 1, size: int = 20) -> dict:
        items, total = await self._repository.list_files(page=page, size=size)
        total_pages = -(-total // size)  # ceil division
        return {
            "items": [self._to_response(f) for f in items],
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages,
        }

    async def delete_file(self, file_uuid: str) -> bool:
        core_file = await self._repository.get_by_uuid(file_uuid)
        if not core_file:
            return False
        # Remove from MinIO, log failure but still proceed with DB cleanup
        try:
            await self._minio.remove_object_async(core_file.storage_path)
        except Exception:
            LOGGER.exception("MinIO deletion failed for %s, proceeding with DB cleanup", file_uuid)
        return await self._repository.delete_by_uuid(file_uuid)

    async def delete_files(self, file_uuids: list[str]) -> dict:
        """Delete multiple files and return deletion results."""
        # Delete from DB first (so repeated requests are idempotent),
        # but keep the record info for MinIO deletion + response.
        files_map = await self._repository.delete_by_uuids(file_uuids)

        results: list[dict] = []
        for file_uuid in file_uuids:
            core_file = files_map.get(file_uuid)

            if not core_file:
                results.append(
                    {
                        "file_uuid": file_uuid,
                        "original_name": None,
                        "status": "not_found",
                        "detail": "File not found",
                    }
                )
                continue

            try:
                await self._minio.remove_object_async(core_file.storage_path)
                results.append(
                    {
                        "file_uuid": file_uuid,
                        "original_name": core_file.original_name,
                        "status": "deleted",
                        "detail": None,
                    }
                )
            except Exception as exc:
                LOGGER.exception("MinIO deletion failed for %s", file_uuid)
                results.append(
                    {
                        "file_uuid": file_uuid,
                        "original_name": core_file.original_name,
                        "status": "failed",
                        "detail": str(exc),
                    }
                )

        deleted_count = sum(1 for r in results if r["status"] == "deleted")
        skipped_count = sum(1 for r in results if r["status"] == "not_found")
        failed_count = sum(1 for r in results if r["status"] == "failed")

        return {
            "items": results,
            "total": len(file_uuids),
            "deleted": deleted_count,
            "skipped": skipped_count,
            "failed": failed_count,
        }
    async def get_download_url(self, file_uuid: str) -> dict | None:
        core_file = await self._repository.get_by_uuid(file_uuid)
        if not core_file:
            return None
        url = await self._minio.presigned_get_object_async(core_file.storage_path)
        return {
            "file_uuid": file_uuid,
            "original_name": core_file.original_name,
            "url": url,
            "expires_in": 3600,
        }

    @staticmethod
    def _to_response(core_file: CoreFile) -> dict:
        return {
            "file_uuid": core_file.file_uuid,
            "original_name": core_file.original_name,
            "storage_path": core_file.storage_path,
            "file_type": core_file.file_type,
            "upload_time": core_file.upload_time,
            "status_metadata": core_file.status_metadata,
            "status_case": core_file.status_case,
            "document_type": core_file.document_type,
            "status_guidelinemeta": core_file.status_guidelinemeta,
            "status_ragflow": core_file.status_ragflow,
        }

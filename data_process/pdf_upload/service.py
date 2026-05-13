"""Upload business logic: UUID generation, MinIO upload, DB insert."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from .minio_client import MinioClient
from .models import CoreFile
from .repository import CoreFileRepository

LOGGER = logging.getLogger("pdf_upload")


class UploadService:
    def __init__(
        self,
        repository: CoreFileRepository,
        minio_client: MinioClient,
        max_file_size_mb: int = 100,
        allowed_extensions: tuple[str, ...] = (".pdf",),
    ) -> None:
        self._repository = repository
        self._minio = minio_client
        self.max_file_size_mb = max_file_size_mb
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.allowed_extensions = allowed_extensions

    async def upload(self, original_name: str, content: bytes) -> dict:
        # Reject duplicate filename
        if await self._repository.exists_by_original_name(original_name):
            raise ValueError(f"File already exists: {original_name}")

        file_uuid = str(uuid.uuid4())
        storage_path = original_name

        # 1. Upload to MinIO first (more reliable; DB failure can be retried)
        self._minio.put_object(
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
        )
        saved = await self._repository.insert(core_file)
        return self._to_response(saved)

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
            self._minio.remove_object(core_file.storage_path)
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
                self._minio.remove_object(core_file.storage_path)
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
        url = self._minio.presigned_get_object(core_file.storage_path)
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
        }

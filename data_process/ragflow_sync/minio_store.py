"""MinIO object reader for source PDFs."""

from __future__ import annotations

from .config import RagflowSyncSettings


class MinioObjectStore:
    def __init__(self, settings: RagflowSyncSettings) -> None:
        from data_process.pdf_upload.config import MinioConfig
        from data_process.pdf_upload.minio_client import MinioClient

        config = MinioConfig(
            endpoint=settings.minio_endpoint,
            root_user=settings.minio_access_key,
            root_password=settings.minio_secret_key,
            bucket_name=settings.minio_bucket_name,
        )
        self._client = MinioClient(config, auto_create_bucket=False)

    def get_object(self, object_name: str) -> bytes:
        return self._client.get_object(object_name)


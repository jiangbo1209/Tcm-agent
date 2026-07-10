"""S3 object reader for source PDFs (used by RAGFlow sync)."""

from __future__ import annotations

from .config import RagflowSyncSettings


class S3ObjectStore:
    def __init__(self, settings: RagflowSyncSettings) -> None:
        from UI.backend.app.storage import S3Client, S3Config

        config = S3Config(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket_name=settings.minio_bucket_name,
            region=settings.minio_region,
        )
        self._client = S3Client(config, auto_create_bucket=False)

    def get_object(self, object_name: str) -> bytes:
        return self._client.get_object(object_name)


# Backwards-compatible alias.
MinioObjectStore = S3ObjectStore

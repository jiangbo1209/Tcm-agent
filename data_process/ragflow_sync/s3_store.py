"""S3 object reader for source PDFs (used by RAGFlow sync)."""

from __future__ import annotations

from .config import RagflowSyncSettings


class S3ObjectStore:
    def __init__(self, settings: RagflowSyncSettings) -> None:
        from UI.backend.app.storage import S3Client, S3Config

        config = S3Config(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket_name=settings.s3_bucket_name,
            region=settings.s3_region,
        )
        self._client = S3Client(config)

    def get_object(self, object_name: str) -> bytes:
        return self._client.get_object(object_name)

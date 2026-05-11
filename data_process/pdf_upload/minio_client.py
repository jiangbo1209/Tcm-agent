"""Extended MinIO client with upload support."""

from __future__ import annotations

import io
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from .config import MinioConfig


class _ParsedEndpoint:
    __slots__ = ("endpoint", "secure")

    def __init__(self, endpoint: str, secure: bool) -> None:
        self.endpoint = endpoint
        self.secure = secure


def _parse_endpoint(raw_endpoint: str) -> _ParsedEndpoint:
    endpoint = (raw_endpoint or "localhost:9000").strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        parsed = urlparse(endpoint)
        host = parsed.netloc or parsed.path
        secure = parsed.scheme.lower() == "https"
        return _ParsedEndpoint(endpoint=host, secure=secure)
    return _ParsedEndpoint(endpoint=endpoint, secure=False)


class MinioClient:
    """Extended MinIO wrapper with bucket management, upload, and presigned URLs."""

    def __init__(self, config: MinioConfig, *, auto_create_bucket: bool = True) -> None:
        self._config = config
        parsed = _parse_endpoint(config.endpoint)

        self._client = Minio(
            endpoint=parsed.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=parsed.secure,
        )

        if auto_create_bucket:
            self.ensure_bucket()

    @property
    def bucket_name(self) -> str:
        return self._config.bucket_name

    @property
    def client(self) -> Minio:
        return self._client

    def ensure_bucket(self) -> None:
        """Ensure target bucket exists; create it when missing."""
        if not self._client.bucket_exists(self._config.bucket_name):
            self._client.make_bucket(self._config.bucket_name)

    def put_object(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload bytes to MinIO. Returns the object name (storage_path)."""
        stream = io.BytesIO(data)
        self._client.put_object(
            bucket_name=self._config.bucket_name,
            object_name=object_name,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def presigned_get_object(
        self,
        object_name: str,
        *,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """Generate a secure presigned URL for object retrieval."""
        normalized = (object_name or "").strip()
        if not normalized:
            raise ValueError("object_name is required")
        try:
            return self._client.presigned_get_object(
                bucket_name=self._config.bucket_name,
                object_name=normalized,
                expires=expires,
            )
        except S3Error:
            raise

    def remove_object(self, object_name: str) -> None:
        """Remove an object from MinIO."""
        self._client.remove_object(
            bucket_name=self._config.bucket_name,
            object_name=object_name,
        )

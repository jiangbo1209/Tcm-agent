"""S3-compatible object storage client (Tencent COS / AWS S3 / self-hosted S3).

Wraps the S3 protocol SDK and exposes a small async-friendly surface used
by the upload service. The bucket is never auto-created — the caller must
provision it in the cloud console ahead of time.
"""

from __future__ import annotations

import asyncio
import io
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from .config import S3Config

__all__ = ["S3Client", "S3Error"]


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


class S3Client:
    """Async-friendly wrapper around the S3 protocol.

    The underlying low-level client is exposed via :attr:`client` for the few
    code paths that need direct access (e.g. presigned URL customisation).
    """

    def __init__(self, config: S3Config, *, auto_create_bucket: bool = False) -> None:
        self._config = config
        parsed = _parse_endpoint(config.endpoint)

        self._client = Minio(
            endpoint=parsed.endpoint,
            access_key=config.access_key,
            secret_key=config.secret_key,
            secure=parsed.secure,
            region=config.region,
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
        """Upload bytes to S3. Returns the object name (storage_path)."""
        stream = io.BytesIO(data)
        self._client.put_object(
            bucket_name=self._config.bucket_name,
            object_name=object_name,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        return object_name

    async def put_object_async(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/pdf",
    ) -> str:
        """Upload bytes without blocking the event loop."""
        return await asyncio.to_thread(
            self.put_object,
            object_name=object_name,
            data=data,
            content_type=content_type,
        )

    def presigned_get_object(
        self,
        object_name: str,
        *,
        expires: timedelta = timedelta(hours=1),
        response_headers: dict[str, str] | None = None,
    ) -> str:
        """Generate a presigned URL for object retrieval."""
        normalized = (object_name or "").strip()
        if not normalized:
            raise ValueError("object_name is required")
        try:
            return self._client.presigned_get_object(
                bucket_name=self._config.bucket_name,
                object_name=normalized,
                expires=expires,
                response_headers=response_headers,
            )
        except S3Error:
            raise

    async def presigned_get_object_async(
        self,
        object_name: str,
        *,
        expires: timedelta = timedelta(hours=1),
        response_headers: dict[str, str] | None = None,
    ) -> str:
        """Generate a presigned URL without blocking the event loop."""
        return await asyncio.to_thread(
            self.presigned_get_object,
            object_name=object_name,
            expires=expires,
            response_headers=response_headers,
        )

    def get_object(self, object_name: str) -> bytes:
        """Download object from S3, return bytes."""
        response = self._client.get_object(
            bucket_name=self._config.bucket_name,
            object_name=object_name,
        )
        data = response.read()
        response.close()
        response.release_conn()
        return data

    async def get_object_async(self, object_name: str) -> bytes:
        """Download object without blocking the event loop."""
        return await asyncio.to_thread(self.get_object, object_name)

    def remove_object(self, object_name: str) -> None:
        """Remove an object from S3."""
        self._client.remove_object(
            bucket_name=self._config.bucket_name,
            object_name=object_name,
        )

    async def remove_object_async(self, object_name: str) -> None:
        """Remove an object without blocking the event loop."""
        await asyncio.to_thread(self.remove_object, object_name=object_name)

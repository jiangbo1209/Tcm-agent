"""MinIO utility wrapper for bucket management and presigned URL generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.config import MinioConfig


@dataclass(frozen=True)
class ParsedEndpoint:
    endpoint: str
    secure: bool


def _parse_endpoint(raw_endpoint: str) -> ParsedEndpoint:
    endpoint = (raw_endpoint or "localhost:9000").strip()
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        parsed = urlparse(endpoint)
        host = parsed.netloc or parsed.path
        secure = parsed.scheme.lower() == "https"
        return ParsedEndpoint(endpoint=host, secure=secure)
    return ParsedEndpoint(endpoint=endpoint, secure=False)


class MinioClient:
    """Thin wrapper around MinIO SDK used by backend services."""

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
        exists = self._client.bucket_exists(self._config.bucket_name)
        if not exists:
            self._client.make_bucket(self._config.bucket_name)

    def presigned_get_object(
        self,
        object_name: str,
        *,
        expires: timedelta = timedelta(hours=1),
        response_headers: dict[str, str] | None = None,
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
                response_headers=response_headers,
            )
        except S3Error:
            raise

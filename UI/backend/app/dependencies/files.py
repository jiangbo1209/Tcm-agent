"""FastAPI dependency providers for the file upload router."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_upload_config
from app.core.database import get_async_db
from app.storage import CoreFileRepository, S3Client, UploadService
from app.storage.config import UploadConfig


def get_s3_client(request: Request) -> S3Client | None:
    """Return the process-wide :class:`S3Client` from ``app.state``.

    Returns ``None`` if S3 credentials are not configured. The router treats
    ``None`` as a 503 (storage unavailable).
    """
    return getattr(request.app.state, "s3_client", None)


def get_upload_config_dep() -> UploadConfig:
    return get_upload_config()


def get_upload_service(
    session: AsyncSession = Depends(get_async_db),
    s3: S3Client | None = Depends(get_s3_client),
    upload_cfg: UploadConfig = Depends(get_upload_config_dep),
) -> UploadService:
    if s3 is None:
        raise HTTPException(
            status_code=503,
            detail="Object storage is not configured. Set S3_* environment variables.",
        )
    repository = CoreFileRepository(session)
    return UploadService(
        repository=repository,
        s3_client=s3,
        max_file_size_mb=upload_cfg.max_file_size_mb,
        allowed_extensions=upload_cfg.extensions_tuple,
        batch_concurrency=upload_cfg.batch_concurrency,
    )

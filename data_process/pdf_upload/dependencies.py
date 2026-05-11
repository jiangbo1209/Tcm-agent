"""FastAPI dependency injection providers."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_minio_config, get_postgres_config, get_upload_config
from .minio_client import MinioClient
from .models import Base
from .repository import CoreFileRepository
from .service import UploadService

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_minio_client: MinioClient | None = None


def init_dependencies() -> None:
    global _engine, _session_factory, _minio_client

    pg_config = get_postgres_config()
    _engine = create_async_engine(pg_config.dsn, echo=False, pool_size=5)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    minio_config = get_minio_config()
    _minio_client = MinioClient(minio_config)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Dependencies not initialized; call init_dependencies() first")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def build_service(session: AsyncSession) -> UploadService:
    if _minio_client is None:
        raise RuntimeError("Dependencies not initialized; call init_dependencies() first")
    upload_config = get_upload_config()
    repository = CoreFileRepository(session)
    return UploadService(
        repository=repository,
        minio_client=_minio_client,
        max_file_size_mb=upload_config.max_file_size_mb,
        allowed_extensions=upload_config.allowed_extensions,
    )


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def ensure_tables() -> None:
    if _engine is not None:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

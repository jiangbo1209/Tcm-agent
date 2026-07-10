"""PostgreSQL database engine and session management.

Two engines coexist:

* Sync engine + :func:`get_db` — used by existing routers (auth, chat, search,
  graph, admin, users) which were built on psycopg2.
* Async engine + :func:`get_async_db` — used **only** by the file upload
  router (:mod:`app.routers.files`). The async engine is built lazily and
  has its own connection pool, so it does not interfere with the sync one.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.config import get_database_config

LOGGER = logging.getLogger(__name__)


# --- Sync engine (existing) -------------------------------------------------

def _build_pg_url() -> URL:
    cfg = get_database_config()
    return URL.create(
        "postgresql+psycopg2",
        username=cfg.user,
        password=cfg.password,
        host=cfg.host,
        port=cfg.port,
        database=cfg.database,
    )


engine = create_engine(_build_pg_url(), pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Async engine (for files router only) -----------------------------------

_async_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_async_engine() -> None:
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        return
    cfg = get_database_config()
    try:
        _async_engine = create_async_engine(
            cfg.async_dsn,
            echo=False,
            pool_size=5,
            pool_pre_ping=True,
        )
        _async_session_factory = async_sessionmaker(
            _async_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    except Exception:
        LOGGER.exception("Failed to initialize async DB engine")
        raise


async def get_async_db():
    """Yield an :class:`AsyncSession` for the files router.

    The session is committed on success and rolled back on exception.
    """
    if _async_session_factory is None:
        _ensure_async_engine()
    assert _async_session_factory is not None
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_async_engine() -> None:
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None

"""PostgreSQL database engine for graph data."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from app.config import get_database_config


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


pg_engine = create_engine(_build_pg_url(), pool_pre_ping=True, echo=False)
PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


def get_pg_db():
    db = PgSession()
    try:
        yield db
    finally:
        db.close()

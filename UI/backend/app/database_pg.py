"""PostgreSQL database engine for graph data."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_database_config


def _build_pg_url() -> str:
    cfg = get_database_config()
    return f"postgresql://{cfg.user}:{cfg.password}@{cfg.host}:{cfg.port}/{cfg.database}"


pg_engine = create_engine(_build_pg_url(), pool_pre_ping=True, echo=False)
PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)


def get_pg_db():
    db = PgSession()
    try:
        yield db
    finally:
        db.close()

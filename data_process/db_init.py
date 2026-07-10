"""Initialize required database tables via SQLAlchemy."""

from __future__ import annotations

import sys

from data_process.graph_builder.database import connect_postgres, create_graph_schema
from data_process.graph_builder.config import GraphBuilderSettings
from data_process.ragflow_sync import orm as _ragflow_sync_orm  # noqa: F401
from sqlalchemy import inspect, text
from UI.backend.app.models import Base, MedCase, CoreFile, LitMetadata, GuidelineMetadata


def _ensure_uploader_id_column(conn) -> None:
    """Add core_file.uploader_id column if it does not exist.

    The column was introduced when the upload service moved into
    UI/backend with JWT auth; older deployments created the table without it.
    """
    inspector = inspect(conn)
    if "core_file" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("core_file")}
    if "uploader_id" in existing:
        return
    conn.execute(text("ALTER TABLE core_file ADD COLUMN uploader_id INTEGER"))
    conn.execute(
        text("CREATE INDEX IF NOT EXISTS idx_core_file_uploader ON core_file (uploader_id)")
    )


def main() -> int:
    if len(sys.argv) > 1:
        print("Usage: python -m data_process.db_init", file=sys.stderr)
        return 2

    settings = GraphBuilderSettings()
    if not settings.password:
        print(
            "PostgreSQL password is required. Set DB_PASSWORD/POSTGRES_PASSWORD in .env.",
            file=sys.stderr,
        )
        return 1

    engine = connect_postgres(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        database=settings.database,
    )

    try:
        with engine.begin() as conn:
            Base.metadata.create_all(conn)
            _ensure_uploader_id_column(conn)
            create_graph_schema(conn)
        print("Database schema initialization finished")
        return 0
    except Exception as exc:
        print(f"Database schema initialization failed: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

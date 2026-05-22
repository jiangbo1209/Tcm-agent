"""Initialize required database tables via SQLAlchemy."""

from __future__ import annotations

import sys

from data_process.case_metadata import models as _case_models  # noqa: F401
from data_process.graph_builder.database import connect_postgres, create_graph_schema
from data_process.graph_builder.config import GraphBuilderSettings
from data_process.lit_metadata.app.models.orm import Base as LitMetadataBase
from data_process.pdf_upload.models import Base as UploadBase


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
            UploadBase.metadata.create_all(conn)
            LitMetadataBase.metadata.create_all(conn)
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

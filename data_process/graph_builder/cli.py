"""Command-line entry point for rebuilding graph nodes and edges."""

from __future__ import annotations

import sys

from .builder import BuildGraphOptions, run
from .settings import GraphBuilderSettings


def options_from_settings(settings: GraphBuilderSettings) -> BuildGraphOptions:
    return BuildGraphOptions(
        host=settings.host,
        port=settings.port,
        user=settings.user,
        password=settings.password,
        database=settings.database,
        strategy=settings.strategy,
        paper_top_k=settings.paper_top_k,
        record_top_k=settings.record_top_k,
        paper_min_score=settings.paper_min_score,
        record_min_score=settings.record_min_score,
    )


def main() -> int:
    if len(sys.argv) > 1:
        print(
            "This command reads .env only; CLI arguments are not supported.",
            file=sys.stderr,
        )
        print("Usage: python -m data_process.graph_builder", file=sys.stderr)
        return 2

    settings = GraphBuilderSettings()

    if not settings.password:
        print(
            "PostgreSQL password is required. Set DB_PASSWORD/POSTGRES_PASSWORD in .env.",
            file=sys.stderr,
        )
        return 1

    return run(options_from_settings(settings))

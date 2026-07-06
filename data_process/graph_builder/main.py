"""Command-line entry point for rebuilding graph nodes and edges."""

from __future__ import annotations

import argparse
import sys

from .builder import BuildGraphOptions, run
from .config import GraphBuilderSettings


def options_from_settings(settings: GraphBuilderSettings, device: str) -> BuildGraphOptions:
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
        device=device,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_process.graph_builder.main",
        description="Rebuild the knowledge-graph nodes / edges tables from PostgreSQL metadata.",
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
        help="Backend for pairwise Jaccard edge construction. "
             "'auto' uses cuPy (GPU) when available and falls back to the CPU reference implementation.",
    )
    parser.add_argument(
        "--strategy",
        choices=("truncate", "upsert"),
        default=None,
        help="Override GRAPH_BUILDER_STRATEGY: 'truncate' wipes the graph tables before insert, "
             "'upsert' merges on conflict.",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    settings = GraphBuilderSettings()
    if args.strategy is not None:
        settings = settings.model_copy(update={"strategy": args.strategy})

    if not settings.password:
        print(
            "PostgreSQL password is required. Set DB_PASSWORD/POSTGRES_PASSWORD in .env.",
            file=sys.stderr,
        )
        return 1

    return run(options_from_settings(settings, args.device))


if __name__ == "__main__":
    raise SystemExit(main())
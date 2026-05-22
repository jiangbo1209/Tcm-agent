"""Command-line entry point for rebuilding graph nodes and edges."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

from .builder import BuildGraphOptions, run


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_SQL = PROJECT_ROOT / "UI" / "configs" / "graph_nodes_edges.sql"


def load_project_env() -> None:
    env_path = PROJECT_ROOT / ".env"
    if load_dotenv is not None:
        load_dotenv(env_path, override=False)
        return
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value
    return default


def int_env(*names: str, default: int) -> int:
    value = first_env(*names)
    if value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m data_process.graph_builder",
        description="Build nodes and edges from source tables lit_metadata and med_case",
    )
    parser.add_argument(
        "--host",
        default=first_env("DB_HOST", "POSTGRES_HOST", default="127.0.0.1"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int_env("DB_PORT", "POSTGRES_PORT", default=5432),
    )
    parser.add_argument(
        "--user",
        default=first_env("DB_USER", "POSTGRES_USER", default="postgres"),
    )
    parser.add_argument("--password", default=first_env("DB_PASSWORD", "POSTGRES_PASSWORD"))
    parser.add_argument("--database", default=first_env("DB_NAME", "POSTGRES_DB", default="postgres"))
    parser.add_argument(
        "--schema-sql",
        default=str(DEFAULT_SCHEMA_SQL),
        help="Path to DDL SQL file",
    )
    parser.add_argument(
        "--strategy",
        default="truncate",
        choices=["truncate", "upsert"],
        help="truncate: rebuild from scratch; upsert: idempotent incremental update",
    )
    parser.add_argument("--paper-top-k", type=int, default=3)
    parser.add_argument("--record-top-k", type=int, default=2)
    parser.add_argument("--paper-min-score", type=float, default=0.02)
    parser.add_argument("--record-min-score", type=float, default=0.02)
    return parser


def options_from_args(args: argparse.Namespace) -> BuildGraphOptions:
    return BuildGraphOptions(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        schema_sql=args.schema_sql,
        strategy=args.strategy,
        paper_top_k=args.paper_top_k,
        record_top_k=args.record_top_k,
        paper_min_score=args.paper_min_score,
        record_min_score=args.record_min_score,
    )


def main(argv: list[str] | None = None) -> int:
    load_project_env()
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if not args.password:
        print(
            "PostgreSQL password is required. Use --password or set DB_PASSWORD/POSTGRES_PASSWORD.",
            file=sys.stderr,
        )
        return 1

    return run(options_from_args(args))

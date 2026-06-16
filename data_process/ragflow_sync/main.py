"""Command-line entry point for RAGFlow synchronization."""

from __future__ import annotations

import argparse
import sys

from .config import RagflowSyncSettings
from .database import RagflowSyncRepository, connect_database
from .minio_store import MinioObjectStore
from .ragflow_client import RagflowClient
from .service import RagflowSyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync TCM literature and case data to RAGFlow.")
    parser.add_argument("--source", choices=["all", "literature", "case"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records per selected source.")
    parser.add_argument("--dry-run", action="store_true", help="Preview records without uploading.")
    parser.add_argument("--force", action="store_true", help="Upload even when a parsed status exists.")
    parser.add_argument("--no-parse", action="store_true", help="Upload and update metadata without triggering parse.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = RagflowSyncSettings()

    if not settings.ragflow_dataset_id:
        print("RAGFLOW_DATASET_ID is required.", file=sys.stderr)
        return 2
    if not args.dry_run and not settings.ragflow_api_key:
        print("RAGFLOW_API_KEY is required unless --dry-run is used.", file=sys.stderr)
        return 2

    engine = connect_database(settings)
    repository = RagflowSyncRepository(engine)
    object_store = None if args.dry_run else MinioObjectStore(settings)
    ragflow_client = None if args.dry_run else RagflowClient(
        base_url=settings.normalized_ragflow_base_url,
        api_key=settings.ragflow_api_key,
        dataset_id=settings.ragflow_dataset_id,
        timeout=settings.ragflow_request_timeout,
    )
    service = RagflowSyncService(
        repository=repository,
        object_store=object_store,
        ragflow_client=ragflow_client,
        dataset_id=settings.ragflow_dataset_id,
        domain=settings.ragflow_domain,
        parse_after_upload=settings.ragflow_parse_after_upload and not args.no_parse,
    )

    try:
        results = service.sync(args.source, limit=args.limit, dry_run=args.dry_run, force=args.force)
    finally:
        repository.close()

    for result in results:
        doc = f" document_id={result.document_id}" if result.document_id else ""
        msg = f" message={result.message}" if result.message else ""
        print(f"{result.source_type} {result.file_uuid}: {result.action}{doc}{msg}")

    failed = sum(1 for result in results if result.action == "failed")
    print(f"Finished: total={len(results)} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())


"""Command-line entry point for RAGFlow synchronization."""

from __future__ import annotations

import argparse
import sys

from .config import RagflowSyncSettings
from .database import RagflowSyncRepository, connect_database
from .minio_store import MinioObjectStore
from .ragflow_client import RagflowClient
from .service import RagflowSyncService


SELECTED_SOURCES = {
    "all": ("literature", "case"),
    "literature": ("literature",),
    "case": ("case",),
    "guideline": ("guideline",),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync TCM literature, case, or guideline data to RAGFlow.")
    parser.add_argument("--source", choices=["all", "literature", "case", "guideline"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records per selected source.")
    parser.add_argument("--dry-run", action="store_true", help="Preview records without uploading.")
    parser.add_argument("--force", action="store_true", help="Upload even when a parsed status exists.")
    parser.add_argument("--only-failed", action="store_true", help="Retry only items whose last sync status is failed.")
    parser.add_argument("--no-parse", action="store_true", help="Upload and update metadata without triggering parse.")
    return parser


def dataset_ids_from_settings(settings: RagflowSyncSettings) -> dict[str, str]:
    return {
        "literature": settings.ragflow_literature_dataset_id,
        "case": settings.ragflow_case_dataset_id,
        "guideline": settings.ragflow_guideline_dataset_id,
    }


def validate_dataset_ids(source: str, dataset_ids: dict[str, str]) -> list[str]:
    missing = []
    for selected_source in SELECTED_SOURCES[source]:
        if not dataset_ids.get(selected_source):
            missing.append(selected_source)
    return missing


def summarize_results(results) -> dict[str, int]:
    summary = {"uploaded": 0, "parsed": 0, "skipped": 0, "failed": 0}
    for result in results:
        if result.action in summary:
            summary[result.action] += 1
    return summary


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = RagflowSyncSettings()
    dataset_ids = dataset_ids_from_settings(settings)

    missing_dataset_ids = validate_dataset_ids(args.source, dataset_ids)
    if missing_dataset_ids:
        names = ", ".join(f"RAGFLOW_{item.upper()}_DATASET_ID" for item in missing_dataset_ids)
        print(f"{names} required for --source {args.source}.", file=sys.stderr)
        return 2
    if not args.dry_run and not settings.ragflow_api_key:
        print("RAGFLOW_API_KEY is required unless --dry-run is used.", file=sys.stderr)
        return 2

    engine = connect_database(settings)
    repository = RagflowSyncRepository(engine)
    object_store = None if args.dry_run else MinioObjectStore(settings)
    ragflow_clients = {}
    if not args.dry_run:
        ragflow_clients = {
            source: RagflowClient(
                base_url=settings.normalized_ragflow_base_url,
                api_key=settings.ragflow_api_key,
                dataset_id=dataset_ids[source],
                timeout=settings.ragflow_request_timeout,
            )
            for source in SELECTED_SOURCES[args.source]
        }
    service = RagflowSyncService(
        repository=repository,
        object_store=object_store,
        ragflow_clients=ragflow_clients,
        dataset_ids=dataset_ids,
        domain=settings.ragflow_domain,
        parse_after_upload=settings.ragflow_parse_after_upload and not args.no_parse,
    )

    try:
        results = service.sync(
            args.source,
            limit=args.limit,
            dry_run=args.dry_run,
            force=args.force,
            only_failed=args.only_failed,
        )
    finally:
        repository.close()

    for result in results:
        doc = f" document_id={result.document_id}" if result.document_id else ""
        stage = f" stage={result.stage}" if result.stage else ""
        msg = f" message={result.message}" if result.message else ""
        print(f"{result.source_type} {result.file_uuid}: {result.action}{stage}{doc}{msg}")

    summary = summarize_results(results)
    print(
        "Summary: "
        f"uploaded={summary['uploaded']} "
        f"parsed={summary['parsed']} "
        f"skipped={summary['skipped']} "
        f"failed={summary['failed']} "
        f"total={len(results)}"
    )
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

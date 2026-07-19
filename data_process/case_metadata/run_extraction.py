#!/usr/bin/env python3
"""Manual trigger script for case metadata extraction.

Usage:
    python -m data_process.case_metadata.run_extraction
    python -m data_process.case_metadata.run_extraction --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)


def current_model_name() -> str:
    return (
        os.getenv("DATA_PROCESS_GEMINI_MODEL")
        or os.getenv("CASE_METADATA_LLM_MODEL")
        or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract case metadata from uploaded case PDFs.")
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of pending case PDFs to process in this run.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    return args


async def main(argv: list[str] | None = None) -> int:
    from .service import CaseExtractionService

    args = parse_args(argv)
    service = CaseExtractionService()

    try:
        print("=" * 60)
        print("TCM Case Metadata Extraction")
        print("=" * 60)
        print(f"Gemini model: {current_model_name()}")
        print(f"Limit: {args.limit if args.limit is not None else 'all pending cases'}")
        print()

        # Ensure tables exist
        await service.ensure_tables()

        # Process pending cases
        summary = await service.process_pending_cases(limit=args.limit)

        # Print summary
        print()
        print("-" * 40)
        print(f"Total pending: {summary.total}")
        print(f"  Success: {summary.success}")
        print(f"  Skipped: {summary.skipped}")
        print(f"  Failed:  {summary.failed}")

        if summary.results:
            print()
            for r in summary.results:
                status = "SKIP" if r.skipped else ("OK" if r.success else "FAIL")
                print(f"  [{status}] {r.original_name}")
                if r.error:
                    print(f"         Error: {r.error}")
                if r.missing_fields:
                    print(f"         Missing fields: {', '.join(r.missing_fields[:5])}{'...' if len(r.missing_fields) > 5 else ''}")

        return 0 if summary.failed == 0 else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        LOGGER = logging.getLogger("case_metadata")
        LOGGER.exception("Fatal error")
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 2
    finally:
        await service.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

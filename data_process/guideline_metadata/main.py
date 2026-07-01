#!/usr/bin/env python3
"""Manual trigger script for guideline metadata synchronization.

Usage:
    python -m data_process.guideline_metadata.main
    python -m data_process.guideline_metadata.main --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import logging
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync guideline metadata from lit_metadata")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum rows to sync. 0 means no limit.",
    )
    return parser.parse_args()


async def main() -> int:
    from .service import GuidelineMetadataSyncService

    args = parse_args()
    service = GuidelineMetadataSyncService()

    try:
        print("=" * 60)
        print("TCM Guideline Metadata Sync")
        print("=" * 60)
        print(f"Limit: {args.limit if args.limit > 0 else 'no limit'}")
        print()

        await service.ensure_tables()
        summary = await service.sync_pending(limit=args.limit)

        print()
        print("-" * 40)
        print(f"Total pending: {summary.total}")
        print(f"  Synced: {summary.synced}")
        print(f"  Failed: {summary.failed}")

        if summary.results:
            print()
            for item in summary.results:
                status = "OK" if item.success else "FAIL"
                print(f"  [{status}] {item.original_name}")
                if item.error:
                    print(f"         Error: {item.error}")

        return 0 if summary.failed == 0 else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        logger = logging.getLogger("guideline_metadata")
        logger.exception("Fatal error")
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 2
    finally:
        await service.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

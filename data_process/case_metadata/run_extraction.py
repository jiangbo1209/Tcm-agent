#!/usr/bin/env python3
"""Manual trigger script for case metadata extraction.

Usage:
    python -m data_process.case_metadata.run_extraction
"""

from __future__ import annotations

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


async def main() -> int:
    from .service import CaseExtractionService

    service = CaseExtractionService()

    try:
        print("=" * 60)
        print("TCM Case Metadata Extraction")
        print("=" * 60)
        print(f"Gemini model: {__import__('os').getenv('GEMINI_MODEL', 'gemini-3-flash-preview')}")
        print()

        # Ensure tables exist
        await service.ensure_tables()

        # Process all pending cases
        summary = await service.process_pending_cases()

        # Print summary
        print()
        print("-" * 40)
        print(f"Total pending: {summary.total}")
        print(f"  Success: {summary.success}")
        print(f"  Failed:  {summary.failed}")

        if summary.results:
            print()
            for r in summary.results:
                status = "OK" if r.success else "FAIL"
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

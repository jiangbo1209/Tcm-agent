#!/usr/bin/env python3
"""Manual trigger script for AI paper summary generation.

Usage:
    python -m data_process.ai_summary.main
    python -m data_process.ai_summary.main --limit 10
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
    return os.getenv("GEMINI_MODEL") or os.getenv("LLM_MODEL", "gemini-3-flash-preview")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate AI summaries for literature papers."
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of pending records to process in this run.",
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    return args


async def main(argv: list[str] | None = None) -> int:
    from .service import AiSummaryService

    args = parse_args(argv)
    service = AiSummaryService()

    try:
        print("=" * 60)
        print("TCM AI Paper Summary Generation")
        print("=" * 60)
        print(f"Model: {current_model_name()}")
        print(f"Limit: {args.limit if args.limit is not None else 'all pending records'}")
        print()

        summary = await service.process_pending(limit=args.limit)

        print()
        print("-" * 40)
        print(f"Total pending: {summary['total']}")
        print(f"  Success: {summary['success']}")
        print(f"  Failed:  {summary['failed']}")

        return 0 if summary["failed"] == 0 else 1

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        LOGGER = logging.getLogger("ai_summary")
        LOGGER.exception("Fatal error")
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 2
    finally:
        await service.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

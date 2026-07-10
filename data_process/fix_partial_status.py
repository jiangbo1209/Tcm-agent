"""Scan lit_metadata and mark records with missing fields as partial.

Usage:
    python -m data_process.fix_partial_status          # dry-run, show what would change
    python -m data_process.fix_partial_status --apply   # actually update the database
"""

from __future__ import annotations

import sys

from sqlalchemy import or_, select, update, func
from sqlalchemy.orm import Session

from lit_metadata.app.models.orm import LitMetadata
from UI.backend.app.config import PostgresSettings
from sqlalchemy import create_engine, URL
from urllib.parse import quote_plus


def _build_engine():
    cfg = PostgresSettings()
    user = quote_plus(cfg.user)
    password = quote_plus(cfg.password)
    dsn = f"postgresql+psycopg2://{user}:{password}@{cfg.host}:{cfg.port}/{cfg.database}"
    return create_engine(dsn, pool_pre_ping=True)


REQUIRED_FIELDS = [
    ("authors", "authors"),
    ("abstract", "abstract"),
    ("keywords", "keywords"),
    ("paper_type", "paper_type"),
    ("journal", "journal"),
    ("pub_year", "pub_year"),
]


def _check_record(record) -> list[str]:
    missing = []
    for col, label in REQUIRED_FIELDS:
        val = getattr(record, col, None)
        if not val:
            missing.append(label)
        elif isinstance(val, list) and len(val) == 0:
            missing.append(label)
    return missing


def main():
    apply = "--apply" in sys.argv

    engine = _build_engine()
    SessionLocal = __import__("sqlalchemy.orm", fromlist=["sessionmaker"]).sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        stmt = select(LitMetadata).where(LitMetadata.crawl_status == "success")
        records = db.execute(stmt).scalars().all()

        print(f"Found {len(records)} records with crawl_status='success'")
        print()

        to_fix = []
        for record in records:
            missing = _check_record(record)
            if missing:
                to_fix.append((record, missing))

        if not to_fix:
            print("No records need fixing.")
            return 0

        print(f"Records to mark as partial: {len(to_fix)}")
        print()
        for record, missing in to_fix:
            title = record.title or record.original_name or f"#{record.id}"
            print(f"  [{record.id}] {title[:60]}  missing: {', '.join(missing)}")

        if not apply:
            print()
            print("Dry-run mode. To apply changes, run with --apply")
            return 0

        updated = 0
        for record, missing in to_fix:
            db.execute(
                update(LitMetadata)
                .where(LitMetadata.id == record.id)
                .values(
                    crawl_status="partial",
                    error_message=f"Missing metadata fields: {', '.join(missing)}",
                )
            )
            updated += 1

        db.commit()
        print()
        print(f"Updated {updated} records to crawl_status='partial'")
        return 0

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

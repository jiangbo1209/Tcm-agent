from __future__ import annotations

import csv
import json
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, settings
from app.core.exceptions import ExportError
from app.database import AsyncSessionLocal
from app.repositories.failed_record_repository import FailedRecordRepository


class ExportService:
    """Export failed records to CSV."""

    CSV_HEADERS = [
        "file_name",
        "file_path",
        "cleaned_title",
        "attempted_sites",
        "failure_reason",
        "error_message",
        "suggested_action",
        "created_at",
    ]

    def __init__(
        self,
        app_settings: Settings = settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    ) -> None:
        self.settings = app_settings
        self.session_factory = session_factory

    async def export_failed_to_csv(self) -> str:
        output_dir = Path(self.settings.OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "failed_records.csv"

        try:
            async with self.session_factory() as session:
                repo = FailedRecordRepository(session)
                records = await repo.list_all()

            with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=self.CSV_HEADERS)
                writer.writeheader()
                for record in records:
                    writer.writerow(
                        {
                            "file_name": record.file_name,
                            "file_path": record.file_path,
                            "cleaned_title": record.cleaned_title,
                            "attempted_sites": json.dumps(record.attempted_sites or [], ensure_ascii=False),
                            "failure_reason": record.failure_reason,
                            "error_message": record.error_message,
                            "suggested_action": record.suggested_action,
                            "created_at": record.created_at.isoformat() if record.created_at else "",
                        }
                    )

            logger.info("Exported failed records: path={}, count={}", output_path, len(records))
            return str(output_path)
        except Exception as exc:
            raise ExportError(f"Failed to export failed records to CSV: {exc}") from exc

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.core.config import Settings, settings
from app.models.schemas import DatasetFile


class DatasetScanner:
    """Scan local dataset directory for PDF files without reading file content."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings

    def scan(self) -> list[DatasetFile]:
        dataset_dir = Path(self.settings.DATASET_DIR)
        dataset_dir.mkdir(parents=True, exist_ok=True)

        files: list[DatasetFile] = []
        for path in sorted(dataset_dir.rglob("*")):
            if not path.is_file():
                continue
            if self._should_ignore(path, dataset_dir):
                continue
            if path.suffix.lower() != ".pdf":
                continue
            files.append(
                DatasetFile(
                    file_name=path.name,
                    file_path=str(path.resolve()),
                    suffix=path.suffix.lower(),
                )
            )

        logger.info("Dataset scan finished: dir={}, pdf_count={}", dataset_dir, len(files))
        return files

    @staticmethod
    def _should_ignore(path: Path, dataset_dir: Path) -> bool:
        try:
            relative_parts = path.relative_to(dataset_dir).parts
        except ValueError:
            relative_parts = path.parts
        if any(part.startswith(".") for part in relative_parts):
            return True
        name = path.name
        return name.startswith("~") or name.endswith(".tmp") or name.endswith(".part")

from __future__ import annotations

from datetime import datetime, timezone

from models.orm import CoreFile
from services.core_file_scanner import CoreFileScanner


def test_core_file_to_pending_file_uses_original_name() -> None:
    record = CoreFile(
        file_uuid="file-1",
        original_name="论文标题.pdf",
        storage_path="remote/path/论文标题.pdf",
        file_type="pdf",
        upload_time=datetime.now(timezone.utc),
        status_metadata=False,
        status_case=True,
    )

    data = CoreFileScanner._to_pending_file(record)

    assert data.file_uuid == "file-1"
    assert data.file_name == "论文标题.pdf"
    assert data.file_path == "remote/path/论文标题.pdf"
    assert data.suffix == ".pdf"


def test_core_file_to_pending_file_infers_suffix_from_type() -> None:
    record = CoreFile(
        file_uuid="file-2",
        original_name="论文标题",
        storage_path="remote/path/论文标题",
        file_type="pdf",
        upload_time=datetime.now(timezone.utc),
        status_metadata=False,
        status_case=True,
    )

    data = CoreFileScanner._to_pending_file(record)

    assert data.suffix == ".pdf"

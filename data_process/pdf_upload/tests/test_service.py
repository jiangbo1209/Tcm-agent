"""Unit tests for UploadService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import pytest_asyncio

from data_process.pdf_upload.minio_client import MinioClient
from data_process.pdf_upload.models import CoreFile
from data_process.pdf_upload.repository import CoreFileRepository
from data_process.pdf_upload.service import UploadService


@pytest.fixture
def mock_minio() -> MagicMock:
    client = MagicMock(spec=MinioClient)
    client.put_object.return_value = "test-uuid/test.pdf"
    client.remove_object.return_value = None
    client.presigned_get_object.return_value = (
        "http://minio:9000/tcm-documents/test-uuid/test.pdf"
    )
    return client


@pytest.fixture
def service(session, mock_minio) -> UploadService:
    repository = CoreFileRepository(session)
    return UploadService(
        repository=repository,
        minio_client=mock_minio,
        max_file_size_mb=100,
    )


@pytest.mark.asyncio
async def test_upload_success(service: UploadService, mock_minio):
    result = await service.upload("test_paper.pdf", b"%PDF-1.4 fake content")

    assert result["original_name"] == "test_paper.pdf"
    assert result["file_type"] == "pdf"
    assert result["status_metadata"] is False
    assert result["status_case"] is False
    assert result["original_name"] in result["storage_path"]
    mock_minio.put_object.assert_called_once()


@pytest.mark.asyncio
async def test_get_file(service: UploadService):
    upload_result = await service.upload("paper.pdf", b"%PDF-1.4 content")
    file_uuid = upload_result["file_uuid"]

    result = await service.get_file(file_uuid)
    assert result is not None
    assert result["file_uuid"] == file_uuid


@pytest.mark.asyncio
async def test_get_file_not_found(service: UploadService):
    result = await service.get_file("nonexistent-uuid")
    assert result is None


@pytest.mark.asyncio
async def test_list_files(service: UploadService):
    await service.upload("paper1.pdf", b"%PDF content 1")
    await service.upload("paper2.pdf", b"%PDF content 2")

    result = await service.list_files(page=1, size=10)
    assert result["total"] == 2
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_list_files_pagination(service: UploadService):
    for i in range(5):
        await service.upload(f"paper{i}.pdf", b"%PDF content")

    result = await service.list_files(page=1, size=2)
    assert result["total"] == 5
    assert len(result["items"]) == 2
    assert result["total_pages"] == 3


@pytest.mark.asyncio
async def test_delete_file(service: UploadService, mock_minio):
    upload_result = await service.upload("delete_me.pdf", b"%PDF content")
    file_uuid = upload_result["file_uuid"]

    deleted = await service.delete_file(file_uuid)
    assert deleted is True
    mock_minio.remove_object.assert_called_once()

    result = await service.get_file(file_uuid)
    assert result is None


@pytest.mark.asyncio
async def test_delete_file_minio_failure_still_deletes_db(service: UploadService, mock_minio):
    upload_result = await service.upload("minio_fail.pdf", b"%PDF content")
    file_uuid = upload_result["file_uuid"]

    mock_minio.remove_object.side_effect = Exception("MinIO down")
    deleted = await service.delete_file(file_uuid)
    assert deleted is True

    result = await service.get_file(file_uuid)
    assert result is None


@pytest.mark.asyncio
async def test_delete_file_not_found(service: UploadService):
    deleted = await service.delete_file("nonexistent-uuid")
    assert deleted is False


@pytest.mark.asyncio
async def test_get_download_url(service: UploadService, mock_minio):
    upload_result = await service.upload("download_me.pdf", b"%PDF content")
    file_uuid = upload_result["file_uuid"]

    result = await service.get_download_url(file_uuid)
    assert result is not None
    assert "url" in result
    assert result["expires_in"] == 3600
    mock_minio.presigned_get_object.assert_called_once()


@pytest.mark.asyncio
async def test_upload_duplicate_rejected(service: UploadService):
    await service.upload("dup_paper.pdf", b"%PDF content")
    with pytest.raises(ValueError, match="File already exists"):
        await service.upload("dup_paper.pdf", b"%PDF content v2")

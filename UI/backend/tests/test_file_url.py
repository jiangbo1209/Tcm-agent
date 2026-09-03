"""Wave2 file-url responsibility migration smoke tests."""

from types import SimpleNamespace

import pytest

from app.services.graph_service import GraphService
from app.storage.file_token import validate_file_token
from app.storage.service import UploadService


def _make_service() -> UploadService:
    async def _get_by_uuid(file_uuid: str):
        return SimpleNamespace(
            original_name="a.pdf",
            storage_path="literature/u1/a.pdf",
        )

    fake_repo = SimpleNamespace(get_by_uuid=_get_by_uuid)
    return UploadService(
        repository=fake_repo,
        s3_client=None,
        max_file_size_mb=100,
        allowed_extensions=(".pdf",),
        batch_concurrency=5,
    )


def _extract_token(url: str) -> str:
    assert url.startswith("/api/files/stream?token=")
    return url.split("token=")[-1]


@pytest.mark.asyncio
async def test_get_download_url_view_mode_inline():
    service = _make_service()
    result = await service.get_download_url("u1", mode="view")
    assert result is not None
    assert result["file_uuid"] == "u1"
    assert result["original_name"] == "a.pdf"
    token = _extract_token(result["url"])
    storage_path, file_name, disposition = validate_file_token(token)
    assert disposition == "inline"
    assert storage_path == "literature/u1/a.pdf"
    assert file_name == "a.pdf"


@pytest.mark.asyncio
async def test_get_download_url_download_mode_attachment():
    service = _make_service()
    result = await service.get_download_url("u1", mode="download")
    assert result is not None
    token = _extract_token(result["url"])
    _, _, disposition = validate_file_token(token)
    assert disposition == "attachment"


def test_map_paper_detail_includes_file_uuid():
    service = GraphService.__new__(GraphService)
    detail = service._map_paper_detail(
        {
            "file_uuid": "u9",
            "original_name": "x.pdf",
            "storage_path": "p",
            "title": "T",
            "authors": None,
            "abstract": None,
            "keywords": None,
            "journal": None,
            "pub_year": None,
            "paper_type": None,
            "source_site": None,
            "source_url": None,
            "matched_title": None,
            "is_exact_match": None,
            "crawl_status": None,
            "error_message": None,
        }
    )
    assert detail["file_uuid"] == "u9"
    assert detail["file_name"] == "x.pdf"

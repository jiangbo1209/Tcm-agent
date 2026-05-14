"""API endpoint tests using TestClient with in-memory DB and dependency overrides."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_process.pdf_upload.dependencies import build_service, get_session
from data_process.pdf_upload.minio_client import MinioClient
from data_process.pdf_upload.models import Base
from data_process.pdf_upload.repository import CoreFileRepository
from data_process.pdf_upload.service import UploadService

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _make_mock_minio() -> MagicMock:
    mock = MagicMock(spec=MinioClient)
    mock.put_object.side_effect = lambda object_name, data, content_type="application/pdf": object_name
    mock.remove_object.return_value = None
    mock.presigned_get_object.return_value = "http://minio:9000/tcm-documents/test.pdf?signature=abc"
    return mock


@pytest_asyncio.fixture(scope="module")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="module")
def client(test_engine):
    from data_process.pdf_upload.main import app

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    mock_minio = _make_mock_minio()

    async def override_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    # Patch lifespan + module-level _minio_client so build_service works
    with patch("data_process.pdf_upload.main.init_dependencies"), \
         patch("data_process.pdf_upload.main.ensure_tables"), \
         patch("data_process.pdf_upload.main.dispose_engine"), \
         patch("data_process.pdf_upload.dependencies._minio_client", mock_minio):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_pdf_success(client):
    pdf_content = b"%PDF-1.4 fake pdf content for testing"
    response = client.post(
        "/api/files/upload",
        files={"file": ("test_paper.pdf", pdf_content, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["original_name"] == "test_paper.pdf"
    assert data["file_type"] == "pdf"
    assert data["status_metadata"] is False
    assert data["status_case"] is False
    assert "file_uuid" in data


def test_upload_non_pdf_rejected(client):
    response = client.post(
        "/api/files/upload",
        files={"file": ("document.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


def test_upload_empty_file_rejected(client):
    response = client.post(
        "/api/files/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "Empty file" in response.json()["detail"]


def test_list_files(client):
    pdf_content = b"%PDF-1.4 content for list test"
    client.post(
        "/api/files/upload",
        files={"file": ("list_test.pdf", pdf_content, "application/pdf")},
    )

    response = client.get("/api/files/", params={"page": 1, "size": 10})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_get_file_by_uuid(client):
    pdf_content = b"%PDF-1.4 content for get test"
    upload_resp = client.post(
        "/api/files/upload",
        files={"file": ("get_test.pdf", pdf_content, "application/pdf")},
    )
    file_uuid = upload_resp.json()["file_uuid"]

    response = client.get(f"/api/files/{file_uuid}")
    assert response.status_code == 200
    assert response.json()["file_uuid"] == file_uuid


def test_get_file_not_found(client):
    response = client.get("/api/files/nonexistent-uuid")
    assert response.status_code == 404


def test_download_url(client):
    pdf_content = b"%PDF-1.4 content for download test"
    upload_resp = client.post(
        "/api/files/upload",
        files={"file": ("download_test.pdf", pdf_content, "application/pdf")},
    )
    file_uuid = upload_resp.json()["file_uuid"]

    response = client.get(f"/api/files/{file_uuid}/download-url")
    assert response.status_code == 200
    data = response.json()
    assert "url" in data


def test_delete_file(client):
    pdf_content = b"%PDF-1.4 content for delete test"
    upload_resp = client.post(
        "/api/files/upload",
        files={"file": ("delete_test.pdf", pdf_content, "application/pdf")},
    )
    file_uuid = upload_resp.json()["file_uuid"]

    response = client.delete(f"/api/files/{file_uuid}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    get_resp = client.get(f"/api/files/{file_uuid}")
    assert get_resp.status_code == 404


def test_upload_duplicate_rejected(client):
    pdf1 = b"%PDF-1.4 dup test"
    resp1 = client.post(
        "/api/files/upload",
        files={"file": ("dup_test.pdf", pdf1, "application/pdf")},
    )
    assert resp1.status_code == 200

    # Same filename should be 409
    resp2 = client.post(
        "/api/files/upload",
        files={"file": ("dup_test.pdf", b"%PDF-1.4 dup v2", "application/pdf")},
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_batch_upload(client):
    pdf_a = b"%PDF-1.4 paper A"
    pdf_b = b"%PDF-1.4 paper B"
    txt_c = b"not a pdf"

    resp = client.post(
        "/api/files/batch-upload",
        files=[
            ("files", ("batch_a.pdf", pdf_a, "application/pdf")),
            ("files", ("batch_b.pdf", pdf_b, "application/pdf")),
            ("files", ("batch_c.txt", txt_c, "text/plain")),
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["uploaded"] == 2
    assert data["failed"] == 1

    # Verify items
    statuses = {item["original_name"]: item["status"] for item in data["items"]}
    assert statuses["batch_a.pdf"] == "uploaded"
    assert statuses["batch_b.pdf"] == "uploaded"
    assert statuses["batch_c.txt"] == "failed"


def test_batch_upload_skip_duplicate(client):
    pdf_dup = b"%PDF-1.4 dup batch"
    # Pre-upload one file
    client.post(
        "/api/files/upload",
        files={"file": ("batch_dup.pdf", pdf_dup, "application/pdf")},
    )
    # Batch upload with one duplicate and one new
    pdf_new = b"%PDF-1.4 new in batch"
    resp = client.post(
        "/api/files/batch-upload",
        files=[
            ("files", ("batch_dup.pdf", pdf_dup, "application/pdf")),
            ("files", ("batch_new.pdf", pdf_new, "application/pdf")),
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["uploaded"] == 1
    assert data["skipped"] == 1

    statuses = {item["original_name"]: item["status"] for item in data["items"]}
    assert statuses["batch_dup.pdf"] == "skipped"
    assert statuses["batch_new.pdf"] == "uploaded"

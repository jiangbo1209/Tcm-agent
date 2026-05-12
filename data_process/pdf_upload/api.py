"""File upload API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from .dependencies import build_service, get_session
from .schemas import (
    BatchUploadResponse,
    BatchUploadItem,
    DeleteResponse,
    DownloadUrlResponse,
    FileListResponse,
    UploadResponse,
)
from .service import UploadService

LOGGER = logging.getLogger("pdf_upload")

router = APIRouter(prefix="/api/files", tags=["file-upload"])


def _normalize_filename(filename: str) -> str:
    """Fix mis-encoded Chinese filenames on Windows.

    When curl on Windows (GBK locale) uploads a file, the filename bytes are
    GBK-encoded but python-multipart decodes them as Latin-1, producing
    garbled Unicode codepoints (e.g. \\u00b4\\u00ab).  We reverse this by
    encoding back to Latin-1 (recovering the original GBK bytes) and then
    decoding as GBK to get proper UTF-8 strings.
    """
    try:
        raw_bytes = filename.encode("latin-1")
        return raw_bytes.decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename


def _get_service(session: AsyncSession = Depends(get_session)) -> UploadService:
    return build_service(session)


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    service: UploadService = Depends(_get_service),
):
    # Validate file extension using configured allowed_extensions
    filename = _normalize_filename(file.filename) if file.filename else None
    if not filename or not any(
        filename.lower().endswith(ext) for ext in service.allowed_extensions
    ):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file rejected")
    if len(content) > service.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {service.max_file_size_mb}MB",
        )

    try:
        result = await service.upload(filename, content)
    except ValueError as exc:
        # Duplicate filename
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except S3Error as exc:
        LOGGER.exception("MinIO upload failed")
        raise HTTPException(status_code=502, detail=f"Storage error: {exc.code}") from exc
    except Exception as exc:
        LOGGER.exception("Upload processing failed")
        raise HTTPException(status_code=500, detail="Internal upload error") from exc
    finally:
        await file.close()

    return result


@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_pdf(
    files: list[UploadFile] = File(...),
    service: UploadService = Depends(_get_service),
):
    results: list[BatchUploadItem] = []
    uploaded = 0
    skipped = 0
    failed = 0

    for file in files:
        filename = _normalize_filename(file.filename) if file.filename else None

        # Validate extension
        if not filename or not any(
            filename.lower().endswith(ext) for ext in service.allowed_extensions
        ):
            results.append(BatchUploadItem(
                original_name=file.filename or "",
                status="failed",
                detail="Only PDF files are accepted",
            ))
            failed += 1
            await file.close()
            continue

        content = await file.read()
        await file.close()

        # Validate size
        if len(content) == 0:
            results.append(BatchUploadItem(
                original_name=filename, status="failed", detail="Empty file rejected",
            ))
            failed += 1
            continue
        if len(content) > service.max_file_size_bytes:
            results.append(BatchUploadItem(
                original_name=filename, status="failed",
                detail=f"File exceeds maximum size of {service.max_file_size_mb}MB",
            ))
            failed += 1
            continue

        # Upload, skip on duplicate
        try:
            result = await service.upload(filename, content)
            results.append(BatchUploadItem(
                file_uuid=result["file_uuid"],
                original_name=filename,
                status="uploaded",
            ))
            uploaded += 1
        except ValueError:
            results.append(BatchUploadItem(
                original_name=filename, status="skipped",
                detail="File already exists",
            ))
            skipped += 1
        except (S3Error, Exception) as exc:
            LOGGER.exception("Batch upload failed for %s", filename)
            results.append(BatchUploadItem(
                original_name=filename, status="failed",
                detail="Internal upload error",
            ))
            failed += 1

    return BatchUploadResponse(
        items=results,
        total=len(results),
        uploaded=uploaded,
        skipped=skipped,
        failed=failed,
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    service: UploadService = Depends(_get_service),
):
    return await service.list_files(page=page, size=size)


@router.get("/{file_uuid}", response_model=UploadResponse)
async def get_file(
    file_uuid: str,
    service: UploadService = Depends(_get_service),
):
    result = await service.get_file(file_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.get("/{file_uuid}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    file_uuid: str,
    service: UploadService = Depends(_get_service),
):
    try:
        result = await service.get_download_url(file_uuid)
    except S3Error as exc:
        LOGGER.exception("Failed to generate presigned URL")
        raise HTTPException(status_code=502, detail=f"Storage error: {exc.code}") from exc
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.delete("/{file_uuid}", response_model=DeleteResponse)
async def delete_file(
    file_uuid: str,
    service: UploadService = Depends(_get_service),
):
    deleted = await service.delete_file(file_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return DeleteResponse(deleted=True, file_uuid=file_uuid)

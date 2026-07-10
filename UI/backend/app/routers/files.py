"""File upload REST API.

All endpoints require JWT authentication; the uploader's ``User.id`` is
written to ``core_file.uploader_id`` for audit purposes.
"""

from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.dependencies.files import get_upload_service
from app.storage import S3Error
from app.models.user import User
from app.storage import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchUploadItem,
    BatchUploadResponse,
    DeleteResponse,
    DownloadUrlResponse,
    FileListResponse,
    UploadResponse,
    UploadService,
)

LOGGER = logging.getLogger("file_upload")

router = APIRouter(prefix="/api/files", tags=["file-upload"])


def _normalize_filename(filename: str | None) -> str | None:
    """Fix mis-encoded Chinese filenames on Windows clients.

    When curl on Windows (GBK locale) uploads a file, the filename bytes are
    GBK-encoded but python-multipart decodes them as Latin-1, producing
    garbled Unicode codepoints (e.g. ``\\u00b4\\u00ab``).  We reverse this by
    encoding back to Latin-1 (recovering the original GBK bytes) and then
    decoding as GBK to get proper UTF-8 strings.
    """
    if not filename:
        return filename
    try:
        raw_bytes = filename.encode("latin-1")
        return raw_bytes.decode("gbk")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return filename


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    document_type: int = Form(
        0,
        ge=0,
        le=2,
        description="Document type: 0=literature, 1=case, 2=guideline",
    ),
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    filename = _normalize_filename(file.filename)
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
        result = await service.upload(
            filename,
            content,
            document_type=document_type,
            uploader_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except S3Error as exc:
        LOGGER.exception("S3 upload failed")
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
    document_type: int = Form(
        0,
        ge=0,
        le=2,
        description="Document type for all uploaded files: 0=literature, 1=case, 2=guideline",
    ),
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    results: list[BatchUploadItem | None] = [None] * len(files)
    valid_files: list[tuple[str, bytes]] = []
    valid_positions: list[int] = []

    for index, file in enumerate(files):
        filename = _normalize_filename(file.filename)

        if not filename or not any(
            filename.lower().endswith(ext) for ext in service.allowed_extensions
        ):
            results[index] = BatchUploadItem(
                file_uuid=None,
                original_name=file.filename or "",
                status="failed",
                detail="Only PDF files are accepted",
            )
            await file.close()
            continue

        content = await file.read()
        await file.close()

        if len(content) == 0:
            results[index] = BatchUploadItem(
                file_uuid=None,
                original_name=filename,
                status="failed",
                detail="Empty file rejected",
            )
            continue
        if len(content) > service.max_file_size_bytes:
            results[index] = BatchUploadItem(
                file_uuid=None,
                original_name=filename,
                status="failed",
                detail=f"File exceeds maximum size of {service.max_file_size_mb}MB",
            )
            continue

        valid_positions.append(index)
        valid_files.append((filename, content))

    if valid_files:
        try:
            batch_result = await service.upload_many(
                valid_files,
                document_type=document_type,
                uploader_id=current_user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            LOGGER.exception("Batch upload processing failed")
            raise HTTPException(status_code=500, detail="Internal upload error") from exc

        for position, item in zip(valid_positions, batch_result["items"]):
            results[position] = BatchUploadItem(**item)

    final_results = [item for item in results if item is not None]
    uploaded = sum(1 for item in final_results if item.status == "uploaded")
    skipped = sum(1 for item in final_results if item.status == "skipped")
    failed = sum(1 for item in final_results if item.status == "failed")

    return BatchUploadResponse(
        items=final_results,
        total=len(final_results),
        uploaded=uploaded,
        skipped=skipped,
        failed=failed,
    )


@router.get("/", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    return await service.list_files(page=page, size=size)


@router.get("/{file_uuid}", response_model=UploadResponse)
async def get_file(
    file_uuid: str,
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    result = await service.get_file(file_uuid)
    if not result:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.get("/{file_uuid}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    file_uuid: str,
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
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
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    deleted = await service.delete_file(file_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return DeleteResponse(deleted=True, file_uuid=file_uuid)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_files(
    request: BatchDeleteRequest,
    current_user: User = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service),
):
    if not request.file_uuids:
        raise HTTPException(status_code=400, detail="file_uuids cannot be empty")

    result = await service.delete_files(request.file_uuids)
    return BatchDeleteResponse(
        items=result["items"],
        total=result["total"],
        deleted=result["deleted"],
        skipped=result["skipped"],
        failed=result["failed"],
    )

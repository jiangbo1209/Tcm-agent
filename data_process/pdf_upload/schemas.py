"""Pydantic request/response schemas for file upload API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    file_uuid: str = Field(..., description="Generated UUID for the uploaded file")
    original_name: str
    storage_path: str = Field(..., description="MinIO object path")
    file_type: str
    upload_time: datetime
    status_metadata: bool
    status_case: bool


class FileListResponse(BaseModel):
    items: list[UploadResponse]
    total: int
    page: int
    size: int
    total_pages: int


class DownloadUrlResponse(BaseModel):
    file_uuid: str
    original_name: str
    url: str
    expires_in: int = Field(3600, description="URL expiry in seconds")


class DeleteResponse(BaseModel):
    deleted: bool
    file_uuid: str


class BatchUploadItem(BaseModel):
    file_uuid: str | None = Field(None, description="UUID if upload succeeded")
    original_name: str
    status: str = Field(..., description="uploaded | skipped | failed")
    detail: str | None = None


class BatchUploadResponse(BaseModel):
    items: list[BatchUploadItem]
    total: int = Field(..., description="Total files in batch")
    uploaded: int = Field(..., description="Successfully uploaded count")
    skipped: int = Field(..., description="Skipped count")


class BatchDeleteRequest(BaseModel):
    file_uuids: list[str] = Field(..., description="List of file UUIDs to delete")


class BatchDeleteItem(BaseModel):
    file_uuid: str
    original_name: str | None = None
    status: str = Field(..., description="deleted | not_found | failed")
    detail: str | None = None


class BatchDeleteResponse(BaseModel):
    items: list[BatchDeleteItem]
    total: int = Field(..., description="Total files requested for deletion")
    deleted: int = Field(..., description="Successfully deleted count")
    skipped: int = Field(..., description="Skipped (duplicate) count")
    failed: int = Field(..., description="Failed count")


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None

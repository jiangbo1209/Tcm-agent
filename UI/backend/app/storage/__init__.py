"""Object storage layer: S3 client + upload service + repository.

Used by:

* :mod:`app.routers.files` — REST API for uploads (JWT-gated)
* ``data_process.ragflow_sync`` and other workers that read PDFs from S3
"""

from .config import S3Config, UploadConfig, get_s3_config, get_upload_config
from .repository import CoreFileRepository
from .s3_client import S3Client
from .schemas import (
    BatchDeleteItem,
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchUploadItem,
    BatchUploadResponse,
    DeleteResponse,
    DownloadUrlResponse,
    ErrorResponse,
    FileListResponse,
    UploadResponse,
)
from .service import DOCUMENT_TYPE_PREFIX, UploadService

__all__ = [
    "BatchDeleteItem",
    "BatchDeleteRequest",
    "BatchDeleteResponse",
    "BatchUploadItem",
    "BatchUploadResponse",
    "CoreFileRepository",
    "DOCUMENT_TYPE_PREFIX",
    "DeleteResponse",
    "DownloadUrlResponse",
    "ErrorResponse",
    "FileListResponse",
    "S3Client",
    "S3Config",
    "UploadConfig",
    "UploadResponse",
    "UploadService",
    "get_s3_config",
    "get_upload_config",
]

"""Legacy MinIO wrapper — now an alias for :class:`app.storage.S3Client`.

Historical code imported ``MinioClient`` from this module. The class is
preserved as a name alias so call sites (e.g. ``graph_service.py``) continue
to work without changes. New code should use :class:`S3Client` directly.
"""

from __future__ import annotations

from app.storage import S3Client

MinioClient = S3Client

__all__ = ["MinioClient", "S3Client"]

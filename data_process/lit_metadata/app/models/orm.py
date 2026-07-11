"""Re-export of canonical ORM models for :mod:`data_process.lit_metadata.app`.

The actual class definitions live in :mod:`UI.backend.app.models`. This
module exists so that legacy imports inside :mod:`data_process.lit_metadata`
(e.g. ``from app.models.orm import LitMetadata``) continue to resolve.
"""

from __future__ import annotations

from UI.backend.app.models import (
    Base,
    CoreFile,
    GuidelineMetadata,
    LitMetadata,
)

__all__ = ["Base", "CoreFile", "GuidelineMetadata", "LitMetadata"]

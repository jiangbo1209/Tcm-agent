"""Deprecated re-export module.

The canonical ORM definitions live in :mod:`UI.backend.app.models`. This file
remains so that legacy imports like
``from data_process.lit_metadata.app.models.orm import LitMetadata`` continue
to work; new code should import from ``UI.backend.app.models`` directly.
"""

from __future__ import annotations

from UI.backend.app.models import (
    Base,
    CoreFile,
    GuidelineMetadata,
    LitMetadata,
)

__all__ = ["Base", "CoreFile", "GuidelineMetadata", "LitMetadata"]

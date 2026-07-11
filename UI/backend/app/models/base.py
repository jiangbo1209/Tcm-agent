"""SQLAlchemy declarative base for non-graph ORM models.

Most ORM classes (CoreFile, MedCase, LitMetadata, GuidelineMetadata, ...) inherit from :class:`Base`.
Graph tables (Node/Edge) use :class:`~app.models.GraphBase` so they can be managed independently.
Other modules (data_process/*, scripts) should import models from :mod:`app.models`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

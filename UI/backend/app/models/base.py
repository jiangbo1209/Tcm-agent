"""SQLAlchemy declarative base, single source of truth for all ORM models.

All ORM classes (CoreFile, MedCase, LitMetadata, GuidelineMetadata, Node, Edge)
inherit from :class:`Base` defined here. Other modules (data_process/*, scripts)
should import from :mod:`app.models`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

"""Separate SQLAlchemy declarative base for the graph (``nodes`` / ``edges``) tables.

Lives in its own metadata so that ``Base.metadata.create_all`` (which creates
the user-data tables) does not redundantly create the graph tables. The
graph tables are managed by :mod:`data_process.graph_builder`.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class GraphBase(DeclarativeBase):
    pass

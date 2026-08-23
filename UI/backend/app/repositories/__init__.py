"""Repository package.

Provides independent injectable repository classes:
:class:`GraphRepository`, :class:`DetailRepository` and :class:`SearchRepository`,
all deriving from :class:`BaseRepository`.
"""

from app.repositories.base import BaseRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.detail_repo import DetailRepository
from app.repositories.search_repo import SearchRepository

__all__ = ["BaseRepository", "GraphRepository", "DetailRepository", "SearchRepository"]

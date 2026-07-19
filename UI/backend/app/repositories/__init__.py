"""Repository package.

Provides :class:`GraphRepository` as a composite class that merges
all sub-modules via cooperative multiple inheritance (MRO).
"""

from __future__ import annotations

from app.repositories.base import GraphRepositoryBase
from app.repositories.graph_repo import GraphRepoMixin
from app.repositories.detail_repo import DetailRepoMixin
from app.repositories.search_repo import SearchRepoMixin
from app.repositories.fulltext_checker import FulltextCheckerMixin


class GraphRepository(
    GraphRepoMixin,
    DetailRepoMixin,
    SearchRepoMixin,
    FulltextCheckerMixin,
    GraphRepositoryBase,
):
    """Combined repository providing all graph/search/detail operations."""


__all__ = ["GraphRepository"]

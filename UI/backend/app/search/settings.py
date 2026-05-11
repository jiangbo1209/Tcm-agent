"""Search runtime settings for scalable query strategies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SearchBackendMode(str, Enum):
    """Search strategy modes.

    auto: Prefer FULLTEXT when indexes are ready, fallback to LIKE.
    fulltext: Force FULLTEXT strategy first; fallback to LIKE on SQL errors.
    like: Always use LIKE strategy.
    """

    AUTO = "auto"
    FULLTEXT = "fulltext"
    LIKE = "like"


@dataclass(frozen=True)
class SearchConfig:
    backend_mode: SearchBackendMode = SearchBackendMode.AUTO
    suggest_default_size: int = 8

from __future__ import annotations

from models.schemas import SearchResult
from utils.text import compress_spaces, replace_full_width_spaces


class ExactTitleMatcher:
    """Strict title matcher: normalize only spaces, then compare equality."""

    def normalize(self, title: str) -> str:
        return compress_spaces(replace_full_width_spaces(title))

    def is_exact_match(self, expected_title: str, result_title: str) -> bool:
        return self.normalize(expected_title) == self.normalize(result_title)

    def find_exact_match(self, expected_title: str, results: list[SearchResult]) -> SearchResult | None:
        for result in results:
            if self.is_exact_match(expected_title, result.title):
                return result
        return None

"""Title matcher with exact and fuzzy matching support."""
from __future__ import annotations

from app.models.schemas import SearchResult
from app.utils.text import compress_spaces, replace_full_width_spaces


class ExactTitleMatcher:
    """Strict + fuzzy title matcher."""

    def normalize(self, title: str) -> str:
        return compress_spaces(replace_full_width_spaces(title))

    def is_exact_match(self, expected_title: str, result_title: str) -> bool:
        return self.normalize(expected_title) == self.normalize(result_title)

    def find_exact_match(self, expected_title: str, results: list[SearchResult]) -> SearchResult | None:
        for result in results:
            if self.is_exact_match(expected_title, result.title):
                return result
        return None

    def find_fuzzy_match(
        self, expected_title: str, expected_author: str | None, results: list[SearchResult]
    ) -> SearchResult | None:
        if not expected_author:
            return None
        for result in results:
            if self._titles_similar(expected_title, result.title) and self._author_matches(
                expected_author, result
            ):
                return result
        return None

    @staticmethod
    def _char_diff(a: str, b: str) -> int:
        a = a.replace(" ", "").replace("　", "")
        b = b.replace(" ", "").replace("　", "")
        if a == b:
            return 0
        if len(a) < len(b):
            a, b = b, a
        diff = 0
        import difflib
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if tag == "replace":
                diff += max(i2 - i1, j2 - j1)
            elif tag == "delete":
                diff += i2 - i1
            elif tag == "insert":
                diff += j2 - j1
        return diff

    @classmethod
    def _titles_similar(cls, expected: str, result: str) -> bool:
        a = cls.normalize(expected)
        b = cls.normalize(result)
        if a == b:
            return True
        # Allow up to 3 character differences for short titles
        diff = cls._char_diff(a, b)
        max_diff = 2 if len(a) > 8 else 1
        return diff <= max_diff

    @staticmethod
    def _author_matches(expected_author: str, result: SearchResult) -> bool:
        raw = result.raw_data or {}
        # Try common author field names
        authors_text = (
            raw.get("authors")
            or raw.get("author")
            or raw.get("creator")
            or raw.get("string_creator")
            or raw.get("authors_text")
            or ""
        )
        if not authors_text:
            return False
        if isinstance(authors_text, list):
            authors_text = " ".join(str(a) for a in authors_text)
        return expected_author in str(authors_text)

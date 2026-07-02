"""Title matcher with exact and fuzzy matching support."""
from __future__ import annotations

from app.models.schemas import SearchResult
from app.utils.text import compress_spaces, replace_full_width_spaces


class ExactTitleMatcher:
    def normalize(self, title: str) -> str:
        return self._norm(title)

    def is_exact_match(self, expected_title: str, result_title: str) -> bool:
        return self._norm(expected_title) == self._norm(result_title)

    def find_exact_match(self, expected_title: str, results: list[SearchResult]) -> SearchResult | None:
        for result in results:
            if self.is_exact_match(expected_title, result.title):
                return result
        return None

    def find_fuzzy_match(
        self, expected_title: str, expected_author: str | None, results: list[SearchResult]
    ) -> SearchResult | None:
        best: SearchResult | None = None
        best_diff = 999

        for result in results:
            a = self._norm(expected_title)
            b = self._norm(result.title)
            if a == b:
                return result

            diff = self._char_diff(a, b)

            if diff <= 2:
                if diff < best_diff:
                    best = result
                    best_diff = diff

            elif diff == 5 and expected_author and self._author_matches(expected_author, result):
                if diff < best_diff:
                    best = result
                    best_diff = diff

        return best

    @staticmethod
    def _norm(title: str) -> str:
        t = replace_full_width_spaces(title)
        t = compress_spaces(t)
        t = t.replace("\uff05", "%")
        return t

    @staticmethod
    def _char_diff(a: str, b: str) -> int:
        a = a.replace(" ", "").replace("\u3000", "")
        b = b.replace(" ", "").replace("\u3000", "")
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

    @staticmethod
    def _author_matches(expected_author: str, result: SearchResult) -> bool:
        raw = result.raw_data or {}
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
        result_authors = str(authors_text)
        for author in expected_author.split():
            if author in result_authors:
                return True
        return False

"""Clean a PDF file name into a paper title candidate and extract author names."""
from __future__ import annotations

import re
from pathlib import Path

from app.utils.text import compress_spaces, replace_full_width_spaces


class FilenameCleaner:
    DOWNLOAD_MARKERS = ("下载", "副本", "CNKI", "知网", "万方", "维普", "NSTL", "e读", "CALIS")
    NUMBER_PREFIX_PATTERNS = (
        re.compile(r"^\s*\d+[\._、+]+(?=[\u4e00-\u9fa5]{3})"),
        re.compile(r"^\s*[\[\【\(（]\d+[\]\】\)）]\s*(?=[\u4e00-\u9fa5]{3})"),
    )
    # Mixed prefix like "3.0+T+MR" or "21061+" before Chinese title.
    # Only strip prefixes that contain digits or '+' to avoid removing legitimate
    # medical terms like "Budd-Chiari".
    MIXED_PREFIX_PATTERN = re.compile(r"^\s*[^\u4e00-\u9fa5]*(?:\d|\+)[^\u4e00-\u9fa5]*(?=[\u4e00-\u9fa5]{3})")
    _AUTHOR_RE = re.compile(r"_([\u4e00-\u9fa5\u00b7·]{2,4}|[A-Za-z][A-Za-z\s\.]{1,19})$")
    TRAILING_AUTHOR_PATTERN = _AUTHOR_RE
    TRAILING_DUP_PATTERN = re.compile(r"\s*[\(（]\s*\d{1,3}\s*[\)）]\s*$")

    def clean(self, file_name: str) -> str:
        return self.clean_with_author(file_name)[0]

    def clean_with_author(self, file_name: str) -> tuple[str, str | None]:
        pure_name = Path(file_name).name
        stem = Path(pure_name).stem
        stem = stem.lstrip("_")

        author, title_stem = self._extract_trailing_authors(stem)

        title = replace_full_width_spaces(title_stem)
        title = title.replace("_", " ")
        title = compress_spaces(title)

        for pattern in self.NUMBER_PREFIX_PATTERNS:
            title = pattern.sub("", title)
            title = compress_spaces(title)

        title = self.MIXED_PREFIX_PATTERN.sub("", title)
        title = compress_spaces(title)

        # Remaining '+' separators (e.g. inside titles) become spaces
        title = title.replace("+", " ")
        title = compress_spaces(title)

        # Remove shortened tokens like "AZ...Ab" (filename ellipsis)
        title = re.sub(r"\w*\.\.\.\w*\s*[、,;]?\s*", "", title)
        title = compress_spaces(title)

        title = self._remove_trailing_download_markers(title)
        title = self._remove_trailing_filename_artifacts(title)
        title = self._remove_outer_wrappers(title)
        title = compress_spaces(title)

        if not title:
            raise ValueError(f"Cleaned title is empty for file name: {file_name}")
        return title, author

    def _extract_trailing_authors(self, stem: str) -> tuple[str | None, str]:
        """Extract consecutive trailing _作者 suffixes from the stem."""
        if stem.startswith("_"):
            return None, stem
        authors: list[str] = []
        remaining = stem
        while True:
            match = self._AUTHOR_RE.search(remaining)
            if not match:
                break
            authors.insert(0, match.group(1))
            remaining = remaining[:match.start()]
        return (" ".join(authors) if authors else None), remaining

    def _remove_trailing_download_markers(self, title: str) -> str:
        marker_pattern = "|".join(re.escape(marker) for marker in self.DOWNLOAD_MARKERS)
        bracketed_pattern = re.compile(
            rf"\s*[\(\（\[\【]\s*(?:{marker_pattern})\s*[\)\）\]\】]\s*$",
            flags=re.IGNORECASE,
        )
        entire_marker_pattern = re.compile(
            rf"^\s*(?:{marker_pattern})\s*$",
            flags=re.IGNORECASE,
        )
        delimited_pattern = re.compile(
            rf"[\s_\-\.、]+(?:{marker_pattern})\s*$",
            flags=re.IGNORECASE,
        )

        cleaned = title
        for _ in range(5):
            previous = cleaned
            cleaned = entire_marker_pattern.sub("", cleaned)
            cleaned = bracketed_pattern.sub("", cleaned)
            cleaned = delimited_pattern.sub("", cleaned)
            cleaned = compress_spaces(cleaned)
            if cleaned == previous:
                break
        return cleaned

    def _remove_trailing_filename_artifacts(self, title: str) -> str:
        cleaned = title
        for _ in range(5):
            previous = cleaned
            cleaned = self.TRAILING_DUP_PATTERN.sub("", cleaned)
            cleaned = self.TRAILING_AUTHOR_PATTERN.sub("", cleaned)
            cleaned = compress_spaces(cleaned)
            if cleaned == previous:
                break
        return cleaned

    @staticmethod
    def _remove_outer_wrappers(title: str) -> str:
        stripped = title.strip()
        wrapper_pairs = (("《", "》"), ("<", ">"))
        for left, right in wrapper_pairs:
            if stripped.startswith(left) and stripped.endswith(right):
                return stripped[len(left) : -len(right)].strip()
        return stripped

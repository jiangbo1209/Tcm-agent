from __future__ import annotations

import re
from pathlib import Path

from app.utils.text import compress_spaces, replace_full_width_spaces


class FilenameCleaner:
    """Clean a PDF file name into a conservative paper title candidate."""

    DOWNLOAD_MARKERS = ("下载", "副本", "CNKI", "知网", "万方", "维普", "NSTL", "e读", "CALIS")
    NUMBER_PREFIX_PATTERNS = (
        re.compile(r"^\s*\d{1,5}[\._\-、\s]+"),
        re.compile(r"^\s*[\[\【\(（]\d{1,5}[\]\】\)）]\s*"),
    )
    TRAILING_AUTHOR_PATTERN = re.compile(r"_[\u4e00-\u9fa5]{2,4}$")
    TRAILING_DUP_PATTERN = re.compile(r"\s*[\(（]\s*\d{1,3}\s*[\)）]\s*$")

    def clean(self, file_name: str) -> str:
        pure_name = Path(file_name).name
        title = Path(pure_name).stem
        title = replace_full_width_spaces(title)
        title = compress_spaces(title)

        for pattern in self.NUMBER_PREFIX_PATTERNS:
            title = pattern.sub("", title)
            title = compress_spaces(title)

        title = self._remove_trailing_download_markers(title)
        title = self._remove_trailing_filename_artifacts(title)
        title = self._remove_outer_wrappers(title)
        title = compress_spaces(title)

        if not title:
            raise ValueError(f"Cleaned title is empty for file name: {file_name}")
        return title

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
    def extract_author(file_name: str) -> str | None:
        pure_name = Path(file_name).stem
        match = re.search(r"_([\u4e00-\u9fa5]{2,6})$", pure_name)
        return match.group(1) if match else None

    @staticmethod
    def _remove_outer_wrappers(title: str) -> str:
        stripped = title.strip()
        wrapper_pairs = (("《", "》"), ("<", ">"))
        for left, right in wrapper_pairs:
            if stripped.startswith(left) and stripped.endswith(right):
                return stripped[len(left) : -len(right)].strip()
        return stripped

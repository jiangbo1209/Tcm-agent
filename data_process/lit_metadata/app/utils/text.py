from __future__ import annotations

import re
from html import unescape
from urllib.parse import urljoin


def replace_full_width_spaces(value: str) -> str:
    return value.replace("\u3000", " ")


def compress_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = compress_spaces(replace_full_width_spaces(value))
    return cleaned or None


def strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    without_tags = re.sub(r"<[^>]+>", "", value)
    return clean_text(unescape(without_tags))


def split_authors(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[\uFF0C,\uFF1B;\u3001\s]+", value)
    return [part.strip() for part in parts if part.strip()]


def split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[\uFF0C,\uFF1B;\u3001]+", value)
    return [part.strip() for part in parts if part.strip()]


def absolutize_url(base_url: str, url: str | None) -> str | None:
    if not url:
        return None
    return urljoin(base_url.rstrip("/") + "/", url)

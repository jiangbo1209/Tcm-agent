"""Shared list-ish parsing/formatting helpers."""

from __future__ import annotations

import json
from typing import Any


def parse_listish(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in (str(v).strip() for v in value) if item]
    raw = str(value).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [item for item in (str(v).strip() for v in parsed) if item]
    cleaned = raw.strip("[](){}")
    parts = cleaned.replace("；", ";").replace("，", ",").replace("、", ",").replace(";", ",").split(",")
    return [item for item in (part.strip(" '\"").strip() for part in parts) if item]


def format_list_field(value: Any, sep: str = "、") -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return sep.join(parse_listish(list(value))) or None
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return value
            if isinstance(data, list):
                return sep.join(parse_listish(data)) or None
        return value
    return str(value)

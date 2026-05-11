"""Gemini SSE streaming client for PDF case extraction.

Adapted from D:\\SleepPause\\Program\\python\\ML\\scripts\\extract_single_paper.py
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from jsonschema import Draft202012Validator

LOGGER = logging.getLogger("case_metadata")

# ==================== Config ====================

RELAY_BASE_URL = os.getenv(
    "RELAY_BASE_URL",
    "https://x666.me/v1beta/models/{model}:streamGenerateContent?alt=sse",
)
RELAY_API_KEY = os.getenv("RELAY_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

CONNECT_TIMEOUT = 100
READ_TIMEOUT = 180
TOTAL_TIMEOUT = 300
FIRST_TOKEN_TIMEOUT = 150
TEMPERATURE = 0.0

MAX_RETRIES = 3
RETRY_DELAY = 10


# ==================== Schema helpers ====================

def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonschema_to_gemini_schema(node: Any) -> Any:
    """Convert local JSON Schema to Gemini responseSchema format."""
    if isinstance(node, dict):
        converted: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"$schema", "additionalProperties"}:
                continue
            if key == "type" and isinstance(value, list):
                non_null_types = [t for t in value if t != "null"]
                if len(non_null_types) == 1:
                    converted["type"] = non_null_types[0]
                    converted["nullable"] = True
                elif len(non_null_types) > 1:
                    converted["type"] = non_null_types[0]
                else:
                    converted["type"] = "string"
                    converted["nullable"] = True
            else:
                converted[key] = jsonschema_to_gemini_schema(value)
        return converted
    if isinstance(node, list):
        return [jsonschema_to_gemini_schema(item) for item in node]
    return node


# ==================== Prompt builder ====================

def build_final_prompt(base_prompt: str, field_names: list[str]) -> str:
    field_list = "，".join(field_names)
    json_template = {name: None for name in field_names}
    template_text = json.dumps(json_template, ensure_ascii=False, indent=2)

    appended = (
        "\n\n【系统追加硬约束（必须遵守）】\n"
        "1. 输出必须是一个且仅一个 JSON 对象。\n"
        "2. JSON 键必须且仅能来自以下字段，不得新增或修改：\n"
        f"{field_list}\n"
        "3. 若信息无法从 PDF 确认，字段值必须为 JSON 原生 null。\n"
        "4. 禁止编造，必须基于当前上传 PDF 的证据。\n"
        "5. 严禁输出 markdown 代码块和任何解释文字。\n"
        "6. 输出前请确保 20 个字段全部出现。\n\n"
        "【JSON 结构模板】\n"
        f"{template_text}\n"
    )
    return base_prompt.rstrip() + appended


# ==================== Payload builder ====================

def build_payload(final_prompt: str, pdf_bytes: bytes, gemini_schema: dict[str, Any]) -> dict[str, Any]:
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "contents": [
            {
                "parts": [
                    {"text": final_prompt},
                    {
                        "inlineData": {
                            "mimeType": "application/pdf",
                            "data": pdf_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema,
        },
    }


# ==================== SSE streaming call ====================

def call_gemini_stream(payload: dict[str, Any]) -> str:
    if not RELAY_API_KEY:
        raise RuntimeError("RELAY_API_KEY not set in environment")

    url = RELAY_BASE_URL.format(model=GEMINI_MODEL)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {RELAY_API_KEY}",
    }

    wall_start = time.time()
    first_text_received = False
    text_parts: list[str] = []

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with requests.post(
        url,
        headers=headers,
        data=data,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        stream=True,
        proxies={"http": None, "https": None},
    ) as resp:
        if resp.status_code != 200:
            preview = resp.text[:800]
            raise RuntimeError(f"HTTP {resp.status_code}: {preview}")

        resp.encoding = "utf-8"
        for line in resp.iter_lines(decode_unicode=True):
            elapsed = time.time() - wall_start
            if elapsed > TOTAL_TIMEOUT:
                raise RuntimeError(f"Total timeout (>{TOTAL_TIMEOUT}s)")
            if not first_text_received and elapsed > FIRST_TOKEN_TIMEOUT:
                raise RuntimeError(f"First token timeout (>{FIRST_TOKEN_TIMEOUT}s)")

            if not line or not line.startswith("data:"):
                continue

            data_line = line[len("data:"):].strip()
            if data_line == "[DONE]":
                break

            try:
                chunk = json.loads(data_line)
            except json.JSONDecodeError:
                continue

            for candidate in chunk.get("candidates", []):
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    text = part.get("text", "")
                    if text:
                        first_text_received = True
                        text_parts.append(text)

    merged = "".join(text_parts).strip()
    if not merged:
        raise RuntimeError("Model returned empty text")
    return merged


# ==================== JSON parsing ====================

def extract_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if not candidate:
        raise ValueError("Empty response text")

    # 1) Direct parse
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2) Strip markdown fences
    stripped = re.sub(r"^\s*```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```\s*$", "", stripped)
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3) raw_decode scan from first {
    decoder = json.JSONDecoder()
    start = stripped.find("{")
    while start != -1:
        try:
            obj, _ = decoder.raw_decode(stripped[start:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            start = stripped.find("{", start + 1)
            continue
        break

    preview = candidate[:500].replace("\n", "\\n")
    raise ValueError(f"Cannot parse JSON from model output. Preview: {preview}")


# ==================== Normalize + validate ====================

def normalize_record(record: dict[str, Any], field_names: list[str]) -> tuple[dict[str, Any], list[str], list[str]]:
    normalized: dict[str, Any] = {}
    missing_fields: list[str] = []

    for field in field_names:
        if field not in record:
            normalized[field] = None
            missing_fields.append(field)
            continue

        value = record[field]
        if value is None:
            normalized[field] = None
        elif isinstance(value, str):
            normalized[field] = value.strip() if value.strip() else None
        elif isinstance(value, (int, float, bool)):
            normalized[field] = str(value)
        else:
            normalized[field] = json.dumps(value, ensure_ascii=False)

    extra_fields = [key for key in record.keys() if key not in field_names]
    return normalized, missing_fields, extra_fields


def validate_record(record: dict[str, Any], local_schema: dict[str, Any]) -> None:
    validator = Draft202012Validator(local_schema)
    errors = sorted(validator.iter_errors(record), key=lambda item: list(item.path))
    if not errors:
        return
    details = []
    for err in errors[:10]:
        loc = ".".join([str(p) for p in err.path]) if err.path else "<root>"
        details.append(f"{loc}: {err.message}")
    raise ValueError("Schema validation: " + "；".join(details))

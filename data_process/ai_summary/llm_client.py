"""LLM client for AI paper summary — reuses Gemini-compatible API pattern from case_metadata."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any

import requests

LOGGER = logging.getLogger("ai_summary")

GEMINI_BASE_URL = (
    os.getenv("DATA_PROCESS_GEMINI_BASE_URL")
    or os.getenv("GEMINI_BASE_URL")
    or os.getenv("RELAY_BASE_URL")
    or "https://runanytime.hxi.me"
)
GEMINI_API_KEY = (
    os.getenv("DATA_PROCESS_GEMINI_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or os.getenv("RELAY_API_KEY", "")
)
GEMINI_MODEL = (
    os.getenv("DATA_PROCESS_GEMINI_MODEL")
    or os.getenv("GEMINI_MODEL")
    or "gemini-3.5-flash"
)
GEMINI_AUTH_HEADER = (
    os.getenv("DATA_PROCESS_GEMINI_AUTH_HEADER")
    or os.getenv("GEMINI_AUTH_HEADER")
    or os.getenv("RELAY_AUTH_HEADER")
    or "x-goog-api-key"
)

CONNECT_TIMEOUT = 100
READ_TIMEOUT = 180
TOTAL_TIMEOUT = 300
FIRST_TOKEN_TIMEOUT = 150

SUMMARIZE_TEMPERATURE = 0.3
MAX_RETRIES = 3
RETRY_DELAY = 10


def _build_endpoint() -> str:
    base_url = GEMINI_BASE_URL.rstrip("/")
    if "{model}" in base_url:
        return base_url.format(model=GEMINI_MODEL)
    if "/v1beta/models/" in base_url:
        return base_url
    if base_url.endswith("/v1beta/models"):
        return f"{base_url}/{GEMINI_MODEL}:streamGenerateContent?alt=sse"
    return f"{base_url}/v1beta/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse"


def _build_auth_headers() -> dict[str, str]:
    header_name = GEMINI_AUTH_HEADER.strip() or "x-goog-api-key"
    if header_name.lower() in {"authorization", "bearer"}:
        return {"Authorization": f"Bearer {GEMINI_API_KEY}"}
    return {header_name: GEMINI_API_KEY}


def build_payload(prompt: str, pdf_bytes: bytes) -> dict[str, Any]:
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
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
            "temperature": SUMMARIZE_TEMPERATURE,
        },
    }


def call_llm_stream(payload: dict[str, Any]) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("DATA_PROCESS_GEMINI_API_KEY not set in environment")

    url = _build_endpoint()
    headers = {
        "Content-Type": "application/json",
        **_build_auth_headers(),
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

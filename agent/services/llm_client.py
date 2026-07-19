"""Qwen OpenAI-compatible LLM client used by Agent services."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import requests

from agent.config import AgentSettings, get_agent_settings


class LLMClientError(RuntimeError):
    """Raised when the LLM request fails or returns an invalid payload."""


class LLMClient:
    """Qwen client through the OpenAI-compatible chat completions API."""

    def __init__(self, settings: AgentSettings | None = None) -> None:
        self._settings = settings or get_agent_settings()

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        response = requests.post(
            self._chat_completions_url(),
            headers=self._json_headers(),
            json=self._body(prompt, system_prompt, stream=False),
            timeout=self._settings.llm_timeout_seconds,
        )
        payload = self._unwrap_json_response(response)
        return self._extract_text(payload)

    def stream_generate(self, prompt: str, system_prompt: str | None = None) -> Iterable[str]:
        with requests.post(
            self._chat_completions_url(),
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._settings.llm_api_key}",
            },
            json=self._body(prompt, system_prompt, stream=True),
            timeout=self._settings.llm_timeout_seconds,
            stream=True,
        ) as response:
            if not response.ok:
                raise LLMClientError(f"LLM HTTP {response.status_code}: {response.text[:500]}")
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if line == "[DONE]":
                    break
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = self._extract_stream_text(payload)
                if text:
                    yield text

    def _body(self, prompt: str, system_prompt: str | None, stream: bool) -> dict[str, Any]:
        if not self._settings.llm_base_url:
            raise LLMClientError("AGENT_LLM_BASE_URL is not configured")
        if not self._settings.llm_api_key:
            raise LLMClientError("AGENT_LLM_API_KEY is not configured")
        if not self._settings.llm_model:
            raise LLMClientError("AGENT_LLM_MODEL is not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": self._settings.llm_model,
            "messages": messages,
            "temperature": self._settings.llm_temperature,
            "max_tokens": self._settings.llm_max_tokens,
        }
        if stream:
            body["stream"] = True
        return body

    def _chat_completions_url(self) -> str:
        base_url = self._settings.llm_base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/v1/chat/completions"

    def _json_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.llm_api_key}",
        }

    def _unwrap_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMClientError(f"LLM returned non-JSON response: {response.text[:500]}") from exc

        if not response.ok:
            raise LLMClientError(f"LLM HTTP {response.status_code}: {payload}")
        return payload

    def _extract_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise LLMClientError(f"LLM response did not contain choices: {payload}")
        message = choices[0].get("message") or {}
        text = message.get("content") or choices[0].get("text") or ""
        text = text.strip()
        if not text:
            raise LLMClientError(f"LLM response did not contain text: {payload}")
        return text

    def _extract_stream_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        first = choices[0]
        delta = first.get("delta") or {}
        return delta.get("content") or first.get("text") or ""

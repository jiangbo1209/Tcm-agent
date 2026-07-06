"""LLM client used by Agent services."""

from __future__ import annotations

from typing import Any

import requests

from agent.config import AgentSettings, get_agent_settings


class LLMClientError(RuntimeError):
    """Raised when the LLM request fails or returns an invalid payload."""


class LLMClient:
    """OpenAI-compatible by default, with a Gemini-compatible branch kept for legacy relays."""

    def __init__(self, settings: AgentSettings | None = None) -> None:
        self._settings = settings or get_agent_settings()

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        provider = self._settings.llm_provider.lower()
        if provider in {"gemini", "google"}:
            return self._generate_gemini(prompt, system_prompt)
        if provider in {"openai", "openai-compatible", "chat_completions"}:
            return self._generate_openai_compatible(prompt, system_prompt)
        raise LLMClientError(f"Unsupported LLM_PROVIDER: {self._settings.llm_provider}")

    def _generate_gemini(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self._settings.llm_base_url:
            raise LLMClientError("LLM_BASE_URL is not configured")
        if not self._settings.llm_api_key:
            raise LLMClientError("LLM_API_KEY or RELAY_API_KEY is not configured")

        url = self._gemini_url()
        body: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": self._settings.llm_temperature,
                "maxOutputTokens": self._settings.llm_max_tokens,
            },
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        response = requests.post(
            url,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json=body,
            timeout=self._settings.llm_timeout_seconds,
        )
        payload = self._unwrap_json_response(response)
        return self._extract_gemini_text(payload)

    def _generate_openai_compatible(self, prompt: str, system_prompt: str | None = None) -> str:
        if not self._settings.llm_base_url:
            raise LLMClientError("LLM_BASE_URL is not configured")
        if not self._settings.llm_api_key:
            raise LLMClientError("LLM_API_KEY or RELAY_API_KEY is not configured")

        url = self._openai_url()
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
        response = requests.post(
            url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._settings.llm_api_key}",
            },
            json=body,
            timeout=self._settings.llm_timeout_seconds,
        )
        payload = self._unwrap_json_response(response)
        return self._extract_openai_text(payload)

    def _gemini_url(self) -> str:
        base_url = self._settings.llm_base_url.rstrip("/")
        if "{model}" in base_url:
            return base_url.format(model=self._settings.llm_model)
        if base_url.endswith(":generateContent"):
            return base_url
        if "/models/" in base_url:
            return f"{base_url}/{self._settings.llm_model}:generateContent"
        return f"{base_url}/v1beta/models/{self._settings.llm_model}:generateContent"

    def _openai_url(self) -> str:
        base_url = self._settings.llm_base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/v1/chat/completions"

    def _auth_headers(self) -> dict[str, str]:
        header_name = self._settings.llm_auth_header.strip() or "x-goog-api-key"
        if header_name.lower() == "authorization":
            return {"Authorization": f"Bearer {self._settings.llm_api_key}"}
        return {header_name: self._settings.llm_api_key}

    def _unwrap_json_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMClientError(f"LLM returned non-JSON response: {response.text[:500]}") from exc

        if not response.ok:
            raise LLMClientError(f"LLM HTTP {response.status_code}: {payload}")
        return payload

    def _extract_gemini_text(self, payload: dict[str, Any]) -> str:
        texts: list[str] = []
        for candidate in payload.get("candidates", []):
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                text = part.get("text")
                if text:
                    texts.append(text)
        result = "\n".join(texts).strip()
        if not result:
            raise LLMClientError(f"LLM response did not contain text: {payload}")
        return result

    def _extract_openai_text(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise LLMClientError(f"LLM response did not contain choices: {payload}")
        message = choices[0].get("message") or {}
        text = message.get("content") or choices[0].get("text") or ""
        text = text.strip()
        if not text:
            raise LLMClientError(f"LLM response did not contain text: {payload}")
        return text

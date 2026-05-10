from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class ChatCompletionClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.llm_base_url.rstrip("/")
        self.default_model = self.settings.llm_model
        self.default_temperature = self.settings.llm_temperature
        self.default_max_tokens = self.settings.llm_max_tokens
        self._http_client = http_client

        if not self.settings.has_llm_credentials:
            raise ValueError("LLM_API_KEY is not configured")

    def generate_completion(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        # The payload intentionally mirrors the OpenAI-compatible chat API so
        # we can swap providers later without changing agent code.
        payload = {
            "model": model or self.default_model,
            "messages": self._build_messages(prompt, system_message),
            "temperature": temperature
            if temperature is not None
            else self.default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.default_max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        client = self._http_client or httpx.Client(timeout=60.0)
        owns_client = self._http_client is None

        try:
            response = client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            logger.error("LLM request failed: %s", exc)
            return ""
        finally:
            if owns_client:
                client.close()

        return self._extract_content(data)

    @staticmethod
    def _build_messages(prompt: str, system_message: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            logger.error("Unexpected LLM response format: %s", payload)
            return ""

        message = choices[0].get("message", {})
        content = message.get("content", "")
        return content.strip() if isinstance(content, str) else ""

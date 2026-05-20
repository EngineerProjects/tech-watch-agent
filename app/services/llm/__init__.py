"""
LLM service for chat completions.

Provides a unified interface for interacting with OpenAI-compatible
LLM APIs across multiple providers (OpenRouter, Ollama, Z.ai, OpenAI).
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Optional

import httpx
from pydantic import BaseModel

from app.config.settings import Settings, get_settings
from app.core.logging import get_logger
from app.services.llm.providers import (
    LLMProviders,
    get_provider_config,
    list_providers,
    check_provider_health_sync,
)


logger = get_logger(__name__)


class ChatCompletionClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._provider_name = self.settings.llm_provider
        self._provider_config = get_provider_config(self._provider_name)
        if self._provider_config is None:
            raise ValueError(f"Unknown LLM provider: {self._provider_name}")

        self.base_url = self._provider_config.base_url
        self.default_model = self.settings.llm_model or self._provider_config.default_model
        self.default_temperature = self.settings.llm_temperature
        self.default_max_tokens = self.settings.llm_max_tokens
        
        # Use provider-specific API key if available
        if self._provider_name == LLMProviders.ZAI and self.settings.zai_api_key:
            self._api_key = self.settings.zai_api_key
        else:
            self._api_key = self.settings.llm_api_key
            
        self._http_client = http_client
        # Fallback model chain for when the primary model is rate-limited.
        # Models are tried left-to-right before giving up entirely.
        self._fallback_models: list[str] = list(self.settings.llm_fallback_models)

        if self._provider_config.requires_api_key and not self._api_key:
            raise ValueError(f"LLM provider '{self._provider_name}' requires API key")

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def available_models(self) -> list[str]:
        return list_providers()

    async def async_generate_completion(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
        max_retries: int = 5,
        initial_delay: float = 2.0,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        """Generate a completion with exponential backoff + model fallback chain.
        
        Args:
            ...
            response_model: Optional Pydantic model for structured output
        """
        import asyncio

        # Build the ordered list of models to try: primary → fallbacks
        models_to_try = [model or self.default_model] + self._fallback_models

        for model_candidate in models_to_try:
            for attempt in range(max_retries):
                try:
                    result = await self._async_make_request(
                        prompt=prompt,
                        system_message=system_message,
                        model=model_candidate,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extra_headers=extra_headers,
                        response_model=response_model,
                    )
                    if model_candidate != (model or self.default_model):
                        logger.info("Succeeded with fallback model: %s", model_candidate)
                    return result
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 429:
                        delay = initial_delay * (2 ** attempt)
                        logger.warning(
                            "[%s] Rate limited (attempt %d/%d). Retrying in %.1fs...",
                            model_candidate, attempt + 1, max_retries, delay,
                        )
                        await asyncio.sleep(delay)
                    elif exc.response.status_code >= 500:
                        delay = initial_delay * (2 ** attempt)
                        logger.warning(
                            "[%s] Server error %d (attempt %d/%d). Retrying in %.1fs...",
                            model_candidate, exc.response.status_code,
                            attempt + 1, max_retries, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("[%s] LLM client error (no retry): %s", model_candidate, exc)
                        return None if response_model else ""
                except httpx.HTTPError as exc:
                    logger.error("[%s] LLM network error: %s", model_candidate, exc)
                    return None if response_model else ""

            logger.warning(
                "[%s] All %d retries exhausted. Trying next fallback model...",
                model_candidate, max_retries,
            )

        logger.error(
            "All models exhausted. Primary: %s, Fallbacks: %s",
            model or self.default_model,
            self._fallback_models,
        )
        return None if response_model else ""

    async def _async_make_request(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> Any:
        payload = {
            "model": model or self.default_model,
            "messages": self._build_messages(prompt, system_message),
            "temperature": temperature
            if temperature is not None
            else self.default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.default_max_tokens,
        }

        # Handle structured output for providers that support it (OpenRouter, OpenAI)
        if response_model and self._provider_name in [LLMProviders.OPENROUTER, LLMProviders.OPENAI]:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                }
            }
        elif response_model:
            # For Ollama/others, we append format instruction to prompt
            schema_json = response_model.model_json_schema()
            payload["messages"][-1]["content"] += f"\n\nReturn ONLY a JSON object matching this schema: {schema_json}"
            # Some providers like Ollama support a simple "json" format
            if self._provider_name == LLMProviders.OLLAMA:
                payload["format"] = "json"

        headers = {
            "Content-Type": "application/json",
        }
        if self._provider_config.auth_type.value == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif self._provider_config.auth_type.value == "api_key":
            headers["X-API-Key"] = self._api_key
        if extra_headers:
            headers.update(extra_headers)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        content = self._extract_content(data)
        
        if response_model:
            import json
            try:
                # Clean content if it contains markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                return response_model.model_validate_json(content)
            except Exception as exc:
                logger.error("Failed to parse structured output: %s. Content: %s", exc, content)
                raise ValueError(f"Invalid structured output: {exc}")

        return content

    def generate_completion(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
        max_retries: int = 5,
        initial_delay: float = 2.0,
    ) -> str:
        import time

        last_error = None
        for attempt in range(max_retries):
            try:
                return self._make_request(
                    prompt=prompt,
                    system_message=system_message,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_headers=extra_headers,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code == 429:
                    # Rate limited - exponential backoff
                    delay = initial_delay * (2 ** attempt)
                    logger.warning(
                        "LLM rate limited (attempt %d/%d). Retrying in %.1fs...",
                        attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                elif exc.response.status_code >= 500:
                    # Server error - retry with backoff
                    delay = initial_delay * (2 ** attempt)
                    logger.warning(
                        "LLM server error %d (attempt %d/%d). Retrying in %.1fs...",
                        exc.response.status_code, attempt + 1, max_retries, delay
                    )
                    time.sleep(delay)
                else:
                    # Client error - don't retry
                    logger.error("LLM request failed: %s", exc)
                    return ""
            except httpx.HTTPError as exc:
                logger.error("LLM request failed: %s", exc)
                return ""

        if last_error:
            logger.error("LLM request failed after %d retries: %s", max_retries, last_error)
        return ""

    def _make_request(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        payload = {
            "model": model or self.default_model,
            "messages": self._build_messages(prompt, system_message),
            "temperature": temperature
            if temperature is not None
            else self.default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.default_max_tokens,
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self._provider_config.auth_type.value == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif self._provider_config.auth_type.value == "api_key":
            headers["X-API-Key"] = self._api_key
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
        finally:
            if owns_client:
                client.close()

        return self._extract_content(data)

    async def async_stream_completion(
        self,
        prompt: str,
        system_message: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion from the LLM provider.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            model: Optional model override
            temperature: Optional temperature override
            max_tokens: Optional max tokens override
            extra_headers: Optional additional headers
            
        Yields:
            Chunks of the generated content as they arrive
        """
        payload = {
            "model": model or self.default_model,
            "messages": self._build_messages(prompt, system_message),
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.default_max_tokens,
            "stream": True,
        }

        headers = {
            "Content-Type": "application/json",
        }
        if self._provider_config.auth_type.value == "bearer":
            headers["Authorization"] = f"Bearer {self._api_key}"
        elif self._provider_config.auth_type.value == "api_key":
            headers["X-API-Key"] = self._api_key
        if extra_headers:
            headers.update(extra_headers)

        import json
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception as exc:
                        logger.debug("Failed to parse stream chunk: %s", exc)
                        continue

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
        
        # Handle Z.ai and other providers that use reasoning_content
        content = message.get("content", "")
        if not content:
            content = message.get("reasoning_content", "")
            
        return content.strip() if isinstance(content, str) else ""

    def health_check(self) -> bool:
        return check_provider_health_sync(self._provider_name, self._api_key)

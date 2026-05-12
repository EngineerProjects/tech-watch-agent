"""
LLM Provider configurations and registry.

Defines known providers, their API endpoints, authentication methods,
and default models. Allows dynamic provider selection at runtime.
"""

from __future__ import annotations

import httpx
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from app.core.logging import get_logger


logger = get_logger(__name__)


class AuthType(Enum):
    BEARER = "bearer"
    NONE = "none"
    API_KEY_HEADER = "api_key"


@dataclass(frozen=True)
class LLMProviderConfig:
    name: str
    base_url: str
    default_model: str
    auth_type: AuthType = AuthType.BEARER
    api_key: str = ""
    requires_api_key: bool = True
    chat_endpoint: str = "/chat/completions"
    extra_headers: dict[str, str] = field(default_factory=dict)

    def build_headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_type == AuthType.BEARER:
            headers["Authorization"] = f"Bearer {api_key}"
        elif self.auth_type == AuthType.API_KEY_HEADER:
            headers["X-API-Key"] = api_key
        headers.update(self.extra_headers)
        return headers


class LLMProviders:
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"
    ZAI = "zai"
    OPENAI = "openai"


_PROVIDER_REGISTRY: dict[str, LLMProviderConfig] = {}


def _register_provider(config: LLMProviderConfig) -> None:
    _PROVIDER_REGISTRY[config.name] = config


def _unregister_provider(name: str) -> None:
    _PROVIDER_REGISTRY.pop(name, None)


def _init_providers() -> None:
    _register_provider(LLMProviderConfig(
        name=LLMProviders.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4.1-mini",
        auth_type=AuthType.BEARER,
        requires_api_key=True,
    ))
    _register_provider(LLMProviderConfig(
        name=LLMProviders.OLLAMA,
        base_url="http://localhost:11434/v1",
        default_model="llama3.2",
        auth_type=AuthType.NONE,
        requires_api_key=False,
    ))
    _register_provider(LLMProviderConfig(
        name=LLMProviders.ZAI,
        base_url="https://api.z.ai/api/paas/v4",
        default_model="glm-4.7-flash",
        auth_type=AuthType.BEARER,
        requires_api_key=True,
    ))
    _register_provider(LLMProviderConfig(
        name=LLMProviders.OPENAI,
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        auth_type=AuthType.BEARER,
        requires_api_key=True,
    ))


_init_providers()


def list_providers() -> list[str]:
    """List all registered provider names."""
    return list(_PROVIDER_REGISTRY.keys())


def get_provider_config(name: str) -> Optional[LLMProviderConfig]:
    """Get config for a provider by name."""
    return _PROVIDER_REGISTRY.get(name)


def register_provider(
    name: str,
    base_url: str,
    default_model: str,
    auth_type: AuthType = AuthType.BEARER,
    api_key: str = "",
    requires_api_key: bool = True,
    extra_headers: dict[str, str] | None = None,
) -> None:
    """Register a custom LLM provider at runtime."""
    _register_provider(LLMProviderConfig(
        name=name,
        base_url=base_url,
        default_model=default_model,
        auth_type=auth_type,
        api_key=api_key,
        requires_api_key=requires_api_key,
        extra_headers=extra_headers or {},
    ))


async def check_provider_health(
    name: str,
    api_key: str = "",
    timeout: float = 10.0,
) -> bool:
    """Check if a provider endpoint is reachable.

    Args:
        name: Provider name
        api_key: API key for the provider
        timeout: Request timeout in seconds

    Returns:
        True if the provider responds to a models list request
    """
    config = get_provider_config(name)
    if config is None:
        logger.warning("Unknown provider: %s", name)
        return False

    if config.requires_api_key and not api_key:
        logger.warning("Provider %s requires API key", name)
        return False

    headers = config.build_headers(api_key)
    url = f"{config.base_url.rstrip('/')}/models"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            return response.status_code == 200
    except httpx.HTTPError as exc:
        logger.warning("Provider %s health check failed: %s", name, exc)
        return False


def check_provider_health_sync(
    name: str,
    api_key: str = "",
    timeout: float = 10.0,
) -> bool:
    """Sync version of provider health check."""
    config = get_provider_config(name)
    if config is None:
        return False

    if config.requires_api_key and not api_key:
        return False

    headers = config.build_headers(api_key)
    url = f"{config.base_url.rstrip('/')}/models"

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            return response.status_code == 200
    except httpx.HTTPError as exc:
        logger.warning("Provider %s health check failed: %s", name, exc)
        return False

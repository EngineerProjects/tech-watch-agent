from typing import Any
import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.security import require_admin_access
from app.config.settings import get_settings
from app.api.models import ProviderListResponse, ProviderResponse, ProviderHealthResponse, ProviderSetRequest, OllamaPullRequest, OllamaPullResponse
from app.services.llm.model_catalog import build_provider_catalogs
from app.services.llm.providers import (
    list_providers,
    get_provider_config,
    check_provider_health_sync,
)

router = APIRouter(prefix="/llm", tags=["LLM"])


def _ollama_api_base_url() -> str:
    settings = get_settings()
    config = get_provider_config("ollama")
    raw = ((settings.llm_base_url if settings.llm_provider == "ollama" and settings.llm_base_url else None) or (config.base_url if config else "http://localhost:11434/v1")).rstrip("/")
    if raw.endswith("/v1"):
        raw = raw[:-3]
    if raw.endswith("/api"):
        return raw
    return f"{raw}/api"


async def _pull_ollama_model(model_name: str) -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0, connect=10.0)) as client:
        response = await client.post(
            f"{_ollama_api_base_url()}/pull",
            json={"model": model_name, "stream": False},
        )
        response.raise_for_status()


def _provider_api_key(provider_name: str) -> str:
    settings = get_settings()
    if provider_name == "zai":
        return settings.zai_api_key or settings.llm_api_key
    return settings.llm_api_key


def _provider_base_url(provider_name: str) -> str | None:
    settings = get_settings()
    if provider_name == settings.llm_provider and settings.llm_base_url:
        return settings.llm_base_url
    config = get_provider_config(provider_name)
    return config.base_url if config else None


@router.get("/providers", response_model=ProviderListResponse)
async def list_llm_providers() -> ProviderListResponse:
    """List all available LLM providers with curated/discovered model catalogs."""
    settings = get_settings()
    providers = [ProviderResponse(**provider) for provider in build_provider_catalogs(settings)]
    return ProviderListResponse(
        providers=providers,
        current_provider=settings.llm_provider,
        current_model=settings.llm_model or (get_provider_config(settings.llm_provider).default_model if get_provider_config(settings.llm_provider) else ""),
        current_embedding_provider=settings.embedding_provider,
        current_embedding_model=settings.embedding_model,
    )


@router.get("/providers/{provider_name}", response_model=ProviderResponse)
async def get_llm_provider(provider_name: str) -> ProviderResponse:
    """Get details about a specific provider."""
    for provider in build_provider_catalogs(get_settings()):
        if provider["name"] == provider_name:
            return ProviderResponse(**provider)
    raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")


@router.get("/providers/{provider_name}/health", response_model=ProviderHealthResponse)
async def check_llm_provider_health(provider_name: str) -> ProviderHealthResponse:
    """Check if a provider is reachable."""
    import time

    config = get_provider_config(provider_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    start = time.perf_counter()
    healthy = check_provider_health_sync(
        provider_name,
        _provider_api_key(provider_name),
        timeout=10.0,
        base_url=_provider_base_url(provider_name),
    )
    latency = round((time.perf_counter() - start) * 1000, 1)

    return ProviderHealthResponse(
        provider=provider_name,
        healthy=healthy,
        latency_ms=latency,
    )


@router.post("/providers/switch", dependencies=[Depends(require_admin_access)])
async def switch_llm_provider(payload: ProviderSetRequest) -> dict[str, Any]:
    """Return the switch preview. Persistence should happen via /config."""
    resolved_settings = get_settings()
    config = get_provider_config(payload.provider)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' not found")

    current_provider = resolved_settings.llm_provider
    current_model = resolved_settings.llm_model or get_provider_config(current_provider).default_model if get_provider_config(current_provider) else ""

    return {
        "status": "ok",
        "message": "Use /config to persist runtime provider/model changes.",
        "current_provider": current_provider,
        "current_model": current_model,
        "requested_provider": payload.provider,
        "requested_model": payload.model or config.default_model,
    }


@router.post("/ollama/pull", response_model=OllamaPullResponse, dependencies=[Depends(require_admin_access)])
async def pull_ollama_model(payload: OllamaPullRequest) -> OllamaPullResponse:
    """Pull a model into the local Ollama instance."""
    try:
        await _pull_ollama_model(payload.model)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Ollama pull failed: {exc}") from exc

    return OllamaPullResponse(
        status="ok",
        provider="ollama",
        model=payload.model,
        message=f"Ollama model '{payload.model}' pulled successfully",
    )

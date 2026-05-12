from typing import Any
from fastapi import APIRouter, HTTPException

from app.config.settings import get_settings
from app.api.models import ProviderListResponse, ProviderResponse, ProviderHealthResponse, ProviderSetRequest
from app.services.llm.providers import (
    list_providers,
    get_provider_config,
    check_provider_health_sync,
)

router = APIRouter(prefix="/llm", tags=["LLM"])

@router.get("/providers", response_model=ProviderListResponse)
async def list_llm_providers() -> ProviderListResponse:
    """List all available LLM providers and current configuration."""
    settings = get_settings()
    providers = [
        ProviderResponse(
            name=name,
            base_url=config.base_url,
            default_model=config.default_model,
            requires_api_key=config.requires_api_key,
        )
        for name, config in [(n, get_provider_config(n)) for n in list_providers()]
        if config is not None
    ]
    return ProviderListResponse(
        providers=providers,
        current_provider=settings.llm_provider,
        current_model=settings.llm_model or (get_provider_config(settings.llm_provider).default_model if get_provider_config(settings.llm_provider) else ""),
    )

@router.get("/providers/{provider_name}", response_model=ProviderResponse)
async def get_llm_provider(provider_name: str) -> ProviderResponse:
    """Get details about a specific provider."""
    config = get_provider_config(provider_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")
    return ProviderResponse(
        name=config.name,
        base_url=config.base_url,
        default_model=config.default_model,
        requires_api_key=config.requires_api_key,
    )

@router.get("/providers/{provider_name}/health", response_model=ProviderHealthResponse)
async def check_llm_provider_health(provider_name: str) -> ProviderHealthResponse:
    """Check if a provider is reachable."""
    import time
    settings = get_settings()
    config = get_provider_config(provider_name)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    start = time.perf_counter()
    healthy = check_provider_health_sync(provider_name, settings.llm_api_key, timeout=10.0)
    latency = round((time.perf_counter() - start) * 1000, 1)

    return ProviderHealthResponse(
        provider=provider_name,
        healthy=healthy,
        latency_ms=latency,
    )

@router.post("/providers/switch")
async def switch_llm_provider(payload: ProviderSetRequest) -> dict[str, str]:
    """Switch active LLM provider (runtime only - update .env to persist)."""
    resolved_settings = get_settings()
    config = get_provider_config(payload.provider)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Provider '{payload.provider}' not found")

    current_provider = resolved_settings.llm_provider
    current_model = resolved_settings.llm_model or get_provider_config(current_provider).default_model if get_provider_config(current_provider) else ""

    return {
        "status": "ok",
        "message": f"Runtime switch not persisted. Set LLM_PROVIDER={payload.provider} in .env",
        "current_provider": current_provider,
        "current_model": current_model,
        "requested_provider": payload.provider,
        "requested_model": payload.model or config.default_model,
    }

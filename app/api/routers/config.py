"""
Runtime configuration API.

GET  /config        — current effective settings (env + DB overrides); API keys masked
PATCH /config       — persist changes to DB (encrypted for sensitive fields); applied immediately
POST /config/search/test — test a search provider with a live query
"""

from __future__ import annotations

from app.api.security import require_admin_access
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config.settings import get_settings, set_db_overrides
from app.core.crypto import encrypt_value, decrypt_overrides, is_encryption_active, SENSITIVE_FIELDS
from app.db.base import async_session_factory
from app.db.repositories import AppConfigRepository
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["Config"], dependencies=[Depends(require_admin_access)])

# All keys the frontend may read / write
ALLOWED_KEYS = {
    "llm_provider", "llm_api_key", "llm_model", "llm_base_url",
    "llm_temperature", "llm_max_tokens", "llm_fallback_models", "llm_provider_models",
    "embedding_provider", "embedding_model", "embedding_provider_models", "zai_api_key",
    "tavily_api_key", "serper_api_key", "semantic_scholar_api_key", "github_api_token", "searxng_url",
    "exa_api_key", "langsearch_api_key", "jina_api_key",
    "search_web_providers", "search_free_providers", "search_academic_providers", "search_code_providers",
    "scrapling_fetcher", "scrapling_timeout", "scrapling_max_content_length",
    "crawl4ai_filter", "crawl4ai_threshold", "crawl4ai_timeout",
    "crawl4ai_max_content_length", "crawl4ai_headless",
    "content_extractor_strategy", "content_extractor_timeout",
    "content_extractor_max_length",
    "sender_email", "recipient_emails", "gmail_credentials_json", "gmail_token_json", "gmail_credentials_path", "gmail_token_path",
    "newsletter_title", "newsletter_topics", "max_articles_per_topic",
    "schedule_times", "timezone",
    "log_level",
}


def _mask(field: str, value: Any) -> Any:
    """Mask sensitive values in GET responses — show only last 4 chars."""
    if field not in SENSITIVE_FIELDS:
        return value
    s = str(value)
    if not s:
        return ""
    return ("••••••••" + s[-4:]) if len(s) > 4 else "••••••••"


def _is_sensitive_update(key: str, value: Any) -> bool:
    if key not in SENSITIVE_FIELDS:
        return False
    if value is None:
        return False
    raw = str(value).strip()
    return bool(raw and not raw.startswith("••"))


async def _reload_runtime_configuration(request: Request | None = None) -> None:
    async with async_session_factory() as db:
        raw_overrides = await AppConfigRepository(db).get_all()

    overrides = decrypt_overrides(raw_overrides)
    set_db_overrides(overrides)

    resolved = get_settings()
    if request is not None:
        request.app.state.settings = resolved

    try:
        from app.api.main import _register_default_tools
        from app.tools.registry import get_global_registry
        from app.tools.registry_init import initialize_tools

        registry = get_global_registry()
        registry.clear()
        _register_default_tools(resolved)
        initialize_tools()
    except Exception as exc:
        logger.warning("Could not refresh tool registry after config change: %s", exc)


@router.get("")
async def get_config() -> dict[str, Any]:
    """Return current effective settings. Sensitive values are masked."""
    s = get_settings()

    raw: dict[str, Any] = {
        "llm_provider":     s.llm_provider,
        "llm_api_key":      s.llm_api_key,
        "llm_model":        s.llm_model,
        "llm_base_url":     s.llm_base_url,
        "llm_temperature":  s.llm_temperature,
        "llm_max_tokens":   s.llm_max_tokens,
        "llm_fallback_models": s.llm_fallback_models,
        "llm_provider_models": s.llm_provider_models,
        "embedding_provider": s.embedding_provider,
        "embedding_model":    s.embedding_model,
        "embedding_provider_models": s.embedding_provider_models,
        "zai_api_key":      s.zai_api_key,
        "tavily_api_key":   s.tavily_api_key,
        "serper_api_key":   s.serper_api_key,
        "semantic_scholar_api_key": s.semantic_scholar_api_key,
        "github_api_token": s.github_api_token,
        "searxng_url":      s.searxng_url,
        "exa_api_key":      s.exa_api_key,
        "langsearch_api_key": s.langsearch_api_key,
        "jina_api_key":     s.jina_api_key,
        "search_web_providers": s.search_web_providers,
        "search_free_providers": s.search_free_providers,
        "search_academic_providers": s.search_academic_providers,
        "search_code_providers": s.search_code_providers,
        "scrapling_fetcher":            s.scrapling_fetcher,
        "scrapling_timeout":            s.scrapling_timeout,
        "scrapling_max_content_length": s.scrapling_max_content_length,
        "crawl4ai_filter":              s.crawl4ai_filter,
        "crawl4ai_threshold":           s.crawl4ai_threshold,
        "crawl4ai_timeout":             s.crawl4ai_timeout,
        "crawl4ai_max_content_length":  s.crawl4ai_max_content_length,
        "crawl4ai_headless":            s.crawl4ai_headless,
        "content_extractor_strategy":   s.content_extractor_strategy,
        "content_extractor_timeout":    s.content_extractor_timeout,
        "content_extractor_max_length": s.content_extractor_max_length,
        "sender_email":            s.sender_email,
        "recipient_emails":        s.recipient_emails,
        "gmail_credentials_json":  s.gmail_credentials_json,
        "gmail_token_json":        s.gmail_token_json,
        "gmail_credentials_path":  s.gmail_credentials_path,
        "gmail_token_path":        s.gmail_token_path,
        "newsletter_title":        s.newsletter_title,
        "newsletter_topics":       s.newsletter_topics,
        "max_articles_per_topic":  s.max_articles_per_topic,
        "schedule_times":          s.schedule_times,
        "timezone":                s.timezone,
        "app_env":                 s.app_env,
        "log_level":               s.log_level,
        "app_port":                s.app_port,
    }

    masked = {k: _mask(k, v) for k, v in raw.items()}
    masked["_encryption_active"] = is_encryption_active()
    masked["_sensitive_configured"] = {
        key: bool(str(raw.get(key, "")).strip())
        for key in SENSITIVE_FIELDS
        if key in raw
    }
    return masked


@router.patch("")
async def update_config(request: Request, updates: dict[str, Any]) -> dict[str, Any]:
    """Persist settings to DB. Sensitive fields are encrypted at rest."""
    filtered = {k: v for k, v in updates.items() if k in ALLOWED_KEYS}
    if not filtered:
        return {"status": "ok", "updated": []}

    settings = get_settings()
    if settings.app_env.lower() in {"production", "staging"} and not is_encryption_active():
        sensitive_updates = [key for key, value in filtered.items() if _is_sensitive_update(key, value)]
        if sensitive_updates:
            raise HTTPException(
                status_code=503,
                detail="Sensitive runtime settings require CONFIG_ENCRYPTION_KEY in production/staging",
            )

    def serialize(key: str, value: Any) -> str:
        if isinstance(value, list):
            return ",".join(str(i).strip() for i in value)
        if isinstance(value, dict):
            import json
            return json.dumps(value)
        return str(value)

    async with async_session_factory() as db:
        repo = AppConfigRepository(db)
        for key, value in filtered.items():
            # Don't overwrite a real key with the masked placeholder
            raw = serialize(key, value)
            if key in SENSITIVE_FIELDS and raw.startswith("••"):
                continue
            stored = encrypt_value(key, raw)
            await repo.set(key, stored)
        await db.commit()

    try:
        await _reload_runtime_configuration(request)
    except Exception as exc:
        logger.warning("Could not reload runtime configuration after save: %s", exc)

    return {"status": "ok", "updated": list(filtered.keys())}


@router.post("/reset")
async def reset_config(request: Request, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    requested_keys = payload.get("keys") if isinstance(payload, dict) else None
    keys = [key for key in (requested_keys or []) if key in ALLOWED_KEYS]

    async with async_session_factory() as db:
        repo = AppConfigRepository(db)
        if keys:
            for key in keys:
                await repo.delete(key)
        else:
            existing = await repo.get_all()
            for key in existing:
                if key in ALLOWED_KEYS:
                    await repo.delete(key)
        await db.commit()

    try:
        await _reload_runtime_configuration(request)
    except Exception as exc:
        logger.warning("Could not reload runtime configuration after reset: %s", exc)

    return {"status": "ok", "reset": keys or "all"}


# ─────────────────────────────────────────────────────────────────────────────
# Search provider test
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_NAMES = {
    "tavily":            "tavily_search",
    "serper":            "serper",
    "searxng":           "searxng",
    "exa":               "exa_search",
    "langsearch":        "langsearch",
    "jina":              "jina_reader",
    "semantic_scholar":  "semantic_scholar",
    "openalex":          "openalex",
    "arxiv":             "arxiv",
    "github":            "github",
}


def _provider_test_params(provider: str, query: str) -> dict[str, Any]:
    if provider == "github":
        return {"action": "search_repos", "query": query, "limit": 5}
    if provider == "arxiv":
        return {"action": "search", "query": query, "limit": 5}
    if provider in {"openalex", "semantic_scholar"}:
        return {"query": query, "limit": 5}
    return {"query": query, "topic": query, "url": query}


@router.post("/search/test")
async def test_search_provider(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Run a quick test query against a search provider.

    Body: { "provider": "tavily" | "searxng" | "exa" | "serper" | "langsearch" | "jina",
             "query": "optional query string" }
    """
    provider = payload.get("provider", "").lower()
    query = payload.get("query", "latest AI research 2025")

    if provider not in _TOOL_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. Available: {list(_TOOL_NAMES)}"
        )

    tool_name = _TOOL_NAMES[provider]

    try:
        from app.tools.registry import get_global_registry
        registry = get_global_registry()

        if tool_name not in registry:
            return {
                "ok": False,
                "provider": provider,
                "error": f"Tool '{tool_name}' not registered (API key missing or tool disabled)",
                "results": [],
            }

        tool = registry.get(tool_name)
        result = await tool.execute(_provider_test_params(provider, query))

        if isinstance(result, dict):
            ok = result.get("success", True)
            data = result.get("data") or result.get("results") or []
            error = result.get("error")
        else:
            ok = getattr(result, "success", True)
            data = getattr(result, "data", []) or []
            error = getattr(result, "error", None)

        # Normalise to a short summary list
        items: list[dict] = []
        normalised_data = data
        if isinstance(data, dict):
            normalised_data = data.get("results") or data.get("articles") or []
        if isinstance(normalised_data, list):
            for item in normalised_data[:5]:
                if isinstance(item, str):
                    items.append({"url": item})
                elif isinstance(item, dict):
                    items.append({
                        "title": item.get("title", ""),
                        "url":   item.get("url", item.get("link", item.get("pdf_url", ""))),
                        "snippet": (item.get("snippet") or item.get("content") or item.get("abstract") or "")[:200],
                    })

        return {"ok": ok, "provider": provider, "query": query, "results": items, "error": error}

    except Exception as exc:
        logger.warning("Search test failed for provider '%s': %s", provider, exc)
        return {"ok": False, "provider": provider, "error": str(exc), "results": []}

"""
Runtime configuration API.

GET  /config        — current effective settings (env + DB overrides); API keys masked
PATCH /config       — persist changes to DB (encrypted for sensitive fields); applied immediately
POST /config/search/test — test a search provider with a live query
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException

from app.config.settings import get_settings, set_db_overrides
from app.core.crypto import encrypt_value, decrypt_value, decrypt_overrides, SENSITIVE_FIELDS
from app.db.base import async_session_factory
from app.db.repositories import AppConfigRepository
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/config", tags=["Config"])

# All keys the frontend may read / write
ALLOWED_KEYS = {
    "llm_provider", "llm_api_key", "llm_model", "llm_base_url",
    "llm_temperature", "llm_max_tokens", "llm_fallback_models",
    "embedding_provider", "embedding_model",
    "tavily_api_key", "serper_api_key", "searxng_url",
    "exa_api_key", "langsearch_api_key", "jina_api_key",
    "scrapling_fetcher", "scrapling_timeout", "scrapling_max_content_length",
    "crawl4ai_filter", "crawl4ai_threshold", "crawl4ai_timeout",
    "crawl4ai_max_content_length", "crawl4ai_headless",
    "content_extractor_strategy", "content_extractor_timeout",
    "content_extractor_max_length",
    "sender_email", "recipient_emails",
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


@router.get("")
async def get_config() -> dict[str, Any]:
    """Return current effective settings. Sensitive values are masked."""
    s = get_settings()

    try:
        async with async_session_factory() as db:
            saved_raw = await AppConfigRepository(db).get_all()
        # Decrypt DB overrides to read the actual saved values for derived fields
        saved = decrypt_overrides(saved_raw)
    except Exception:
        saved = {}

    raw: dict[str, Any] = {
        "llm_provider":     s.llm_provider,
        "llm_api_key":      s.llm_api_key,
        "llm_model":        s.llm_model,
        "llm_base_url":     s.llm_base_url,
        "llm_temperature":  s.llm_temperature,
        "llm_max_tokens":   s.llm_max_tokens,
        "llm_fallback_models": s.llm_fallback_models,
        "embedding_provider": saved.get("embedding_provider", s.llm_provider),
        "embedding_model":    saved.get("embedding_model", ""),
        "tavily_api_key":   s.tavily_api_key,
        "serper_api_key":   s.serper_api_key,
        "searxng_url":      s.searxng_url,
        "exa_api_key":      s.exa_api_key,
        "langsearch_api_key": s.langsearch_api_key,
        "jina_api_key":     s.jina_api_key,
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
        "newsletter_title":        s.newsletter_title,
        "newsletter_topics":       s.newsletter_topics,
        "max_articles_per_topic":  s.max_articles_per_topic,
        "schedule_times":          s.schedule_times,
        "timezone":                s.timezone,
        "app_env":                 s.app_env,
        "log_level":               s.log_level,
        "app_port":                s.app_port,
    }

    return {k: _mask(k, v) for k, v in raw.items()}


@router.patch("")
async def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Persist settings to DB. Sensitive fields are encrypted at rest."""
    filtered = {k: v for k, v in updates.items() if k in ALLOWED_KEYS}

    def serialize(key: str, value: Any) -> str:
        if isinstance(value, list):
            return ",".join(str(i).strip() for i in value)
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

    # Reload settings immediately so agent picks up new values
    try:
        async with async_session_factory() as db:
            raw_overrides = await AppConfigRepository(db).get_all()
        set_db_overrides(decrypt_overrides(raw_overrides))
    except Exception as exc:
        logger.warning("Could not reload DB overrides after save: %s", exc)

    return {"status": "ok", "updated": list(filtered.keys())}


# ─────────────────────────────────────────────────────────────────────────────
# Search provider test
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_NAMES = {
    "tavily":     "tavily_search",
    "serper":     "serper",
    "searxng":    "searxng",
    "exa":        "exa_search",
    "langsearch": "langsearch",
    "jina":       "jina_reader",
}


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
        result = await tool.execute({"query": query, "topic": query, "url": query})

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
        if isinstance(data, list):
            for item in data[:5]:
                if isinstance(item, str):
                    items.append({"url": item})
                elif isinstance(item, dict):
                    items.append({
                        "title": item.get("title", ""),
                        "url":   item.get("url", item.get("link", "")),
                        "snippet": (item.get("snippet") or item.get("content") or "")[:200],
                    })

        return {"ok": ok, "provider": provider, "query": query, "results": items, "error": error}

    except Exception as exc:
        logger.warning("Search test failed for provider '%s': %s", provider, exc)
        return {"ok": False, "provider": provider, "error": str(exc), "results": []}

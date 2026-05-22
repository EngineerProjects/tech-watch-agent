from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]




def _parse_json_dict(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}

def _default_cors_origins() -> list[str]:
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


# Runtime overrides loaded from DB at startup (key → raw string value).
# DB values override env vars; get_settings() picks them up automatically
# because set_db_overrides() clears the lru_cache.
_DB_OVERRIDES: dict[str, str] = {}


def set_db_overrides(overrides: dict[str, str]) -> None:
    """Replace DB overrides and invalidate the settings cache."""
    global _DB_OVERRIDES
    _DB_OVERRIDES = {k: v for k, v in overrides.items() if v is not None}
    get_settings.cache_clear()


def _apply_overrides(kwargs: dict) -> dict:
    """Merge _DB_OVERRIDES into env-resolved kwargs (DB wins over env)."""
    for key, raw in _DB_OVERRIDES.items():
        if key not in kwargs:
            continue
        current = kwargs[key]
        try:
            if isinstance(current, bool):
                kwargs[key] = raw.lower() in ("1", "true", "yes")
            elif isinstance(current, int):
                kwargs[key] = int(raw)
            elif isinstance(current, float):
                kwargs[key] = float(raw)
            elif isinstance(current, list):
                kwargs[key] = _parse_csv(raw)
            elif isinstance(current, dict):
                kwargs[key] = _parse_json_dict(raw)
            else:
                kwargs[key] = raw
        except (ValueError, AttributeError):
            pass
    return kwargs


@dataclass(slots=True)
class Settings:
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = field(default_factory=_default_cors_origins)
    admin_api_token: str = ""

    # Database configuration
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/techwatch"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/techwatch"

    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_fallback_models: list[str] = field(default_factory=list)
    llm_provider_models: dict[str, dict[str, object]] = field(default_factory=dict)
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_provider_models: dict[str, str] = field(default_factory=dict)

    # Z.ai specific settings
    zai_api_key: str = ""

    newsletter_title: str = "Tech Watch Agent"
    newsletter_topics: list[str] = field(
        default_factory=lambda: [
            "AI news",
            "Machine Learning breakthroughs",
            "Tech startups",
            "OpenAI updates",
            "Google AI developments",
            "Tech industry trends",
        ]
    )
    news_sources: list[str] = field(
        default_factory=lambda: [
            "https://techcrunch.com/category/artificial-intelligence/",
            "https://www.theverge.com/ai-artificial-intelligence",
            "https://venturebeat.com/ai/",
            "https://www.wired.com/tag/artificial-intelligence/",
            "https://www.artificialintelligence-news.com/",
        ]
    )
    max_articles_per_topic: int = 5
    crawl_timeout_seconds: int = 30

    sender_email: str = ""
    recipient_emails: list[str] = field(default_factory=list)
    gmail_credentials_json: str = ""
    gmail_token_json: str = ""
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"

    tavily_api_key: str = ""
    serper_api_key: str = ""
    semantic_scholar_api_key: str = ""
    github_api_token: str = ""
    # Search providers (used by NewsSearchService fallback chain)
    searxng_url: str = "http://localhost:8080"
    exa_api_key: str = ""
    langsearch_api_key: str = ""
    jina_api_key: str = ""
    search_web_providers: list[str] = field(default_factory=lambda: ["tavily", "exa", "langsearch"])
    search_free_providers: list[str] = field(default_factory=lambda: ["searxng"])
    search_academic_providers: list[str] = field(default_factory=lambda: ["searxng", "arxiv", "semantic_scholar", "openalex"])
    search_code_providers: list[str] = field(default_factory=lambda: ["searxng", "github"])
    scrapling_fetcher: str = "basic"
    scrapling_timeout: int = 30
    scrapling_max_content_length: int = 50000
    crawl4ai_filter: str = "pruning"
    crawl4ai_threshold: float = 0.48
    crawl4ai_timeout: int = 30
    crawl4ai_max_content_length: int = 50000
    crawl4ai_headless: bool = True
    content_extractor_strategy: str = "markdown"
    content_extractor_timeout: int = 60
    content_extractor_max_length: int = 50000

    schedule_times: list[str] = field(default_factory=lambda: ["08:00", "18:00"])
    timezone: str = "Europe/Paris"

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Settings":
        # A plain dataclass keeps the V1 lightweight while still centralizing
        # all environment parsing in one place.
        load_dotenv(dotenv_path=env_file, override=False)

        kwargs: dict = dict(
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            cors_origins=_parse_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")),
            admin_api_token=os.getenv("ADMIN_API_TOKEN", ""),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/techwatch",
            ),
            database_sync_url=os.getenv(
                "DATABASE_SYNC_URL",
                "postgresql://postgres:postgres@localhost:5432/techwatch",
            ),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_fallback_models=_parse_csv(os.getenv("LLM_FALLBACK_MODELS", "")),
            llm_provider_models=_parse_json_dict(os.getenv("LLM_PROVIDER_MODELS", "{}")),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", os.getenv("LLM_PROVIDER", "openai")),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            embedding_provider_models=_parse_json_dict(os.getenv("EMBEDDING_PROVIDER_MODELS", "{}")),
            zai_api_key=os.getenv("ZAI_API_KEY", ""),
            newsletter_title=os.getenv("NEWSLETTER_TITLE", "Tech Watch Agent"),
            newsletter_topics=_parse_csv(
                os.getenv(
                    "NEWSLETTER_TOPICS",
                    (
                        "AI news,Machine Learning breakthroughs,Tech startups,"
                        "OpenAI updates,Google AI developments,Tech industry trends"
                    ),
                )
            ),
            max_articles_per_topic=int(os.getenv("MAX_ARTICLES_PER_TOPIC", "5")),
            crawl_timeout_seconds=int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30")),
            sender_email=os.getenv("SENDER_EMAIL", ""),
            recipient_emails=_parse_csv(os.getenv("RECIPIENT_EMAILS", "")),
            gmail_credentials_json="",
            gmail_token_json="",
            gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
            gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "token.json"),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
            serper_api_key=os.getenv("SERPER_API_KEY", ""),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""),
            github_api_token=os.getenv("GITHUB_API_TOKEN", ""),
            searxng_url=os.getenv("SEARXNG_URL", "http://localhost:8080"),
            exa_api_key=os.getenv("EXA_API_KEY", ""),
            langsearch_api_key=os.getenv("LANGSEARCH_API_KEY", ""),
            jina_api_key=os.getenv("JINA_API_KEY", ""),
            search_web_providers=_parse_csv(os.getenv("SEARCH_WEB_PROVIDERS", "tavily,exa,langsearch")),
            search_free_providers=_parse_csv(os.getenv("SEARCH_FREE_PROVIDERS", "searxng")),
            search_academic_providers=_parse_csv(os.getenv("SEARCH_ACADEMIC_PROVIDERS", "searxng,arxiv,semantic_scholar,openalex")),
            search_code_providers=_parse_csv(os.getenv("SEARCH_CODE_PROVIDERS", "searxng,github")),
            scrapling_fetcher=os.getenv("SCRAPLING_FETCHER", "basic"),
            scrapling_timeout=int(os.getenv("SCRAPLING_TIMEOUT", "30")),
            scrapling_max_content_length=int(os.getenv("SCRAPLING_MAX_CONTENT_LENGTH", "50000")),
            crawl4ai_filter=os.getenv("CRAWL4AI_FILTER", "pruning"),
            crawl4ai_threshold=float(os.getenv("CRAWL4AI_THRESHOLD", "0.48")),
            crawl4ai_timeout=int(os.getenv("CRAWL4AI_TIMEOUT", "30")),
            crawl4ai_max_content_length=int(os.getenv("CRAWL4AI_MAX_CONTENT_LENGTH", "50000")),
            crawl4ai_headless=os.getenv("CRAWL4AI_HEADLESS", "true").lower() == "true",
            content_extractor_strategy=os.getenv("CONTENT_EXTRACTOR_STRATEGY", "markdown"),
            content_extractor_timeout=int(os.getenv("CONTENT_EXTRACTOR_TIMEOUT", "60")),
            content_extractor_max_length=int(os.getenv("CONTENT_EXTRACTOR_MAX_LENGTH", "50000")),
            schedule_times=_parse_csv(os.getenv("SCHEDULE_TIMES", "08:00,18:00")),
            timezone=os.getenv("TIMEZONE", "Europe/Paris"),
        )
        return cls(**_apply_overrides(kwargs))

    @property
    def has_llm_credentials(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def has_email_delivery(self) -> bool:
        return bool(self.sender_email and self.recipient_emails)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Settings are cached so imports across the app share the same resolved config.
    return Settings.from_env()

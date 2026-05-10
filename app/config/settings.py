from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class Settings:
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database configuration
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/techwatch"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/techwatch"

    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000

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
    gmail_credentials_path: str = "credentials.json"
    gmail_token_path: str = "token.json"

    tavily_api_key: str = ""
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

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/techwatch",
            ),
            database_sync_url=os.getenv(
                "DATABASE_SYNC_URL",
                "postgresql://postgres:postgres@localhost:5432/techwatch",
            ),
            llm_provider=os.getenv("LLM_PROVIDER", "openrouter"),
            llm_base_url=os.getenv("LLM_BASE_URL", ""),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", ""),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            llm_max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
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
            gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
            gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", "token.json"),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
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

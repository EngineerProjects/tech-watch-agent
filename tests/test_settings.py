from __future__ import annotations

import os
from pathlib import Path

from app.config.settings import Settings, get_settings


def test_settings_parse_lists_from_env_file(tmp_path: Path) -> None:
    get_settings.cache_clear()
    os.environ.pop("NEWSLETTER_TOPICS", None)
    os.environ.pop("RECIPIENT_EMAILS", None)
    os.environ.pop("SCHEDULE_TIMES", None)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "NEWSLETTER_TOPICS=AI news,OpenAI updates",
                "RECIPIENT_EMAILS=a@example.com,b@example.com",
                "SCHEDULE_TIMES=08:00,18:00",
                "LLM_API_KEY=test-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings.from_env(env_file)

    assert settings.newsletter_topics == ["AI news", "OpenAI updates"]
    assert settings.recipient_emails == ["a@example.com", "b@example.com"]
    assert settings.schedule_times == ["08:00", "18:00"]
    assert settings.has_llm_credentials is True

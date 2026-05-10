from __future__ import annotations

from app.config.settings import Settings, get_settings
from app.core.models import Article


class ArticleRanker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def filter_relevant_articles(self, articles: list[Article], topic: str) -> list[Article]:
        topic_keywords = topic.lower().split()
        ranked: list[Article] = []

        for article in articles:
            title_lower = article.title.lower()
            summary_lower = article.summary.lower()

            relevance_score = 0
            for keyword in topic_keywords:
                if keyword in title_lower:
                    relevance_score += 2
                if keyword in summary_lower:
                    relevance_score += 1

            if relevance_score == 0 and self._looks_like_tech_article(title_lower, summary_lower):
                relevance_score = 1

            if relevance_score <= 0:
                continue

            article.relevance_score = relevance_score
            article.topic = topic
            ranked.append(article)

        ranked.sort(key=lambda item: item.relevance_score, reverse=True)
        return ranked[: self.settings.max_articles_per_topic]

    @staticmethod
    def _looks_like_tech_article(title: str, summary: str) -> bool:
        keywords = (
            "ai",
            "artificial",
            "intelligence",
            "tech",
            "technology",
            "startup",
            "openai",
            "google",
            "machine",
            "learning",
            "data",
            "algorithm",
            "neural",
            "deep",
        )
        return any(keyword in title or keyword in summary for keyword in keywords)

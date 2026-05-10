from __future__ import annotations

from app.config.settings import Settings
from app.core.models import Article
from app.services.article_ranker import ArticleRanker


def test_article_ranker_sorts_by_relevance() -> None:
    ranker = ArticleRanker(Settings(max_articles_per_topic=5))
    articles = [
        Article(
            title="AI breakthrough changes machine learning",
            summary="A major AI leap",
            url="https://example.com/1",
            topic="",
        ),
        Article(
            title="General startup update",
            summary="A tech startup expands operations",
            url="https://example.com/2",
            topic="",
        ),
    ]

    ranked = ranker.filter_relevant_articles(articles, "AI news")

    assert ranked[0].url == "https://example.com/1"
    assert all(article.topic == "AI news" for article in ranked)

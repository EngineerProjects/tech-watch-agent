from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from app.config.settings import Settings, get_settings
from app.core.models import Article
from app.core.logging import get_logger

logger = get_logger(__name__)

# Comprehensive list of tech-related keywords for secondary scoring
TECH_KEYWORDS = frozenset({
    "ai", "artificial intelligence", "ml", "machine learning", "deep learning",
    "llm", "large language model", "transformer", "neural network", "generative ai",
    "openai", "anthropic", "google", "meta", "nvidia", "microsoft", "apple",
    "python", "rust", "typescript", "golang", "java", "c++",
    "cloud", "aws", "azure", "gcp", "serverless", "kubernetes", "docker",
    "devops", "ci/cd", "security", "cybersecurity", "encryption", "privacy",
    "blockchain", "crypto", "web3", "metaverse", "vr", "ar",
    "quantum computing", "robotics", "automation", "iot", "edge computing",
    "database", "sql", "nosql", "vector database", "rag", "langchain",
    "startup", "funding", "acquisition", "ipo", "market trend",
    "framework", "library", "open source", "github", "stack overflow",
    "benchmark", "performance", "optimization", "scalability",
})

class ArticleRanker:
    """Ranks and filters articles based on relevance to a topic."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def rank_articles(self, articles: list[Article], topic: str) -> list[Article]:
        """Rank articles by relevance to topic without filtering.
        
        Args:
            articles: List of articles to rank
            topic: The research topic
            
        Returns:
            List of articles with relevance_score set, sorted by score
        """
        topic_lower = topic.lower()
        topic_words = set(re.findall(r'\w+', topic_lower))
        # Remove small stop words from topic words
        topic_words = {w for w in topic_words if len(w) > 2}

        for article in articles:
            score = self.compute_score(article, topic_lower, topic_words)
            article.relevance_score = score
            article.topic = topic

        # Sort by score (descending) and then by date if available
        return sorted(
            articles, 
            key=lambda x: (x.relevance_score, x.published_date or ""), 
            reverse=True
        )

    def filter_relevant_articles(self, articles: list[Article], topic: str, limit: Optional[int] = None) -> list[Article]:
        """Rank and filter articles, returning only the most relevant ones.
        
        Args:
            articles: List of articles to filter
            topic: The research topic
            limit: Optional limit on number of articles (defaults to settings)
            
        Returns:
            Sorted list of relevant articles
        """
        ranked = self.rank_articles(articles, topic)
        
        # Filter out very low relevance articles (score <= 0)
        relevant = [a for a in ranked if a.relevance_score > 0]
        
        # Apply limit
        max_articles = limit or self.settings.max_articles_per_topic
        return relevant[:max_articles]

    def compute_score(self, article: Article, topic_lower: str, topic_words: set[str]) -> int:
        """Compute a detailed relevance score for an article.

        Scoring logic:
        - Exact topic match in title: +10
        - Exact topic match in summary: +5
        - Word match in title: +2 per word
        - Word match in summary: +1 per word
        - Tech keyword match: +1 (cap at 3)
        - Recency bonus: +3 today, +2 yesterday, +1 last 7 days
        - Content length bonus: +1 if summary > 200 chars
        """
        title_lower = article.title.lower() if article.title else ""
        summary_lower = article.summary.lower() if article.summary else ""

        score = 0

        # 1. Exact phrase match
        if topic_lower in title_lower:
            score += 10
        elif topic_lower in summary_lower:
            score += 5

        # 2. Individual word matches
        for word in topic_words:
            if word in title_lower:
                score += 2
            if word in summary_lower:
                score += 1

        # 3. Tech keyword context
        tech_score = 0
        for kw in TECH_KEYWORDS:
            if kw in title_lower or kw in summary_lower:
                tech_score += 1
                if tech_score >= 3:
                    break
        score += tech_score

        # 4. Recency bonus
        if article.published_date:
            try:
                pub = article.published_date
                if isinstance(pub, str):
                    pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                age_days = (now - pub).days
                if age_days == 0:
                    score += 3
                elif age_days == 1:
                    score += 2
                elif age_days <= 7:
                    score += 1
            except Exception:
                pass

        # 5. Content length bonus (prefer articles with actual content/summary)
        if len(summary_lower) > 200:
            score += 1

        return score

    @staticmethod
    def _looks_like_tech_article(title: str, summary: str) -> bool:
        """Heuristic to check if an article is tech-related."""
        t_lower = title.lower()
        s_lower = summary.lower()
        return any(kw in t_lower or kw in s_lower for kw in TECH_KEYWORDS)

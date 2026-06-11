import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from app.db.base import async_session_factory
from app.db.repositories import ArticleRepository
from app.api.models import ArticleResponse

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    topics: Optional[str] = Query(None),
    sources: Optional[str] = Query(None),
    min_relevance: int = Query(0),
    limit: int = Query(50),
) -> list[ArticleResponse]:
    """List articles with optional filters."""
    topic_list = topics.split(",") if topics else None

    async with async_session_factory() as session:
        repo = ArticleRepository(session)

        if topic_list:
            articles = []
            for topic in topic_list:
                topic_articles = await repo.get_by_topic(topic, limit)
                articles.extend(topic_articles)
        else:
            articles = await repo.get_recent(limit=limit)

        return [
            ArticleResponse(
                id=str(a.id),
                title=a.title,
                summary=a.summary,
                url=a.url,
                source=a.source,
                topic=a.topic,
                published_date=a.published_date,
                relevance_score=a.relevance_score,
            )
            for a in articles[:limit]
        ]

@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str) -> ArticleResponse:
    """Get a specific article."""
    async with async_session_factory() as session:
        repo = ArticleRepository(session)
        article = await repo.get_by_id(uuid.UUID(article_id))

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        return ArticleResponse(
            id=str(article.id),
            title=article.title,
            summary=article.summary,
            url=article.url,
            source=article.source,
            topic=article.topic,
            published_date=article.published_date,
            relevance_score=article.relevance_score,
        )

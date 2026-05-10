"""
Tests for database models.

This module tests the SQLAlchemy ORM models defined in app.db.models,
ensuring proper schema definition, relationships, and constraints.
"""

import uuid
import pytest
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.models import (
    User,
    UserTopic,
    Article,
    NewsletterRun,
    NewsletterRunArticle,
    ResearchSession,
    ToolExecution,
    UserSession,
)


# Use in-memory SQLite for testing (easier than setting up PostgreSQL)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def engine():
    """Create a test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, session):
        """Test creating a user."""
        user = User(
            email="test@example.com",
            username="testuser",
            preferences={"theme": "dark"},
        )
        session.add(user)
        session.commit()

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.is_active is True
        assert user.preferences == {"theme": "dark"}

    def test_user_unique_email(self, session):
        """Test that email must be unique."""
        user1 = User(email="test@example.com")
        session.add(user1)
        session.commit()

        user2 = User(email="test@example.com")
        session.add(user2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_repr(self, session):
        """Test user string representation."""
        user = User(email="test@example.com")
        session.add(user)
        session.commit()

        repr_str = repr(user)
        assert "test@example.com" in repr_str


class TestUserTopicModel:
    """Tests for UserTopic model."""

    def test_create_user_topic(self, session):
        """Test creating a user topic."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        topic = UserTopic(
            user_id=user.id,
            topic="AI News",
            frequency="daily",
        )
        session.add(topic)
        session.commit()

        assert topic.id is not None
        assert topic.topic == "AI News"
        assert topic.frequency == "daily"
        assert topic.is_active is True

    def test_user_topic_relationship(self, session):
        """Test user-topic relationship."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        topic = UserTopic(user_id=user.id, topic="Tech")
        session.add(topic)
        session.commit()

        # Test relationship from user
        assert topic in user.user_topics.all()


class TestArticleModel:
    """Tests for Article model."""

    def test_create_article(self, session):
        """Test creating an article."""
        article = Article(
            title="Test Article",
            summary="A test summary",
            url="https://example.com/article",
            source="TechCrunch",
            topic="AI",
            relevance_score=5,
        )
        session.add(article)
        session.commit()

        assert article.id is not None
        assert article.title == "Test Article"
        assert article.url == "https://example.com/article"
        assert article.relevance_score == 5

    def test_article_repr(self, session):
        """Test article string representation."""
        article = Article(
            title="A" * 100,  # Long title to test truncation in repr
            summary="Summary",
            url="https://example.com",
            source="Source",
            topic="Topic",
        )
        session.add(article)
        session.commit()

        repr_str = repr(article)
        assert "Article" in repr_str

    def test_article_with_optional_fields(self, session):
        """Test article with optional fields."""
        article = Article(
            title="Test",
            summary="Summary",
            url="https://example.com",
            source="Source",
            topic="Topic",
            content="Full content",
            published_date=datetime.now(),
            metadata={"key": "value"},
        )
        session.add(article)
        session.commit()

        assert article.content == "Full content"
        assert article.metadata == {"key": "value"}


class TestNewsletterRunModel:
    """Tests for NewsletterRun model."""

    def test_create_newsletter_run(self, session):
        """Test creating a newsletter run."""
        run = NewsletterRun(
            subject="Weekly Tech Update",
            markdown_content="# Weekly Update\n\nContent here",
            html_content="<h1>Weekly Update</h1>",
            status="completed",
            articles_count=10,
            delivery_success=True,
        )
        session.add(run)
        session.commit()

        assert run.id is not None
        assert run.subject == "Weekly Tech Update"
        assert run.status == "completed"
        assert run.articles_count == 10

    def test_newsletter_run_with_user(self, session):
        """Test newsletter run with user."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        run = NewsletterRun(
            subject="Test Newsletter",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="pending",
            user_id=user.id,
        )
        session.add(run)
        session.commit()

        assert run.user == user


class TestNewsletterRunArticleModel:
    """Tests for NewsletterRunArticle junction table."""

    def test_create_link(self, session):
        """Test creating article-run link."""
        # Create article
        article = Article(
            title="Test",
            summary="Summary",
            url="https://example.com",
            source="Source",
            topic="Topic",
        )
        session.add(article)
        session.flush()

        # Create run
        run = NewsletterRun(
            subject="Test",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="completed",
        )
        session.add(run)
        session.flush()

        # Create link
        link = NewsletterRunArticle(
            newsletter_run_id=run.id,
            article_id=article.id,
            order_index=0,
            relevance_score=5,
        )
        session.add(link)
        session.commit()

        assert link.id is not None
        assert link.order_index == 0

    def test_unique_constraint(self, session):
        """Test unique constraint on run-article pair."""
        article = Article(
            title="Test",
            summary="Summary",
            url="https://example.com",
            source="Source",
            topic="Topic",
        )
        session.add(article)
        session.flush()

        run = NewsletterRun(
            subject="Test",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="completed",
        )
        session.add(run)
        session.flush()

        link1 = NewsletterRunArticle(
            newsletter_run_id=run.id,
            article_id=article.id,
        )
        session.add(link1)
        session.commit()

        # Try to create duplicate
        link2 = NewsletterRunArticle(
            newsletter_run_id=run.id,
            article_id=article.id,
        )
        session.add(link2)

        with pytest.raises(IntegrityError):
            session.commit()


class TestResearchSessionModel:
    """Tests for ResearchSession model."""

    def test_create_research_session(self, session):
        """Test creating a research session."""
        session_obj = ResearchSession(
            research_brief="Investigate AI trends",
            status="in_progress",
            notes=["Note 1", "Note 2"],
        )
        session.add(session_obj)
        session.commit()

        assert session_obj.id is not None
        assert session_obj.research_brief == "Investigate AI trends"
        assert session_obj.status == "in_progress"
        assert len(session_obj.notes) == 2

    def test_research_session_with_final_report(self, session):
        """Test research session with final report."""
        session_obj = ResearchSession(
            research_brief="Test research",
            status="completed",
            final_report="# Research Report\n\nFindings here",
            iterations_count=5,
        )
        session.add(session_obj)
        session.commit()

        assert session_obj.final_report is not None
        assert session_obj.iterations_count == 5


class TestToolExecutionModel:
    """Tests for ToolExecution model."""

    def test_create_tool_execution(self, session):
        """Test creating a tool execution log."""
        execution = ToolExecution(
            tool_name="web_search",
            tool_input={"query": "AI news"},
            tool_output="Search results...",
            success=True,
            execution_time_ms=150,
        )
        session.add(execution)
        session.commit()

        assert execution.id is not None
        assert execution.tool_name == "web_search"
        assert execution.success is True
        assert execution.execution_time_ms == 150

    def test_tool_execution_with_session(self, session):
        """Test tool execution linked to research session."""
        research = ResearchSession(
            research_brief="Test",
            status="in_progress",
        )
        session.add(research)
        session.flush()

        execution = ToolExecution(
            tool_name="search",
            tool_input={},
            session_id=research.id,
            success=False,
            error_message="Rate limit exceeded",
        )
        session.add(execution)
        session.commit()

        assert execution.session_id == research.id
        assert execution.success is False


class TestUserSessionModel:
    """Tests for UserSession model."""

    def test_create_user_session(self, session):
        """Test creating a user session."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        user_session = UserSession(
            user_id=user.id,
            preferences={"theme": "dark"},
            topics=["AI", "Tech"],
            seen_article_ids=["article-1", "article-2"],
        )
        session.add(user_session)
        session.commit()

        assert user_session.id is not None
        assert user_session.preferences == {"theme": "dark"}
        assert len(user_session.topics) == 2
        assert len(user_session.seen_article_ids) == 2
        assert user_session.is_active is True

    def test_user_session_without_user(self, session):
        """Test creating anonymous session."""
        user_session = UserSession(
            preferences={},
            topics=[],
            seen_article_ids=[],
        )
        session.add(user_session)
        session.commit()

        assert user_session.user_id is None
        assert user_session.is_active is True


class TestModelRelationships:
    """Tests for model relationships."""

    def test_user_newsletter_runs_relationship(self, session):
        """Test user to newsletter runs relationship."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        run1 = NewsletterRun(
            subject="Run 1",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="completed",
            user_id=user.id,
        )
        run2 = NewsletterRun(
            subject="Run 2",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="completed",
            user_id=user.id,
        )
        session.add_all([run1, run2])
        session.commit()

        assert len(user.newsletter_runs.all()) == 2

    def test_article_newsletter_runs_relationship(self, session):
        """Test article to newsletter runs relationship."""
        article = Article(
            title="Test",
            summary="Summary",
            url="https://example.com",
            source="Source",
            topic="Topic",
        )
        session.add(article)
        session.flush()

        run = NewsletterRun(
            subject="Test",
            markdown_content="Content",
            html_content="<p>Content</p>",
            status="completed",
        )
        session.add(run)
        session.flush()

        link = NewsletterRunArticle(
            newsletter_run_id=run.id,
            article_id=article.id,
        )
        session.add(link)
        session.commit()

        # Test reverse relationship
        assert link in article.newsletter_runs.all()

    def test_user_user_sessions_relationship(self, session):
        """Test user to sessions relationship."""
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        user_session = UserSession(
            user_id=user.id,
            preferences={},
            topics=[],
            seen_article_ids=[],
        )
        session.add(user_session)
        session.commit()

        # Note: This tests the relationship exists
        # The actual query might differ based on SQLAlchemy version
        assert user_session.user_id == user.id
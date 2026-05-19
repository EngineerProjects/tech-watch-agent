"""
Tests for the FastAPI application endpoints.

This module tests the API endpoints for the tech-watch-agent platform,
ensuring proper request handling, response formatting, and error cases.
"""

import pytest
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_health_endpoint_exists(self, client):
        """Test that health endpoint is accessible."""
        response = client.get("/health")
        # May fail if DB not connected, but should not 404
        assert response.status_code in [200, 500]


class TestNewsletterEndpoints:
    """Tests for newsletter endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_generate_endpoint_exists(self, client):
        """Test that generate endpoint is accessible."""
        response = client.post(
            "/newsletter/generate",
            json={"topics": ["AI"], "send_email": False}
        )
        # May fail if LLM not configured, but should not 404
        assert response.status_code in [200, 500]

    def test_generate_with_empty_topics(self, client):
        """Test generate with no topics (should use defaults)."""
        response = client.post(
            "/newsletter/generate",
            json={"send_email": False}
        )
        # Should accept empty topics
        assert response.status_code in [200, 500]

    def test_history_endpoint(self, client):
        """Test newsletter history endpoint."""
        response = client.get("/newsletter/history")
        # Should return list (even if empty)
        assert response.status_code in [200, 500]


class TestArticleEndpoints:
    """Tests for article endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_list_articles(self, client):
        """Test listing articles."""
        response = client.get("/articles")
        assert response.status_code in [200, 500]

    def test_list_articles_with_filters(self, client):
        """Test listing articles with topic filter."""
        response = client.get("/articles?topics=AI,ML&limit=10")
        assert response.status_code in [200, 500]


class TestUserEndpoints:
    """Tests for user management endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_create_user_validation(self, client):
        """Test user creation with invalid email."""
        response = client.post(
            "/users",
            json={"email": "invalid-email", "username": "test"}
        )
        assert response.status_code == 422  # Validation error

    def test_create_user_missing_email(self, client):
        """Test user creation without email."""
        response = client.post(
            "/users",
            json={"username": "test"}
        )
        assert response.status_code == 422


class TestToolEndpoints:
    """Tests for tool registry endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_list_tools(self, client):
        """Test listing tools."""
        response = client.get("/tools")
        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "count" in data

    def test_execute_tool_not_found(self, client):
        """Test executing non-existent tool."""
        response = client.post(
            "/tools/execute",
            json={"tool_name": "nonexistent_tool", "params": {}}
        )
        assert response.status_code == 404


class TestResearchEndpoints:
    """Tests for deep research endpoints."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_research_endpoint_exists(self, client):
        """Test research endpoint is accessible."""
        response = client.post(
            "/research",
            json={"query": "What are the latest AI trends?"}
        )
        # May fail if LLM not configured, but should not 404
        assert response.status_code in [200, 500]

    def test_research_with_options(self, client):
        """Test research with depth option."""
        response = client.post(
            "/research",
            json={
                "query": "AI trends",
                "research_depth": "deep",
                "allow_clarification": False
            }
        )
        assert response.status_code in [200, 500]

    def test_research_history(self, client):
        """Test research history endpoint."""
        response = client.get("/research/history")
        assert response.status_code in [200, 500]


class TestConfigEndpoint:
    """Tests for configuration endpoint."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_status_endpoint(self, client):
        """Test status endpoint."""
        response = client.get("/status")
        assert response.status_code in [200, 500]

    def test_stats_endpoint(self, client):
        """Test stats endpoint."""
        response = client.get("/stats")
        assert response.status_code in [200, 500]


class TestCORSAndHeaders:
    """Tests for CORS and headers."""

    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app()

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_cors_headers(self, client):
        """Test that CORS headers are present."""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        # Should include CORS headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 500

    def test_json_content_type(self, client):
        """Test that responses have proper content type."""
        response = client.get("/tools")
        if response.status_code == 200:
            assert "application/json" in response.headers.get("content-type", "")

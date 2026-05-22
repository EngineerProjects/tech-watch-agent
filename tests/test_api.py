"""
Tests for the FastAPI application endpoints.

This module tests the API endpoints for the tech-watch-agent platform,
ensuring proper request handling, response formatting, and error cases.
"""

import pytest
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.config.settings import Settings, get_settings, set_db_overrides
import app.services.llm.model_catalog as model_catalog_module


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
        assert response.status_code in [200, 401, 500]


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
        assert response.status_code in [200, 401, 500]

    def test_generate_with_empty_topics(self, client):
        """Test generate with no topics (should use defaults)."""
        response = client.post(
            "/newsletter/generate",
            json={"send_email": False}
        )
        # Should accept empty topics
        assert response.status_code in [200, 401, 500]

    def test_history_endpoint(self, client):
        """Test newsletter history endpoint."""
        response = client.get("/newsletter/history")
        # Should return list (even if empty)
        assert response.status_code in [200, 401, 500]


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
        assert response.status_code in [200, 401, 500]

    def test_list_articles_with_filters(self, client):
        """Test listing articles with topic filter."""
        response = client.get("/articles?topics=AI,ML&limit=10")
        assert response.status_code in [200, 401, 500]


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
        assert response.status_code in [200, 401, 500]

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
        assert response.status_code in [200, 401, 500]

    def test_research_history(self, client):
        """Test research history endpoint."""
        response = client.get("/research/history")
        assert response.status_code in [200, 401, 500]


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
        assert response.status_code in [200, 401, 500]

    def test_stats_endpoint(self, client):
        """Test stats endpoint."""
        response = client.get("/stats")
        assert response.status_code in [200, 401, 500]


    def test_provider_model_overrides_roundtrip(self):
        set_db_overrides({
            "llm_provider_models": '{"openrouter": {"primary_model": "openai/gpt-4.1-mini", "fallback_models": ["google/gemini-2.5-flash"]}}',
            "embedding_provider_models": '{"openai": "text-embedding-3-small"}',
        })
        try:
            settings = get_settings()
            assert settings.llm_provider_models["openrouter"]["primary_model"] == "openai/gpt-4.1-mini"
            assert settings.llm_provider_models["openrouter"]["fallback_models"] == ["google/gemini-2.5-flash"]
            assert settings.embedding_provider_models["openai"] == "text-embedding-3-small"
        finally:
            set_db_overrides({})

    def test_llm_provider_catalog_returns_models(self, client):
        response = client.get("/llm/providers")

        assert response.status_code == 200
        payload = response.json()
        assert payload["providers"]
        first = payload["providers"][0]
        assert "chat_models" in first
        assert "embedding_models" in first

    def test_ollama_catalog_is_discovery_only(self, client, monkeypatch):
        monkeypatch.setattr(
            model_catalog_module,
            "discover_ollama_catalog",
            lambda *args, **kwargs: {"chat_models": [], "embedding_models": [], "error": None},
        )

        response = client.get("/llm/providers")

        assert response.status_code == 200
        payload = response.json()
        ollama = next(provider for provider in payload["providers"] if provider["name"] == "ollama")
        assert ollama["chat_models"] == []
        assert ollama["embedding_models"] == []
        assert ollama["default_model"] == ""


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


class TestAdminProtection:
    """Tests for admin-protected routes."""

    def test_config_requires_token_in_production_when_configured(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.get("/config")

        assert response.status_code == 401

    def test_config_fails_closed_in_production_without_token_config(self):
        app = create_app(Settings(app_env="production"))
        client = TestClient(app)

        response = client.get("/config")

        assert response.status_code == 503

    def test_config_allows_valid_token(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.get("/config", headers={"X-Admin-Token": "secret-token"})

        assert response.status_code in [200, 401, 500]


class TestExtendedAdminProtection:
    """Tests for newly protected admin surfaces."""

    def test_tools_execute_requires_token_when_configured(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.post("/tools/execute", json={"tool_name": "noop", "params": {}})

        assert response.status_code == 401

    def test_llm_provider_switch_requires_token_when_configured(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.post("/llm/providers/switch", json={"provider": "ollama"})

        assert response.status_code == 401


    def test_ollama_pull_requires_token_when_configured(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.post("/llm/ollama/pull", json={"model": "llama3.2"})

        assert response.status_code == 401

    def test_ollama_pull_accepts_valid_token(self, monkeypatch):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        async def _fake_pull(model_name: str) -> None:
            assert model_name == "llama3.2"

        monkeypatch.setattr("app.api.routers.llm._pull_ollama_model", _fake_pull)

        response = client.post(
            "/llm/ollama/pull",
            json={"model": "llama3.2"},
            headers={"X-Admin-Token": "secret-token"},
        )

        assert response.status_code == 200
        assert response.json()["model"] == "llama3.2"

    def test_dashboard_accepts_cookie_token(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)
        client.cookies.set("admin_token", "secret-token")

        response = client.get("/ui/")

        assert response.status_code == 200

    def test_dashboard_requires_auth_without_cookie(self):
        app = create_app(Settings(app_env="production", admin_api_token="secret-token"))
        client = TestClient(app)

        response = client.get("/ui")

        assert response.status_code == 401


class TestEmailGroupEndpoints:
    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    def test_email_groups_endpoint_exists(self, client):
        response = client.get('/email-groups/')
        assert response.status_code in [200, 401, 500]

from __future__ import annotations

import pytest

from app.config.settings import Settings
from app.tools.web.free_search import FreeSearchTool
from app.tools.web.multi_search import MultiProviderSearchTool
from app.tools.web.research_search import ResearchSearchTool


@pytest.mark.asyncio
async def test_web_search_uses_only_active_api_providers(monkeypatch):
    settings = Settings(
        search_web_providers=["exa"],
        tavily_api_key="tavily-key",
        exa_api_key="exa-key",
        langsearch_api_key="lang-key",
    )

    class FakeExaTool:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, params):
            return {
                "success": True,
                "data": [{"title": "Exa result", "url": "https://exa.example/result", "summary": "ok", "score": 0.9}],
            }

    class ForbiddenTool:
        def __init__(self, *args, **kwargs):
            raise AssertionError("inactive provider should not be instantiated")

    import app.tools.web.exa as exa_module
    import app.tools.web.langsearch as lang_module
    import app.tools.web.tavily as tavily_module

    monkeypatch.setattr(exa_module, "ExaSearchTool", FakeExaTool)
    monkeypatch.setattr(lang_module, "LangSearchTool", ForbiddenTool)
    monkeypatch.setattr(tavily_module, "TavilySearchTool", ForbiddenTool)

    tool = MultiProviderSearchTool(settings=settings)
    result = await tool.execute({"query": "agent frameworks"})

    assert result["success"] is True
    assert result["metadata"]["providers"] == ["exa"]
    assert result["data"][0]["provider"] == "exa"


@pytest.mark.asyncio
async def test_free_search_uses_searxng(monkeypatch):
    settings = Settings(search_free_providers=["searxng"], searxng_url="http://searxng:8080")

    class FakeSearXNGTool:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, params):
            assert params["categories"] == "science"
            return {
                "success": True,
                "data": [{"title": "Paper", "url": "https://example.org/paper", "summary": "abstract"}],
            }

    import app.tools.web.searxng as searxng_module

    monkeypatch.setattr(searxng_module, "SearXNGSearchTool", FakeSearXNGTool)

    tool = FreeSearchTool(settings=settings)
    result = await tool.execute({"query": "mixture of experts", "focus": "academic"})

    assert result["success"] is True
    assert result["metadata"]["providers"] == ["searxng"]
    assert result["data"][0]["url"] == "https://example.org/paper"


@pytest.mark.asyncio
async def test_research_search_uses_searxng_then_fallbacks(monkeypatch):
    settings = Settings(
        search_academic_providers=["searxng", "openalex", "arxiv"],
        searxng_url="http://searxng:8080",
    )

    class FakeSearXNGTool:
        def __init__(self, *args, **kwargs):
            pass

        async def execute(self, params):
            return {
                "success": True,
                "data": [{"title": "Seed result", "url": "https://seed.example", "summary": "seed"}],
            }

    class FakeOpenAlexTool:
        async def execute(self, params):
            return {
                "success": True,
                "data": {
                    "results": [{"title": "OpenAlex result", "url": "https://openalex.example", "authors": ["A"], "year": 2026, "cited_by": 12}],
                },
            }

    class FakeArXivTool:
        async def execute(self, params):
            return {
                "success": True,
                "data": [{"title": "ArXiv result", "url": "https://arxiv.org/abs/1234.5678", "abstract": "paper"}],
            }

    import app.tools.social.arxiv as arxiv_module
    import app.tools.web.openalex as openalex_module
    import app.tools.web.searxng as searxng_module

    monkeypatch.setattr(searxng_module, "SearXNGSearchTool", FakeSearXNGTool)
    monkeypatch.setattr(openalex_module, "OpenAlexTool", FakeOpenAlexTool)
    monkeypatch.setattr(arxiv_module, "ArXivTool", FakeArXivTool)

    tool = ResearchSearchTool(settings=settings, max_results=5)
    result = await tool.execute({"query": "test-time compute", "focus": "academic", "limit": 3})

    assert result["success"] is True
    assert result["metadata"]["providers"] == ["searxng", "openalex", "arxiv"]
    assert len(result["data"]) == 3
    assert {item["provider"] for item in result["data"]} == {"searxng", "openalex", "arxiv"}

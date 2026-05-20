from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.embedding.service import DEFAULT_EMBEDDING_DIM, EmbeddingService
from app.tools.memory.search_memory import SearchMemoryTool


def test_embedding_fallback_has_expected_dimension() -> None:
    service = EmbeddingService(provider="unsupported-provider")

    result = service._embed_fallback("offline embedding input")

    assert result.provider == "fallback"
    assert len(result.embedding) == DEFAULT_EMBEDDING_DIM
    assert any(value != 0.0 for value in result.embedding)


@pytest.mark.asyncio
async def test_search_memory_uses_vector_store_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class DummyContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeVectorStore:
        def __init__(self, session, config=None):
            self.session = session
            self.config = config

        async def generate_embedding(self, text: str) -> list[float]:
            captured["query_text"] = text
            return [0.1] * DEFAULT_EMBEDDING_DIM

        async def search(self, **kwargs):
            captured.update(kwargs)
            return [
                SimpleNamespace(
                    id="article-1",
                    score=0.91,
                    metadata={
                        "title": "AI systems update",
                        "url": "https://example.com/ai",
                        "summary": "Latest change",
                        "topic": "AI",
                        "source": "test",
                    },
                )
            ]

    monkeypatch.setattr("app.db.base.get_db_context", lambda: DummyContext())
    monkeypatch.setattr("app.rag.vector_store.VectorStore", FakeVectorStore)

    tool = SearchMemoryTool()
    result = await tool.execute({"query": "AI", "top_k": 2, "topic_filter": "AI", "min_score": 0.5})

    assert result["success"] is True
    assert captured["query_text"] == "AI"
    assert captured["top_k"] == 4
    assert captured["similarity_threshold"] == 0.5
    assert captured["filter_metadata"] == {"topic": "AI"}
    assert captured["query_embedding"]

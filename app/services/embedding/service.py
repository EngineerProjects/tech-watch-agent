"""
Embedding service for vector search.

Provides real embeddings using:
1. OpenAI embeddings
2. OpenRouter embeddings
3. Z.ai embeddings
4. Ollama embeddings

Features:
- Batch processing for efficiency
- In-memory caching
- Fallback chain for resilience
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from app.config.settings import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)
DEFAULT_EMBEDDING_DIM = 1536


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    embedding: list[float]
    model: str
    provider: str
    tokens_used: int = 0
    cached: bool = False


class EmbeddingService:
    """Multi-provider embedding service with fallback support."""

    _providers_all_failed: bool = False

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or self._settings.embedding_provider
        self._model = model or self._settings.embedding_model or self._get_default_model()
        self._cache: dict[str, list[float]] = {}
        self._cache_size = 1000

    def _get_default_model(self) -> str:
        if self._provider == "openai":
            return "text-embedding-3-small"
        if self._provider == "openrouter":
            return "openai/text-embedding-3-small"
        if self._provider == "zai":
            return "embedding-2"
        if self._provider == "ollama":
            from app.services.llm.model_catalog import discover_ollama_catalog

            discovered = discover_ollama_catalog(self._settings.llm_base_url)
            embedding_models = discovered.get("embedding_models", []) or []
            return embedding_models[0].id if embedding_models else ""
        return "text-embedding-3-small"

    async def embed(self, text: str) -> EmbeddingResult:
        if EmbeddingService._providers_all_failed:
            return self._embed_fallback(text)

        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self._model,
                provider=self._provider,
                cached=True,
            )

        try:
            return await self._embed_via_provider(self._provider, text)
        except Exception as exc:
            logger.warning("%s embedding failed: %s, trying fallback chain", self._provider, exc)
            return await self._embed_with_fallback(text, failed_provider=self._provider)

    async def _embed_via_provider(self, provider: str, text: str) -> EmbeddingResult:
        if provider == "openai":
            return await self._embed_openai(text)
        if provider == "openrouter":
            return await self._embed_openrouter(text)
        if provider == "zai":
            return await self._embed_zai(text)
        if provider == "ollama":
            return await self._embed_ollama(text)
        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _fallback_providers(self, failed_provider: str) -> list[str]:
        providers = ["openai", "openrouter", "zai", "ollama"]
        ordered = [p for p in providers if p != failed_provider]

        def configured(provider: str) -> bool:
            if provider == "openai":
                return bool(self._settings.llm_api_key)
            if provider == "openrouter":
                return bool(self._settings.llm_api_key and self._settings.llm_base_url)
            if provider == "zai":
                return bool(self._settings.zai_api_key or self._settings.llm_api_key)
            if provider == "ollama":
                return bool(self._settings.llm_base_url)
            return False

        return [provider for provider in ordered if configured(provider)]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        results = []
        for text in texts:
            results.append(await self.embed(text))
        return results

    async def _embed_openai(self, text: str) -> EmbeddingResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._settings.llm_api_key)
        return await self._embed_openai_compatible(
            client=client,
            provider_name="openai",
            text=text,
            model=self._model,
        )

    async def _embed_openrouter(self, text: str) -> EmbeddingResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self._settings.llm_api_key,
            base_url=(self._settings.llm_base_url or "https://openrouter.ai/api/v1"),
        )
        return await self._embed_openai_compatible(
            client=client,
            provider_name="openrouter",
            text=text,
            model=self._model,
        )

    async def _embed_zai(self, text: str) -> EmbeddingResult:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self._settings.zai_api_key or self._settings.llm_api_key,
            base_url="https://api.z.ai/api/paas/v4",
        )
        return await self._embed_openai_compatible(
            client=client,
            provider_name="zai",
            text=text,
            model=self._model,
        )

    async def _embed_openai_compatible(self, client, provider_name: str, text: str, model: str) -> EmbeddingResult:
        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=model,
                provider=provider_name,
                cached=True,
            )

        response = await client.embeddings.create(
            model=model,
            input=text[:8000],
        )
        embedding = response.data[0].embedding
        self._add_to_cache(cache_key, embedding)

        usage = getattr(response, "usage", None)
        tokens_used = getattr(usage, "total_tokens", 0) if usage is not None else 0
        return EmbeddingResult(
            embedding=embedding,
            model=model,
            provider=provider_name,
            tokens_used=tokens_used,
        )

    async def _embed_ollama(self, text: str) -> EmbeddingResult:
        import httpx

        if not self._model:
            raise ValueError("No Ollama embedding model configured or detected")

        base_url = (self._settings.llm_base_url or "http://localhost:11434/v1").rstrip("/")
        api_url = base_url[:-3] if base_url.endswith("/v1") else base_url

        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self._model,
                provider="ollama",
                cached=True,
            )

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.post(
                f"{api_url}/api/embed",
                json={"model": self._model, "input": text[:8000]},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings") or []
            embedding = embeddings[0] if embeddings else data.get("embedding", [])

            if not embedding:
                raise ValueError("Empty embedding response")

            self._add_to_cache(cache_key, embedding)
            return EmbeddingResult(
                embedding=embedding,
                model=self._model,
                provider="ollama",
            )

    async def _embed_with_fallback(self, text: str, failed_provider: str) -> EmbeddingResult:
        providers = self._fallback_providers(failed_provider)
        for provider in providers:
            try:
                return await self._embed_via_provider(provider, text)
            except Exception as exc:
                logger.warning("Fallback provider %s failed: %s", provider, exc)

        logger.warning("All embedding providers failed, switching to deterministic fallback")
        EmbeddingService._providers_all_failed = True
        return self._embed_fallback(text)

    def _embed_fallback(self, text: str) -> EmbeddingResult:
        import math

        embedding: list[float] = []
        counter = 0
        while len(embedding) < DEFAULT_EMBEDDING_DIM:
            digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
            for i in range(0, len(digest), 4):
                chunk = digest[i:i + 4]
                if len(chunk) < 4:
                    continue
                value = int.from_bytes(chunk, "big") / 0xFFFFFFFF
                embedding.append((value * 2.0) - 1.0)
                if len(embedding) == DEFAULT_EMBEDDING_DIM:
                    break
            counter += 1

        norm = math.sqrt(sum(x * x for x in embedding))
        normalized = [x / norm for x in embedding] if norm else embedding

        cache_key = self._cache_key(text)
        self._add_to_cache(cache_key, normalized)

        return EmbeddingResult(
            embedding=normalized,
            model="fallback-hash",
            provider="fallback",
        )

    async def _sleep_with_backoff(self, attempt: int) -> None:
        import asyncio
        await asyncio.sleep(2**attempt)

    def _add_to_cache(self, key: str, embedding: list[float]) -> None:
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = embedding

    @staticmethod
    def _cache_key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:64]


def create_embedding_service(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> EmbeddingService:
    return EmbeddingService(provider=provider, model=model)

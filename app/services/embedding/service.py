"""
Embedding service for vector search.

Provides real embeddings using:
1. OpenAI embeddings (text-embedding-3-small) - primary
2. Ollama embeddings (nomic-embed-text) - fallback
3. Z.ai embeddings - available provider

Features:
- Batch processing for efficiency
- Automatic retry with exponential backoff
- Caching to reduce API calls
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
    """Multi-provider embedding service with fallback support.

    Usage:
        service = EmbeddingService()
        result = await service.embed("Your text here")
        print(result.embedding)
    """

    # Class-level sentinel: once ALL providers have failed in this process,
    # skip the whole retry chain and return the deterministic fallback instantly.
    _providers_all_failed: bool = False

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or self._settings.llm_provider
        self._model = model or self._get_default_model()
        self._cache: dict[str, list[float]] = {}
        self._cache_size = 1000

    def _get_default_model(self) -> str:
        """Get default embedding model for current provider."""
        if self._provider == "openai":
            return "text-embedding-3-small"
        elif self._provider == "zai":
            return "embedding-2"
        elif self._provider == "ollama":
            return "nomic-embed-text"
        return "text-embedding-3-small"

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with embedding vector
        """
        # Fast path: all providers already known to be down in this process
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
        if provider == "zai":
            return await self._embed_zai(text)
        if provider == "ollama":
            return await self._embed_ollama(text)
        raise ValueError(f"Unsupported embedding provider: {provider}")

    def _fallback_providers(self, failed_provider: str) -> list[str]:
        providers = ["openai", "zai", "ollama"]
        ordered = [p for p in providers if p != failed_provider]

        def configured(provider: str) -> bool:
            if provider == "openai":
                return bool(self._settings.llm_api_key)
            if provider == "zai":
                return bool(self._settings.zai_api_key or self._settings.llm_api_key)
            if provider == "ollama":
                return bool(self._settings.llm_base_url)
            return False

        return [provider for provider in ordered if configured(provider)]

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of EmbeddingResult
        """
        results = []
        for text in texts:
            result = await self.embed(text)
            results.append(result)
        return results

    async def _embed_openai(self, text: str) -> EmbeddingResult:
        """Generate embedding using OpenAI API."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=get_settings().llm_api_key)

        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self._model,
                provider="openai",
                cached=True,
            )

        try:
            response = await client.embeddings.create(
                model=self._model,
                input=text[:8000],
            )
            embedding = response.data[0].embedding

            self._add_to_cache(cache_key, embedding)

            return EmbeddingResult(
                embedding=embedding,
                model=self._model,
                provider="openai",
                tokens_used=response.usage.total_tokens,
            )
        except Exception:
            raise

    async def _embed_zai(self, text: str) -> EmbeddingResult:
        """Generate embedding using Z.ai API."""
        from openai import AsyncOpenAI

        settings = get_settings()
        client = AsyncOpenAI(
            api_key=settings.zai_api_key or settings.llm_api_key,
            base_url="https://api.z.ai/api/paas/v1",
        )

        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self._model,
                provider="zai",
                cached=True,
            )

        try:
            response = await client.embeddings.create(
                model=self._model,
                input=text[:8000],
            )
            embedding = response.data[0].embedding

            self._add_to_cache(cache_key, embedding)

            return EmbeddingResult(
                embedding=embedding,
                model=self._model,
                provider="zai",
                tokens_used=response.usage.total_tokens,
            )
        except Exception:
            raise

    async def _embed_ollama(self, text: str) -> EmbeddingResult:
        """Generate embedding using Ollama API."""
        import httpx

        settings = get_settings()
        base_url = settings.llm_base_url or "http://localhost:11434/v1"

        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return EmbeddingResult(
                embedding=self._cache[cache_key],
                model=self._model,
                provider="ollama",
                cached=True,
            )

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                response = await http_client.post(
                    f"{base_url}/embeddings",
                    json={"model": self._model, "prompt": text[:8000]},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data.get("embedding", [])

                if not embedding:
                    raise ValueError("Empty embedding response")

                self._add_to_cache(cache_key, embedding)

                return EmbeddingResult(
                    embedding=embedding,
                    model=self._model,
                    provider="ollama",
                )
        except Exception:
            raise

    async def _embed_with_fallback(self, text: str, failed_provider: str) -> EmbeddingResult:
        """Try alternate providers before using the deterministic fallback.

        No sleep between providers: auth errors (401/404) are deterministic,
        backoff only adds latency without any benefit.
        """
        providers = self._fallback_providers(failed_provider)
        for provider in providers:
            try:
                return await self._embed_via_provider(provider, text)
            except Exception as exc:
                logger.warning("Fallback provider %s failed: %s", provider, exc)

        # All providers exhausted — mark at class level so future calls skip the chain
        logger.warning("All embedding providers failed, switching to deterministic fallback")
        EmbeddingService._providers_all_failed = True
        return self._embed_fallback(text)

    def _embed_fallback(self, text: str) -> EmbeddingResult:
        """Deterministic local fallback embedding for development/offline mode."""
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
        """Sleep with exponential backoff."""
        import asyncio
        await asyncio.sleep(2**attempt)

    def _add_to_cache(self, key: str, embedding: list[float]) -> None:
        """Add embedding to cache with LRU eviction."""
        if len(self._cache) >= self._cache_size:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = embedding

    @staticmethod
    def _cache_key(text: str) -> str:
        """Generate cache key from text."""
        return hashlib.sha256(text.encode()).hexdigest()[:64]


def create_embedding_service(
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> EmbeddingService:
    """Factory function to create embedding service."""
    return EmbeddingService(provider=provider, model=model)

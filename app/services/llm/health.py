"""
LLM Health Check Manager.

Provides comprehensive health monitoring for LLM providers including:
- Connection status checks
- Latency measurement
- Auto-fallback to healthy providers
- Provider health history
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

from app.core.logging import get_logger
from app.services.llm.providers import (
    LLMProviders,
    LLMProviderConfig,
    get_provider_config,
    list_providers,
)


logger = get_logger(__name__)


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    """Health status for a single provider."""
    name: str
    status: ProviderStatus
    is_reachable: bool
    latency_ms: float | None
    last_check: datetime
    error_message: str | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class HealthCheckResult:
    """Result of a comprehensive health check."""
    overall_healthy: bool
    primary_provider: str
    active_provider: str
    provider_healths: dict[str, ProviderHealth]
    fallback_available: bool
    fallback_provider: str | None
    latency_ms: float | None
    timestamp: datetime = field(default_factory=datetime.now)


class LLMHealthManager:
    """Manages LLM provider health checks and auto-fallback.
    
    Features:
    - Periodic health checks
    - Automatic fallback to healthy providers
    - Latency monitoring
    - Consecutive failure tracking
    """

    def __init__(
        self,
        primary_provider: str = LLMProviders.ZAI,
        fallback_providers: list[str] | None = None,
        health_check_interval: float = 60.0,
        failure_threshold: int = 3,
    ) -> None:
        self._primary_provider = primary_provider
        self._fallback_providers = fallback_providers or [
            LLMProviders.OLLAMA,
            LLMProviders.OPENROUTER,
        ]
        self._health_check_interval = health_check_interval
        self._failure_threshold = failure_threshold
        
        self._provider_healths: dict[str, ProviderHealth] = {}
        self._active_provider: str = primary_provider
        self._last_comprehensive_check: datetime | None = None
        
        # Initialize health statuses
        for provider_name in list_providers():
            self._provider_healths[provider_name] = ProviderHealth(
                name=provider_name,
                status=ProviderStatus.UNKNOWN,
                is_reachable=False,
                latency_ms=None,
                last_check=datetime.now(),
            )

    @property
    def active_provider(self) -> str:
        """Get the currently active (healthy) provider."""
        return self._active_provider

    @property
    def is_healthy(self) -> bool:
        """Check if the active provider is healthy."""
        health = self._provider_healths.get(self._active_provider)
        return health is not None and health.status == ProviderStatus.HEALTHY

    def get_health_status(self, provider_name: str) -> ProviderHealth | None:
        """Get health status for a specific provider."""
        return self._provider_healths.get(provider_name)

    def get_all_healths(self) -> dict[str, ProviderHealth]:
        """Get health statuses for all providers."""
        return self._provider_healths.copy()

    async def check_provider_async(
        self,
        provider_name: str,
        api_key: str = "",
        timeout: float = 10.0,
    ) -> ProviderHealth:
        """Perform async health check on a single provider.
        
        Args:
            provider_name: Name of the provider to check
            api_key: API key (if required)
            timeout: Request timeout in seconds
            
        Returns:
            ProviderHealth with current status
        """
        config = get_provider_config(provider_name)
        if config is None:
            return ProviderHealth(
                name=provider_name,
                status=ProviderStatus.UNKNOWN,
                is_reachable=False,
                latency_ms=None,
                last_check=datetime.now(),
                error_message="Unknown provider",
            )

        start_time = time.time()
        headers = config.build_headers(api_key)
        url = f"{config.base_url.rstrip('/')}/models"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers=headers)
                latency = (time.time() - start_time) * 1000
                
                is_healthy = response.status_code == 200
                
                health = ProviderHealth(
                    name=provider_name,
                    status=ProviderStatus.HEALTHY if is_healthy else ProviderStatus.UNHEALTHY,
                    is_reachable=is_healthy,
                    latency_ms=latency,
                    last_check=datetime.now(),
                    error_message=None if is_healthy else f"HTTP {response.status_code}",
                )
                
                # Update consecutive counts
                current = self._provider_healths.get(provider_name)
                if current:
                    if is_healthy:
                        health.consecutive_successes = current.consecutive_successes + 1
                        health.consecutive_failures = 0
                    else:
                        health.consecutive_failures = current.consecutive_failures + 1
                        health.consecutive_successes = 0
                        health.error_message = f"HTTP {response.status_code}"
                else:
                    health.consecutive_successes = 1 if is_healthy else 0
                    health.consecutive_failures = 0 if is_healthy else 1

                # Determine degraded status
                if latency and latency > 5000:  # > 5 seconds
                    health.status = ProviderStatus.DEGRADED
                    logger.warning("Provider %s latency high: %.0fms", provider_name, latency)

        except httpx.TimeoutException:
            health = ProviderHealth(
                name=provider_name,
                status=ProviderStatus.UNHEALTHY,
                is_reachable=False,
                latency_ms=None,
                last_check=datetime.now(),
                error_message="Timeout",
            )
            current = self._provider_healths.get(provider_name)
            if current:
                health.consecutive_failures = current.consecutive_failures + 1
                health.consecutive_successes = 0

        except httpx.HTTPError as exc:
            health = ProviderHealth(
                name=provider_name,
                status=ProviderStatus.UNHEALTHY,
                is_reachable=False,
                latency_ms=None,
                last_check=datetime.now(),
                error_message=str(exc)[:100],
            )
            current = self._provider_healths.get(provider_name)
            if current:
                health.consecutive_failures = current.consecutive_failures + 1
                health.consecutive_successes = 0

        except Exception as exc:
            health = ProviderHealth(
                name=provider_name,
                status=ProviderStatus.UNHEALTHY,
                is_reachable=False,
                latency_ms=None,
                last_check=datetime.now(),
                error_message=str(exc)[:100],
            )
            current = self._provider_healths.get(provider_name)
            if current:
                health.consecutive_failures = current.consecutive_failures + 1
                health.consecutive_successes = 0

        self._provider_healths[provider_name] = health
        return health

    async def check_all_providers(
        self,
        api_keys: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> HealthCheckResult:
        """Check health of all registered providers.
        
        Args:
            api_keys: Dict mapping provider names to API keys
            timeout: Request timeout in seconds
            
        Returns:
            HealthCheckResult with comprehensive status
        """
        api_keys = api_keys or {}
        tasks = []
        provider_names = list(self._provider_healths.keys())
        
        for provider_name in provider_names:
            api_key = api_keys.get(provider_name, "")
            tasks.append(self.check_provider_async(provider_name, api_key, timeout))
        
        # Run all checks in parallel
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Find healthy fallback
        fallback_provider = None
        for provider in self._fallback_providers:
            health = self._provider_healths.get(provider)
            if health and health.status == ProviderStatus.HEALTHY:
                fallback_provider = provider
                break
        
        # Update active provider if needed
        primary_health = self._provider_healths.get(self._primary_provider)
        if primary_health and primary_health.status != ProviderStatus.HEALTHY:
            if fallback_provider:
                self._active_provider = fallback_provider
                logger.warning(
                    "Primary provider %s unhealthy. Switched to fallback: %s",
                    self._primary_provider, fallback_provider
                )
            else:
                logger.error("No healthy provider available!")
        
        # Calculate overall latency
        active_health = self._provider_healths.get(self._active_provider)
        overall_latency = active_health.latency_ms if active_health else None
        
        self._last_comprehensive_check = datetime.now()
        
        return HealthCheckResult(
            overall_healthy=self.is_healthy,
            primary_provider=self._primary_provider,
            active_provider=self._active_provider,
            provider_healths=self._provider_healths.copy(),
            fallback_available=fallback_provider is not None,
            fallback_provider=fallback_provider,
            latency_ms=overall_latency,
        )

    async def ensure_healthy_provider(self, api_keys: dict[str, str] | None = None) -> str:
        """Ensure we have a healthy provider, switching if necessary.
        
        Args:
            api_keys: Dict mapping provider names to API keys
            
        Returns:
            Name of the healthy provider to use
        """
        current_health = self._provider_healths.get(self._active_provider)
        
        # If current provider is unhealthy or unknown, check and switch
        if current_health is None or current_health.status != ProviderStatus.HEALTHY:
            logger.info("Checking provider health...")
            result = await self.check_all_providers(api_keys)
            
            if not result.overall_healthy:
                logger.error("All providers unhealthy! Using primary anyway.")
        
        return self._active_provider

    def switch_to_provider(self, provider_name: str) -> bool:
        """Manually switch to a specific provider.
        
        Args:
            provider_name: Name of provider to switch to
            
        Returns:
            True if switch successful, False otherwise
        """
        health = self._provider_healths.get(provider_name)
        if health is None:
            logger.error("Cannot switch to unknown provider: %s", provider_name)
            return False
        
        if health.status == ProviderStatus.UNHEALTHY:
            logger.warning(
                "Switching to unhealthy provider: %s (reason: %s)",
                provider_name, health.error_message
            )
        
        self._active_provider = provider_name
        logger.info("Switched to provider: %s", provider_name)
        return True

    def get_best_available_provider(self) -> str:
        """Get the best available provider (healthy with lowest latency).
        
        Returns:
            Name of the best available provider
        """
        candidates = []
        
        # Add primary if healthy
        primary_health = self._provider_healths.get(self._primary_provider)
        if primary_health and primary_health.status == ProviderStatus.HEALTHY:
            candidates.append((self._primary_provider, primary_health.latency_ms or float('inf')))
        
        # Add fallbacks if healthy
        for provider in self._fallback_providers:
            if provider == self._primary_provider:
                continue
            health = self._provider_healths.get(provider)
            if health and health.status == ProviderStatus.HEALTHY:
                candidates.append((provider, health.latency_ms or float('inf')))
        
        if not candidates:
            return self._primary_provider
        
        # Return provider with lowest latency
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def reset_failure_count(self, provider_name: str) -> None:
        """Reset failure count for a provider after successful request.
        
        Args:
            provider_name: Name of provider to reset
        """
        if provider_name in self._provider_healths:
            self._provider_healths[provider_name].consecutive_failures = 0


# Global health manager instance
_health_manager: LLMHealthManager | None = None


def get_health_manager() -> LLMHealthManager:
    """Get the global health manager instance."""
    global _health_manager
    if _health_manager is None:
        _health_manager = LLMHealthManager()
    return _health_manager


def reset_health_manager() -> None:
    """Reset the global health manager (for testing)."""
    global _health_manager
    _health_manager = None

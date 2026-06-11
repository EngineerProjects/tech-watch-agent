"""
Health check system for tech-watch-agent.

This module provides comprehensive health checking for all system components:
- Database connectivity and performance
- Memory/vector store status
- Agent availability and responsiveness
- External service dependencies

The health check system supports:
- Individual component checks
- Aggregated system health
- Detailed status reporting
- Configurable timeouts
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from app.db.base import async_session_factory
from app.core.logging import get_logger


logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for a single component.

    Attributes:
        name: Component name
        status: Health status enum
        message: Human-readable status message
        response_time_ms: Response time in milliseconds (if applicable)
        details: Additional component-specific details
        checked_at: Timestamp of last check
    """

    name: str
    status: HealthStatus
    message: str = ""
    response_time_ms: Optional[float] = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)

    def is_healthy(self) -> bool:
        """Check if component is in healthy state."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
        }


@dataclass
class SystemHealth:
    """Overall system health status.

    Attributes:
        overall_status: Aggregated health status
        components: List of individual component health checks
        uptime_seconds: System uptime
        version: Application version
        timestamp: Overall check timestamp
    """

    overall_status: HealthStatus
    components: list[ComponentHealth] = field(default_factory=list)
    uptime_seconds: float = 0.0
    version: str = "0.2.0"
    timestamp: datetime = field(default_factory=datetime.now)

    def is_healthy(self) -> bool:
        """Check if overall system is healthy."""
        return self.overall_status == HealthStatus.HEALTHY

    def get_unhealthy_components(self) -> list[ComponentHealth]:
        """Get list of unhealthy components."""
        return [c for c in self.components if c.status != HealthStatus.HEALTHY]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.overall_status.value,
            "uptime_seconds": self.uptime_seconds,
            "version": self.version,
            "components": [c.to_dict() for c in self.components],
            "unhealthy_count": len(self.get_unhealthy_components()),
            "timestamp": self.timestamp.isoformat(),
        }


class HealthChecker:
    """Comprehensive health checker for system components.

    This class coordinates health checks across all system components
    and provides aggregated health status.

    Usage:
        checker = HealthChecker()
        health = await checker.check_all()

        if health.is_healthy():
            print("All systems operational")
        else:
            for component in health.get_unhealthy_components():
                print(f"Issue: {component.name} - {component.message}")
    """

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        """Initialize health checker.

        Args:
            timeout_seconds: Timeout for each health check
        """
        self._timeout = timeout_seconds
        self._start_time = time.time()

    @property
    def uptime(self) -> float:
        """Get system uptime in seconds."""
        return time.time() - self._start_time

    async def check_all(self) -> SystemHealth:
        """Run all health checks and return aggregated status.

        Returns:
            SystemHealth with all component statuses
        """
        components = []

        # Run all checks concurrently for efficiency
        tasks = [
            check_database_health(),
            check_memory_health(),
            check_agents_health(),
            check_tools_health(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
            elif isinstance(result, Exception):
                logger.error("Health check exception: %s", result)
                components.append(
                    ComponentHealth(
                        name="unknown",
                        status=HealthStatus.UNKNOWN,
                        message=str(result),
                    )
                )

        # Determine overall status
        overall_status = self._determine_overall_status(components)

        return SystemHealth(
            overall_status=overall_status,
            components=components,
            uptime_seconds=self.uptime,
        )

    async def check_database(self) -> ComponentHealth:
        """Check database connectivity."""
        return await check_database_health()

    async def check_memory(self) -> ComponentHealth:
        """Check memory/vector store."""
        return await check_memory_health()

    async def check_agents(self) -> ComponentHealth:
        """Check agent availability."""
        return await check_agents_health()

    async def check_tools(self) -> ComponentHealth:
        """Check tool registry."""
        return await check_tools_health()

    def _determine_overall_status(
        self,
        components: list[ComponentHealth],
    ) -> HealthStatus:
        """Determine overall system health from component statuses.

        Args:
            components: List of component health checks

        Returns:
            Aggregated HealthStatus
        """
        if not components:
            return HealthStatus.UNKNOWN

        # Check for any unhealthy components
        has_unhealthy = any(c.status == HealthStatus.UNHEALTHY for c in components)
        if has_unhealthy:
            return HealthStatus.UNHEALTHY

        # Check for any degraded components
        has_degraded = any(c.status == HealthStatus.DEGRADED for c in components)
        if has_degraded:
            return HealthStatus.DEGRADED

        # Check for unknown components
        has_unknown = any(c.status == HealthStatus.UNKNOWN for c in components)
        if has_unknown:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY


async def check_database_health() -> ComponentHealth:
    """Check database connectivity and performance.

    Returns:
        ComponentHealth for database
    """
    start_time = time.time()

    try:
        async with async_session_factory() as session:
            from sqlalchemy import text

            # Simple connectivity check
            result = await session.execute(text("SELECT 1"))
            result.scalar()

            # Check pgvector extension
            try:
                await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                vector_enabled = True
            except Exception:
                vector_enabled = False

            response_time = (time.time() - start_time) * 1000

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY if response_time < 1000 else HealthStatus.DEGRADED,
                message="Database connection successful",
                response_time_ms=response_time,
                details={
                    "vector_enabled": vector_enabled,
                    "driver": "asyncpg",
                },
            )

    except Exception as exc:
        response_time = (time.time() - start_time) * 1000
        logger.error("Database health check failed: %s", exc)

        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database connection failed: {exc}",
            response_time_ms=response_time,
        )


async def check_memory_health() -> ComponentHealth:
    """Check memory/vector store health.

    Returns:
        ComponentHealth for memory system
    """
    start_time = time.time()

    try:
        from app.rag.memory_manager import MemoryManager

        async with async_session_factory() as session:
            manager = MemoryManager(session)
            health = await manager.health_check()

            response_time = (time.time() - start_time) * 1000

            if health.get("database") == "healthy":
                status = HealthStatus.HEALTHY
                message = "Memory system operational"
            else:
                status = HealthStatus.DEGRADED
                message = "Memory system partially operational"

            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                response_time_ms=response_time,
                details=health,
            )

    except Exception as exc:
        response_time = (time.time() - start_time) * 1000
        logger.warning("Memory health check error: %s", exc)

        # Memory might not be initialized yet
        return ComponentHealth(
            name="memory",
            status=HealthStatus.UNKNOWN,
            message=f"Memory system not initialized: {exc}",
            response_time_ms=response_time,
        )


async def check_agents_health() -> ComponentHealth:
    """Check agent availability and responsiveness.

    Returns:
        ComponentHealth for agents
    """
    start_time = time.time()

    try:
        from app.config.settings import get_settings

        settings = get_settings()
        agent_status = {}

        # Check newsletter agent
        try:
            from app.agents.newsletter.agent import create_newsletter_agent
            create_newsletter_agent(settings)
            agent_status["newsletter"] = True
        except Exception as exc:
            agent_status["newsletter"] = False
            logger.warning("Newsletter agent check failed: %s", exc)

        # Check deep research agent
        try:
            from app.agents.deep_research.agent import create_deep_research_agent
            create_deep_research_agent(settings=settings)
            agent_status["deep_research"] = True
        except Exception as exc:
            agent_status["deep_research"] = False
            logger.warning("Deep research agent check failed: %s", exc)

        response_time = (time.time() - start_time) * 1000

        all_healthy = all(agent_status.values())
        all_available = any(agent_status.values())

        if all_healthy:
            status = HealthStatus.HEALTHY
            message = "All agents available"
        elif all_available:
            status = HealthStatus.DEGRADED
            message = "Some agents unavailable"
        else:
            status = HealthStatus.UNHEALTHY
            message = "No agents available"

        return ComponentHealth(
            name="agents",
            status=status,
            message=message,
            response_time_ms=response_time,
            details={
                "agents": agent_status,
                "available_count": sum(agent_status.values()),
                "total_count": len(agent_status),
            },
        )

    except Exception as exc:
        response_time = (time.time() - start_time) * 1000
        logger.error("Agent health check failed: %s", exc)

        return ComponentHealth(
            name="agents",
            status=HealthStatus.UNHEALTHY,
            message=f"Agent health check failed: {exc}",
            response_time_ms=response_time,
        )


async def check_tools_health() -> ComponentHealth:
    """Check tool registry health.

    Returns:
        ComponentHealth for tools
    """
    start_time = time.time()

    try:
        from app.tools.registry import get_global_registry

        registry = get_global_registry()
        tools = registry.list_tools()
        enabled_count = sum(1 for t in tools if registry.is_enabled(t))

        response_time = (time.time() - start_time) * 1000

        return ComponentHealth(
            name="tools",
            status=HealthStatus.HEALTHY,
            message=f"{enabled_count}/{len(tools)} tools enabled",
            response_time_ms=response_time,
            details={
                "total_tools": len(tools),
                "enabled_tools": enabled_count,
                "tools": tools,
            },
        )

    except Exception as exc:
        response_time = (time.time() - start_time) * 1000
        logger.error("Tools health check failed: %s", exc)

        return ComponentHealth(
            name="tools",
            status=HealthStatus.UNHEALTHY,
            message=f"Tool registry error: {exc}",
            response_time_ms=response_time,
        )


async def quick_health_check() -> dict[str, str]:
    """Perform a quick health check for basic monitoring.

    Returns:
        Dictionary with basic health status
    """
    checker = HealthChecker(timeout_seconds=2.0)

    try:
        health = await checker.check_all()

        return {
            "status": health.overall_status.value,
            "components": len(health.components),
            "unhealthy": len(health.get_unhealthy_components()),
        }

    except Exception as exc:
        logger.error("Quick health check failed: %s", exc)
        return {
            "status": "unknown",
            "error": str(exc),
        }
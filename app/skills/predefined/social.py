"""
Social monitoring skill for tracking social platforms.

This skill coordinates monitoring across multiple social platforms
(GitHub, Reddit, YouTube, ArXiv, RSS) to gather
comprehensive social signals.
"""

from __future__ import annotations

from typing import Any

from app.skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillResult,
    SkillContext,
    SkillCategory,
)
from app.core.logging import get_logger


logger = get_logger(__name__)


class SocialMonitorSkill(BaseSkill):
    """Skill for monitoring social platforms and aggregating signals.

    Coordinates GitHub, Reddit, YouTube, ArXiv, and RSS monitoring
    to create a unified view of social activity around a topic.
    """

    SOCIAL_TOOLS = ["github", "reddit", "arxiv", "rss", "youtube"]

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="social_monitor",
            description="Monitor social platforms (GitHub, Reddit, ArXiv, RSS, YouTube) for comprehensive social signals",
            category=SkillCategory.RESEARCH,
            version="1.0.0",
            tags=["social", "monitoring", "github", "reddit", "arxiv", "rss", "youtube"],
            requires_tools=self.SOCIAL_TOOLS,
            max_duration_seconds=240,
        )

    async def validate(self, params: dict) -> tuple[bool, str | None]:
        if "topic" not in params and "query" not in params:
            return False, "'topic' or 'query' is required"
        return True, None

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        topic = params.get("topic") or params.get("query", "")
        platforms = params.get("platforms", self.SOCIAL_TOOLS)
        max_per_platform = params.get("max_per_platform", 5)

        if not topic:
            return SkillResult(success=False, error="No topic provided")

        logger.info("SocialMonitorSkill: monitoring '%s' on %s", topic, platforms)

        import asyncio

        results: list[dict] = []
        errors: list[str] = []

        for platform in platforms:
            if platform not in self.SOCIAL_TOOLS:
                continue

            tool = None
            for name in context.available_tools:
                if platform in name.lower():
                    from app.tools.registry import get_tool
                    tool = get_tool(name)
                    break

            if tool is None:
                from app.tools.registry import get_tool
                tool = get_tool(platform)

            if tool is None:
                errors.append(f"Tool '{platform}' not found")
                continue

            tool_params = self._build_params(platform, topic, max_per_platform, params)

            try:
                if hasattr(tool, "execute"):
                    result = await tool.execute(tool_params)
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe(tool_params)
                else:
                    continue

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", [])
                    platform_results = []
                    if isinstance(data, list):
                        for item in data[:max_per_platform]:
                            if isinstance(item, dict):
                                platform_results.append({**item, "platform": platform})
                            else:
                                platform_results.append({"content": str(item), "platform": platform})
                        results.extend(platform_results)
                    elif isinstance(data, dict):
                        results.append({**data, "platform": platform})
                else:
                    errors.append(f"{platform}: {result.get('error', 'unknown error') if isinstance(result, dict) else 'failed'}")
            except Exception as exc:
                logger.warning("SocialMonitorSkill platform '%s' failed: %s", platform, exc)
                errors.append(f"{platform}: {exc}")

        if not results:
            return SkillResult(
                success=False,
                error=f"No social signals found: {'; '.join(errors) if errors else 'unknown error'}",
                metadata={"topic": topic, "platforms_checked": len(platforms)},
            )

        return SkillResult(
            success=True,
            data={
                "topic": topic,
                "results": results,
                "count": len(results),
                "platforms": list(set(r.get("platform", "unknown") for r in results)),
            },
            message=f"Social monitoring complete: {len(results)} signals from {len(set(r.get('platform') for r in results))} platforms",
            metadata={
                "topic": topic,
                "result_count": len(results),
                "platforms_covered": list(set(r.get("platform") for r in results)),
                "errors": errors,
            },
        )

    @staticmethod
    def _build_params(platform: str, topic: str, limit: int, base_params: dict) -> dict:
        base = {"topic": topic, "limit": limit}
        if platform == "github":
            return {"query": topic, "sort": base_params.get("sort", "stars")}
        if platform == "reddit":
            return {"query": topic, "subreddit": base_params.get("subreddit", ""), "sort": base_params.get("reddit_sort", "hot")}
        if platform == "arxiv":
            return {"query": topic, "max_results": limit}
        if platform == "rss":
            return {"url": base_params.get("rss_url", ""), "topic": topic, "limit": limit}
        if platform == "youtube":
            return {"query": topic, "max_results": limit}
        return base


class PaperAnalyzerSkill(BaseSkill):
    """Skill for analyzing academic papers and research documents.

    Coordinates PDF extraction, semantic scholar search, and arxiv
    to gather and analyze academic research on a topic.
    """

    PAPER_TOOLS = ["research_paper", "arxiv"]

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="paper_analyzer",
            description="Analyze academic papers: search, extract, summarize, and synthesize research",
            category=SkillCategory.RESEARCH,
            version="1.0.0",
            tags=["papers", "academic", "research", "arxiv", "pdf", "semantic_scholar"],
            requires_tools=self.PAPER_TOOLS,
            max_duration_seconds=300,
        )

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        query = params.get("query") or params.get("topic", "")
        action = params.get("action", "search")
        max_papers = params.get("max_papers", 5)

        if not query:
            return SkillResult(success=False, error="No query provided")

        logger.info("PaperAnalyzerSkill: '%s' (action=%s)", query, action)

        import asyncio
        results: list[dict] = []
        errors: list[str] = []

        for tool_name in self.PAPER_TOOLS:
            from app.tools.registry import get_tool
            tool = get_tool(tool_name)
            if tool is None:
                continue

            tool_params = {"query": query, "limit": max_papers, "action": action}

            try:
                if hasattr(tool, "execute"):
                    result = await tool.execute(tool_params)
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe(tool_params)
                else:
                    continue

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", [])
                    if isinstance(data, list):
                        results.extend(data[:max_papers])
                    elif data:
                        results.append(data)
                elif isinstance(result, dict):
                    errors.append(f"{tool_name}: {result.get('error', 'unknown')}")
            except Exception as exc:
                errors.append(f"{tool_name}: {exc}")

        if not results:
            return SkillResult(
                success=False,
                error=f"No papers found: {'; '.join(errors) if errors else 'unknown error'}",
                metadata={"query": query, "action": action},
            )

        return SkillResult(
            success=True,
            data={
                "query": query,
                "action": action,
                "papers": results[:max_papers],
                "count": len(results),
            },
            message=f"Paper analysis complete: {len(results)} papers found for '{query}'",
            metadata={"query": query, "result_count": len(results), "errors": errors},
        )
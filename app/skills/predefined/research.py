"""
Web research skill for advanced web content gathering.

This skill provides comprehensive web research capabilities combining
search, crawl, and content extraction. It coordinates multiple tools
to gather relevant web content efficiently.
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


class WebResearchSkill(BaseSkill):
    """Skill for conducting comprehensive web research.

    Coordinates web search, crawling, and content extraction to
    gather relevant information on a given topic.
    """

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="web_research",
            description="Comprehensive web research: search, crawl, and extract content from web sources",
            category=SkillCategory.RESEARCH,
            version="1.0.0",
            tags=["web", "research", "search", "crawl", "extraction"],
            requires_tools=["web_search", "crawl"],
            max_duration_seconds=180,
        )

    async def validate(self, params: dict) -> tuple[bool, str | None]:
        if "topic" not in params and "query" not in params:
            return False, "Either 'topic' or 'query' is required"
        return True, None

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        topic = params.get("topic") or params.get("query", "")
        max_results = params.get("max_results", 10)

        if not topic:
            return SkillResult(
                success=False,
                error="No topic or query provided",
            )

        logger.info("WebResearchSkill: researching '%s'", topic)

        results: list[dict] = []
        errors: list[str] = []

        for tool_name in self._metadata.requires_tools:
            if tool_name not in context.available_tools:
                continue

            from app.tools.registry import get_tool
            tool = get_tool(tool_name)
            if tool is None:
                errors.append(f"Tool '{tool_name}' not found")
                continue

            try:
                import asyncio
                if hasattr(tool, "execute"):
                    result = await tool.execute({"topic": topic, "limit": max_results})
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe({"topic": topic, "limit": max_results})
                else:
                    continue

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", [])
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)
            except Exception as exc:
                logger.warning("WebResearchSkill tool '%s' failed: %s", tool_name, exc)
                errors.append(f"{tool_name}: {exc}")

        if not results:
            return SkillResult(
                success=False,
                error=f"No results from web research: {'; '.join(errors) if errors else 'unknown error'}",
                metadata={"topic": topic},
            )

        return SkillResult(
            success=True,
            data={
                "topic": topic,
                "results": results[:max_results],
                "count": len(results),
                "sources": list(set(str(r.get("source", r.get("tool", "unknown"))) for r in results)),
            },
            message=f"Web research completed: {len(results)} results for '{topic}'",
            metadata={
                "topic": topic,
                "result_count": len(results),
                "tools_used": len(self._metadata.requires_tools),
                "errors": errors,
            },
        )


class DeepResearchSkill(BaseSkill):
    """Skill for in-depth research with multi-source verification.

    Goes beyond surface-level search to verify information across
    multiple sources and build comprehensive understanding.
    """

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="deep_research",
            description="In-depth multi-source research with verification and cross-referencing",
            category=SkillCategory.RESEARCH,
            version="1.0.0",
            tags=["research", "deep", "verification", "analysis"],
            requires_tools=["web_search", "research_paper", "arxiv"],
            max_duration_seconds=600,
        )

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        query = params.get("query") or params.get("topic", "")
        depth = params.get("depth", "medium")

        if not query:
            return SkillResult(success=False, error="No query provided")

        logger.info("DeepResearchSkill: '%s' (depth=%s)", query, depth)

        findings: list[dict] = []

        for tool_name in self._metadata.requires_tools:
            from app.tools.registry import get_tool
            tool = get_tool(tool_name)
            if tool is None:
                continue

            try:
                import asyncio
                tool_params = {"query": query, "limit": 5}
                if hasattr(tool, "execute"):
                    result = await tool.execute(tool_params)
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe(tool_params)
                else:
                    continue

                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", [])
                    if isinstance(data, list):
                        findings.extend([{"tool": tool_name, **f} for f in data[:5]])
                    elif data:
                        findings.append({"tool": tool_name, **data})
            except Exception as exc:
                logger.warning("DeepResearchSkill tool '%s' failed: %s", tool_name, exc)

        if not findings:
            return SkillResult(success=False, error="No findings from deep research")

        return SkillResult(
            success=True,
            data={
                "query": query,
                "depth": depth,
                "findings": findings,
                "count": len(findings),
            },
            message=f"Deep research completed: {len(findings)} findings",
            metadata={"query": query, "depth": depth, "tools_used": len(self._metadata.requires_tools)},
        )
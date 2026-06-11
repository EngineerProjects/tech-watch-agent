"""
Analysis skills for extracting insights and synthesizing information.

These skills help agents analyze gathered content, extract key insights,
compare sources, and identify patterns.
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


class InsightExtractionSkill(BaseSkill):
    """Skill for extracting key insights from raw content."""

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="insight_extraction",
            description="Extract key insights, trends, and patterns from gathered content",
            category=SkillCategory.ANALYSIS,
            version="1.0.0",
            tags=["analysis", "insights", "trends", "extraction"],
            requires_tools=[],
            max_duration_seconds=120,
        )

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        content = params.get("content", params.get("data", []))
        focus = params.get("focus", "general")

        if not content:
            return SkillResult(success=False, error="No content provided")

        if context.llm_client is None:
            from app.services.llm import ChatCompletionClient
            context.llm_client = ChatCompletionClient()

        prompt = f"""Analyze the following content and extract key insights.

Focus: {focus}

Content:
{self._format_content(content)}

Provide:
1. Key findings (bullet points)
2. Main trends or patterns
3. Notable claims or conclusions
4. Any contradictions or debates

Format as structured JSON with: insights[], trends[], claims[], contradictions[]"""

        try:
            response = context.llm_client.generate_completion(
                prompt=prompt,
                system_message="You are an expert analyst. Extract actionable insights from research content.",
                temperature=0.3,
                max_tokens=3000,
            )

            import json
            import re
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            try:
                analysis = json.loads(text)
            except json.JSONDecodeError:
                analysis = {"raw_insights": text, "insights": [], "trends": [], "claims": [], "contradictions": []}

            return SkillResult(
                success=True,
                data=analysis,
                message=f"Insight extraction complete: {len(analysis.get('insights', []))} insights found",
                metadata={"focus": focus, "content_items": len(content) if isinstance(content, list) else 1},
            )
        except Exception as exc:
            logger.error("InsightExtractionSkill failed: %s", exc)
            return SkillResult(success=False, error=str(exc))

    @staticmethod
    def _format_content(content: Any) -> str:
        if isinstance(content, list):
            parts = []
            for i, item in enumerate(content[:20]):
                if isinstance(item, dict):
                    title = item.get("title", item.get("name", f"Item {i+1}"))
                    summary = item.get("summary", item.get("description", ""))
                    parts.append(f"- {title}: {summary[:500]}")
                else:
                    parts.append(f"- {str(item)[:500]}")
            return "\n".join(parts)
        return str(content)[:5000]


class SourceComparisonSkill(BaseSkill):
    """Skill for comparing and cross-referencing multiple sources."""

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="source_comparison",
            description="Compare multiple sources to identify agreements, contradictions, and knowledge gaps",
            category=SkillCategory.ANALYSIS,
            version="1.0.0",
            tags=["comparison", "sources", "verification", "cross-reference"],
            requires_tools=[],
            max_duration_seconds=180,
        )

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        sources = params.get("sources", [])
        topic = params.get("topic", "")

        if len(sources) < 2:
            return SkillResult(success=False, error="At least 2 sources required")

        if context.llm_client is None:
            from app.services.llm import ChatCompletionClient
            context.llm_client = ChatCompletionClient()

        prompt = f"""Compare the following sources on topic: {topic}

Sources:
{self._format_sources(sources)}

Provide a structured comparison:
1. Agreements: What all sources agree on
2. Contradictions: Where sources disagree
3. Complementary info: What each source adds that others don't
4. Knowledge gaps: What's missing or unverified

Format as JSON with: agreements[], contradictions[], complements[], gaps[]"""

        try:
            response = context.llm_client.generate_completion(
                prompt=prompt,
                system_message="You are a research analyst comparing information from multiple sources.",
                temperature=0.3,
                max_tokens=3000,
            )

            import json
            import re
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            try:
                comparison = json.loads(text)
            except json.JSONDecodeError:
                comparison = {"raw": text, "agreements": [], "contradictions": [], "complements": [], "gaps": []}

            return SkillResult(
                success=True,
                data=comparison,
                message=f"Source comparison complete: {len(sources)} sources compared",
                metadata={"sources_count": len(sources), "topic": topic},
            )
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    @staticmethod
    def _format_sources(sources: list) -> str:
        parts = []
        for i, src in enumerate(sources[:5]):
            if isinstance(src, dict):
                name = src.get("source", src.get("name", f"Source {i+1}"))
                content = src.get("content", src.get("summary", src.get("text", "")))
                parts.append(f"### Source {i+1}: {name}\n{content[:1000]}")
            else:
                parts.append(f"### Source {i+1}\n{str(src)[:1000]}")
        return "\n\n".join(parts)


class TrendAnalysisSkill(BaseSkill):
    """Skill for identifying and tracking trends across content."""

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="trend_analysis",
            description="Identify trends, patterns, and temporal changes across research content",
            category=SkillCategory.ANALYSIS,
            version="1.0.0",
            tags=["trends", "temporal", "patterns", "emerging"],
            requires_tools=[],
            max_duration_seconds=120,
        )

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        content = params.get("content", [])
        timeframe = params.get("timeframe", "recent")

        if not content:
            return SkillResult(success=False, error="No content provided")

        if context.llm_client is None:
            from app.services.llm import ChatCompletionClient
            context.llm_client = ChatCompletionClient()

        prompt = f"""Analyze trends and patterns in the following content.

Timeframe focus: {timeframe}

Content:
{self._format_content(content)}

Identify:
1. Emerging trends or themes
2. Declining or stable topics
3. Shifts in focus or direction
4. Predicted emerging developments

Format as JSON with: emerging_trends[], stable_topics[], declining_topics[], predictions[]"""

        try:
            response = context.llm_client.generate_completion(
                prompt=prompt,
                system_message="You are a trend analyst identifying patterns in research and news content.",
                temperature=0.4,
                max_tokens=3000,
            )

            import json
            import re
            text = response.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            try:
                trends = json.loads(text)
            except json.JSONDecodeError:
                trends = {"raw": text, "emerging_trends": [], "stable_topics": [], "declining_topics": [], "predictions": []}

            return SkillResult(
                success=True,
                data=trends,
                message="Trend analysis complete",
                metadata={"timeframe": timeframe, "content_items": len(content) if isinstance(content, list) else 1},
            )
        except Exception as exc:
            return SkillResult(success=False, error=str(exc))

    @staticmethod
    def _format_content(content: Any) -> str:
        if isinstance(content, list):
            parts = []
            for item in content[:30]:
                if isinstance(item, dict):
                    title = item.get("title", item.get("name", ""))
                    summary = item.get("summary", item.get("description", ""))
                    date = item.get("published_date", item.get("date", ""))
                    date_str = f" ({date})" if date else ""
                    parts.append(f"- {title}{date_str}: {summary[:300]}")
                else:
                    parts.append(f"- {str(item)[:300]}")
            return "\n".join(parts)
        return str(content)[:5000]
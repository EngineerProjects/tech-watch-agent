"""
Skills module for tech-watch-agent.

Skills are reusable, composable modules that agents can use to perform
specific tasks. Unlike tools (external utilities), skills combine LLM
reasoning with tool access for agent-specific capabilities.

Usage:
    from app.skills.registry import get_skill_registry, register_skill
    from app.skills.base import BaseSkill, SkillResult, SkillContext

    # Register a skill
    register_skill(MySkill())

    # Use in an agent
    skill = get_skill("web_research")
    result = await skill.execute(params, context)

Available skill categories:
- RESEARCH: Web research, paper analysis, social monitoring
- ANALYSIS: Insight extraction, source comparison, trend analysis
- SYNTHESIS: Report generation, summarization
- COMMUNICATION: Email, messaging
- EXECUTION: Tool orchestration, workflow management
- UTILITY: Helpers, formatters, validators
"""

from app.skills.base import (
    BaseSkill,
    SkillMetadata,
    SkillResult,
    SkillContext,
    SkillCategory,
    CompositeSkill,
)
from app.skills.registry import (
    SkillRegistry,
    get_skill_registry,
    register_skill,
    get_skill,
)
from app.skills.predefined import (
    WebResearchSkill,
    DeepResearchSkill,
    InsightExtractionSkill,
    SourceComparisonSkill,
    TrendAnalysisSkill,
    SocialMonitorSkill,
    PaperAnalyzerSkill,
)


__all__ = [
    "BaseSkill",
    "SkillMetadata",
    "SkillResult",
    "SkillContext",
    "SkillCategory",
    "CompositeSkill",
    "SkillRegistry",
    "get_skill_registry",
    "register_skill",
    "get_skill",
    "WebResearchSkill",
    "DeepResearchSkill",
    "InsightExtractionSkill",
    "SourceComparisonSkill",
    "TrendAnalysisSkill",
    "SocialMonitorSkill",
    "PaperAnalyzerSkill",
]
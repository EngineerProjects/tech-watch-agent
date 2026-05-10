"""
Base skill interface for the skill plugin system.

Skills are reusable, composable modules that agents can use to perform
specific tasks. Unlike tools (which are external utilities), skills are
agent-specific capabilities that combine LLM reasoning with tool access.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SkillCategory(str, Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    COMMUNICATION = "communication"
    EXECUTION = "execution"
    UTILITY = "utility"


@dataclass
class SkillMetadata:
    name: str
    description: str
    category: SkillCategory
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    requires_tools: list[str] = field(default_factory=list)
    max_duration_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "tags": self.tags,
            "requires_tools": self.requires_tools,
            "max_duration_seconds": self.max_duration_seconds,
        }


@dataclass
class SkillResult:
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class SkillContext:
    task: str
    agent_name: str
    available_tools: list[str] = field(default_factory=list)
    llm_client: Any = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    custom: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for skills.

    A skill is a composable module that provides a specific capability
    to agents. Skills combine LLM reasoning with tool access to perform
    tasks within a larger workflow.

    Attributes:
        _metadata: Skill metadata
    """

    def __init__(self) -> None:
        self._metadata = self._create_metadata()

    @abstractmethod
    def _create_metadata(self) -> SkillMetadata:
        """Create the skill metadata. Must be implemented by subclasses."""
        raise NotImplementedError

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    @property
    def name(self) -> str:
        return self._metadata.name

    @property
    def description(self) -> str:
        return self._metadata.description

    @property
    def category(self) -> SkillCategory:
        return self._metadata.category

    @abstractmethod
    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        """Execute the skill.

        Args:
            params: Skill-specific parameters
            context: Execution context with task, tools, LLM access

        Returns:
            SkillResult with success status, data, and metadata
        """
        raise NotImplementedError

    async def validate(self, params: dict) -> tuple[bool, Optional[str]]:
        """Validate skill parameters before execution.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def get_required_tools(self) -> list[str]:
        """Return list of tool names this skill requires."""
        return self._metadata.requires_tools


class CompositeSkill(BaseSkill):
    """A skill composed of multiple sub-skills.

    Useful for creating high-level skills from simpler ones.
    """

    def __init__(self, skills: list[BaseSkill] | None = None) -> None:
        self._sub_skills: dict[str, BaseSkill] = {}
        if skills:
            for skill in skills:
                self._sub_skills[skill.name] = skill
        super().__init__()

    def _create_metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="composite",
            description="A skill composed of multiple sub-skills",
            category=SkillCategory.UTILITY,
        )

    def add_skill(self, skill: BaseSkill) -> None:
        self._sub_skills[skill.name] = skill

    def remove_skill(self, name: str) -> bool:
        return self._sub_skills.pop(name, None) is not None

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        return self._sub_skills.get(name)

    @property
    def skills(self) -> dict[str, BaseSkill]:
        return self._sub_skills.copy()

    async def execute(self, params: dict, context: SkillContext) -> SkillResult:
        raise NotImplementedError("Use execute_chain or execute_parallel instead")

    async def execute_chain(
        self,
        params: dict,
        context: SkillContext,
        order: list[str] | None = None,
    ) -> SkillResult:
        """Execute sub-skills in sequence."""
        skill_order = order or list(self._sub_skills.keys())
        results: list[dict] = []
        errors: list[str] = []

        for skill_name in skill_order:
            skill = self._sub_skills.get(skill_name)
            if skill is None:
                errors.append(f"Skill '{skill_name}' not found")
                continue

            skill_params = params.get(skill_name, params)
            result = await skill.execute(skill_params, context)
            results.append({"skill": skill_name, "result": result.to_dict()})

            if not result.success:
                errors.append(f"{skill_name}: {result.error or result.message}")

        return SkillResult(
            success=len(errors) == 0,
            data={"steps": results},
            message="Chain execution complete",
            error="; ".join(errors) if errors else None,
        )

    async def execute_parallel(
        self,
        params: dict,
        context: SkillContext,
        skill_names: list[str] | None = None,
    ) -> SkillResult:
        """Execute multiple sub-skills concurrently."""
        import asyncio

        skills_to_run = [
            (name, self._sub_skills[name])
            for name in (skill_names or list(self._sub_skills.keys()))
            if name in self._sub_skills
        ]

        async def run_skill(name: str, skill: BaseSkill) -> tuple[str, SkillResult]:
            skill_params = params.get(name, params)
            result = await skill.execute(skill_params, context)
            return name, result

        import asyncio
        tasks = [run_skill(n, s) for n, s in skills_to_run]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[dict] = []
        errors: list[str] = []

        for item in results_raw:
            if isinstance(item, Exception):
                errors.append(str(item))
            else:
                name, result = item
                results.append({"skill": name, "result": result.to_dict()})
                if not result.success:
                    errors.append(f"{name}: {result.error or result.message}")

        return SkillResult(
            success=len(errors) == 0,
            data={"steps": results},
            message=f"Parallel execution of {len(results)} skills complete",
            error="; ".join(errors) if errors else None,
        )
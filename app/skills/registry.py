"""
Skill registry for dynamic skill management.

Provides centralized management of skill instances, similar to the tool registry.
Skills can be registered, looked up, and filtered by category.
"""

from __future__ import annotations

from typing import Optional

from app.skills.base import BaseSkill, SkillCategory, SkillMetadata
from app.core.logging import get_logger


logger = get_logger(__name__)


class SkillRegistry:
    """Registry for managing skill instances.

    Provides centralized management of all skills in the system.
    Supports dynamic registration, lookup, and category-based filtering.

    Usage:
        registry = SkillRegistry()
        registry.register(web_research_skill)
        registry.register(social_monitor_skill, aliases=["monitor"])

        skill = registry.get("web_research")
        research_skills = registry.list_by_category(SkillCategory.RESEARCH)
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._categories: dict[SkillCategory, list[str]] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        skill: BaseSkill,
        name: Optional[str] = None,
        aliases: Optional[list[str]] = None,
    ) -> None:
        """Register a skill in the registry.

        Args:
            skill: The skill instance to register
            name: Optional custom name (defaults to skill.name)
            aliases: Optional list of alternative names

        Raises:
            ValueError: If a skill with the same name is already registered
        """
        skill_name = name or skill.name

        if skill_name in self._skills:
            raise ValueError(
                f"Skill '{skill_name}' is already registered. "
                f"Unregister first or use a different name."
            )

        self._skills[skill_name] = skill

        category = skill.category
        if skill_name not in self._categories.get(category, []):
            self._categories.setdefault(category, []).append(skill_name)

        if aliases:
            for alias in aliases:
                if alias in self._skills:
                    raise ValueError(f"Alias '{alias}' conflicts with existing skill name")
                self._aliases[alias] = skill_name

        logger.info("Registered skill: %s (category: %s)", skill_name, category.value)

    def unregister(self, name: str) -> bool:
        """Unregister a skill from the registry.

        Args:
            name: Name of the skill to unregister

        Returns:
            True if the skill was unregistered, False if not found
        """
        if name not in self._skills:
            return False

        skill = self._skills[name]
        category = skill.category

        del self._skills[name]

        if name in self._categories.get(category, []):
            self._categories[category].remove(name)

        aliases_to_remove = [a for a, target in self._aliases.items() if target == name]
        for alias in aliases_to_remove:
            del self._aliases[alias]

        logger.info("Unregistered skill: %s", name)
        return True

    def get(self, name: str) -> Optional[BaseSkill]:
        """Get a skill by name, resolving aliases.

        Args:
            name: Name or alias of the skill

        Returns:
            The skill instance or None if not found
        """
        resolved_name = self._aliases.get(name, name)
        return self._skills.get(resolved_name)

    def get_or_raise(self, name: str) -> BaseSkill:
        """Get a skill by name, raising if not found."""
        skill = self.get(name)
        if skill is None:
            raise KeyError(f"Skill '{name}' not found in registry")
        return skill

    def list_all(self) -> list[str]:
        """Get list of all registered skill names."""
        return list(self._skills.keys())

    def list_by_category(self, category: SkillCategory) -> list[BaseSkill]:
        """Get all skills in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of skills in the category
        """
        skill_names = self._categories.get(category, [])
        return [self._skills[name] for name in skill_names if name in self._skills]

    def list_metadata(self) -> list[SkillMetadata]:
        """Get metadata for all registered skills."""
        return [skill.metadata for skill in self._skills.values()]

    def enable(self, name: str) -> bool:
        """Enable a skill."""
        skill = self.get(name)
        if skill:
            logger.info("Enabled skill: %s", name)
            return True
        return False

    def disable(self, name: str) -> bool:
        """Disable a skill."""
        skill = self.get(name)
        if skill:
            logger.info("Disabled skill: %s", name)
            return True
        return False

    def clear(self) -> None:
        """Clear all skills from the registry."""
        count = len(self._skills)
        self._skills.clear()
        self._categories.clear()
        self._aliases.clear()
        logger.info("Cleared %d skills from registry", count)

    @property
    def count(self) -> int:
        return len(self._skills)

    def __contains__(self, name: str) -> bool:
        return name in self._skills

    def __iter__(self):
        return iter(self._skills.values())


_global_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry singleton."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def register_skill(
    skill: BaseSkill,
    name: Optional[str] = None,
    aliases: Optional[list[str]] = None,
) -> None:
    """Register a skill in the global registry."""
    get_skill_registry().register(skill, name, aliases)


def get_skill(name: str) -> Optional[BaseSkill]:
    """Get a skill from the global registry."""
    return get_skill_registry().get(name)
"""
Configuration for the deep research agent.

This module defines the configuration options specific to the deep research
agent. It extends the base AgentConfig with research-specific settings
like iteration limits, model choices, and tool configurations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from app.agents.base.base_agent import AgentConfig


@dataclass
class DeepResearchConfig(AgentConfig):
    """Configuration for the deep research agent.

    Extends AgentConfig with settings specific to deep research operations:
    - Model choices for different phases
    - Iteration limits for research loops
    - Tool configurations
    - Research depth settings

    Attributes:
        research_model: Model for research/exploration tasks
        compression_model: Model for compressing/summarizing findings
        final_report_model: Model for generating the final report
        max_researcher_iterations: Max iterations for sub-researchers
        max_react_tool_calls: Max tool calls in REACT loops
        max_concurrent_research_units: Max parallel research units
        allow_clarification: Whether to ask clarifying questions
        mcp_prompt: MCP (Model Context Protocol) server configuration
    """

    # Model configuration - can be different for different phases
    research_model: str = "openai/gpt-4.1-mini"
    research_model_max_tokens: int = 4096
    compression_model: str = "openai/gpt-4.1-mini"
    compression_model_max_tokens: int = 8192
    final_report_model: str = "openai/gpt-4o"
    final_report_model_max_tokens: int = 16384

    # Iteration and resource limits
    max_researcher_iterations: int = 5
    max_react_tool_calls: int = 10
    max_concurrent_research_units: int = 3

    # Behavior flags
    allow_clarification: bool = True

    # Tool configuration
    mcp_prompt: Optional[str] = None

    # Custom settings
    research_depth: str = "medium"  # "shallow", "medium", "deep"
    citation_style: str = "numbered"  # "numbered", "inline", "footnote"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.max_researcher_iterations < 1:
            raise ValueError("max_researcher_iterations must be at least 1")
        if self.max_concurrent_research_units < 1:
            raise ValueError("max_concurrent_research_units must be at least 1")
        if self.research_depth not in ("shallow", "medium", "deep"):
            raise ValueError("research_depth must be one of: shallow, medium, deep")

    def get_research_iteration_limit(self) -> int:
        """Get iteration limit based on research depth.

        Returns:
            Number of iterations based on depth setting
        """
        depth_limits = {
            "shallow": 2,
            "medium": 5,
            "deep": 10,
        }
        return depth_limits.get(self.research_depth, 5)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Dictionary representation of config
        """
        return {
            **super().to_dict(),
            "research_model": self.research_model,
            "compression_model": self.compression_model,
            "final_report_model": self.final_report_model,
            "max_researcher_iterations": self.max_researcher_iterations,
            "max_react_tool_calls": self.max_react_tool_calls,
            "max_concurrent_research_units": self.max_concurrent_research_units,
            "allow_clarification": self.allow_clarification,
            "research_depth": self.research_depth,
            "citation_style": self.citation_style,
        }


class ConfigurationFromConfig:
    """Helper to create config from runnable config.

    This class provides utilities for extracting configuration
    from LangGraph's runnable config objects.
    """

    @staticmethod
    def from_runnable_config(config: dict[str, Any]) -> DeepResearchConfig:
        """Create DeepResearchConfig from LangGraph config.

        Args:
            config: The runnable configuration dict

        Returns:
            DeepResearchConfig instance
        """
        configurable = config.get("configurable", {})

        return DeepResearchConfig(
            name=configurable.get("name", "deep_research"),
            research_model=configurable.get("research_model", "openai/gpt-4.1-mini"),
            compression_model=configurable.get("compression_model", "openai/gpt-4.1-mini"),
            final_report_model=configurable.get("final_report_model", "openai/gpt-4o"),
            max_researcher_iterations=configurable.get("max_researcher_iterations", 5),
            max_react_tool_calls=configurable.get("max_react_tool_calls", 10),
            max_concurrent_research_units=configurable.get("max_concurrent_research_units", 3),
            allow_clarification=configurable.get("allow_clarification", True),
            research_depth=configurable.get("research_depth", "medium"),
        )
"""
Orchestrator agent configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal, Union

from app.agents.base.base_agent import AgentConfig
from app.agents.orchestrator.graph import RetryPolicy


@dataclass
class OrchestratorConfig(AgentConfig):
    """Configuration for the orchestrator agent.

    Extends AgentConfig with orchestrator-specific settings:
    - max_steps: Maximum number of plan steps
    - min_articles: Minimum articles before proceeding
    - max_iterations: Max analysis cycles
    - parallel_research: Enable parallel tool dispatch
    - send_email: Enable email delivery
    - checkpointing: Enable state persistence
    - human_approval: Enable human-in-the-loop checkpoints
    """

    name: str = "OrchestratorAgent"
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 4000
    max_iterations: int = 5
    timeout_seconds: int = 600

    max_steps: int = 10
    min_articles: int = 3
    min_sources: int = 2
    parallel_research: bool = True
    send_email: bool = True
    topics: list[str] = field(default_factory=list)
    custom_sources: list[str] = field(default_factory=list)

    enable_checkpointing: bool = False
    checkpoint_backend: Literal["memory", "postgres"] = "memory"
    retry_policy: RetryPolicy = field(default_factory=lambda: {
        "max_attempts": 3,
        "initial_interval": 1.0,
        "backoff_factor": 2.0,
        "max_interval": 60.0,
    })
    human_approval_enabled: bool = False
    approval_threshold: float = 0.7

    def __post_init__(self) -> None:
        if not self.model:
            from app.config.settings import get_settings
            s = get_settings()
            self.model = s.llm_model or "openai/gpt-4.1-mini"
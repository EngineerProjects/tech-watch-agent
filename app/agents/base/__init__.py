"""
Base module for agent framework.

This module provides the foundational classes for building AI agents
using LangGraph. It includes state definitions, base agent class,
and common utilities for agent development.
"""

from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult
from app.agents.base.agent_state import AgentState, create_initial_state, merge_state_updates

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "AgentResult",
    "AgentState",
    "create_initial_state",
    "merge_state_updates",
]
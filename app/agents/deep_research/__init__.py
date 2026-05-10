"""
Deep Research agent module.

This module provides a deep research agent that can conduct thorough
investigations on complex topics. It uses a multi-agent architecture
with a supervisor delegating to parallel researcher sub-agents.

Inspired by the open_deep_research repository patterns but adapted
for the tech-watch-agent architecture.

Features:
- Supervisor-researcher multi-agent pattern
- Parallel research execution
- Research compression/summarization
- Structured final report generation
"""

from app.agents.deep_research.graph import DeepResearchWorkflow, DeepResearchGraphBuilder
from app.agents.deep_research.config import DeepResearchConfig
from app.agents.deep_research.nodes import DeepResearchNodes
from app.agents.deep_research.agent import DeepResearchAgent

__all__ = [
    "DeepResearchWorkflow",
    "DeepResearchGraphBuilder",
    "DeepResearchConfig",
    "DeepResearchNodes",
    "DeepResearchAgent",
]
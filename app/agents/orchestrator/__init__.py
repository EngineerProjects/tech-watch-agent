"""
Orchestrator agent module.

The main orchestrator agent that coordinates comprehensive tech research:
- Plans execution from user task
- Dispatches research in parallel (web, social, papers)
- Collects and validates results
- Analyzes and synthesizes into final report
- Delivers via email

Usage:
    agent = OrchestratorAgent()
    result = await agent.execute({"task": "Research AI trends this week", "topics": ["AI", "ML"]})
"""

from app.agents.orchestrator.agent import (
    OrchestratorAgent,
    OrchestratorConfig,
    create_orchestrator_agent,
)
from app.agents.orchestrator.graph import (
    OrchestratorGraphBuilder,
    OrchestratorWorkflow,
    create_orchestrator_workflow,
)
from app.agents.orchestrator.nodes import OrchestratorNodes
from app.agents.orchestrator.state import (
    OrchestratorState,
    PlanStep,
    StepStatus,
    StepType,
)


__all__ = [
    "OrchestratorAgent",
    "OrchestratorConfig",
    "create_orchestrator_agent",
    "OrchestratorGraphBuilder",
    "OrchestratorWorkflow",
    "create_orchestrator_workflow",
    "OrchestratorNodes",
    "OrchestratorState",
    "PlanStep",
    "StepStatus",
    "StepType",
]
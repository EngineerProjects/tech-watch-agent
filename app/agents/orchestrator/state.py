"""
Orchestrator agent state definitions.

Defines the TypedDict state for the orchestrator agent, including
the execution plan structure and all intermediate results.
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepType(str, Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    VALIDATION = "validation"
    EMAIL = "email"
    CUSTOM = "custom"


class PlanStep(TypedDict):
    step_id: str
    name: str
    description: str
    step_type: StepType
    status: StepStatus
    tool_name: str | None
    params: dict | None
    result: str | None
    error: str | None
    started_at: str | None
    completed_at: str | None


class OrchestratorState(TypedDict, total=False):
    task: str
    task_id: str
    plan: list[PlanStep]
    current_step_index: int
    articles: list[dict]
    research_results: list[dict]
    analysis_results: str
    synthesis_result: str
    final_report: str
    email_sent: bool
    email_result: str | None
    validation_errors: list[str]
    iteration_count: int
    max_iterations: int
    errors: list[str]
    started_at: str | None
    completed_at: str | None
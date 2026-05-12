"""
Orchestrator agent nodes.

Implements the core nodes for the orchestrator LangGraph workflow:
- supervisor: Entry point that delegates to other nodes
- planner: Generates the execution plan
- dispatcher: Executes individual plan steps
- dispatcher_parallel: Executes steps in parallel with retry policies
- collector: Aggregates results from parallel steps
- validator: Validates quality of collected results
- analyzer: Extracts insights from collected data
- synthesizer: Creates the final report
- emailer: Sends the report via email

Features:
- Retry policies with exponential backoff for parallel execution
- Fallback chain (try multiple tools if one fails)
- Error aggregation with detailed logging
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from app.agents.newsletter.agent import NewsletterAgent, NewsletterAgentConfig
from app.agents.orchestrator.state import (
    OrchestratorState,
    PlanStep,
    StepStatus,
    StepType,
    parse_step_type,
)
from app.agents.orchestrator.prompts import (
    SUPERVISOR_USER,
    PLANNER_USER,
    DISPATCHER_USER,
    COLLECTOR_USER,
    VALIDATOR_USER,
    ANALYZER_USER,
    SYNTHESIZER_USER,
    EMAILER_USER,
)
from app.services.llm import ChatCompletionClient
from app.services.llm.health import LLMHealthManager, get_health_manager
from app.tools.registry import get_global_registry
from app.core.logging import get_logger


logger = get_logger(__name__)

RETRY_POLICY = {
    "max_attempts": 3,
    "initial_interval": 1.0,
    "backoff_factor": 2.0,
    "max_interval": 60.0,
}

FALLBACK_TOOLS = {
    "search": ["duckduckgo_search", "arxiv", "openalex_search"],
    "research": ["deep_research", "tavily", "arxiv"],
    "crawl": ["crawl4ai", "scrapling", "http_fetch"],
}


# Step types that CAN run in parallel (no resource conflicts)
PARALLELIZABLE_STEP_TYPES = {
    StepType.RESEARCH,
    StepType.DEEP_RESEARCH,
    StepType.NEWSLETTER,
    StepType.CRAWL,
    StepType.SEARCH,
    StepType.SOCIAL,
    StepType.PAPER,
    StepType.VIDEO,
}

# Step types that MUST run SEQUENTIALLY
SEQUENTIAL_ONLY_STEP_TYPES = {
    StepType.SYNTHESIS,
    StepType.ANALYSIS,
    StepType.EMAIL,
    StepType.VALIDATION,
    StepType.COLLECTION,
    StepType.SUMMARY,
}


def analyze_step_dependencies(plan: list[PlanStep]) -> dict[str, list[str]]:
    """Analyze dependencies between steps.
    
    Returns a dict mapping step_id to list of step_ids it depends on.
    
    Dependency rules:
    - Steps with same tool that modifies state: sequential
    - Steps after SYNTHESIS/ANALYSIS: depend on earlier results
    - EMAIL: depends on SYNTHESIS completion
    """
    dependencies: dict[str, list[str]] = {}
    step_types_by_idx: dict[int, StepType] = {}
    step_ids_by_idx: dict[int, str] = {}
    
    # First pass: map indices and types
    for idx, step in enumerate(plan):
        step_id = step.get("step_id", f"idx_{idx}")
        step_type = step.get("step_type")
        step_ids_by_idx[idx] = step_id
        step_types_by_idx[idx] = step_type
        
        # By default, no dependencies
        dependencies[step_id] = []
    
    # Second pass: identify dependencies
    for idx, step in enumerate(plan):
        step_id = step.get("step_id", f"idx_{idx}")
        step_type = step.get("step_type")
        
        # SYNTHESIS/ANALYSIS depend on all research steps before them
        if step_type in {StepType.SYNTHESIS, StepType.ANALYSIS}:
            for prev_idx in range(idx):
                prev_type = step_types_by_idx.get(prev_idx)
                if prev_type in PARALLELIZABLE_STEP_TYPES:
                    dependencies[step_id].append(step_ids_by_idx[prev_idx])
        
        # EMAIL depends on SYNTHESIS
        if step_type == StepType.EMAIL:
            for prev_idx in range(idx):
                prev_type = step_types_by_idx.get(prev_idx)
                if prev_type == StepType.SYNTHESIS:
                    dependencies[step_id].append(step_ids_by_idx[prev_idx])
                    break
            else:
                # EMAIL depends on previous analysis
                for prev_idx in range(idx):
                    prev_type = step_types_by_idx.get(prev_idx)
                    if prev_type == StepType.ANALYSIS:
                        dependencies[step_id].append(step_ids_by_idx[prev_idx])
                        break
    
    return dependencies


def group_parallel_steps(plan: list[PlanStep]) -> tuple[list[list[int]], list[int]]:
    """Group steps by parallelization potential.
    
    Returns:
        - parallel_groups: List of step index groups that can run in parallel
        - sequential_indices: Indices of steps that must run sequentially
    
    Algorithm:
    1. Identify sequential-only steps (SYNTHESIS, EMAIL, etc.)
    2. Group remaining steps by step_type (same type = can run parallel)
    3. Steps with same type can run together
    """
    parallelizable_indices: list[int] = []
    sequential_indices: list[int] = []
    
    for idx, step in enumerate(plan):
        step_type = step.get("step_type")
        
        if step_type in SEQUENTIAL_ONLY_STEP_TYPES:
            sequential_indices.append(idx)
        else:
            parallelizable_indices.append(idx)
    
    # Group parallelizable by step_type
    by_type: dict[StepType, list[int]] = {}
    for idx in parallelizable_indices:
        step_type = plan[idx].get("step_type")
        if step_type not in by_type:
            by_type[step_type] = []
        by_type[step_type].append(idx)
    
    parallel_groups = list(by_type.values())
    return parallel_groups, sequential_indices


def _parse_json_safe(text: str) -> Any:
    """Parse JSON from LLM output, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        text = re.sub(r"^.*?\[", "[", text, count=1)
        text = re.sub(r"\].*?$", "]", text, count=1)
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON: %s", text[:200])
            return []


class OrchestratorNodes:
    """Collection of nodes for the orchestrator agent.

    Each node is a callable that takes state and returns updated state.
    The nodes implement the supervisor pattern: a central coordinator
    that dispatches work to specialists and synthesizes results.

    Features:
    - Retry policies with exponential backoff for parallel execution
    - Fallback chain (try multiple tools if one fails)
    - Error aggregation with detailed logging
    - LLM health monitoring with auto-fallback
    """

    def __init__(
        self,
        llm_client: Optional[ChatCompletionClient] = None,
        max_articles: int = 5,
        min_sources: int = 2,
        health_manager: Optional[LLMHealthManager] = None,
    ) -> None:
        self._llm_client = llm_client
        self._max_articles = max_articles
        self._min_sources = min_sources
        self._registry = get_global_registry()
        self._deep_research_agent = None
        self._health_manager = health_manager or get_health_manager()

    def _client(self) -> ChatCompletionClient:
        if self._llm_client is None:
            self._llm_client = ChatCompletionClient()
        return self._llm_client

    async def _ensure_healthy_llm(self) -> str:
        """Ensure LLM provider is healthy, switching if necessary.
        
        Returns:
            Name of the active (healthy) provider
        """
        try:
            from app.config.settings import get_settings
            settings = get_settings()
            
            api_keys = {
                "zai": settings.zai_api_key or "",
                "openrouter": settings.llm_api_key or "",
            }
            
            active_provider = await self._health_manager.ensure_healthy_provider(api_keys)
            
            if active_provider != self._health_manager.active_provider:
                logger.info("Switched LLM provider to: %s", active_provider)
            
            return active_provider
        except Exception as exc:
            logger.warning("Health check failed: %s. Using default provider.", exc)
            return self._health_manager.active_provider
        return self._llm_client

    def _get_deep_research_agent(self):
        if self._deep_research_agent is None:
            from app.agents.deep_research.agent import create_deep_research_agent
            self._deep_research_agent = create_deep_research_agent()
        return self._deep_research_agent

    def _get_tool(self, tool_name: str) -> Optional[Any]:
        """Get a tool by name from registry.

        Also handles agent-as-tool by checking the registry for
        agents wrapped as tools.
        """
        # First try the regular tool registry
        tool = self._registry.get(tool_name)

        # If not found, try agent-as-tool pattern
        if tool is None:
            from app.agents import wrap_agent_as_tool
            tool = wrap_agent_as_tool(tool_name)

        if tool is None:
            logger.warning("Tool '%s' not found in registry", tool_name)

        return tool

    async def supervisor(self, state: OrchestratorState) -> OrchestratorState:
        """Entry point. If no plan exists, delegate to planner. Otherwise continue."""
        task = state.get("task", "")
        plan = state.get("plan", [])

        if not task:
            state["errors"] = state.get("errors", []) + ["No task provided"]
            return state

        if not plan:
            return state

        state["iteration_count"] = state.get("iteration_count", 0) + 1
        return state

    async def planner(self, state: OrchestratorState) -> OrchestratorState:
        """Generate execution plan from task using LLM.
        
        PLAN MODE STRICT:
        - Must generate a valid plan with at least 1 step
        - Each step must have required fields (step_id, name, step_type)
        - Retries up to max_plan_retries times before using fallback
        - Cannot exit without a complete plan
        - Includes LLM health check before execution
        """
        task = state.get("task", "")
        topics = state.get("metadata", {}).get("topics", task)
        
        max_plan_retries = state.get("max_plan_retries", 3)
        plan_attempts = state.get("plan_attempts", 0)

        # Ensure LLM is healthy before planning
        active_provider = await self._ensure_healthy_llm()
        logger.info("Using LLM provider for planning: %s", active_provider)

        client = self._client()
        
        # Get date for prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        prompt = PLANNER_USER.format(
            task=task,
            topics=", ".join(topics) if isinstance(topics, list) else topics,
        )

        try:
            logger.info("Generating plan for task: %s (attempt %d/%d)", 
                       task[:100], plan_attempts + 1, max_plan_retries)
            
            response = await client.async_generate_completion(
                prompt=prompt,
                system_message="""You are a Planning Agent. Create structured execution plans.

CRITICAL: You MUST return valid JSON that conforms to this exact schema:
[
  {
    "step_id": "step_1",
    "name": "Short name",
    "description": "What this step does",
    "step_type": "research|deep_research|analysis|synthesis|email|newsletter",
    "tool_name": "tool_name",
    "params": {}
  }
]

Rules:
- step_id must be unique (step_1, step_2, etc.)
- name must be 1-50 characters
- step_type must be one of the valid types
- tool_name must be a registered tool name
- Return ONLY valid JSON array, no markdown, no explanation""",
                temperature=0.2,
                max_tokens=3000,
            )

            if not response:
                raise ValueError("LLM returned empty response for planner")

            plan_data = _parse_json_safe(response)
            
            # Strict validation: must be a non-empty list
            if not isinstance(plan_data, list) or len(plan_data) == 0:
                raise ValueError("Planner returned empty or invalid plan")
            
            # Validate each step has required fields
            for i, step in enumerate(plan_data):
                if not isinstance(step, dict):
                    raise ValueError(f"Step {i} is not a valid object")
                if "step_id" not in step:
                    step["step_id"] = f"step_{i+1}"
                if "name" not in step:
                    raise ValueError(f"Step {i} missing required field 'name'")
                if "step_type" not in step:
                    raise ValueError(f"Step {i} missing required field 'step_type'")
                # Validate step_type
                try:
                    parse_step_type(step.get("step_type", "research"))
                except ValueError:
                    step["step_type"] = "research"

            plan: list[PlanStep] = []
            for i, step in enumerate(plan_data[:10]):
                plan.append(PlanStep(
                    step_id=step.get("step_id", f"step_{i+1}"),
                    name=step.get("name", f"Step {i+1}"),
                    description=step.get("description", ""),
                    step_type=parse_step_type(step.get("step_type", "research")),
                    status=StepStatus.PENDING,
                    tool_name=step.get("tool_name"),
                    params=step.get("params", {}),
                    result=None,
                    error=None,
                    started_at=None,
                    completed_at=None,
                ))

            state["plan"] = plan
            state["current_step_index"] = 0
            state["started_at"] = datetime.now().isoformat()
            state["plan_attempts"] = 0  # Reset on success
            logger.info("Planner generated %d steps", len(plan))

        except Exception as exc:
            logger.error("Planner failed: %s (attempt %d/%d)", 
                        exc, plan_attempts + 1, max_plan_retries)
            
            state["plan_attempts"] = plan_attempts + 1
            state["errors"] = state.get("errors", []) + [f"Planner attempt {plan_attempts + 1} failed: {exc}"]
            
            # STRICT MODE: Only use fallback after max retries
            if plan_attempts >= max_plan_retries - 1:
                logger.warning("Max plan retries reached. Using fallback plan.")
                state["plan"] = [
                    PlanStep(
                        step_id="fallback_step",
                        name="Deep Research",
                        description=f"Conduct deep research on {task}",
                        step_type=StepType.DEEP_RESEARCH,
                        status=StepStatus.PENDING,
                        tool_name="deep_research",
                        params={"query": task},
                        result=None,
                        error=None,
                        started_at=None,
                        completed_at=None,
                    )
                ]
                state["current_step_index"] = 0
                state["started_at"] = datetime.now().isoformat()
                state["plan_attempts"] = 0  # Reset after fallback
                state["errors"] = state.get("errors", []) + ["Used fallback plan after max retries"]
            # Otherwise, raise to trigger retry in graph
            else:
                raise ValueError(f"Plan validation failed: {exc}")

        return state

    async def dispatcher(self, state: OrchestratorState) -> OrchestratorState:
        """Execute the current plan step using the appropriate tool."""
        plan = state.get("plan", [])
        current_idx = state.get("current_step_index", 0)
        research_results = state.get("research_results", [])

        if current_idx >= len(plan):
            return state

        step = plan[current_idx]

        if step["status"] in (StepStatus.DONE, StepStatus.SKIPPED):
            state["current_step_index"] = current_idx + 1
            return state

        plan[current_idx]["status"] = StepStatus.RUNNING
        plan[current_idx]["started_at"] = datetime.now().isoformat()

        tool_name = step.get("tool_name")
        step_type = step.get("step_type")
        params = step.get("params", {}) or {}
        step_id = step["step_id"]

        try:
            # Handle DEEP_RESEARCH step type - use unified tool lookup
            if step_type == StepType.DEEP_RESEARCH:
                logger.info("Executing DEEP RESEARCH for step %s (via tool registry)", step_id)
                tool = self._get_tool("deep_research")
                if tool is None:
                    raise ValueError("Deep research agent not found in registry")

                query = step.get("description", params.get("query", state.get("task", "")))
                result = await tool.execute({
                    "query": query,
                    "metadata": {"parent_task_id": state.get("task_id")}
                })

                success = result.get("success", False)
                data = result.get("data", {})
                error = result.get("error")

            # Normal tool execution
            elif not tool_name:
                plan[current_idx]["status"] = StepStatus.SKIPPED
                plan[current_idx]["error"] = "No tool specified"
                plan[current_idx]["completed_at"] = datetime.now().isoformat()
                state["current_step_index"] = current_idx + 1
                return state
            else:
                tool = self._get_tool(tool_name)
                if tool is None:
                    raise ValueError(f"Tool '{tool_name}' not found")

                if hasattr(tool, "execute"):
                    result = await tool.execute(params)
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe(params)
                else:
                    raise ValueError(f"Tool '{tool_name}' has no execute method")

                if isinstance(result, dict):
                    success = result.get("success", False)
                    data = result.get("data", [])
                    error = result.get("error")
                elif isinstance(result, list):
                    success = True
                    data = result
                    error = None
                else:
                    success = True
                    data = result
                    error = None

            if success:
                plan[current_idx]["status"] = StepStatus.DONE
                plan[current_idx]["result"] = json.dumps(data) if isinstance(data, (list, dict)) else str(data)
                plan[current_idx]["completed_at"] = datetime.now().isoformat()

                research_results.append({
                    "step_id": step_id,
                    "step_name": step["name"],
                    "tool": tool_name or "deep_research",
                    "data": data,
                    "count": len(data) if isinstance(data, list) else 1,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info("Step '%s' completed with %d results", step_id, len(data) if isinstance(data, list) else 1)

                if isinstance(data, list):
                    await self._persist_articles_from_step(data, step_name, tool_name or "deep_research")
            else:
                plan[current_idx]["status"] = StepStatus.FAILED
                plan[current_idx]["error"] = error or "Unknown error"
                plan[current_idx]["completed_at"] = datetime.now().isoformat()
                logger.warning("Step '%s' failed: %s", step_id, error)

        except Exception as exc:
            logger.error("Dispatcher error for step '%s': %s", step_id, exc)
            plan[current_idx]["status"] = StepStatus.FAILED
            plan[current_idx]["error"] = str(exc)
            plan[current_idx]["completed_at"] = datetime.now().isoformat()
            state["errors"] = state.get("errors", []) + [f"Step {step_id} failed: {exc}"]

        state["plan"] = plan
        state["research_results"] = research_results
        state["current_step_index"] = current_idx + 1

        return state

    async def _execute_with_retry(
        self,
        step: PlanStep,
        idx: int,
        tool_name: str,
        params: dict,
        state: OrchestratorState,
    ) -> tuple[int, dict]:
        """Execute a step with retry policy and fallback chain."""
        step_id = step["step_id"]
        step_type = step.get("step_type")
        policy = RETRY_POLICY.copy()

        tools_to_try = [tool_name]
        if tool_name in FALLBACK_TOOLS:
            tools_to_try.extend(FALLBACK_TOOLS[tool_name])

        last_error = None
        for attempt in range(policy["max_attempts"]):
            for current_tool in tools_to_try:
                try:
                    interval = min(
                        policy["initial_interval"] * (policy["backoff_factor"] ** attempt),
                        policy["max_interval"]
                    )
                    if attempt > 0 and interval > 0:
                        await asyncio.sleep(interval)

                    if step_type == StepType.DEEP_RESEARCH:
                        tool = self._get_tool("deep_research")
                        if tool is None:
                            continue
                        query = step.get("description", params.get("query", state.get("task", "")))
                        result = await tool.execute({
                            "query": query,
                            "metadata": {"parent_task_id": state.get("task_id")}
                        })
                    elif step_type == StepType.NEWSLETTER:
                        result = await self._call_newsletter_agent(state, step)
                    else:
                        tool = self._get_tool(current_tool)
                        if tool is None:
                            continue
                        if hasattr(tool, "execute"):
                            result = await tool.execute(params)
                        elif hasattr(tool, "execute_safe"):
                            result = await tool.execute_safe(params)
                        else:
                            continue

                    if result.get("success"):
                        return idx, {
                            "success": True,
                            "data": result.get("data", {}),
                            "step_id": step_id,
                            "tool": current_tool,
                            "attempts": attempt + 1,
                        }
                    last_error = result.get("error", "Unknown error")
                except Exception as exc:
                    last_error = str(exc)

        return idx, {
            "success": False,
            "error": last_error or f"All tools failed after {policy['max_attempts']} attempts",
            "step_id": step_id,
            "tool": tool_name,
            "attempts": policy["max_attempts"],
        }

    async def dispatcher_parallel(self, state: OrchestratorState) -> OrchestratorState:
        """Fan-out dispatcher: launch all independent steps in parallel.

        PARALLEL EXECUTION WITH CONFLICT DETECTION:
        - Analyzes step dependencies before execution
        - Groups steps by type for parallel execution
        - RESEARCH, DEEP_RESEARCH, NEWSLETTER can run in parallel
        - SYNTHESIS, ANALYSIS, EMAIL run sequentially after research
        
        Algorithm:
        1. Analyze dependencies using group_parallel_steps()
        2. Execute parallel groups simultaneously
        3. Handle sequential-only steps separately
        """
        plan = state.get("plan", [])
        
        if not plan:
            return state
        
        # Analyze dependencies
        parallel_groups, sequential_indices = group_parallel_steps(plan)
        
        # Find all pending parallelizable steps
        pending_parallel: list[int] = []
        for group in parallel_groups:
            for idx in group:
                if plan[idx].get("status") == StepStatus.PENDING:
                    pending_parallel.append(idx)
        
        pending_sequential = [i for i in sequential_indices 
                           if plan[i].get("status") == StepStatus.PENDING]
        
        if not pending_parallel and not pending_sequential:
            return await self.dispatcher(state)
        
        logger.info("Execution plan: %d parallel groups, %d sequential steps",
                   len(parallel_groups), len(pending_sequential))

        async def run_step(step: PlanStep, idx: int) -> tuple[int, dict]:
            tool_name = step.get("tool_name") or "search"
            params = step.get("params", {}) or {}
            step_id = step["step_id"]
            step_type = step.get("step_type")
            
            if step_type == StepType.DEEP_RESEARCH:
                return await self._execute_with_retry(step, idx, tool_name, params, state)
            
            return await self._execute_with_retry(step, idx, tool_name, params, state)

        try:
            tasks = [run_step(plan[i], i) for i in pending_parallel]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            research_results = state.get("research_results", [])
            updated_plan = plan[:]
            
            completed_count = 0

            for item in results:
                if isinstance(item, Exception) or not isinstance(item, tuple):
                    continue
                idx, result = item
                if idx >= len(updated_plan):
                    continue

                updated_plan[idx]["started_at"] = datetime.now().isoformat()
                updated_plan[idx]["completed_at"] = datetime.now().isoformat()

                if result.get("success"):
                    updated_plan[idx]["status"] = StepStatus.DONE
                    updated_plan[idx]["result"] = json.dumps(result.get("data")) if isinstance(result.get("data"), (list, dict)) else str(result.get("data"))
                    research_results.append({
                        "step_id": result.get("step_id"),
                        "step_name": plan[idx]["name"],
                        "tool": result.get("tool", ""),
                        "data": result.get("data", []),
                        "count": len(result.get("data", [])) if isinstance(result.get("data"), list) else 1,
                        "timestamp": datetime.now().isoformat(),
                    })
                    completed_count += 1
                else:
                    updated_plan[idx]["status"] = StepStatus.FAILED
                    updated_plan[idx]["error"] = result.get("error", "Unknown error")

            state["plan"] = updated_plan
            state["research_results"] = research_results
            
            # Update current_step_index to first pending sequential step
            if pending_sequential:
                state["current_step_index"] = pending_sequential[0]
            elif pending_parallel:
                # After all parallel done, move to next phase
                state["current_step_index"] = max(pending_parallel) + 1 if pending_parallel else 0
            else:
                state["current_step_index"] = 0
                
            logger.info("Parallel dispatch completed: %d/%d parallel steps done, %d sequential pending",
                       completed_count, len(pending_parallel), len(pending_sequential))

        except Exception as exc:
            logger.error("Parallel dispatcher failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Parallel dispatch failed: {exc}"]

        return state

    async def collector(self, state: OrchestratorState) -> OrchestratorState:
        """Aggregate all research results into a unified corpus.

        Also persists articles to the database for future retrieval.
        """
        research_results = state.get("research_results", [])
        task = state.get("task", "")

        if not research_results:
            state["errors"] = state.get("errors", []) + ["No research results to collect"]
            return state

        corpus_parts = []
        articles_to_store = []

        for r in research_results:
            tool = r.get("tool", "unknown")
            data = r.get("data", [])
            count = r.get("count", 0)
            step_name = r.get("step_name", "")

            if isinstance(data, list):
                items = []
                for item in data[:self._max_articles]:
                    if isinstance(item, dict):
                        items.append(f"- {item.get('title', item.get('name', str(item)))}: {item.get('summary', item.get('description', ''))[:200]}")
                        articles_to_store.append(item)
                    elif isinstance(item, str):
                        items.append(f"- {item}")
                    else:
                        items.append(f"- {str(item)[:200]}")
                corpus_parts.append(f"### {step_name} ({tool}, {count} items)\n" + "\n".join(items))
            else:
                corpus_parts.append(f"### {step_name} ({tool}): {str(data)[:500]}")

        corpus = "\n\n".join(corpus_parts)

        client = self._client()
        prompt = COLLECTOR_USER.format(results=corpus)

        try:
            summary = await client.async_generate_completion(
                prompt=prompt,
                system_message="You are the Collector Agent. Aggregate research results.",
                temperature=0.3,
                max_tokens=4000,
            )
            state["articles"] = research_results
            logger.info("Collector aggregated %d result sets", len(research_results))

            await self._persist_articles(articles_to_store)

        except Exception as exc:
            logger.error("Collector failed: %s", exc)
            state["articles"] = research_results
            state["errors"] = state.get("errors", []) + [f"Collector error: {exc}"]

        return state

    async def _persist_articles(self, articles: list[dict]) -> None:
        """Persist articles to database for future retrieval.

        Uses ArticleService to store with deduplication.
        """
        if not articles:
            return

        try:
            from app.services.article_service import ArticleService

            article_service = ArticleService()
            await article_service.save_articles(articles)
            logger.info("Persisted %d articles to database", len(articles))
        except Exception as exc:
            logger.warning("Failed to persist articles: %s", exc)

    async def _persist_articles_from_step(
        self,
        articles: list,
        step_name: str,
        tool_name: str,
    ) -> None:
        """Persist articles from a single research step to database.

        Args:
            articles: List of article data (dicts) from the step
            step_name: Name of the step that produced the articles
            tool_name: Name of the tool used to fetch articles
        """
        if not articles:
            return

        try:
            from app.services.article_service import ArticleService

            enriched_articles = []
            for item in articles:
                if isinstance(item, dict):
                    enriched = {
                        "title": item.get("title", item.get("name", "")),
                        "summary": item.get("summary", item.get("description", "")),
                        "url": item.get("url", ""),
                        "topic": step_name,
                        "source": tool_name,
                        "published_date": item.get("published_date", item.get("date", "")),
                    }
                    enriched_articles.append(enriched)

            if enriched_articles:
                article_service = ArticleService()
                await article_service.save_articles(enriched_articles)
                logger.info(
                    "Persisted %d articles from step '%s' via %s",
                    len(enriched_articles),
                    step_name,
                    tool_name,
                )
        except Exception as exc:
            logger.warning("Failed to persist articles from step '%s': %s", step_name, exc)

    async def _call_newsletter_agent(
        self,
        state: OrchestratorState,
        step: PlanStep,
    ) -> dict:
        """Call NewsletterAgent as a sub-agent.

        The NewsletterAgent handles article collection, analysis, and
        newsletter composition. We pass the orchestrator's task and
        collected research results to it.

        Args:
            state: Current orchestrator state
            step: The plan step containing newsletter configuration

        Returns:
            Dict with success status and newsletter data
        """
        try:
            from app.agents.newsletter.agent import NewsletterAgent
            from app.core.models import Article

            task = state.get("task", "")
            topics = state.get("topics", [])

            articles_input = None
            research_results = state.get("research_results", [])
            if research_results:
                articles_input = self._extract_articles_from_results(research_results)
                logger.info("Passing %d articles from orchestrator to NewsletterAgent", len(articles_input))

            params = step.get("params", {}) or {}

            agent = NewsletterAgent(
                config=NewsletterAgentConfig(
                    topics=topics if topics else [task],
                    send_email=False,
                    max_articles_per_topic=params.get("max_articles", 10),
                )
            )

            result = await agent.execute({
                "topics": topics if topics else [task],
                "articles": articles_input,
            })

            if result.success:
                return {
                    "success": True,
                    "data": {
                        "newsletter_generated": True,
                        "subject": result.data.get("subject", task),
                        "content": result.data.get("newsletter", ""),
                        "articles_count": result.metadata.get("article_count", 0),
                        "quality_score": result.metadata.get("quality_score", 0),
                    },
                }
            else:
                return {
                    "success": False,
                    "error": (result.errors[0] if result.errors else "Newsletter agent failed"),
                }

        except Exception as exc:
            logger.error("Newsletter agent call failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _extract_articles_from_results(
        self,
        research_results: list[dict],
    ) -> list[Article]:
        """Convert orchestrator research results into Article objects.

        Args:
            research_results: List of research result dicts

        Returns:
            List of Article objects
        """
        from app.core.models import Article

        articles = []
        seen_urls: set[str] = set()

        for result in research_results:
            data = result.get("data", [])
            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue

                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue

                seen_urls.add(url)
                article = Article(
                    title=item.get("title", item.get("name", "")),
                    summary=item.get("summary", item.get("description", "")),
                    url=url,
                    topic=result.get("step_name", "unknown"),
                    source=item.get("source", result.get("tool", "orchestrator")),
                    published_date=item.get("published_date", item.get("date", "")),
                    content=item.get("content", item.get("text", "")),
                )
                articles.append(article)

        return articles

    async def validator(self, state: OrchestratorState) -> OrchestratorState:
        """Validate that collected results meet quality thresholds.

        Also computes a quality score for human-in-the-loop approval.
        """
        research_results = state.get("research_results", [])
        task = state.get("task", "")

        article_count = sum(
            r.get("count", 0) for r in research_results
            if isinstance(r.get("data"), (list, dict))
        )
        source_count = len(research_results)

        validation_errors = []
        quality_score = 0.0

        if article_count < 3:
            validation_errors.append(f"Insufficient articles: {article_count} < 3")
        else:
            quality_score += 0.4

        if source_count < 2:
            validation_errors.append(f"Insufficient sources: {source_count} < 2")
        else:
            quality_score += 0.2

        has_successful_results = any(r.get("count", 0) > 0 for r in research_results)
        if has_successful_results:
            quality_score += 0.3

        if len(task) > 20:
            quality_score += 0.1

        quality_score = min(quality_score, 1.0)

        state["validation_errors"] = validation_errors
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        state["quality_score"] = quality_score

        if validation_errors:
            max_iter = state.get("max_iterations", 5)
            iteration = state.get("iteration_count", 0)
            if iteration >= max_iter:
                logger.warning("Max iterations reached (%d/%d), proceeding despite validation errors", iteration, max_iter)
            else:
                logger.info("Validation failed (attempt %d/%d): %s. Will retry.", iteration, max_iter, validation_errors)

        logger.info("Validator: %d articles from %d sources, quality=%.2f", article_count, source_count, quality_score)
        return state

    async def human_approval(self, state: OrchestratorState) -> OrchestratorState:
        """Human-in-the-loop approval checkpoint.

        This node pauses execution and waits for human approval.
        In a real implementation, this would use LangGraph's interrupt
        mechanism or a message queue to pause and wait for user input.

        For now, it automatically approves if quality score is above threshold.
        """
        quality_score = state.get("quality_score", 0.0)
        approval_threshold = state.get("approval_threshold", 0.7)

        state["approval_status"] = "auto_approved" if quality_score >= approval_threshold else "needs_review"

        if quality_score >= approval_threshold:
            logger.info("Auto-approved: quality %.2f >= threshold %.2f", quality_score, approval_threshold)
            state["approval_result"] = "approved"
        else:
            logger.warning("Needs review: quality %.2f < threshold %.2f", quality_score, approval_threshold)
            state["approval_result"] = "pending"

        state["approved_at"] = datetime.now().isoformat() if quality_score >= approval_threshold else None

        return state

    async def analyzer(self, state: OrchestratorState) -> OrchestratorState:
        """Extract key insights from the research corpus."""
        research_results = state.get("research_results", [])
        task = state.get("task", "")

        corpus_parts = []
        for r in research_results:
            data = r.get("data", [])
            step_name = r.get("step_name", "")
            if isinstance(data, list):
                items = []
                for item in data[:10]:
                    if isinstance(item, dict):
                        title = item.get("title", item.get("name", ""))
                        summary = item.get("summary", item.get("description", ""))
                        url = item.get("url", "")
                        items.append(f"- [{title}]({url})" if url else f"- {title}: {summary}")
                    else:
                        items.append(f"- {str(item)[:200]}")
                if items:
                    corpus_parts.append(f"### {step_name}\n" + "\n".join(items))
            elif data:
                corpus_parts.append(f"### {step_name}: {str(data)[:500]}")

        corpus = "\n\n".join(corpus_parts) or "No corpus available"

        client = self._client()
        prompt = ANALYZER_USER.format(task=task, corpus=corpus)

        try:
            analysis = await client.async_generate_completion(
                prompt=prompt,
                system_message="You are the Analyst Agent. Extract key insights from research.",
                temperature=0.4,
                max_tokens=4000,
            )
            state["analysis_results"] = analysis
            logger.info("Analyzer completed")
        except Exception as exc:
            logger.error("Analyzer failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Analyzer error: {exc}"]

        return state

    async def synthesizer(self, state: OrchestratorState) -> OrchestratorState:
        """Create the final comprehensive report.

        Also stores the report in ResearchSession for future reference.
        """
        research_results = state.get("research_results", [])
        analysis = state.get("analysis_results", "")
        task = state.get("task", "")

        corpus_parts = []
        for r in research_results:
            data = r.get("data", [])
            step_name = r.get("step_name", "")
            tool = r.get("tool", "")
            if isinstance(data, list):
                items = []
                for item in data[:8]:
                    if isinstance(item, dict):
                        title = item.get("title", item.get("name", ""))
                        summary = item.get("summary", item.get("description", ""))
                        url = item.get("url", "")
                        source = item.get("source", tool)
                        date = item.get("published_date", item.get("date", ""))
                        date_str = f" ({date})" if date else ""
                        items.append(f"- [{title}]({url}){date_str}\n  Source: {source}\n  {summary}")
                    else:
                        items.append(f"- {str(item)[:300]}")
                if items:
                    corpus_parts.append(f"### {step_name}\n" + "\n".join(items))
            elif data:
                corpus_parts.append(f"### {step_name}: {str(data)[:800]}")

        corpus = "\n\n".join(corpus_parts) or "No data available"
        analysis_text = analysis or "No analysis available"

        client = self._client()
        prompt = SYNTHESIZER_USER.format(task=task, corpus=corpus, analysis=analysis_text)

        try:
            report = await client.async_generate_completion(
                prompt=prompt,
                system_message="You are the Synthesizer Agent. Create comprehensive tech reports.",
                temperature=0.4,
                max_tokens=8000,
            )
            state["final_report"] = report
            state["synthesis_result"] = report[:500] + "..." if len(report) > 500 else report
            state["completed_at"] = datetime.now().isoformat()
            logger.info("Synthesizer completed report (%d chars)", len(report))

            await self._persist_research_session(state, task)

        except Exception as exc:
            logger.error("Synthesizer failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Synthesizer error: {exc}"]

        return state

    async def _persist_research_session(
        self,
        state: OrchestratorState,
        task: str,
    ) -> None:
        """Persist research results and report to ResearchSession."""
        try:
            from app.db.base import get_db_context
            from app.db.models import ResearchSession
            import uuid

            research_results = state.get("research_results", [])
            notes = []
            raw_notes = []

            for r in research_results:
                tool = r.get("tool", "")
                step_name = r.get("step_name", "")
                data = r.get("data", [])
                if isinstance(data, list):
                    for item in data[:5]:
                        if isinstance(item, dict):
                            title = item.get("title", item.get("name", ""))
                            summary = item.get("summary", item.get("description", ""))
                            raw_notes.append(f"[{step_name}/{tool}] {title}: {summary[:200]}")

            session = ResearchSession(
                id=uuid.uuid4(),
                user_id=None,
                research_brief=task[:500],
                final_report=state.get("final_report", ""),
                notes=notes,
                raw_notes=raw_notes,
                status="completed",
            )

            async with get_db_context() as db_session:
                db_session.add(session)
                await db_session.commit()
                logger.info("Stored research session with %d notes", len(raw_notes))

        except Exception as exc:
            logger.warning("Failed to persist research session: %s", exc)

    async def emailer(self, state: OrchestratorState) -> OrchestratorState:
        """Send the final report via email."""
        report = state.get("final_report", "")
        task = state.get("task", "")

        if not report:
            state["errors"] = state.get("errors", []) + ["No report to send"]
            return state

        from app.delivery.newsletter_renderer import NewsletterRenderer
        from app.delivery.gmail_client import GmailDeliveryClient
        from app.config.settings import get_settings

        try:
            settings = get_settings()
            renderer = NewsletterRenderer(settings)

            subject = self._extract_subject(report)
            html_content = renderer.render_html(report, subject)
            text_content = renderer.render_text(report)

            state["email_result"] = f"Subject: {subject}\n\nReport prepared ({len(report)} chars)"

            if settings.has_email_delivery and state.get("email_sent") is not True:
                gmail = GmailDeliveryClient(settings)
                success = gmail.send_email(
                    subject=subject,
                    body_html=html_content,
                    body_text=text_content,
                )
                state["email_sent"] = success
                state["email_result"] = f"Email sent: {success}"
                logger.info("Email delivery: %s", "success" if success else "failed")
            else:
                state["email_sent"] = False
                logger.info("Email delivery skipped (not configured)")

        except Exception as exc:
            logger.error("Emailer failed: %s", exc)
            state["email_result"] = f"Email error: {exc}"
            state["email_sent"] = False
            state["errors"] = state.get("errors", []) + [f"Emailer error: {exc}"]

        return state

    @staticmethod
    def _extract_subject(report: str) -> str:
        lines = report.split("\n")
        for line in lines:
            lowered = line.lower().strip()
            if lowered.startswith("# "):
                return line[2:].strip()
            if lowered.startswith("## "):
                return line[3:].strip()
            if "subject:" in lowered:
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip()
        return "Tech Watch Report"

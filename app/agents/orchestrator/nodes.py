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
    ANALYZER_SYSTEM,
    SYNTHESIZER_USER,
    SYNTHESIZER_SYSTEM,
    EMAILER_USER,
)
from langgraph.types import RunnableConfig
from app.services.llm import ChatCompletionClient
from app.services.llm.health import LLMHealthManager, get_health_manager
from app.tools.registry import get_global_registry
from app.core.logging import get_logger
from app.services.session_manager import normalize_plan_payload


logger = get_logger(__name__)

RETRY_POLICY = {
    "max_attempts": 3,
    "initial_interval": 1.0,
    "backoff_factor": 2.0,
    "max_interval": 60.0,
}

FALLBACK_TOOLS = {
    # web_search and searxng both resolve to SearXNGSearchTool, so skip the
    # redundant alias and go straight to Tavily as first real fallback.
    "search": ["tavily_search", "searxng", "exa_search", "arxiv"],
    "web_search": ["tavily_search", "exa_search", "langsearch"],
    "searxng": ["tavily_search", "exa_search", "web_search"],
    "research": ["deep_research", "web_search", "arxiv"],
    "crawl": ["jina_reader", "crawl4ai", "scrapling", "content_extractor"],
    "academic": ["semantic_scholar", "arxiv", "openalex"],
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


def _normalize_step_data(data: Any) -> list[dict]:
    """Convert any tool output shape into a flat list of article dicts.

    Handles:
    - list of dicts (SearXNG, SemanticScholar, GitHub …)
    - Tavily format: {"results": [...], "answer": str, "count": int}
    - MultiProvider format: {"articles": [...], "providers": [...]}
    - deep_research format: {"report": str, "findings": list, "query": str}
    """
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    # Tavily: {"results": [...]}
    if "results" in data and isinstance(data["results"], list):
        out = []
        for r in data["results"]:
            if isinstance(r, dict) and r.get("url"):
                out.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "summary": r.get("content") or r.get("summary") or r.get("description") or "",
                    "source": r.get("source") or r.get("url", "").split("/")[2] if r.get("url") else "",
                    "published_date": r.get("published_date") or r.get("date") or "",
                    "relevance_score": r.get("score") or r.get("relevance_score"),
                })
        return out

    # MultiProvider or generic: {"articles": [...]}
    if "articles" in data and isinstance(data["articles"], list):
        return data["articles"]

    # deep_research AgentAsTool output: {"report": str, "findings": list}
    findings = data.get("findings") or []
    if findings:
        out = []
        for f in findings:
            if isinstance(f, dict):
                out.append({
                    "title": f.get("title") or (f.get("url", "")[:80] if f.get("url") else ""),
                    "url": f.get("url", ""),
                    "summary": (f.get("content") or f.get("summary") or "")[:400],
                    "source": "deep_research",
                    "published_date": "",
                })
        return out

    # Fallback: wrap the report text as a pseudo-article
    report = data.get("report", "")
    if report:
        return [{
            "title": "Rapport de recherche approfondie",
            "url": "",
            "summary": report[:400],
            "source": "deep_research",
            "published_date": "",
        }]

    return []


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
    - Session persistence with plan versioning
    - Memory compaction to avoid context limits
    - Checkpoint/resume for interrupted sessions
    """

    def __init__(
        self,
        llm_client: Optional[ChatCompletionClient] = None,
        max_articles: int = 5,
        min_sources: int = 2,
        health_manager: Optional[LLMHealthManager] = None,
        session_id: Optional[str] = None,
        enable_session_persistence: bool = True,
    ) -> None:
        self._llm_client = llm_client
        self._max_articles = max_articles
        self._min_sources = min_sources
        self._registry = get_global_registry()
        self._deep_research_agent = None
        self._health_manager = health_manager or get_health_manager()
        self._session_manager = None
        self._session_id = session_id
        self._enable_persistence = enable_session_persistence

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
            
            # zai_api_key may be empty; fall back to llm_api_key (which may hold the ZAI key)
            zai_key = settings.zai_api_key or (
                settings.llm_api_key if settings.llm_provider == "zai" else ""
            )
            api_keys = {
                "zai": zai_key,
                "openrouter": getattr(settings, "openrouter_api_key", "") or "",
            }
            
            active_provider = await self._health_manager.ensure_healthy_provider(api_keys)
            
            if active_provider != self._health_manager.active_provider:
                logger.info("Switched LLM provider to: %s", active_provider)
            
            return active_provider
        except Exception as exc:
            logger.warning("Health check failed: %s. Using default provider.", exc)
            return self._health_manager.active_provider

    async def _init_session_manager(self, state: OrchestratorState) -> None:
        """Initialize session manager for this session.
        
        Args:
            state: Current orchestrator state
        """
        if not self._enable_persistence:
            return

        session_ref = state.get("session_id") or self._session_id
        if session_ref is None:
            return

        if self._session_manager is not None and self._session_id == str(session_ref):
            return

        try:
            from app.services.session_manager import SessionManager

            session_uuid = uuid.UUID(str(session_ref))
            self._session_id = str(session_uuid)
            self._session_manager = SessionManager(session_uuid)
            await self._session_manager.initialize()
            logger.info("Session manager initialized for session %s", session_uuid)
        except Exception as exc:
            logger.warning("Failed to initialize session manager: %s", exc)
            self._session_manager = None

    async def _save_phase(
        self, 
        state: OrchestratorState, 
        phase: str,
        reason: str = "phase_transition",
    ) -> None:
        """Save session state at phase transition.
        
        Args:
            state: Current orchestrator state
            phase: New phase name
            reason: Reason for save
        """
        if not self._enable_persistence:
            return

        try:
            await self._init_session_manager(state)

            if self._session_manager is None:
                return

            from app.services.session_manager import SessionPhase
            session_phase = SessionPhase(phase) if phase in [p.value for p in SessionPhase] else SessionPhase.RESEARCH

            await self._session_manager.save_phase(
                phase=session_phase,
                plan=state.get("plan", []),
                current_step_index=state.get("current_step_index", 0),
                reason=reason,
            )
        except Exception as exc:
            logger.warning("Failed to save phase: %s", exc)

    async def _create_checkpoint(
        self,
        state: OrchestratorState,
        phase: str,
    ) -> str:
        """Create a checkpoint for resumable state.
        
        Args:
            state: Current orchestrator state
            phase: Current phase
            
        Returns:
            Checkpoint ID or empty string
        """
        if not self._enable_persistence:
            return ""

        try:
            await self._init_session_manager(state)

            if self._session_manager is None:
                return ""

            from app.services.session_manager import SessionPhase
            session_phase = SessionPhase(phase) if phase in [p.value for p in SessionPhase] else SessionPhase.RESEARCH

            checkpoint_id = await self._session_manager.create_checkpoint(
                phase=session_phase,
                state_snapshot=dict(state),
                articles=state.get("articles", []),
                results=state.get("research_results", []),
            )
            return checkpoint_id
        except Exception as exc:
            logger.warning("Failed to create checkpoint: %s", exc)
            return ""

    async def _compact_memory(
        self,
        state: OrchestratorState,
        reason: str = "phase_transition",
    ) -> None:
        """Compact agent memory to avoid context limits.
        
        This does NOT compact articles (kept full for RAG).
        
        Args:
            state: Current orchestrator state
            reason: Reason for compaction
        """
        if not self._enable_persistence:
            return

        try:
            await self._init_session_manager(state)

            if self._session_manager is None:
                return

            from app.services.session_manager import CompactionReason

            compaction_reason = CompactionReason(reason)
            result = await self._session_manager.compact_memory(state, compaction_reason)
            
            if result.success and result.compression_ratio > 0:
                logger.info(
                    "Memory compacted: original=%d, compacted=%d, ratio=%.1f%%",
                    result.original_size, result.compacted_size, result.compression_ratio * 100
                )
        except Exception as exc:
            logger.warning("Failed to compact memory: %s", exc)

    async def _try_resume_from_checkpoint(self, state: OrchestratorState) -> OrchestratorState:
        """Try to resume session from checkpoint.
        
        Args:
            state: Current orchestrator state
            
        Returns:
            Updated state with checkpoint data, or original state if no checkpoint
        """
        if not self._enable_persistence:
            return state
            
        try:
            await self._init_session_manager(state)
            
            if self._session_manager is None:
                return state
                
            checkpoint = await self._session_manager.resume_from_checkpoint()
            
            if checkpoint:
                logger.info(
                    "Resuming from checkpoint: phase=%s, index=%d",
                    checkpoint["phase"], checkpoint["checkpoint_index"]
                )
                
                # Restore state from checkpoint
                if checkpoint.get("state_snapshot"):
                    snapshot = checkpoint["state_snapshot"]
                    state["plan"] = snapshot.get("plan", state.get("plan", []))
                    state["current_step_index"] = checkpoint["checkpoint_index"]
                    state["research_results"] = checkpoint.get("results_snapshot", [])
                    state["articles"] = checkpoint.get("articles_snapshot", [])
                    state["resumed_from_checkpoint"] = True
                    
        except Exception as exc:
            logger.warning("Failed to resume from checkpoint: %s", exc)
            
        return state

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
        if self._enable_persistence:
            await self._init_session_manager(state)
            if not state.get("resumed_from_checkpoint"):
                state = await self._try_resume_from_checkpoint(state)
            if self._session_manager and self._session_manager.session:
                persisted = self._session_manager.session
                state.setdefault("research_brief", persisted.research_brief)
                if not state.get("task"):
                    state["task"] = persisted.research_brief
                if not state.get("plan") and persisted.plan:
                    state["plan"] = normalize_plan_payload(persisted.plan)
                if not state.get("research_results") and persisted.research_results:
                    state["research_results"] = persisted.research_results
                if state.get("current_step_index", 0) == 0 and persisted.current_step_index:
                    state["current_step_index"] = persisted.current_step_index

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

        from app.core.watch_context import WatchContext
        watch_ctx = state.get("watch_context") or WatchContext.default()
        if isinstance(watch_ctx, dict):
            watch_ctx = WatchContext(**watch_ctx)

        from datetime import datetime as _dt
        session_seed = state.get("session_id", "")[-6:] if state.get("session_id") else ""
        run_ts = _dt.now().strftime("%H:%M:%S")

        # Inject vector memory context so the planner avoids repeating past research
        memory_block = ""
        try:
            from app.tools.memory.search_memory import SearchMemoryTool
            _mem = SearchMemoryTool()
            _mem_result = await _mem.execute({"query": task, "top_k": 8, "min_score": 0.25})
            if _mem_result.get("success"):
                _recent = _mem_result.get("data", {}).get("results", [])
                if _recent:
                    _covered_topics = list({r.get("topic", "") for r in _recent if r.get("topic")})
                    _titles = [r["title"] for r in _recent[:6] if r.get("title")]
                    memory_block = "\n\n## Previously researched (avoid repeating)\n"
                    if _covered_topics:
                        memory_block += f"Topics already covered: {', '.join(_covered_topics[:6])}\n"
                    memory_block += "Recent articles already in memory:\n"
                    memory_block += "\n".join(f"- {t}" for t in _titles)
                    memory_block += "\nFocus on NEW angles, sources, and developments not yet covered."
        except Exception as _mem_exc:
            logger.debug("Planner memory fetch failed (non-blocking): %s", _mem_exc)

        prompt = PLANNER_USER.format(
            task=task,
            watch_context=watch_ctx.to_prompt_block(),
            depth=watch_ctx.depth,
            suggested_steps=watch_ctx.suggested_steps,
            allowed_tools=", ".join(watch_ctx.allowed_tools),
            current_year=watch_ctx.current_year,
            current_month=watch_ctx.month_name,
            topic=", ".join(topics) if isinstance(topics, list) else str(topics),
        )
        prompt += memory_block
        prompt += f"\n\n[session={session_seed} ts={run_ts} vary_approach=true]"

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
- tool_name must be a registered tool name or null (for synthesis)
- ALWAYS end the plan with a synthesis step: {"step_type": "synthesis", "tool_name": null, "params": {}}
- Vary the research approach each time (different tools, angles, queries)
- Return ONLY valid JSON array, no markdown, no explanation""",
                temperature=0.7,
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

            # Ensure the plan ends with a synthesis step
            has_synthesis = any(
                str(s.get("step_type", "")).lower() == "synthesis"
                for s in plan_data
            )
            if not has_synthesis:
                plan_data.append({
                    "step_id": f"step_{len(plan_data) + 1}",
                    "name": "Synthèse finale",
                    "description": "Rédaction du rapport de synthèse final",
                    "step_type": "synthesis",
                    "tool_name": None,
                    "params": {},
                })

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
            
            # Save plan to session (phase: plan)
            await self._save_phase(state, "plan", "plan_created")

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

                normalized_data = _normalize_step_data(data)
                research_results.append({
                    "step_id": step_id,
                    "step_name": step["name"],
                    "tool": tool_name or "deep_research",
                    "data": normalized_data,
                    "count": len(normalized_data) if isinstance(normalized_data, list) else 1,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info("Step '%s' completed with %d results", step_id, len(normalized_data) if isinstance(normalized_data, list) else 1)

                if isinstance(data, list):
                    await self._persist_articles_from_step(data, step["name"], tool_name or "deep_research")
                await self._sync_sources_realtime(state, research_results)
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
        started_at = datetime.now().isoformat()
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
                        data_val = result.get("data")
                        # Normalise to list immediately so we can check emptiness
                        normalized = _normalize_step_data(data_val)
                        if not normalized:
                            last_error = f"Tool '{current_tool}' returned 0 results"
                            logger.debug("Tool '%s' returned empty results, trying fallback", current_tool)
                            continue
                        # Use the normalised list as the canonical data
                        data_val = normalized
                        return idx, {
                            "success": True,
                            "data": data_val if data_val is not None else {},
                            "step_id": step_id,
                            "tool": current_tool,
                            "attempts": attempt + 1,
                            "started_at": started_at,
                            "completed_at": datetime.now().isoformat(),
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
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
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

        async def run_step(step: PlanStep, idx: int, stagger_delay: float = 0.0) -> tuple[int, dict]:
            tool_name = step.get("tool_name") or "search"
            params = step.get("params", {}) or {}
            # Stagger parallel steps that hit SearXNG to avoid concurrent engine throttling
            if stagger_delay > 0:
                await asyncio.sleep(stagger_delay)
            return await self._execute_with_retry(step, idx, tool_name, params, state)

        try:
            # Add a small incremental delay so parallel SearXNG requests don't all land at once
            tasks = [
                run_step(plan[i], i, stagger_delay=0.5 * n)
                for n, i in enumerate(pending_parallel)
            ]
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

                updated_plan[idx]["started_at"] = result.get("started_at") or updated_plan[idx].get("started_at") or datetime.now().isoformat()
                updated_plan[idx]["completed_at"] = result.get("completed_at") or datetime.now().isoformat()

                if result.get("success"):
                    updated_plan[idx]["status"] = StepStatus.DONE
                    updated_plan[idx]["result"] = json.dumps(result.get("data")) if isinstance(result.get("data"), (list, dict)) else str(result.get("data"))
                    normalized_data = _normalize_step_data(result.get("data", []))
                    research_results.append({
                        "step_id": result.get("step_id"),
                        "step_name": plan[idx]["name"],
                        "tool": result.get("tool", ""),
                        "data": normalized_data,
                        "count": len(normalized_data) if isinstance(normalized_data, list) else 1,
                        "timestamp": datetime.now().isoformat(),
                    })
                    completed_count += 1
                else:
                    updated_plan[idx]["status"] = StepStatus.FAILED
                    updated_plan[idx]["error"] = result.get("error", "Unknown error")

            state["plan"] = updated_plan
            state["research_results"] = research_results

            # Sync sources to DB so they appear in the frontend during the session
            await self._sync_sources_realtime(state, research_results)

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

        Also persists articles to the database for future retrieval and
        applies ranking to select the most relevant ones for synthesis.
        """
        research_results = state.get("research_results", [])
        task = state.get("task", "")
        research_brief = state.get("research_brief", task)

        if not research_results:
            state["errors"] = state.get("errors", []) + ["No research results to collect"]
            return state

        # 1. Extract all articles from all steps
        all_articles_data = []
        for r in research_results:
            data = r.get("data", [])
            tool = r.get("tool", "unknown")
            step_name = r.get("step_name", "")
            
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Ensure basic fields exist for ranking
                        item.setdefault("topic", step_name)
                        item.setdefault("source", tool)
                        all_articles_data.append(item)
            elif isinstance(data, dict):
                data.setdefault("topic", step_name)
                data.setdefault("source", tool)
                all_articles_data.append(data)

        # 1b. Inter-session deduplication: separate fresh articles from already-known ones.
        # Fresh articles (not yet in the Article table) are ranked first; known ones are
        # appended as fallback so the session is never empty if all results are familiar.
        fresh_articles_data = all_articles_data
        known_articles_data: list[dict] = []
        candidate_urls = [a.get("url", "") for a in all_articles_data if a.get("url")]
        if candidate_urls:
            try:
                from sqlalchemy import select
                from app.db.base import get_db_context
                from app.db.models import Article as _ArticleDB
                async with get_db_context() as _db:
                    rows = await _db.execute(
                        select(_ArticleDB.url).where(_ArticleDB.url.in_(candidate_urls))
                    )
                    known_urls: set[str] = {r[0] for r in rows}
                fresh_articles_data = [a for a in all_articles_data if a.get("url") not in known_urls]
                known_articles_data = [a for a in all_articles_data if a.get("url") in known_urls]
                if fresh_articles_data:
                    logger.info(
                        "Collector dedup: %d new, %d already seen (suppressed)",
                        len(fresh_articles_data), len(known_articles_data),
                    )
                else:
                    # Nothing new — fall back to all articles to avoid empty synthesis
                    fresh_articles_data = all_articles_data
                    known_articles_data = []
                    logger.info("Collector dedup: all %d articles already seen, keeping all", len(all_articles_data))
            except Exception as _dedup_exc:
                logger.debug("Inter-session dedup skipped (non-blocking): %s", _dedup_exc)

        # 2. Convert to Article objects for ranking
        from app.core.models import Article as ArticleModel
        articles_to_rank = []
        for a in fresh_articles_data:
            articles_to_rank.append(ArticleModel(
                title=a.get("title", a.get("name", "")),
                summary=a.get("summary", a.get("description", "")),
                url=a.get("url", ""),
                source=a.get("source", "unknown"),
                topic=a.get("topic", ""),
                published_date=a.get("published_date", a.get("date")),
            ))

        # 3. Apply ranking
        from app.services.article_ranker import ArticleRanker
        ranker = ArticleRanker()
        # We rank against the main research brief/task
        ranked_articles = ranker.filter_relevant_articles(
            articles_to_rank, 
            research_brief,
            limit=self._max_articles * 3 # Keep more for corpus than for a single step
        )
        
        logger.info("Collector: ranked %d articles down to %d most relevant", 
                   len(articles_to_rank), len(ranked_articles))

        # 4. Build corpus from ranked articles
        corpus_parts = []
        for a in ranked_articles:
            date_str = f" ({a.published_date})" if a.published_date else ""
            corpus_parts.append(
                f"### {a.title}{date_str}\n"
                f"Source: {a.source} | Topic: {a.topic} | Relevance: {a.relevance_score}\n"
                f"URL: {a.url}\n\n"
                f"{a.summary}"
            )

        corpus = "\n\n".join(corpus_parts)

        # 5. Persistent storage
        await self._persist_articles(all_articles_data)

        # 6. Generate summary/aggregation via LLM
        from app.core.watch_context import WatchContext
        watch_ctx = state.get("watch_context") or WatchContext.default()
        if isinstance(watch_ctx, dict):
            watch_ctx = WatchContext(**watch_ctx)

        client = self._client()
        prompt = COLLECTOR_USER.format(
            task=research_brief,
            step_count=len(state.get("plan", [])),
            results=corpus[:15000], # Safety limit for LLM context
            current_year=watch_ctx.current_year,
            current_month=watch_ctx.month_name,
        )

        try:
            summary = await client.async_generate_completion(
                prompt=prompt,
                system_message="You are the Collector Agent. Aggregate research results into a structured summary.",
                temperature=0.3,
                max_tokens=4000,
            )
            # Store summary in analysis_results as a precursor to final synthesis
            state["analysis_results"] = summary
            state["articles"] = all_articles_data
            logger.info("Collector aggregated research into structured summary")

            # Save checkpoint after research phase
            await self._save_phase(state, "collection", "research_completed")
            
            # Create checkpoint and compact memory before analysis
            await self._create_checkpoint(state, "collection")
            await self._compact_memory(state, "research_completed")

        except Exception as exc:
            logger.error("Collector LLM aggregation failed: %s", exc)
            state["articles"] = all_articles_data
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

    async def _sync_sources_realtime(
        self,
        state: OrchestratorState,
        research_results: list[dict],
    ) -> None:
        """Push current research_results into session_sources immediately.

        Called after each step so sources appear in the frontend
        during the session rather than only at completion.
        """
        if not self._enable_persistence:
            return
        try:
            await self._init_session_manager(state)
            if self._session_manager is None:
                return
            await self._session_manager.sync_sources(research_results)
        except Exception as exc:
            logger.debug("Real-time source sync failed: %s", exc)

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
    ) -> list[Article]:  # noqa: F821
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

        In autonomous mode: auto-approves if quality >= threshold.
        In interactive mode (autonomous=False): pauses the graph when quality
        is below threshold so the user can review research results before synthesis.
        The streaming service detects approval_result="awaiting_approval" and
        emits an `approval_required` SSE event, then saves session state.
        """
        quality_score = state.get("quality_score", 0.0)
        approval_threshold = state.get("approval_threshold", 0.7)
        autonomous = state.get("autonomous", True)

        if quality_score >= approval_threshold:
            logger.info("Auto-approved: quality %.2f >= threshold %.2f", quality_score, approval_threshold)
            state["approval_result"] = "approved"
            state["approval_status"] = "auto_approved"
            state["approved_at"] = datetime.now().isoformat()
        elif autonomous:
            # Autonomous mode: bypass regardless of quality
            logger.warning("Bypassing approval in autonomous mode (quality %.2f < %.2f)",
                           quality_score, approval_threshold)
            state["approval_result"] = "approved"
            state["approval_status"] = "auto_approved_autonomous"
            state["approved_at"] = datetime.now().isoformat()
        else:
            # Interactive mode + low quality: pause for human review
            logger.info("Interactive mode: pausing for human approval (quality %.2f < %.2f)",
                        quality_score, approval_threshold)
            state["approval_result"] = "awaiting_approval"
            state["approval_status"] = "needs_review"
            state["approved_at"] = None

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

        from app.core.watch_context import WatchContext
        watch_ctx = state.get("watch_context") or WatchContext.default()
        if isinstance(watch_ctx, dict):
            watch_ctx = WatchContext(**watch_ctx)

        client = self._client()
        prompt = ANALYZER_USER.format(
            task=task,
            corpus=corpus,
            current_year=watch_ctx.current_year,
            current_month=watch_ctx.month_name,
        )

        try:
            analysis = await client.async_generate_completion(
                prompt=prompt,
                system_message=ANALYZER_SYSTEM.format(
                    current_year=watch_ctx.current_year,
                    current_month=watch_ctx.month_name,
                ),
                temperature=0.4,
                max_tokens=4000,
            )
            state["analysis_results"] = analysis
            logger.info("Analyzer completed")

            # Mark analysis plan step as DONE so the sidebar reflects it
            plan = state.get("plan", [])
            for step in plan:
                if str(step.get("step_type", "")).lower() == "analysis":
                    step["status"] = StepStatus.DONE
                    step["completed_at"] = datetime.now().isoformat()
                    step["result"] = f"Analysis completed ({len(analysis)} chars)"
                    break
            state["plan"] = plan

        except Exception as exc:
            logger.error("Analyzer failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Analyzer error: {exc}"]

        return state

    async def synthesizer(self, state: OrchestratorState, config: Optional[RunnableConfig] = None) -> OrchestratorState:
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

        from app.core.watch_context import WatchContext
        from app.agents.orchestrator.prompts import SYNTHESIZER_SYSTEM
        watch_ctx = state.get("watch_context") or WatchContext.default()
        if isinstance(watch_ctx, dict):
            watch_ctx = WatchContext(**watch_ctx)

        client = self._client()
        prompt = SYNTHESIZER_USER.format(
            task=task,
            corpus=corpus,
            analysis=analysis_text,
            current_year=watch_ctx.current_year,
            current_month=watch_ctx.month_name,
        )
        synthesizer_system = SYNTHESIZER_SYSTEM.format(
            synthesizer_context=watch_ctx.to_synthesizer_block(),
            current_year=watch_ctx.current_year,
            current_month=watch_ctx.month_name,
        )

        try:
            from langchain_core.callbacks import dispatch_custom_event

            report = ""
            logger.info("Synthesizer starting streamed report generation...")

            async for chunk in client.async_stream_completion(
                prompt=prompt,
                system_message=synthesizer_system,
                temperature=0.4,
                max_tokens=4000,
            ):
                report += chunk
                # dispatch_custom_event is synchronous in this langchain_core version
                try:
                    dispatch_custom_event("report_chunk", {"chunk": chunk}, config=config)
                except Exception:
                    pass

            state["final_report"] = report
            state["synthesis_result"] = report[:500] + "..." if len(report) > 500 else report
            state["completed_at"] = datetime.now().isoformat()
            logger.info("Synthesizer completed report (%d chars)", len(report))

            # Mark the synthesis plan step as DONE so the sidebar shows it completed
            plan = state.get("plan", [])
            for step in plan:
                if str(step.get("step_type", "")).lower() == "synthesis":
                    step["status"] = StepStatus.DONE
                    step["completed_at"] = datetime.now().isoformat()
                    step["result"] = f"Report generated ({len(report)} chars)"
                    break
            state["plan"] = plan

            await self._persist_research_session(state, task)
            
            # Save final phase (synthesis completed)
            await self._save_phase(state, "synthesis", "report_generated")
            
            # Final checkpoint
            await self._create_checkpoint(state, "synthesis")

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
            from app.services.session_manager import SessionPhase

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

            await self._init_session_manager(state)
            if self._session_manager is None:
                raise ValueError("Session manager unavailable for final persistence")

            await self._session_manager.finalize_session(
                status="completed",
                plan=state.get("plan", []),
                current_step_index=state.get("current_step_index", 0),
                research_results=research_results,
                analysis_results=state.get("analysis_results", ""),
                final_report=state.get("final_report", ""),
                notes=notes,
                raw_notes=raw_notes,
                completed_at=datetime.now(),
            )
            logger.info("Updated research session %s with %d notes", state.get("session_id"), len(raw_notes))

        except Exception as exc:
            logger.warning("Failed to persist research session: %s", exc)

    async def emailer(self, state: OrchestratorState) -> OrchestratorState:
        """Send the final report via email."""
        report = state.get("final_report", "")

        if not report:
            state["errors"] = state.get("errors", []) + ["No report to send"]
            return state

        from app.delivery.service import ReportDeliveryService
        from app.config.settings import get_settings

        try:
            settings = get_settings()
            subject = self._extract_subject(report)
            delivery = ReportDeliveryService(settings)
            result = delivery.deliver(
                report=report,
                subject=subject,
                send=bool(state.get("send_email", True)),
                recipients=state.get("email_recipients"),
            )

            state["email_sent"] = result.sent
            state["email_result"] = result.message

            if not state.get("send_email", True):
                logger.info("Email delivery skipped by orchestrator request")
            elif not result.configured:
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

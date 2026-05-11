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
    """

    def __init__(
        self,
        llm_client: Optional[ChatCompletionClient] = None,
        max_articles: int = 5,
        min_sources: int = 2,
    ) -> None:
        self._llm_client = llm_client
        self._max_articles = max_articles
        self._min_sources = min_sources
        self._registry = get_global_registry()
        self._deep_research_agent = None

    def _client(self) -> ChatCompletionClient:
        if self._llm_client is None:
            self._llm_client = ChatCompletionClient()
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
        """Generate execution plan from task using LLM."""
        task = state.get("task", "")
        # Get topics from metadata or use task if not provided
        topics = state.get("metadata", {}).get("topics", task)

        client = self._client()
        prompt = PLANNER_USER.format(
            task=task,
            topics=", ".join(topics) if isinstance(topics, list) else topics,
        )

        try:
            logger.info("Generating plan for task: %s", task[:100])
            response = await client.async_generate_completion(
                prompt=prompt,
                system_message="You are a Planning Agent. Create structured execution plans. Use 'deep_research' for complex technical topics.",
                temperature=0.3,
                max_tokens=3000,
            )

            if not response:
                raise ValueError("LLM returned empty response for planner")

            plan_data = _parse_json_safe(response)
            if not isinstance(plan_data, list) or not plan_data:
                logger.warning("Planner returned invalid or empty JSON. Falling back to default deep research plan.")
                plan_data = [
                    {
                        "step_id": "step_1",
                        "name": "Deep Research",
                        "description": f"Conduct deep research on {task}",
                        "step_type": "deep_research",
                        "tool_name": "deep_research"
                    }
                ]

            plan: list[PlanStep] = []
            for i, step in enumerate(plan_data[:10]):
                if not isinstance(step, dict):
                    continue
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
            logger.info("Planner generated %d steps", len(plan))

        except Exception as exc:
            logger.error("Planner failed: %s. Falling back to single deep research step.", exc)
            state["plan"] = [
                PlanStep(
                    step_id="fallback_step",
                    name="Deep Research Fallback",
                    description=f"Direct research on {task}",
                    step_type=StepType.DEEP_RESEARCH,
                    status=StepStatus.PENDING,
                    tool_name="deep_research",
                    params={},
                    result=None,
                    error=None,
                    started_at=None,
                    completed_at=None,
                )
            ]
            state["errors"] = state.get("errors", []) + [f"Planner error: {exc}"]

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
        """Fan-out dispatcher: launch all pending research steps in parallel.

        Uses retry policies with exponential backoff and fallback chains.
        """
        plan = state.get("plan", [])
        pending_indices = [
            i for i, step in enumerate(plan)
            if step.get("status") == StepStatus.PENDING
            and step.get("step_type") in (StepType.RESEARCH, StepType.DEEP_RESEARCH)
        ]

        if not pending_indices:
            return await self.dispatcher(state)

        async def run_step(step: PlanStep, idx: int) -> tuple[int, dict]:
            tool_name = step.get("tool_name") or "search"
            params = step.get("params", {}) or {}
            step_id = step["step_id"]
            return await self._execute_with_retry(step, idx, tool_name, params, state)

        try:
            tasks = [run_step(plan[i], i) for i in pending_indices]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            research_results = state.get("research_results", [])
            updated_plan = plan[:]

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
                else:
                    updated_plan[idx]["status"] = StepStatus.FAILED
                    updated_plan[idx]["error"] = result.get("error", "Unknown error")

            state["plan"] = updated_plan
            state["research_results"] = research_results
            current_max = max(pending_indices) if pending_indices else state.get("current_step_index", 0)
            state["current_step_index"] = current_max + 1
            logger.info("Parallel dispatch completed %d steps", len(pending_indices))

        except Exception as exc:
            logger.error("Parallel dispatcher failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Parallel dispatch failed: {exc}"]

        return state

    async def collector(self, state: OrchestratorState) -> OrchestratorState:
        """Aggregate all research results into a unified corpus."""
        research_results = state.get("research_results", [])
        task = state.get("task", "")

        if not research_results:
            state["errors"] = state.get("errors", []) + ["No research results to collect"]
            return state

        corpus_parts = []
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
        except Exception as exc:
            logger.error("Collector failed: %s", exc)
            state["articles"] = research_results
            state["errors"] = state.get("errors", []) + [f"Collector error: {exc}"]

        return state

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
        """Create the final comprehensive report."""
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
        except Exception as exc:
            logger.error("Synthesizer failed: %s", exc)
            state["errors"] = state.get("errors", []) + [f"Synthesizer error: {exc}"]

        return state

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

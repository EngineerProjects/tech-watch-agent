"""
Orchestrator agent nodes.

Implements the core nodes for the orchestrator LangGraph workflow:
- supervisor: Entry point that delegates to other nodes
- planner: Generates the execution plan
- dispatcher: Executes individual plan steps
- collector: Aggregates results from parallel steps
- validator: Validates quality of collected results
- analyzer: Extracts insights from collected data
- synthesizer: Creates the final report
- emailer: Sends the report via email
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Optional

from app.agents.orchestrator.state import (
    OrchestratorState,
    PlanStep,
    StepStatus,
    StepType,
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
        tool = self._registry.get(tool_name)
        if tool is None:
            for t in self._registry.list_tools_metadata():
                if t.name == tool_name:
                    pass
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
                    step_type=StepType(step.get("step_type", "research")),
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
            # Handle Deep Research step type
            if step_type == StepType.DEEP_RESEARCH:
                logger.info("Executing DEEP RESEARCH for step %s", step_id)
                agent = self._get_deep_research_agent()
                query = step.get("description", params.get("query", state.get("task", "")))
                result = await agent.execute({"query": query, "metadata": {"parent_task_id": state.get("task_id")}})
                
                if result.success:
                    success = True
                    data = {"report": result.output.get("report"), "findings": result.output.get("research_results")}
                    error = None
                else:
                    success = False
                    data = []
                    error = ", ".join(result.errors)
            
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

    async def dispatcher_parallel(self, state: OrchestratorState) -> OrchestratorState:
        """Fan-out dispatcher: launch all pending research steps in parallel."""
        import asyncio

        plan = state.get("plan", [])
        pending_indices = [
            i for i, step in enumerate(plan)
            if step.get("status") == StepStatus.PENDING
            and step.get("step_type") in (StepType.RESEARCH, StepType.DEEP_RESEARCH)
        ]

        if not pending_indices:
            return await self.dispatcher(state)

        async def run_step(step: PlanStep, idx: int) -> tuple[int, dict]:
            tool_name = step.get("tool_name")
            step_type = step.get("step_type")
            params = step.get("params", {}) or {}
            step_id = step["step_id"]

            try:
                # Handle Deep Research step type
                if step_type == StepType.DEEP_RESEARCH:
                    logger.info("Executing DEEP RESEARCH for step %s", step_id)
                    agent = self._get_deep_research_agent()
                    query = step.get("description", params.get("query", state.get("task", "")))
                    result = await agent.execute({"query": query, "metadata": {"parent_task_id": state.get("task_id")}})
                    
                    if result.success:
                        return idx, {
                            "success": True,
                            "data": {"report": result.output.get("report"), "findings": result.output.get("research_results")},
                            "step_id": step_id,
                            "tool": "deep_research_agent",
                        }
                    else:
                        return idx, {"success": False, "error": ", ".join(result.errors), "step_id": step_id, "tool": "deep_research_agent"}

                # Normal tool execution
                if not tool_name:
                    return idx, {"success": False, "error": "No tool specified", "step_id": step_id}

                tool = self._get_tool(tool_name)
                if tool is None:
                    return idx, {"success": False, "error": f"Tool '{tool_name}' not found", "step_id": step_id}

                if hasattr(tool, "execute"):
                    result = await tool.execute(params)
                elif hasattr(tool, "execute_safe"):
                    result = await tool.execute_safe(params)
                else:
                    return idx, {"success": False, "error": "No execute method", "step_id": step_id}

                if isinstance(result, dict):
                    return idx, {
                        "success": result.get("success", False),
                        "data": result.get("data", []),
                        "error": result.get("error"),
                        "step_id": step_id,
                        "tool": tool_name,
                    }
                return idx, {"success": True, "data": result or [], "step_id": step_id, "tool": tool_name}
            except Exception as exc:
                logger.error("Error in run_step for %s: %s", step_id, exc)
                return idx, {"success": False, "error": str(exc), "step_id": step_id, "tool": tool_name if 'tool_name' in locals() else "unknown"}

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
        """Validate that collected results meet quality thresholds."""
        research_results = state.get("research_results", [])
        task = state.get("task", "")

        article_count = sum(
            r.get("count", 0) for r in research_results
            if isinstance(r.get("data"), (list, dict))
        )
        source_count = len(research_results)

        validation_errors = []
        if article_count < 3:
            validation_errors.append(f"Insufficient articles: {article_count} < 3")
        if source_count < 2:
            validation_errors.append(f"Insufficient sources: {source_count} < 2")

        state["validation_errors"] = validation_errors
        state["iteration_count"] = state.get("iteration_count", 0) + 1

        if validation_errors:
            max_iter = state.get("max_iterations", 5)
            iteration = state.get("iteration_count", 0)
            if iteration >= max_iter:
                logger.warning("Max iterations reached (%d/%d), proceeding despite validation errors", iteration, max_iter)
            else:
                logger.info("Validation failed (attempt %d/%d): %s. Will retry.", iteration, max_iter, validation_errors)

        logger.info("Validator: %d articles from %d sources", article_count, source_count)
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

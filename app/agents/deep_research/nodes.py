"""
Node implementations for the deep research agent.

This module contains the node implementations that make up the
deep research workflow. Each node performs a specific function
in the research pipeline.

Nodes:
- Clarify: User clarification requests
- WriteBrief: Transform messages into research brief
- Supervisor: Main research coordinator
- Researcher: Individual research units
- Compress: Research compression/summarization
- FinalReport: Final report generation
"""

import asyncio
from typing import Any, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)

from app.agents.deep_research.config import DeepResearchConfig
from app.agents.deep_research.state import (
    DeepResearchAgentState,
    SupervisorState,
    ResearcherState,
    ResearcherOutputState,
    ClarifyWithUser,
    ResearchQuestion,
    ConductResearch,
    ResearchComplete,
)
from app.agents.deep_research.prompts import (
    CLARIFY_WITH_USER_INSTRUCTIONS,
    TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_PROMPT,
    LEAD_RESEARCHER_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
    COMPRESS_RESEARCH_SYSTEM_PROMPT,
    COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE,
    FINAL_REPORT_GENERATION_PROMPT,
    get_today_str,
)
from app.core.logging import get_logger


logger = get_logger(__name__)


class DeepResearchNodes:
    """Collection of nodes for the deep research agent.

    This class provides the node implementations that can be
    assembled into a LangGraph workflow. Each node handles
    a specific part of the research process.

    Attributes:
        config: Optional configuration for the nodes
    """

    def __init__(
        self,
        config: Optional[DeepResearchConfig] = None,
    ) -> None:
        """Initialize the nodes.

        Args:
            config: Optional configuration
        """
        self.config = config or DeepResearchConfig()
        self._llm_client = None

    @property
    def llm_client(self):
        """Lazy load the LLM client."""
        if self._llm_client is None:
            from app.services.llm import ChatCompletionClient
            self._llm_client = ChatCompletionClient()
        return self._llm_client

    def _generate_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """Generate a completion using the LLM client.

        Args:
            prompt: The user prompt
            system_message: Optional system message
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Generated text
        """
        return self.llm_client.generate_completion(
            prompt=prompt,
            system_message=system_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def clarify_with_user(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Analyze user messages and ask clarifying questions if needed.

        This node checks whether the research request is clear enough
        to proceed, or if clarification is needed from the user.

        Args:
            state: Current agent state
            config: Optional runnable config

        Returns:
            Command dict for routing
        """
        from langgraph.types import Command

        # Check if clarification is enabled
        if not self.config.allow_clarification:
            return Command(goto="write_research_brief")

        messages = state.get("messages", [])
        messages_text = get_buffer_string(messages)

        prompt = CLARIFY_WITH_USER_INSTRUCTIONS.format(
            messages=messages_text,
            date=get_today_str(),
        )

        # Generate clarification analysis
        response_text = self._generate_completion(
            prompt=prompt,
            temperature=0.3,
            max_tokens=500,
        )

        # Parse JSON response (simplified - in production use proper parsing)
        try:
            import json
            response = json.loads(response_text)
            need_clarification = response.get("need_clarification", False)
            question = response.get("question", "")
            verification = response.get("verification", "")
        except (json.JSONDecodeError, AttributeError):
            need_clarification = False
            question = ""
            verification = "Proceeding with research based on provided information."

        if need_clarification:
            return Command(
                goto="__end__",
                update={
                    "messages": [AIMessage(content=question)],
                },
            )
        else:
            return Command(
                goto="write_research_brief",
                update={
                    "messages": [AIMessage(content=verification)],
                },
            )

    async def write_research_brief(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Transform user messages into a structured research brief.

        This node analyzes the user's request and generates a focused
        research brief that will guide the supervisor.

        Args:
            state: Current agent state
            config: Optional runnable config

        Returns:
            Command dict for routing
        """
        from langgraph.types import Command

        messages = state.get("messages", [])
        messages_text = get_buffer_string(messages)

        prompt = TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_PROMPT.format(
            messages=messages_text,
            date=get_today_str(),
        )

        # Generate research brief
        research_brief = self._generate_completion(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000,
        )

        # Create supervisor system prompt
        supervisor_system_prompt = LEAD_RESEARCHER_PROMPT.format(
            date=get_today_str(),
            max_researcher_iterations=self.config.max_researcher_iterations,
            max_concurrent_research_units=self.config.max_concurrent_research_units,
        )

        return Command(
            goto="research_supervisor",
            update={
                "research_brief": research_brief,
                "supervisor_messages": {
                    "type": "override",
                    "value": [
                        SystemMessage(content=supervisor_system_prompt),
                        HumanMessage(content=research_brief),
                    ],
                },
            },
        )

    async def supervisor(
        self,
        state: SupervisorState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Lead research supervisor that plans and delegates research.

        The supervisor analyzes the research brief and decides how to
        break down the research into manageable tasks. It delegates
        to sub-researchers via the ConductResearch tool.

        Args:
            state: Current supervisor state
            config: Optional runnable config

        Returns:
            Command dict for routing
        """
        from langgraph.types import Command

        supervisor_messages = state.get("supervisor_messages", [])

        # Create prompt for supervisor decision-making
        messages_text = "\n".join([
            f"{type(m).__name__}: {m.content if hasattr(m, 'content') else str(m)}"
            for m in supervisor_messages
        ])

        prompt = f"""Based on the research brief and current progress, decide your next action.

Current supervisor messages:
{messages_text}

Research Brief:
{state.get('research_brief', '')}

Consider:
1. Should I delegate more research (ConductResearch)?
2. Have I gathered enough information (ResearchComplete)?
3. Should I think more about my strategy (think_tool)?

Be decisive and efficient. Don't over-research.
"""

        # Generate supervisor response
        response = self._generate_completion(
            prompt=prompt,
            system_message=LEAD_RESEARCHER_PROMPT.format(
                date=get_today_str(),
                max_researcher_iterations=self.config.max_researcher_iterations,
                max_concurrent_research_units=self.config.max_concurrent_research_units,
            ),
            temperature=0.4,
            max_tokens=500,
        )

        # Determine routing based on response
        # (Simplified - in production use tool calling)
        research_iterations = state.get("research_iterations", 0)

        if "research is complete" in response.lower() or "sufficient" in response.lower():
            return Command(
                goto="__end__",
                update={
                    "notes": state.get("notes", []),
                    "raw_notes": state.get("raw_notes", []),
                },
            )

        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=response)],
                "research_iterations": research_iterations + 1,
            },
        )

    async def supervisor_tools(
        self,
        state: SupervisorState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Execute supervisor tools (research delegation, thinking).

        This node handles the execution of supervisor tool calls,
        including delegating to research sub-agents.

        Args:
            state: Current supervisor state
            config: Optional runnable config

        Returns:
            Command dict for routing
        """
        from langgraph.types import Command

        supervisor_messages = state.get("supervisor_messages", [])
        research_iterations = state.get("research_iterations", 0)

        if not supervisor_messages:
            return Command(
                goto="__end__",
                update={"notes": [], "raw_notes": []},
            )

        most_recent = supervisor_messages[-1]
        content = most_recent.content if hasattr(most_recent, "content") else str(most_recent)

        # Check for exit conditions
        if research_iterations >= self.config.max_researcher_iterations:
            return Command(
                goto="__end__",
                update={
                    "notes": state.get("notes", []),
                    "raw_notes": state.get("raw_notes", []),
                },
            )

        # Look for research topics in the response
        # (Simplified - in production use structured tool calls)
        research_topics = self._extract_research_topics(content)

        if research_topics:
            # Execute research in parallel
            research_results = await self._execute_research_units(
                research_topics[:self.config.max_concurrent_research_units],
                state,
            )

            # Update state with research results
            notes = list(state.get("notes", []))
            raw_notes = list(state.get("raw_notes", []))

            for result in research_results:
                if result.get("compressed_research"):
                    notes.append(result["compressed_research"])
                if result.get("raw_notes"):
                    raw_notes.extend(result["raw_notes"])

            return Command(
                goto="supervisor",
                update={
                    "supervisor_messages": [],
                    "notes": notes,
                    "raw_notes": raw_notes,
                },
            )

        # No research topics found, continue supervisor
        return Command(goto="supervisor")

    async def _execute_research_units(
        self,
        topics: list[str],
        parent_state: SupervisorState,
    ) -> list[dict[str, Any]]:
        """Execute research units in parallel.

        Args:
            topics: List of research topics
            parent_state: Parent supervisor state

        Returns:
            List of research results
        """
        tasks = []
        for topic in topics:
            task = self._execute_single_researcher(
                research_topic=topic,
                parent_config=parent_state,
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error("Research unit failed: %s", result)
                processed_results.append({"compressed_research": "", "raw_notes": []})
            else:
                processed_results.append(result)

        return processed_results

    async def _execute_single_researcher(
        self,
        research_topic: str,
        parent_config: dict,
    ) -> dict[str, Any]:
        """Execute a single research unit.

        Args:
            research_topic: The topic to research
            parent_config: Configuration from parent

        Returns:
            Research results dict
        """
        researcher_state: ResearcherState = {
            "research_topic": research_topic,
            "researcher_messages": [HumanMessage(content=research_topic)],
            "compressed_research": "",
            "tool_call_iterations": 0,
            "raw_notes": [],
        }

        # Run researcher loop
        for iteration in range(min(5, self.config.max_react_tool_calls)):
            # Generate next action
            messages_text = get_buffer_string(researcher_state["researcher_messages"])
            prompt = f"""Research topic: {research_topic}

Current progress:
{messages_text}

What should I search for next? Provide a specific search query or indicate research is complete."""

            response = self._generate_completion(
                prompt=prompt,
                system_message=RESEARCH_SYSTEM_PROMPT.format(
                    date=get_today_str(),
                    mcp_prompt=self.config.mcp_prompt or "",
                ),
                temperature=0.4,
                max_tokens=2000,
            )

            researcher_state["researcher_messages"].append(AIMessage(content=response))

            # Check if research should end
            if "complete" in response.lower() or len(response) < 100:
                break

        # Compress research results
        compressed = self._compress_research(researcher_state)

        return {
            "compressed_research": compressed,
            "raw_notes": [get_buffer_string(researcher_state["researcher_messages"])],
        }

    def _compress_research(self, researcher_state: ResearcherState) -> str:
        """Compress research findings into a summary.

        Args:
            researcher_state: The researcher state

        Returns:
            Compressed research summary
        """
        messages = researcher_state.get("researcher_messages", [])
        messages_text = get_buffer_string(messages)

        prompt = f"""{COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE}

Research topic: {researcher_state.get('research_topic', '')}

Messages to compress:
{messages_text}
"""

        return self._generate_completion(
            prompt=prompt,
            system_message=COMPRESS_RESEARCH_SYSTEM_PROMPT.format(date=get_today_str()),
            temperature=0.3,
            max_tokens=4000,
        )

    def _extract_research_topics(self, content: str) -> list[str]:
        """Extract research topics from content.

        Args:
            content: Text content to analyze

        Returns:
            List of research topics
        """
        topics = []

        # Simple extraction - look for topic indicators
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:
                # Remove common prefixes
                for prefix in ["- ", "* ", "1. ", "2. ", "3. ", "Topic: ", "Research: "]:
                    if line.startswith(prefix):
                        line = line[len(prefix):]
                if line:
                    topics.append(line)

        return topics[:3]  # Limit to 3 topics

    async def final_report_generation(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Generate the final research report.

        This node takes all collected research and synthesizes it
        into a comprehensive final report.

        Args:
            state: Current agent state
            config: Optional runnable config

        Returns:
            Update dict for final state
        """
        research_brief = state.get("research_brief", "")
        notes = state.get("notes", [])
        messages = state.get("messages", [])
        messages_text = get_buffer_string(messages)
        findings = "\n\n".join(notes) if notes else "No findings collected."

        prompt = FINAL_REPORT_GENERATION_PROMPT.format(
            research_brief=research_brief,
            messages=messages_text,
            findings=findings,
            date=get_today_str(),
        )

        final_report = self._generate_completion(
            prompt=prompt,
            temperature=0.4,
            max_tokens=self.config.final_report_model_max_tokens,
        )

        return {
            "final_report": final_report,
            "messages": [AIMessage(content=final_report)],
        }


# Factory function for creating nodes
def create_nodes(config: Optional[DeepResearchConfig] = None) -> DeepResearchNodes:
    """Create a DeepResearchNodes instance.

    Args:
        config: Optional configuration

    Returns:
        DeepResearchNodes instance
    """
    return DeepResearchNodes(config=config)
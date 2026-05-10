"""
Deep research agent implementation.

This module provides the DeepResearchAgent class that extends BaseAgent
to conduct thorough research on complex topics. It uses a multi-agent
architecture with supervisor-researcher pattern for parallel research.

The agent follows this pipeline:
1. User clarification (optional)
2. Research brief generation
3. Supervisor-led research delegation
4. Parallel researcher execution
5. Research compression/summarization
6. Final report generation
"""

from datetime import datetime
from typing import Any, Optional
import uuid

from langchain_core.messages import HumanMessage

from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult
from app.agents.deep_research.config import DeepResearchConfig
from app.agents.deep_research.graph import DeepResearchWorkflow
from app.agents.deep_research.nodes import DeepResearchNodes
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class DeepResearchAgent(BaseAgent):
    """Agent for conducting deep research on complex topics.

    This agent uses a multi-agent architecture to conduct thorough
    research by:
    - Breaking down complex topics into sub-topics
    - Delegating research to parallel sub-agents
    - Compressing and synthesizing findings
    - Generating comprehensive final reports

    Attributes:
        workflow: The LangGraph workflow for research
        nodes: The agent nodes for each pipeline stage
    """

    def __init__(
        self,
        config: Optional[DeepResearchConfig] = None,
        settings: Optional[Settings] = None,
        workflow: Optional[DeepResearchWorkflow] = None,
        nodes: Optional[DeepResearchNodes] = None,
        checkpointer=None,
    ) -> None:
        """Initialize the deep research agent.

        Args:
            config: Agent configuration
            settings: Application settings
            workflow: Optional pre-configured workflow (for testing)
            nodes: Optional pre-configured nodes (for testing)
        """
        # Use default config if not provided
        if config is None:
            config = DeepResearchConfig()

        super().__init__(config=config, settings=settings)

        self._workflow = workflow
        self._nodes = nodes
        self._checkpointer = checkpointer

    async def setup(self) -> None:
        """Set up agent resources.

        Initializes the workflow and any required services.
        """
        logger.info("Setting up deep research agent")

        # Create nodes if not provided
        if self._nodes is None:
            self._nodes = DeepResearchNodes(config=self.config)

        if self._workflow is None:
            self._workflow = DeepResearchWorkflow(
                config=self.config,
                nodes=self._nodes,
                checkpointer=self._checkpointer,
            )

        logger.info("Deep research agent setup complete")

    async def execute(self, input_data: Any) -> AgentResult:
        """Execute deep research on the given topic.

        This method orchestrates the full research pipeline:
        1. Process user input
        2. Run the research workflow
        3. Return the generated report

        Args:
            input_data: Can be a string (research query) or dict with:
                - query: The research question/topic
                - messages: Optional list of conversation messages
                - research_brief: Optional pre-defined brief

        Returns:
            AgentResult containing the generated report
        """
        import asyncio

        # Ensure setup is done
        if self._workflow is None or self._nodes is None:
            await self.setup()

        # Extract input components
        if isinstance(input_data, str):
            query = input_data
            messages = [HumanMessage(content=query)]
            research_brief = None
        elif isinstance(input_data, dict):
            query = input_data.get("query", "")
            messages = input_data.get("messages", [HumanMessage(content=query)])
            research_brief = input_data.get("research_brief")
        else:
            return AgentResult.create_error(
                errors=["Invalid input format. Expected string or dict with 'query' key."],
            )

        if not query and not research_brief:
            return AgentResult.create_error(
                errors=["No research query provided"],
            )

        import asyncio

        logger.info("Starting deep research for query: %s", query[:100])

        try:
            # Run the workflow asynchronously
            result = await self._workflow.graph.ainvoke(
                {
                    "messages": messages,
                    "supervisor_messages": [],
                    "research_brief": research_brief or "",
                    "notes": [],
                    "raw_notes": [],
                    "final_report": "",
                    "metadata": {},
                    "errors": [],
                },
                config={
                    "recursion_limit": 50,
                    "configurable": {
                        "research_model": self.config.research_model,
                        "compression_model": self.config.compression_model,
                        "final_report_model": self.config.final_report_model,
                        "max_researcher_iterations": self.config.max_researcher_iterations,
                        "max_react_tool_calls": self.config.max_react_tool_calls,
                        "max_concurrent_research_units": self.config.max_concurrent_research_units,
                        "allow_clarification": self.config.allow_clarification,
                        "research_depth": self.config.research_depth,
                    }
                },
            )

            # Extract the final report
            final_report = result.get("final_report", "").strip()
            research_brief_out = result.get("research_brief", "")
            notes = result.get("notes", [])
            errors = result.get("errors", [])

            if errors:
                logger.warning("Deep research completed with errors: %s", errors)

            # Generate metadata
            metadata = {
                "query": query[:200],
                "research_brief_length": len(research_brief_out),
                "notes_count": len(notes),
                "final_report_length": len(final_report),
                "iterations": result.get("metadata", {}).get("iterations", 0),
            }

            if not final_report:
                return AgentResult.create_error(
                    errors=["Research workflow returned empty report"],
                    metadata=metadata,
                )

            return AgentResult.create_success(
                output={
                    "report": final_report,
                    "research_brief": research_brief_out,
                    "notes": notes,
                    "workflow_result": result,
                },
                metadata=metadata,
            )

        except Exception as exc:
            logger.error("Deep research failed: %s", exc)
            return AgentResult.create_error(
                errors=[str(exc)],
                metadata={"query": query[:200]},
            )

    def get_supported_depths(self) -> list[str]:
        """Get supported research depth levels.

        Returns:
            List of supported depth strings
        """
        return ["shallow", "medium", "deep"]

    def get_default_config(self) -> DeepResearchConfig:
        """Get the default configuration for this agent.

        Returns:
            DeepResearchConfig with default values
        """
        return DeepResearchConfig(
            name="deep_research",
            research_model=self.settings.llm_model,
            max_researcher_iterations=5,
            max_concurrent_research_units=3,
            allow_clarification=True,
            research_depth="medium",
        )


# Factory function for creating the agent
def create_deep_research_agent(
    config: Optional[DeepResearchConfig] = None,
    settings: Optional[Settings] = None,
    checkpointer=None,
) -> DeepResearchAgent:
    """Factory function to create a configured deep research agent.

    Args:
        config: Optional configuration
        settings: Optional settings (uses defaults if not provided)

    Returns:
        Configured DeepResearchAgent instance
    """
    if settings is None:
        settings = get_settings()

    if config is None:
        config = DeepResearchConfig(
            name="deep_research",
            research_model=settings.llm_model,
        )

    return DeepResearchAgent(config=config, settings=settings, checkpointer=checkpointer)
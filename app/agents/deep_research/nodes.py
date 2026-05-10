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

from pydantic import BaseModel, Field
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
        tavily_tool: Optional[Any] = None,
    ) -> None:
        """Initialize the nodes.

        Args:
            config: Optional configuration
            tavily_tool: Optional TavilySearchTool instance for web research
        """
        self.config = config or DeepResearchConfig()
        self._llm_client = None
        self._tavily_tool = tavily_tool
        self._think_tool = None
        self._content_extractor = None
        self._web_search_tool = None

    @property
    def llm_client(self):
        """Lazy load the LLM client."""
        if self._llm_client is None:
            from app.services.llm import ChatCompletionClient
            self._llm_client = ChatCompletionClient()
        return self._llm_client

    def _get_tavily_tool(self) -> Any:
        """Lazy load Tavily search tool."""
        if self._tavily_tool is None:
            from app.tools.web.tavily import TavilySearchToolFactory
            self._tavily_tool = TavilySearchToolFactory.from_settings()
        return self._tavily_tool

    def _get_think_tool(self) -> Any:
        """Lazy load ThinkTool."""
        if self._think_tool is None:
            from app.tools.web.think import ThinkTool
            self._think_tool = ThinkTool()
        return self._think_tool

    def _get_content_extractor(self) -> Any:
        """Lazy load ContentExtractorTool."""
        if self._content_extractor is None:
            from app.tools.web.extractor import ContentExtractorFactory
            self._content_extractor = ContentExtractorFactory.from_settings()
        return self._content_extractor

    def _get_web_search_tool(self) -> Any:
        """Lazy load web search tool (DuckDuckGo fallback)."""
        if self._web_search_tool is None:
            from app.tools.web.search import NewsSearchService
            self._web_search_tool = NewsSearchService()
        return self._web_search_tool

    async def _search_with_fallback(self, query: str) -> dict[str, Any]:
        """Execute search with multi-tool fallback chain.

        Tries tools in order:
        1. Tavily (best quality, requires API key)
        2. Web search (DuckDuckGo, free fallback)

        Args:
            query: Search query

        Returns:
            Search results dict with 'results' and 'answer' keys
        """
        # Try Tavily first
        tavily = self._get_tavily_tool()
        if tavily._api_key:
            try:
                result = await tavily.execute({"query": query})
                if result.get("success"):
                    return result.get("data", {})
            except Exception as exc:
                logger.debug("Tavily search failed: %s", exc)

        # Fallback to web search
        web_search = self._get_web_search_tool()
        try:
            urls = await web_search.search_news_urls(query)
            return {
                "results": [{"title": "News article", "url": url, "content": ""} for url in urls],
                "answer": f"Found {len(urls)} news articles for: {query}",
            }
        except Exception as exc:
            logger.debug("Web search failed: %s", exc)

        return {"results": [], "answer": ""}

    async def _extract_content_parallel(self, urls: list[dict]) -> list[dict]:
        """Extract content from multiple URLs in parallel.

        Args:
            urls: List of URL dicts with 'url', 'title' keys

        Returns:
            List of extracted content dicts
        """
        if not urls:
            return []

        extractor = self._get_content_extractor()

        async def extract_single(source: dict) -> dict:
            url = source.get("url", "")
            if not url:
                return {}
            try:
                result = await extractor.execute({
                    "url": url,
                    "strategy": "markdown",
                    "output_format": "markdown",
                })
                if result.get("success"):
                    return {
                        "type": "extracted_content",
                        "url": url,
                        "title": source.get("title", ""),
                        "content": result.get("data", {}).get("content", ""),
                        "tool_used": result.get("metadata", {}).get("tool_used", "unknown"),
                    }
            except Exception as exc:
                logger.debug("Content extraction failed for %s: %s", url, exc)
            return {}

        tasks = [extract_single(u) for u in urls[:5]]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if isinstance(r, dict) and r.get("content")]

    async def _extract_content(self, url: str) -> Optional[str]:
        """Extract clean content from a URL using content_extractor with fallback."""
        try:
            extractor = self._get_content_extractor()
            result = await extractor.execute({
                "url": url,
                "strategy": "markdown",
                "output_format": "markdown",
            })
            if result.get("success"):
                return result.get("data", {}).get("content", "")
        except Exception as exc:
            logger.warning("Content extraction failed for %s: %s", url, exc)
        return None

    async def _generate_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        response_model: Optional[Any] = None,
    ) -> Any:
        """Generate a completion using the LLM client.

        Args:
            prompt: The user prompt
            system_message: Optional system message
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            response_model: Optional Pydantic model for structured output

        Returns:
            Generated text or Pydantic model instance
        """
        return await self.llm_client.async_generate_completion(
            prompt=prompt,
            system_message=system_message,
            temperature=temperature,
            max_tokens=max_tokens,
            response_model=response_model,
        )

    async def clarify_with_user(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Analyze user messages and ask clarifying questions if needed."""
        from langgraph.types import Command

        if not self.config.allow_clarification:
            return Command(goto="write_research_brief")

        messages = state.get("messages", [])
        messages_text = get_buffer_string(messages)

        prompt = CLARIFY_WITH_USER_INSTRUCTIONS.format(
            messages=messages_text,
            date=get_today_str(),
        )

        # Generate structured clarification analysis
        response: ClarifyWithUser = await self._generate_completion(
            prompt=prompt,
            temperature=0.2,
            max_tokens=1000,
            response_model=ClarifyWithUser,
        )

        if not response:
            logger.warning("Failed to get structured clarification response. Proceeding.")
            return Command(goto="write_research_brief")

        if response.need_clarification:
            return Command(
                goto="__end__",
                update={"messages": [AIMessage(content=response.question)]},
            )
        else:
            return Command(
                goto="write_research_brief",
                update={"messages": [AIMessage(content=response.verification)]},
            )

    async def write_research_brief(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Transform user messages into a structured research brief."""
        from langgraph.types import Command

        messages = state.get("messages", [])
        messages_text = get_buffer_string(messages)

        prompt = TRANSFORM_MESSAGES_INTO_RESEARCH_TOPIC_PROMPT.format(
            messages=messages_text,
            date=get_today_str(),
        )

        # Generate structured research brief
        response: ResearchQuestion = await self._generate_completion(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500,
            response_model=ResearchQuestion,
        )

        research_brief = response.research_brief if response else messages_text

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
        """Lead research supervisor that plans and delegates research."""
        from langgraph.types import Command

        research_iterations = state.get("research_iterations", 0)
        
        # Check iteration limit early
        if research_iterations >= self.config.max_researcher_iterations:
            logger.info("Max research iterations reached (%d). Stopping.", research_iterations)
            return Command(goto="__end__")

        supervisor_messages = state.get("supervisor_messages", [])
        messages_text = "\n".join([
            f"{type(m).__name__}: {m.content if hasattr(m, 'content') else str(m)}"
            for m in supervisor_messages
        ])

        prompt = f"""Based on the research brief and current progress, decide your next action.

Research Brief:
{state.get('research_brief', '')}

Current Progress Summary:
{messages_text[-4000:] if len(messages_text) > 4000 else messages_text}

You MUST decide to either:
1. Conduct more research on specific sub-topics (ConductResearch).
2. Conclude that research is complete (ResearchComplete).

Be decisive and efficient."""

        # Use a union-like logic by trying to get one of the two models
        # For simplicity in this implementation, we'll use a combined prompt or tool-like behavior
        # Here we'll try to get ConductResearch or ResearchComplete
        # A better way in LangGraph is to use bind_tools, but we are simulating it with response_model
        
        class SupervisorDecision(BaseModel):
            action: str = Field(description="Action to take: 'research' or 'complete'")
            topics: list[str] = Field(default_factory=list, description="Sub-topics for 'research' action. Max 3.")
            reason: str = Field(description="Reason for this decision")

        decision: SupervisorDecision = await self._generate_completion(
            prompt=prompt,
            system_message=LEAD_RESEARCHER_PROMPT.format(
                date=get_today_str(),
                max_researcher_iterations=self.config.max_researcher_iterations,
                max_concurrent_research_units=self.config.max_concurrent_research_units,
            ),
            temperature=0.4,
            max_tokens=800,
            response_model=SupervisorDecision,
        )

        if not decision:
            logger.warning("Supervisor failed to make a structured decision. Stopping.")
            return Command(goto="__end__")

        if decision.action == "complete" or not decision.topics:
            return Command(goto="__end__")

        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=f"Decision: {decision.action}. Reason: {decision.reason}")],
                "research_iterations": research_iterations + 1,
                "metadata": {"next_topics": decision.topics} # Temporary storage for tools node
            },
        )

    async def supervisor_tools(
        self,
        state: SupervisorState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Execute supervisor tools (research delegation)."""
        from langgraph.types import Command

        research_topics = state.get("metadata", {}).get("next_topics", [])

        if research_topics:
            logger.info("Supervisor delegating research on: %s", research_topics)
            research_results = await self._execute_research_units(
                research_topics[:self.config.max_concurrent_research_units],
                state,
            )

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
                    "supervisor_messages": [AIMessage(content=f"Completed research on: {', '.join(research_topics)}")],
                    "notes": notes,
                    "raw_notes": raw_notes,
                    "metadata": {"next_topics": []} # Clear temporary storage
                },
            )

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

        # Run researcher loop with real Tavily search
        for iteration in range(min(5, self.config.max_react_tool_calls)):
            messages_text = get_buffer_string(researcher_state["researcher_messages"])

            # LLM decides what to search next
            response = await self._generate_completion(
                prompt=f"""Research topic: {research_topic}

Current conversation:
{messages_text}

Based on the research topic and current conversation, decide what to search for next.
If you need more information, provide a specific search query.
If you have enough information, say "RESEARCH_COMPLETE".

Return exactly one of:
- A search query (1-2 sentences, specific)
- "RESEARCH_COMPLETE" if you have enough information

Keep search queries focused and specific for best results.""",
                system_message="You are a research assistant. Generate specific search queries.",
                temperature=0.3,
                max_tokens=500,
            )

            if "RESEARCH_COMPLETE" in response.strip().upper()[:20]:
                break

            # Execute search with fallback chain (Tavily → web_search)
            search_result = await self._search_with_fallback(response.strip())

            results_list = search_result.get("results", [])
            answer = search_result.get("answer", "")

            if results_list or answer:
                search_summary = f"Search: {response.strip()}\n\n"
                if answer:
                    search_summary += f"AI Answer: {answer}\n\n"
                if results_list:
                    for r in results_list[:3]:
                        search_summary += f"- [{r.get('title', '')}]({r.get('url', '')}): {r.get('content', '')[:200]}...\n"

                researcher_state["raw_notes"].append({
                    "query": response.strip(),
                    "answer": answer,
                    "sources": [{"title": r.get("title"), "url": r.get("url")} for r in results_list[:5]],
                })

                # Extract detailed content from top URLs IN PARALLEL
                extracted_results = await self._extract_content_parallel(results_list[:3])

                for extracted in extracted_results:
                    researcher_state["raw_notes"].append(extracted)
                    content_preview = extracted.get("content", "")[:2000]
                    tool_used = extracted.get("tool_used", "unknown")
                    researcher_state["researcher_messages"].append(
                        AIMessage(content=f"[Content extracted via {tool_used}]\n{content_preview}...")
                    )

                researcher_state["researcher_messages"].append(
                    AIMessage(content=f"[Search Results]\n{search_summary}")
                )
                researcher_state["tool_call_iterations"] += 1
            else:
                researcher_state["researcher_messages"].append(
                    AIMessage(content=f"[Search Error] No results found for: {response.strip()}")
                )

            # Use think_tool to reflect on progress and decide next action
            think_tool = self._get_think_tool()
            messages_text = get_buffer_string(researcher_state["researcher_messages"])
            think_result = await think_tool.execute({
                "input": f"Research topic: {research_topic}\n\nMy current research:\n{messages_text}\n\nI've done {researcher_state['tool_call_iterations']} search(es). Should I search more or stop?",
                "depth": "standard",
            })

            if think_result.get("success") and think_result.get("data"):
                reflection = think_result["data"]
                confidence = reflection.get("confidence", "medium")
                recommended = reflection.get("recommended_action", "")

                researcher_state["researcher_messages"].append(
                    AIMessage(content=f"[Think Reflection] Confidence: {confidence}. {recommended}")
                )

                # Stop if confidence is high or recommended action says to stop
                if confidence == "high" or "stop" in recommended.lower()[:50]:
                    break
            elif iteration == min(5, self.config.max_react_tool_calls) - 1:
                # Force stop at max iterations
                break

        # Compress research results
        compressed = await self._compress_research(researcher_state)

        return {
            "compressed_research": compressed,
            "raw_notes": [get_buffer_string(researcher_state["researcher_messages"])],
        }

    async def _compress_research(self, researcher_state: ResearcherState) -> str:
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

        return await self._generate_completion(
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

        final_report = await self._generate_completion(
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
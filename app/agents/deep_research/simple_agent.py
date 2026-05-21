"""
Simplified deep research agent that works reliably.

This is a fallback implementation that uses a simpler flow without
the complex subgraph pattern that has state propagation issues.
"""

from typing import Any, Optional
from datetime import datetime
from app.agents.base.base_agent import BaseAgent, AgentConfig, AgentResult
from app.agents.deep_research.config import DeepResearchConfig
from app.agents.deep_research.nodes import DeepResearchNodes
from app.config.settings import Settings, get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class SimpleDeepResearchAgent(BaseAgent):
    """Simplified deep research using direct tool execution."""

    def __init__(
        self,
        config: Optional[DeepResearchConfig] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        if config is None:
            config = DeepResearchConfig()
        super().__init__(config=config, settings=settings)
        self._nodes = None

    async def setup(self) -> None:
        logger.info("Setting up simplified deep research agent")
        self._nodes = DeepResearchNodes(config=self.config)

    async def execute(self, input_data: Any) -> AgentResult:
        if self._nodes is None:
            await self.setup()

        query = ""
        if isinstance(input_data, str):
            query = input_data
        elif isinstance(input_data, dict):
            query = input_data.get("query", "")

        if not query:
            return AgentResult.create_error(errors=["No query provided"])

        try:
            # Use the search tool to find information
            search_tool = self._nodes._get_web_search_tool()
            urls = await search_tool.search_news_urls(query)
            
            if not urls:
                return AgentResult.create_error(errors=["No URLs found"])

            # Get content from URLs
            results = [{"url": url, "title": url.split("/")[-1]} for url in urls[:10]]
            
            if not results:
                return AgentResult.create_error(errors=["No results found"])

            # Extract content from top results
            extracted = []
            for item in results[:3]:
                url = item.get("url", "")
                if url:
                    content = await self._nodes._extract_content(url)
                    if content:
                        extracted.append({
                            "url": url,
                            "title": item.get("title", ""),
                            "content": content[:2000],
                        })

            # Generate summary using LLM
            llm_client = self._nodes.llm_client
            findings_text = "\n".join(
                f"## {e.get('title', 'Untitled')}\n{e.get('content', '')[:500]}"
                for e in extracted[:3]
            )
            summary_prompt = f"""Research topic: {query}

Provide a comprehensive research summary based on these findings:
{findings_text}

Write a well-structured research report with:
- Executive Summary
- Key Findings
- Implications
- Sources
"""
            report = await llm_client.async_generate_completion(
                prompt=summary_prompt,
                system_message="You are a research analyst. Write comprehensive reports.",
                temperature=0.4,
                max_tokens=4000,
            )

            return AgentResult.create_success(
                output={
                    "report": report,
                    "findings": extracted,
                    "query": query,
                },
                metadata={
                    "query": query[:200],
                    "results_count": len(results),
                    "extracted_count": len(extracted),
                },
            )

        except Exception as exc:
            logger.error("Simple deep research failed: %s", exc)
            return AgentResult.create_error(errors=[str(exc)])


def create_simple_deep_research_agent(
    config: Optional[DeepResearchConfig] = None,
    settings: Optional[Settings] = None,
) -> SimpleDeepResearchAgent:
    """Factory for simplified deep research agent."""
    if settings is None:
        settings = get_settings()
    if config is None:
        config = DeepResearchConfig(name="simple_deep_research")
    return SimpleDeepResearchAgent(config=config, settings=settings)
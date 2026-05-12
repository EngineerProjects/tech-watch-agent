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


class Summary(BaseModel):
    """Structured summary of a webpage."""
    summary: str = Field(description="Comprehensive summary of the webpage content")
    key_excerpts: str = Field(description="Key quotes or data points found on the page")


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
        self._scholar_tool = None
        self._research_paper_tool = None
        self._github_tool = None
        self._arxiv_tool = None
        self._openalex_tool = None
        self._pdf_downloader = None

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

    def _get_scholar_tool(self) -> Any:
        """Lazy load Google Scholar tool."""
        if self._scholar_tool is None:
            from app.tools.web.scholar import GoogleScholarTool
            self._scholar_tool = GoogleScholarTool()
        return self._scholar_tool

    def _get_research_paper_tool(self) -> Any:
        """Lazy load research paper tool."""
        if self._research_paper_tool is None:
            from app.tools.social.research_paper import ResearchPaperTool
            self._research_paper_tool = ResearchPaperTool()
        return self._research_paper_tool

    def _get_github_tool(self) -> Any:
        """Lazy load GitHub tool."""
        if self._github_tool is None:
            from app.tools.social.github import GitHubTool
            self._github_tool = GitHubTool()
        return self._github_tool

    def _get_arxiv_tool(self) -> Any:
        """Lazy load ArXiv tool."""
        if self._arxiv_tool is None:
            from app.tools.social.arxiv import ArXivTool
            self._arxiv_tool = ArXivTool()
        return self._arxiv_tool

    def _get_openalex_tool(self) -> Any:
        """Lazy load OpenAlex tool."""
        if self._openalex_tool is None:
            from app.tools.web.openalex import OpenAlexTool
            self._openalex_tool = OpenAlexTool()
        return self._openalex_tool

    def _get_pdf_downloader(self) -> Any:
        """Lazy load PDF downloader tool."""
        if self._pdf_downloader is None:
            from app.tools.web.pdf_downloader import PDFDownloaderTool, ArXivPDFTool
            self._pdf_downloader = PDFDownloaderTool()
            self._arxiv_pdf_tool = ArXivPDFTool()
        return self._pdf_downloader

    async def _search_with_fallback(self, query: str) -> dict[str, Any]:
        """Execute search with multi-tool fallback chain.

        For academic results (ArXiv, OpenAlex), also extracts full PDF content.
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

        # Try Google Scholar for potentially academic topics
        scholar = self._get_scholar_tool()
        if scholar._api_key:
            try:
                result = await scholar.execute({"query": query, "limit": 5})
                if result.get("success"):
                    return result.get("data", {})
            except Exception as exc:
                logger.debug("Scholar search failed: %s", exc)
        else:
            # Fallback to OpenAlex (Free & Open Source)
            openalex = self._get_openalex_tool()
            try:
                result = await openalex.execute({"query": query, "limit": 5})
                if result.get("success"):
                    data = result.get("data", {})
                    papers = data.get("results", [])
                    # Extract PDF content for each paper
                    for paper in papers:
                        pdf_url = paper.get("pdf_url")
                        if pdf_url:
                            pdf_text = await self._extract_pdf_content(pdf_url)
                            if pdf_text:
                                paper["content"] = pdf_text[:8000]
                    formatted_results = [
                        {
                            "title": p.get("title"),
                            "url": p.get("url"),
                            "content": p.get("content", f"Authors: {', '.join(p.get('authors', []))}. Year: {p.get('year')}. Cited by: {p.get('cited_by')}"),
                        }
                        for p in papers
                    ]
                    return {"results": formatted_results}
            except Exception as exc:
                logger.debug("OpenAlex search failed: %s", exc)

        # Try ArXiv for academic preprints
        arxiv = self._get_arxiv_tool()
        try:
            result = await arxiv.execute({"action": "search", "query": query, "limit": 5})
            if result.get("success"):
                papers = result.get("data", [])
                # For ArXiv, download and extract PDF text for top results
                for paper in papers:
                    paper_url = paper.get("url", "")
                    if "arxiv.org/abs/" in paper_url or paper_url.startswith("http"):
                        pdf_url = self._arxiv_to_pdf_url(paper_url)
                        if pdf_url:
                            pdf_text = await self._extract_pdf_content(pdf_url)
                            if pdf_text:
                                paper["content"] = pdf_text[:8000]
                            else:
                                paper["content"] = paper.get("abstract", "")
                        else:
                            paper["content"] = paper.get("abstract", "")
                    else:
                        paper["content"] = paper.get("abstract", "")

                formatted_results = [
                    {"title": p.get("title"), "url": p.get("url"), "content": p.get("content")}
                    for p in papers
                ]
                return {"results": formatted_results}
        except Exception as exc:
            logger.debug("ArXiv search failed: %s", exc)

        # Try GitHub for technical/code queries
        if any(term in query.lower() for term in ["repo", "github", "code", "library", "framework", "implementation"]):
            github = self._get_github_tool()
            try:
                result = await github.execute({"action": "search_repos", "query": query, "limit": 5})
                if result.get("success"):
                    repos = result.get("data", [])
                    formatted_results = [
                        {"title": f"GitHub: {r.get('name')}", "url": r.get("url"), "content": r.get("description")}
                        for r in repos
                    ]
                    return {"results": formatted_results}
            except Exception as exc:
                logger.debug("GitHub search failed: %s", exc)

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

    @staticmethod
    def _arxiv_to_pdf_url(url: str) -> str:
        """Convert ArXiv abstract URL to PDF URL."""
        match = re.search(r"arxiv\.org/abs/([0-9.]+(?:v\d+)?)", url)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
        return ""

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
        """Extract clean content from a URL using content_extractor, PDF downloader, or research_paper tool."""
        if not url:
            return None

        # If it's a PDF, use the PDF downloader tool
        if url.lower().endswith(".pdf") or "arxiv.org/pdf" in url.lower():
            return await self._extract_pdf_content(url)

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

    async def _extract_pdf_content(self, url: str) -> Optional[str]:
        """Extract text content from a PDF URL.

        Uses the PDF downloader tool to download and parse the PDF,
        extracting text for research analysis.

        Args:
            url: PDF URL (ArXiv, direct PDF, etc.)

        Returns:
            Extracted text content or None on failure
        """
        try:
            pdf_tool = self._get_pdf_downloader()
            result = await pdf_tool.execute({
                "url": url,
                "max_pages": 30,
                "extract_metadata": True,
                "source": self._detect_pdf_source(url),
            })

            if result.get("success"):
                data = result.get("data", {})
                text = data.get("text", "")
                metadata = {
                    "title": data.get("title", ""),
                    "author": data.get("author", ""),
                    "total_pages": data.get("total_pages", 0),
                    "pages_extracted": data.get("pages_extracted", 0),
                    "arxiv_id": data.get("arxiv_id", ""),
                }

                header = f"[PDF Document] {metadata.get('title', url)}\n"
                if metadata.get("author"):
                    header += f"Author: {metadata['author']}\n"
                if metadata.get("total_pages"):
                    header += f"Pages: {metadata['pages_extracted']}/{metadata['total_pages']}\n"
                header += f"Source: {url}\n\n"

                sections = self._extract_pdf_sections(text)
                if sections:
                    header += f"Sections: {', '.join(sections.keys())}\n\n"
                    for section_name, section_text in sections.items():
                        header += f"--- {section_name.upper()} ---\n{section_text[:500]}\n\n"

                return header + f"[Content]\n{text[:10000]}"

            logger.warning("PDF extraction failed for %s: %s", url, result.get("error"))
        except Exception as exc:
            logger.warning("PDF extraction error for %s: %s", url, exc)
        return None

    @staticmethod
    def _detect_pdf_source(url: str) -> str:
        """Detect the source of a PDF URL."""
        if "arxiv.org" in url:
            return "arxiv"
        elif "semantic" in url:
            return "semantic_scholar"
        elif "openalex" in url:
            return "openalex"
        return "direct"

    @staticmethod
    def _extract_pdf_sections(text: str) -> dict[str, str]:
        """Extract key sections from PDF text.

        Args:
            text: Full PDF text

        Returns:
            Dict of section_name -> section_text (first 500 chars)
        """
        sections = {}
        patterns = [
            (r"(?i)\bAbstract\b", "abstract"),
            (r"(?i)^\s*1\.?\s*Introduction\b", "introduction"),
            (r"(?i)^\s*2\.?\s*Background\b", "background"),
            (r"(?i)^\s*3\.?\s*Related Work\b", "related_work"),
            (r"(?i)^\s*4\.?\s*Method\b", "methodology"),
            (r"(?i)^\s*5\.?\s*Experiment", "experiments"),
            (r"(?i)^\s*6\.?\s*Results?\b", "results"),
            (r"(?i)^\s*7\.?\s*Discussion\b", "discussion"),
            (r"(?i)^\s*8\.?\s*Conclusion\b", "conclusion"),
        ]

        text_lines = text.split("\n")
        for pattern, section_name in patterns:
            for i, line in enumerate(text_lines):
                if re.search(pattern, line):
                    section_text = " ".join(text_lines[i : i + 10])
                    sections[section_name] = section_text[:500]
                    break

        return sections

    async def _summarize_content(self, content: str, topic: str) -> Optional[Summary]:
        """Summarize webpage content specifically for the research topic."""
        prompt = f"Summarize the following content in the context of the research topic: {topic}\n\nContent:\n{content[:15000]}"
        try:
            return await self._generate_completion(
                prompt=prompt,
                system_message="Summarize webpage content accurately and extract key excerpts.",
                temperature=0.2,
                max_tokens=1000,
                response_model=Summary
            )
        except Exception as exc:
            logger.warning("Summarization failed for topic %s: %s", topic, exc)
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
        from langchain_core.messages import AIMessage
        from pydantic import BaseModel, Field

        research_iterations = state.get("research_iterations", 0)
        
        # Check iteration limit early
        if research_iterations >= self.config.max_researcher_iterations:
            logger.info("Max research iterations reached (%d). Stopping.", research_iterations)
            return Command(goto="__end__")

        # Handle override reducer format - may be dict with "type": "override"
        raw_messages = state.get("supervisor_messages", [])
        if isinstance(raw_messages, dict) and raw_messages.get("type") == "override":
            supervisor_messages = raw_messages.get("value", [])
        elif isinstance(raw_messages, list):
            supervisor_messages = raw_messages
        else:
            supervisor_messages = []
        
        class SupervisorDecision(BaseModel):
            """Decision taken by the lead researcher."""
            action: str = Field(description="Action to take: 'research' (delegate tasks) or 'complete' (finish research)")
            topics: list[str] = Field(default_factory=list, description="Sub-topics for 'research' action. Max 3.")
            reflection: str = Field(description="Internal reflection on current progress and strategy")
            reason: str = Field(description="Public reason for this decision")

        prompt = f"Based on the research brief and current progress, decide your next action.\n\nResearch Brief:\n{state.get('research_brief', '')}\n\nCurrent supervisor history:\n{get_buffer_string(supervisor_messages[-5:])}\n\nYou MUST decide to either:\n1. Conduct more research on specific sub-topics (ConductResearch).\n2. Conclude that research is complete (ResearchComplete).\n\nUse your reflection to plan the next steps carefully."

        decision: SupervisorDecision = await self._generate_completion(
            prompt=prompt,
            system_message=LEAD_RESEARCHER_PROMPT.format(
                date=get_today_str(),
                max_researcher_iterations=self.config.max_researcher_iterations,
                max_concurrent_research_units=self.config.max_concurrent_research_units,
            ),
            temperature=0.4,
            max_tokens=1000,
            response_model=SupervisorDecision,
        )

        if not decision:
            logger.warning("Supervisor failed to make a structured decision. Stopping.")
            return Command(goto="__end__")

        logger.info("Supervisor Reflection: %s", decision.reflection)

        if decision.action == "complete" or not decision.topics:
            return Command(
                goto="__end__",
                update={"supervisor_messages": [AIMessage(content=f"Research complete. Reason: {decision.reason}")]}
            )

        return Command(
            goto="supervisor_tools",
            update={
                "supervisor_messages": [AIMessage(content=f"Delegating research on topics: {', '.join(decision.topics)}. Reason: {decision.reason}")],
                "research_iterations": research_iterations + 1,
                "metadata": {"next_topics": decision.topics}
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
                raw_notes_data = result.get("raw_notes") or []
                if raw_notes_data:
                    raw_notes.extend(raw_notes_data)

            return Command(
                goto="supervisor",
                update={
                    "supervisor_messages": [AIMessage(content=f"Research units returned {len(research_results)} findings.")],
                    "notes": notes,
                    "raw_notes": raw_notes,
                    "metadata": {"next_topics": []}
                },
            )

        return Command(goto="supervisor")

    async def _execute_research_units(
        self,
        topics: list[str],
        parent_state: SupervisorState,
    ) -> list[dict[str, Any]]:
        """Execute research units in parallel with retry policies."""
        tasks = [
            self._execute_research_unit_with_retry(topic, parent_state)
            for topic in topics
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Research unit %d failed: %s", i, result)
                processed_results.append({
                    "compressed_research": f"Research on '{topics[i]}' failed: {str(result)}",
                    "raw_notes": [],
                    "success": False,
                })
            else:
                processed_results.append({**result, "success": True})

        successful = sum(1 for r in processed_results if r.get("success"))
        logger.info("Research units completed: %d/%d successful", successful, len(topics))

        return processed_results

    async def _execute_research_unit_with_retry(
        self,
        topic: str,
        parent_state: SupervisorState,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        """Execute a research unit with retry on failure."""
        last_error = None
        for attempt in range(max_attempts):
            try:
                return await self._execute_single_researcher(topic, parent_state)
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    await asyncio.sleep(1.0 * (2 ** attempt))
        raise last_error

    async def _execute_single_researcher(
        self,
        research_topic: str,
        parent_config: dict,
    ) -> dict[str, Any]:
        """Execute a single research unit with deep exploration."""
        researcher_state: ResearcherState = {
            "research_topic": research_topic,
            "researcher_messages": [HumanMessage(content=f"Researching topic: {research_topic}")],
            "compressed_research": "",
            "tool_call_iterations": 0,
            "raw_notes": [],
        }

        max_iterations = self.config.max_react_tool_calls
        
        for iteration in range(max_iterations):
            messages_text = get_buffer_string(researcher_state["researcher_messages"])
            reflection_prompt = f"You are researching: {research_topic}\nCurrent progress:\n{messages_text[-4000:]}\n\nAnalyze what you have found and what is missing. If you have enough information, say 'COMPLETE'. Otherwise, provide a specific search query to fill the gaps."

            reflection = await self._generate_completion(
                prompt=reflection_prompt,
                system_message="You are a meticulous research analyst. Reflect on gaps and plan next steps.",
                temperature=0.2,
                max_tokens=500
            )
            
            researcher_state["researcher_messages"].append(AIMessage(content=f"[Reflection] {reflection}"))
            if "COMPLETE" in reflection.upper()[:20]:
                break

            search_query = reflection.split("\n")[-1].strip()
            if not search_query or len(search_query) < 5:
                search_query = research_topic

            search_result = await self._search_with_fallback(search_query)
            results_list = search_result.get("results", [])
            if not results_list:
                researcher_state["researcher_messages"].append(AIMessage(content="No results found for this query."))
                continue

            summarization_tasks = []
            valid_results = []
            for res in results_list[:3]:
                url = res.get("url", "")
                if url:
                    content = await self._extract_content(url)
                    if content:
                        summarization_tasks.append(self._summarize_content(content, research_topic))
                        valid_results.append(res)
            
            if summarization_tasks:
                summaries = await asyncio.gather(*summarization_tasks)
                for i, summary in enumerate(summaries):
                    if summary:
                        url = valid_results[i].get("url")
                        researcher_state["raw_notes"].append(f"Source: {url}\nSummary: {summary.summary}\nExcerpts: {summary.key_excerpts}")
                        researcher_state["researcher_messages"].append(AIMessage(content=f"[Findings from {url}]\n{summary.summary[:1000]}..."))

            researcher_state["tool_call_iterations"] += 1

        compressed = await self._compress_research(researcher_state)
        return {"compressed_research": compressed, "raw_notes": researcher_state["raw_notes"]}

    async def _compress_research(self, researcher_state: ResearcherState) -> str:
        """Compress research findings into a summary."""
        messages = researcher_state.get("researcher_messages", [])
        messages_text = get_buffer_string(messages)
        prompt = f"{COMPRESS_RESEARCH_SIMPLE_HUMAN_MESSAGE}\n\nResearch topic: {researcher_state.get('research_topic', '')}\n\nMessages to compress:\n{messages_text}"
        return await self._generate_completion(
            prompt=prompt,
            system_message=COMPRESS_RESEARCH_SYSTEM_PROMPT.format(date=get_today_str()),
            temperature=0.3,
            max_tokens=4000,
        )

    def _extract_research_topics(self, content: str) -> list[str]:
        """Extract research topics from content."""
        topics = []
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:
                for prefix in ["- ", "* ", "1. ", "2. ", "3. ", "Topic: ", "Research: "]:
                    if line.startswith(prefix):
                        line = line[len(prefix):]
                if line:
                    topics.append(line)
        return topics[:3]

    async def merge_results(
        self,
        state: SupervisorState,
    ) -> dict[str, Any]:
        """Merge and deduplicate research results from parallel units.

        This node runs after supervisor_tools to aggregate results
        from parallel research units and remove duplicates.
        """
        notes = state.get("notes", [])
        raw_notes = state.get("raw_notes", [])

        seen_urls = set()
        deduplicated_raw_notes = []
        for note in raw_notes:
            url_match = note.split("Source: ")[1].split("\n")[0] if "Source: " in note else None
            if url_match and url_match in seen_urls:
                continue
            if url_match:
                seen_urls.add(url_match)
            deduplicated_raw_notes.append(note)

        unique_notes = list(dict.fromkeys(notes))

        logger.info(
            "Merge results: %d notes, %d raw notes (after deduplication)",
            len(unique_notes),
            len(deduplicated_raw_notes),
        )

        return {
            "notes": {"type": "override", "value": unique_notes},
            "raw_notes": {"type": "override", "value": deduplicated_raw_notes},
        }

    async def final_report_generation(
        self,
        state: DeepResearchAgentState,
        config: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Generate the final research report."""
        research_brief = state.get("research_brief", "")
        notes = state.get("notes", [])
        findings = "\n\n".join(notes) if notes else "No findings collected."
        prompt = FINAL_REPORT_GENERATION_PROMPT.format(
            research_brief=research_brief,
            messages=get_buffer_string(state.get("messages", [])),
            findings=findings,
            date=get_today_str(),
        )
        final_report = await self._generate_completion(
            prompt=prompt,
            temperature=0.4,
            max_tokens=self.config.final_report_model_max_tokens,
        )
        return {"final_report": final_report, "messages": [AIMessage(content=final_report)]}


def create_nodes(config: Optional[DeepResearchConfig] = None) -> DeepResearchNodes:
    """Create a DeepResearchNodes instance."""
    return DeepResearchNodes(config=config)

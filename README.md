# tech-watch-agent

**Advanced Multi-Agent Tech Watch Platform with Orchestrator, Deep Research, and Newsletter Generation**

An open-source platform for automated technology monitoring and comprehensive research report generation using AI agents. Built with LangGraph, FastAPI, and PostgreSQL with pgvector for semantic search.

## Status: MVP Complete

All core capabilities are implemented, tested, and functional:
- ✅ Orchestrator agent (V2) with plan-based parallel research pipeline
- ✅ Deep Research agent with supervisor-researcher pattern + PDF extraction
- ✅ Newsletter agent (V2) with quality-based routing, source citations
- ✅ Multi-provider LLM support (OpenRouter, Ollama, Z.ai, OpenAI)
- ✅ 10+ monitoring tools (GitHub, Reddit, ArXiv, RSS, YouTube, Research Papers, Web Search)
- ✅ PDF Downloader tool for academic papers (ArXiv, direct PDFs)
- ✅ Tool plugin system with registry (fully tested)
- ✅ Vector store with pgvector for semantic similarity + hybrid search
- ✅ Email delivery via Gmail with source citations
- ✅ REST API with 25+ endpoints
- ✅ V1 (legacy newsletter) and V2 (orchestrator) execution modes
- ✅ Dual-mode: autonomous (scheduled) + interactive (on-demand with approval)
- ✅ **145 unit tests passing**

## Audit Results (2026-05-12)

### Bugs Fixed
1. **Import error** (`app/prompts/newsletter` → `app/agents/newsletter/prompts`): Module structure refactored to move prompts under agents
2. **Orchestrator factory bug**: `create_orchestrator_agent()` had invalid `checkpointer` parameter removed

### New Features (2026-05-12)
1. **Email as Tool**: `EmailTool` and `EmailPreviewTool` registered in tool registry
   - `email` tool: Send emails via Gmail API with HTML/text rendering
   - `email_preview` tool: Preview email content without sending
2. **Plan Mode Strict**: Planner now retries up to 3 times with strict JSON validation
   - Cannot exit without a valid plan
   - Better error messages and fallbacks
3. **Parallel Newsletter**: NEWSLETTER steps now run in parallel with RESEARCH/DEEP_RESEARCH
4. **Conflict Detection**: New dependency analysis for step execution
   - `group_parallel_steps()`: Groups steps by parallelization potential
   - `analyze_step_dependencies()`: Maps dependencies between steps
   - Sequential-only types: SYNTHESIS, ANALYSIS, EMAIL, VALIDATION, COLLECTION, SUMMARY
5. **Enhanced Prompts**: Complete rewrite of all agent prompts
   - Supervisor: Better role definition and workflow description
   - Planner: Explicit valid tool names list, strict JSON output
   - Dispatcher: Clear tool mapping and execution rules
   - Collector: Better aggregation and deduplication
   - Analyzer: Structured JSON output with sentiment analysis
   - Synthesizer: Professional report template with references
6. **LLM Health Manager**: New health monitoring system
   - `LLMHealthManager` class in `app/services/llm/health.py`
   - Async provider health checks with latency measurement
   - Automatic fallback to healthy providers (Z.ai → Ollama → OpenRouter)
   - Provider status tracking (healthy/degraded/unhealthy)
   - Integration in OrchestratorNodes for pre-execution checks

### Known Issues
- LLM network errors with Z.ai provider (glm-4.5-flash) - system auto-fallbacks to Ollama

### Recommendations
- Consider adding more retry policies for tool failures
- Add more valid tool names to prompts as more tools are registered

## What's New (2026-05-12)

All core capabilities are implemented, tested, and functional:
- ✅ Orchestrator agent (V2) with plan-based parallel research pipeline
- ✅ Deep Research agent with supervisor-researcher pattern + PDF extraction
- ✅ Newsletter agent (V2) with quality-based routing, source citations
- ✅ Multi-provider LLM support (OpenRouter, Ollama, Z.ai, OpenAI)
- ✅ 10+ monitoring tools (GitHub, Reddit, ArXiv, RSS, YouTube, Research Papers, Web Search)
- ✅ PDF Downloader tool for academic papers (ArXiv, direct PDFs)
- ✅ Tool plugin system with registry (fully tested)
- ✅ Vector store with pgvector for semantic similarity + hybrid search
- ✅ Email delivery via Gmail with source citations
- ✅ REST API with 25+ endpoints
- ✅ V1 (legacy newsletter) and V2 (orchestrator) execution modes
- ✅ Dual-mode: autonomous (scheduled) + interactive (on-demand with approval)
- ✅ **127 unit tests passing**

## What's New (2026-05-12)

### Memory Architecture
- **Article persistence**: Articles fetched during research are automatically stored in DB via `ArticleService.save_articles()` — deduplicated by title+URL
- **Report storage**: Final reports are persisted to `ResearchSession` table after synthesis
- **Hybrid vector search**: `VectorStore.search()` now supports keyword filtering + configurable time windows (30 days default)
- **Three memory tiers**: Short-term (LangGraph state), Medium-term (ResearchSession), Long-term (Vector Store)

### Newsletter as Sub-Agent
- Orchestrator can now call `NewsletterAgent` as a `NEWSLETTER` step type
- Passes orchestrator's collected research results to NewsletterAgent (no re-fetch)
- Newsletter uses async nodes with `async_generate_completion()` throughout

### Deep Research PDF Integration
- New `PDFDownloaderTool` + `ArXivPDFTool` for downloading and parsing PDFs
- Downloads PDFs from ArXiv/OpenAlex/any URL, extracts text via PyMuPDF, auto-cleans temp files
- DeepResearch now downloads and extracts full PDF content for academic papers
- Section extraction (abstract, intro, methods, results, conclusion) for structured reading

### Source Citations
- Newsletter editor prompt requires inline citations `[1]`, `[2]` etc. for facts/data/research
- References section appended to every newsletter
- Sources passed to Editor node as formatted reference list

## Architecture

### Agent Hierarchy

```
Orchestrator (V2)
  ├── DeepResearch (sub-agent) — supervisor → parallel researchers
  │     └── PDF Downloader (for ArXiv/OpenAlex papers)
  └── Newsletter (sub-agent) — researcher → analyst → opinion_writer → editor
        └── Source citation with [1], [2] references
```

### Dual-Mode Execution

| Mode | Scheduler (cron) | API endpoint |
|------|-----------------|--------------|
| **Autonomous** | `autonomous=True` — fully automated, no approval | `--autonomous` flag |
| **Interactive** | — | Human-in-the-loop approval before email |

### Memory Flow

```
Research results → collector node → persist_articles() → DB (Article table)
                          ↓
              synthesizer node → persist_research_session() → DB (ResearchSession)
                          ↓
              VectorStore.upsert() with embedding → pgvector
```

## Features

### Core Agents
- **Orchestrator Agent** (V2): Central planner that decomposes tasks into execution plans, dispatches research in parallel across multiple tools, collects/validates results, analyzes, synthesizes reports, and delivers via email. Uses LangGraph StateGraph with supervisor pattern.
- **Deep Research Agent**: Multi-agent supervisor-researcher pattern for in-depth investigations. Supports clarification loops, parallel research units, citation tracking. Downloads and extracts PDF content from ArXiv and OpenAlex.
- **Newsletter Agent** (V2): Automated newsletter generation from collected articles. Quality-based routing (standard/enhanced/basic). Inline source citations with references section. Async nodes throughout.

### Monitoring Tools
- **GitHub**: Repository search, trending repos, commit tracking, issues
- **Reddit**: Subreddit monitoring, hot/new/top posts, search
- **ArXiv**: Academic paper discovery, category browsing, author search, **PDF download with full-text extraction**
- **OpenAlex**: Free academic papers, citation data, **PDF content extraction**
- **RSS/Atom**: Feed aggregation from multiple sources, auto-discovery
- **Web Search**: News article collection via DuckDuckGo HTML
- **YouTube**: Video transcript extraction, metadata, search
- **Research Papers**: Semantic Scholar search, PyMuPDF text extraction, arXiv metadata
- **PDF Downloader**: Download PDFs from any URL, extract text, automatic cleanup

### Technical Features
- **Multi-Provider LLM**: OpenRouter, Ollama, Z.ai, OpenAI with runtime switching and health checks
- **Async-first**: Full async/await for concurrent operations
- **Database**: PostgreSQL with SQLAlchemy async ORM + pgvector
- **Tool Plugin System**: Extensible registry with category filtering
- **Memory Layer**: Article store, vector store (hybrid search), session store
- **Email Delivery**: Gmail OAuth with HTML/text rendering + source citations

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/your-repo/tech-watch-agent
cd tech-watch-agent

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start with Docker

```bash
# Start all services (PostgreSQL, Redis, API)
docker compose -f docker/docker-compose.yml up

# Or start just the API
docker compose -f docker/docker-compose.yml up tech-watch-api
```

### 3. Local Development

```bash
# Install dependencies
pip install -e .

# Run database migrations
alembic upgrade head

# Start API server
python -m app.main --mode api

# Run V2 orchestrator (full research pipeline)
python -m app.main --mode once --no-email

# Run V1 newsletter (legacy)
python -m app.main --mode once --v1 --no-email

# Run scheduled newsletter generation
python -m app.main --mode schedule
```

## Configuration

Edit `.env` file with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/techwatch

# LLM Provider (multi-provider support)
LLM_PROVIDER=openrouter     # openrouter, ollama, zai, openai
LLM_MODEL=                  # Empty = provider default model
LLM_API_KEY=your-api-key   # Not required for ollama

# Newsletter Topics
NEWSLETTER_TOPICS=AI news,Machine Learning,Tech startups

# Email Delivery
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAILS=recipient1@example.com,recipient2@example.com
```

### Available LLM Providers

| Provider | Base URL | Default Model | API Key Required |
|---|---|---|---|
| `openrouter` | `https://openrouter.ai/api/v1` | `openai/gpt-4.1-mini` | Yes |
| `ollama` | `http://localhost:11434/v1` | `llama3.2` | No |
| `zai` | `https://api.z.ai/v1` | `zephyr` | Yes |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | Yes |

## API Endpoints

### Health & Status
- `GET /health` - System health check (database, memory, agents)
- `GET /status` - System status and statistics
- `GET /stats` - Detailed statistics

### Orchestrator (V2 - Main Pipeline)
- `POST /orchestrator/run` - Run full research pipeline
- `POST /orchestrator/task` - Run research task with full control

### Newsletter (V1 - Legacy)
- `POST /newsletter/generate` - Generate newsletter
- `GET /newsletter/history` - Get generation history
- `GET /newsletter/stats` - Get newsletter statistics

### Deep Research
- `POST /research` - Start deep research session
- `GET /research/history` - Get research history

### Articles
- `GET /articles` - List articles with filters
- `GET /articles/{id}` - Get specific article

### Users
- `POST /users` - Create user
- `GET /users/{id}` - Get user
- `GET /users/{id}/topics` - Get user topics
- `POST /users/{id}/topics` - Add user topic

### Tools
- `GET /tools` - List all registered tools
- `GET /tools/{name}` - Get tool details
- `POST /tools/execute` - Execute a tool

### LLM Providers
- `GET /llm/providers` - List all available providers and current config
- `GET /llm/providers/{name}` - Get provider details
- `GET /llm/providers/{name}/health` - Check provider reachability
- `POST /llm/providers/switch` - Switch provider (runtime, update .env to persist)

## Development

### Project Structure

```
app/
├── agents/              # AI agent implementations
│   ├── base/            # Base agent framework
│   ├── orchestrator/    # V2 orchestrator (plan → research → report)
│   │   ├── nodes.py     # supervisor, planner, dispatcher, collector, synthesizer
│   │   ├── state.py     # OrchestratorState, PlanStep, StepType
│   │   └── prompts.py   # Agent prompts
│   ├── newsletter/      # V2 newsletter agent
│   │   ├── agent.py     # NewsletterAgent with async setup/execute
│   │   ├── nodes.py     # async nodes: researcher, analyst, opinion_writer, editor
│   │   ├── graph.py     # LangGraph workflow with quality routing
│   │   └── state.py     # NewsletterState
│   └── deep_research/   # Deep research agent
│       ├── nodes.py     # supervisor, researcher, PDF extraction
│       ├── graph.py     # LangGraph workflow
│       └── simple_agent.py  # Simplified fallback agent
├── api/                 # FastAPI endpoints
├── config/              # Configuration management
├── core/                # Core utilities (logging, models)
├── db/                  # Database layer (models, base, migrations)
├── delivery/            # Email delivery (Gmail, renderer)
├── rag/                 # Vector store with pgvector + hybrid search
├── scheduler/           # Task scheduling
├── services/            # Business logic
│   ├── article_service.py   # Article persistence with deduplication
│   ├── embedding/        # Real embeddings (OpenAI, Z.ai, Ollama)
│   └── llm/             # Multi-provider LLM
├── skills/              # Agent skill modules
├── tools/               # Tool plugins
│   ├── base.py         # BaseTool, ToolCategory, ToolResult
│   ├── memory/          # Memory tools (SearchMemory, GetRecentContext)
│   ├── web/             # Web tools (search, crawl, tavily, openalex, pdf_downloader)
│   └── social/          # Social tools (GitHub, Reddit, ArXiv, YouTube)

alembic/                 # Database migrations
tests/                   # 127 unit tests
docker/                  # Docker configuration
```

### Running Tests

```bash
pytest
pytest --cov=app tests/
pytest tests/test_base_agent.py
```

### Database Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

## Extending the Platform

### Creating a New Tool

```python
from app.tools.base import BaseTool, ToolCategory, ToolResult

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description of my tool"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SEARCH

    async def execute(self, params: dict) -> ToolResult:
        return {"success": True, "data": ..., "error": None, "metadata": {}}
```

### Creating a New Agent

```python
from app.agents.base import BaseAgent, AgentConfig, AgentResult

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        pass

    async def execute(self, input_data: Any) -> AgentResult:
        return AgentResult.create_success(output=...)

    async def cleanup(self) -> None:
        pass
```

## Technology Stack

- **Python 3.11+** - Language
- **FastAPI** - Web framework
- **LangGraph** - Agent orchestration with StateGraph
- **SQLAlchemy 2.0** - ORM (async)
- **PostgreSQL** - Database with pgvector
- **Redis** - Caching and task queue
- **PyMuPDF** - PDF text extraction
- **Alembic** - Database migrations
- **Docker** - Containerization

## License

MIT License - See LICENSE file for details
# tech-watch-agent

**Advanced Multi-Agent Tech Watch Platform with Orchestrator, Deep Research, and Newsletter Generation**

An open-source platform for automated technology monitoring and comprehensive research report generation using AI agents. Built with LangGraph, FastAPI, and PostgreSQL with pgvector for semantic search.

## Status: MVP Complete

All core capabilities are implemented, tested, and functional:
- ✅ Orchestrator agent (V2) with plan-based parallel research pipeline
- ✅ Deep Research agent with supervisor-researcher pattern
- ✅ Newsletter agent (V1) for automated content generation
- ✅ Multi-provider LLM support (OpenRouter, Ollama, Z.ai, OpenAI)
- ✅ 10+ monitoring tools (GitHub, Reddit, ArXiv, RSS, YouTube, Research Papers, Web Search)
- ✅ Tool plugin system with registry (fully tested)
- ✅ Vector store with pgvector for semantic similarity
- ✅ Email delivery via Gmail
- ✅ REST API with 25+ endpoints
- ✅ V1 (legacy newsletter) and V2 (orchestrator) execution modes
- ✅ **94 unit tests passing** (100% of core functionality tested)

## Recent Fixes (2026-05-11)

The following issues were identified and fixed during the Phase 1 audit:
- Fixed duplicate `AgentRegistry` class definitions (consolidated)
- Fixed test imports referencing renamed `OrchestratorScheduler`
- Fixed duplicate property assignment in `NewsletterAgent`
- Fixed `CompositeTool` missing required abstract methods
- Fixed async/await issues in tool tests
- Fixed database model compatibility (PostgreSQL → SQLite for tests via dialect-aware types)
- Fixed relationship configuration in `UserSession` model
- Fixed nullable timestamps in models for SQLite compatibility
- Fixed settings test isolation (cache clear + env var cleanup)

## Roadmap (Next Improvements)

### Phase 2: Enhanced Features
- [ ] Scrapling integration for advanced web fetching
- [ ] Adaptive element tracking for resilient content scraping
- [ ] Multi-session spider support with proxy rotation
- [ ] Cloudflare/anti-bot bypass for protected sites

### Phase 3: Production Hardening
- [ ] LangGraph checkpointing for long-running sessions
- [ ] LangSmith observability integration
- [ ] Celery/Temporal for distributed task queues
- [ ] Web dashboard for monitoring
- [ ] Multi-tenant support
- [ ] Advanced analytics

## Features

### Core Agents
- **Orchestrator Agent** (V2): Central planner that decomposes tasks into execution plans, dispatches research in parallel across multiple tools, collects/validates results, analyzes, synthesizes reports, and delivers via email. Uses LangGraph StateGraph with supervisor pattern.
- **Deep Research Agent**: Multi-agent supervisor-researcher pattern for in-depth investigations. Supports clarification loops, parallel research units, and citation tracking.
- **Newsletter Agent** (V1): Automated newsletter generation from collected articles. Linear pipeline: researcher → analyst → opinion_writer → editor.

### Monitoring Tools
- **GitHub**: Repository search, trending repos, commit tracking, issues
- **Reddit**: Subreddit monitoring, hot/new/top posts, search
- **ArXiv**: Academic paper discovery, category browsing, author search
- **RSS/Atom**: Feed aggregation from multiple sources, auto-discovery
- **Web Search**: News article collection via DuckDuckGo HTML
- **YouTube**: Video transcript extraction, metadata, search
- **Research Papers**: PDF download, PyMuPDF text extraction, Semantic Scholar search, arXiv metadata

### Technical Features
- **Multi-Provider LLM**: OpenRouter, Ollama, Z.ai, OpenAI with runtime switching and health checks
- **Async-first**: Full async/await for concurrent operations
- **Database**: PostgreSQL with SQLAlchemy async ORM + pgvector
- **Tool Plugin System**: Extensible registry with category filtering
- **Skills System**: Reusable skill modules attachable to agents
- **Memory Layer**: Article store, vector store, session store
- **Email Delivery**: Gmail OAuth with HTML/text rendering

## Architecture

```

        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                               ENTRY POINTS                                   │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌──────────────────┐    │
        │   │    CLI     │   │    API     │   │   Worker   │   │    Scheduler     │    │
        │   │            │   │  FastAPI   │   │ Background │   │   APScheduler    │    │
        │   └─────┬──────┘   └─────┬──────┘   └─────┬──────┘   └────────┬─────────┘    │
        │         │                │                │                   │              │
        └─────────┼────────────────┼────────────────┼───────────────────┼──────────────┘
                  │                │                │                   │
                  ▼                ▼                ▼                   ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                                DOMAIN LAYER                                  │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌──────────────────────────────────────────────────────────────────────┐   │
        │   │                      ORCHESTRATOR AGENT (V2)                         │   │
        │   │                                                                      │   │
        │   │  supervisor → planner → dispatcher_parallel → collector              │   │
        │   │                                    ↓                                 │   │
        │   │                                validator                             │   │
        │   │                        (retry loop) ↓                                │   │
        │   │                           analyzer → synthesizer → emailer           │   │
        │   └──────────────────────────────────────────────────────────────────────┘   │
        │                                                                              │
        │   ┌──────────────────────────────────────────────────────────────────────┐   │
        │   │                       SPECIALIST AGENTS                              │   │
        │   │                                                                      │   │
        │   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
        │   │   │ Newsletter   │  │ DeepResearch │  │ DeepResearch │               │   │
        │   │   │    (V1)      │  │ Supervisor   │  │ Researcher   │               │   │
        │   │   └──────────────┘  └──────────────┘  └──────────────┘               │   │
        │   │                                                                      │   │
        │   └──────────────────────────────────────────────────────────────────────┘   │
        │                                                                              │
        └──────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                         SKILLS & TOOLS LAYER                                 │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
        │   │ web_fetch  │  │  social_   │  │  research  │  │  analysis  │             │
        │   │  skill     │  │   monitor  │  │   _paper   │  │   _insights│             │
        │   └────────────┘  └────────────┘  └────────────┘  └────────────┘             │
        │                                                                              │
        │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
        │   │Web Search  │  │  GitHub    │  │  Reddit    │  │   ArXiv    │             │
        │   │   Tool     │  │ Watch Tool │  │ Watch Tool │  │ Watch Tool │             │
        │   └────────────┘  └────────────┘  └────────────┘  └────────────┘             │
        │                                                                              │
        │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
        │   │ RSS Feed   │  │ YouTube    │  │Research    │  │ Custom     │             │
        │   │   Tool     │  │Transcript  │  │  Papers    │  │ Plugins    │             │
        │   └────────────┘  └────────────┘  └────────────┘  └────────────┘             │
        │                                                                              │
        └──────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                              RAG / MEMORY LAYER                              │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
        │   │   Vector Store   │  │  Article Store   │  │ Session / User Context   │   │
        │   │    pgvector      │  │                  │  │        Manager           │   │
        │   └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
        │                                                                              │
        └──────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                             PERSISTENCE LAYER                                │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐   │
        │   │   PostgreSQL     │  │      Redis       │  │      File Storage        │   │
        │   │ Metadata & State │  │ Cache / Queueing │  │   Articles / Snapshots   │   │
        │   └──────────────────┘  └──────────────────┘  └──────────────────────────┘   │
        │                                                                              │
        └──────────────────────────────────────────────────────────────────────────────┘

```

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
│   ├── orchestrator/    # V2 orchestrator (plan -> research -> report)
│   ├── newsletter/       # V1 newsletter agent
│   └── deep_research/   # Deep research agent
├── api/                 # FastAPI endpoints
├── config/              # Configuration management
├── core/                # Core utilities (logging, models)
├── db/                  # Database layer
├── delivery/            # Email delivery (Gmail, renderer)
├── memory/              # Memory/RAG layer
├── scheduler/           # Task scheduling
├── services/            # Business logic
│   └── llm/             # Multi-provider LLM
│       └── providers.py # Provider registry
├── skills/              # Agent skill modules
│   ├── base.py         # Base skill interface
│   ├── registry.py     # Skill registry
│   └── predefined/      # Predefined skills
└── tools/               # Tool plugins
    ├── base.py         # Base tool interface
    ├── registry.py     # Tool registry
    ├── web/            # Web tools (search, crawl)
    └── social/          # Social tools (GitHub, Reddit, etc.)

alembic/                 # Database migrations
tests/                   # Unit tests
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

### Creating a New Skill

```python
from app.skills.base import BaseSkill, SkillResult

class WebResearchSkill(BaseSkill):
    @property
    def name(self) -> str:
        return "web_research"

    @property
    def description(self) -> str:
        return "Advanced web research with adaptive parsing"

    async def execute(self, params: dict, context: dict) -> SkillResult:
        # Skill logic with access to tools and LLM
        return SkillResult(success=True, data=..., message="...")
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
- **Alembic** - Database migrations
- **Docker** - Containerization

## Roadmap (Next Improvements)

- [ ] Scrapling integration for advanced web fetching
- [ ] Adaptive element tracking for resilient content scraping
- [ ] Multi-session spider support with proxy rotation
- [ ] Cloudflare/anti-bot bypass for protected sites
- [ ] LangGraph checkpointing for long-running sessions
- [ ] LangSmith observability integration
- [ ] Celery/Temporal for distributed task queues
- [ ] Web dashboard for monitoring
- [ ] Multi-tenant support
- [ ] Advanced analytics

## License

MIT License - See LICENSE file for details
# tech-watch-agent

**Advanced Multi-Agent Tech Watch Platform with Deep Research Capabilities**

An open-source platform for automated technology monitoring and newsletter generation using AI agents. Built with LangGraph, FastAPI, and PostgreSQL with pgvector for semantic search.

## Features

### Core Capabilities
- **Newsletter Agent**: Automated newsletter generation from collected articles
- **Deep Research Agent**: Multi-agent research system with supervisor-researcher pattern
- **Semantic Search**: Vector-based article similarity and deduplication
- **Multi-User Support**: User preferences and topic subscriptions

### Monitoring Tools
- **GitHub**: Repository search, trending repos, commit tracking
- **Reddit**: Subreddit monitoring, hot/new/top posts, search
- **ArXiv**: Academic paper discovery, category browsing
- **RSS/Atom**: Feed aggregation from multiple sources
- **Web Search**: News article collection and ranking
- **YouTube**: Video transcript extraction
- **Research Papers**: PDF download, text extraction, Semantic Scholar search, arXiv integration

### Technical Features
- **Async-first**: Full async/await for concurrent operations
- **Database**: PostgreSQL with SQLAlchemy async ORM
- **Vector Store**: pgvector for semantic similarity search
- **Tool Plugin System**: Extensible tool architecture
- **Health Monitoring**: Comprehensive health checks and metrics

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
        │   │                           AGENT ENGINE                               │   │
        │   │                                                                      │   │
        │   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
        │   │   │ Newsletter   │  │ DeepResearch │  │ TrendMonitor │               │   │
        │   │   │    Agent     │  │    Agent     │  │    Agent     │               │   │
        │   │   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │   │
        │   │          │                 │                 │                       │   │
        │   │          └─────────────────┼─────────────────┘                       │   │
        │   │                            │                                         │   │
        │   │                   ┌────────▼────────┐                                │   │
        │   │                   │  Custom Agents  │                                │   │
        │   │                   └─────────────────┘                                │   │
        │   │                                                                      │   │
        │   └──────────────────────────────────────────────────────────────────────┘   │
        │                                                                              │
        └──────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                            TOOL PLUGIN SYSTEM                                │
        ├──────────────────────────────────────────────────────────────────────────────┤
        │                                                                              │
        │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
        │   │ Web Search │  │ GitHub     │  │ Reddit     │  │ ArXiv      │             │
        │   │   Tool     │  │ Watch Tool │  │ Watch Tool │  │ Watch Tool │             │
        │   └────────────┘  └────────────┘  └────────────┘  └────────────┘             │
        │                                                                              │
        │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
        │   │ RSS Feed   │  │ YouTube    │  │ HackerNews │  │ Custom     │             │
        │   │   Tool     │  │ Transcript │  │   Monitor  │  │ Plugins    │             │
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
        │   │   Vector Store   │  │  History Store   │  │ Session / User Context   │   │
        │   │    pgvector      │  │  Articles & Logs │  │        Manager           │   │
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

# Generate newsletter once
python -m app.main --mode once --no-email

# Run scheduler
python -m app.main --mode schedule
```

## Configuration

Edit `.env` file with your settings:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/techwatch

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
- `GET /health` - System health check
- `GET /status` - System status and statistics
- `GET /stats` - Detailed statistics

### Newsletter
- `POST /newsletter/generate` - Generate newsletter (async)
- `POST /newsletter/generate/sync` - Generate newsletter (sync)
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
│   ├── newsletter/       # Newsletter generation agent
│   └── deep_research/   # Deep research agent
├── api/                 # FastAPI endpoints
├── config/              # Configuration management
├── core/                # Core utilities (logging, models)
├── db/                  # Database layer
│   ├── models.py        # SQLAlchemy models
│   ├── repositories.py  # Data access layer
│   └── base.py          # Database configuration
├── delivery/            # Email delivery
├── memory/              # Memory/RAG layer
├── monitoring/          # Health checks and metrics
├── prompts/             # Agent prompts
├── scheduler/           # Task scheduling
├── services/            # Business logic services
└── tools/               # Tool plugins
    ├── base.py         # Base tool interface
    ├── registry.py     # Tool registry
    └── social/          # Social media tools

alembic/                 # Database migrations
tests/                   # Unit tests
docker/                  # Docker configuration
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_base_agent.py
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
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
        # Your tool logic here
        return {"success": True, "data": ..., "error": None, "metadata": {}}

# Register the tool
from app.tools.registry import register_tool
register_tool(MyTool())
```

### Creating a New Agent

```python
from app.agents.base import BaseAgent, AgentConfig, AgentResult

class MyAgent(BaseAgent):
    async def setup(self) -> None:
        # Initialize agent resources
        pass

    async def execute(self, input_data: Any) -> AgentResult:
        # Agent logic
        return AgentResult.create_success(output=...)

    async def cleanup(self) -> None:
        # Release resources
        pass
```

## Technology Stack

- **Python 3.11+** - Language
- **FastAPI** - Web framework
- **LangGraph** - Agent orchestration
- **SQLAlchemy 2.0** - ORM (async)
- **PostgreSQL** - Database
- **pgvector** - Vector similarity search
- **Redis** - Caching and task queue
- **Alembic** - Database migrations
- **Docker** - Containerization

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please read the contributing guidelines and submit PRs.

## Roadmap

- [ ] Celery/Temporal integration for task queues
- [ ] Web dashboard for monitoring
- [ ] Additional agent types (trends, comparison)
- [ ] Plugin marketplace
- [ ] Multi-tenant support
- [ ] Advanced analytics
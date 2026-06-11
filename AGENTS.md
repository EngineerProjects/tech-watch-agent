# AGENTS.md — tech-watch-agent

Guide for AI agents (Claude Code, Codex, etc.) working in this repository.

---

## What this project is

`tech-watch-agent` is a multi-agent tech watch platform. Given a subject and topics, it:

1. generates a structured research plan (LangGraph planner node)
2. dispatches parallel search steps across multiple providers (web, academic, social)
3. synthesises a newsletter-style report
4. optionally delivers it by email via Gmail OAuth

The stack: **FastAPI** (API + legacy Jinja dashboard) · **LangGraph** (agent workflows) · **PostgreSQL + pgvector** (sessions, sources, vector memory) · **Redis** (cache) · **SearXNG** (self-hosted search) · **React** (frontend SPA, served by nginx).

---

## Repository layout

```
app/
├── agents/
│   ├── base/          # BaseAgent ABC, AgentConfig, AgentResult
│   ├── orchestrator/  # Main pipeline: supervisor→planner→dispatcher→synthesizer→emailer
│   ├── deep_research/ # Deep-dive sub-agent (called from dispatcher)
│   └── newsletter/    # Newsletter formatting sub-agent
├── api/               # FastAPI routers (orchestrator, sessions, watch-profiles, config…)
├── config/            # Pydantic-settings (Settings, get_settings)
├── core/              # Shared primitives: logging, models, crypto, research_brief
├── db/                # SQLAlchemy models, Alembic base, repositories
├── delivery/          # Gmail client, newsletter renderer, delivery service
├── rag/               # pgvector store, article store, memory manager
├── scheduler/         # APScheduler service for watch-profile scheduling
├── services/          # LLM client, session manager, streaming service, MCP
├── skills/            # Reusable skill primitives (base + registry)
└── tools/             # Tool registry, all executable tools (search, crawl, social…)
alembic/               # Database migrations (one file per version, sequential)
docker/                # Dockerfile, Dockerfile.frontend, docker-compose.yml, nginx.conf
frontend/              # React SPA (Vite + TypeScript)
tests/                 # pytest unit + integration tests
```

---

## How to run locally (without Docker)

```bash
# 1. Install (requires Python 3.11+)
pip install -e ".[dev]"

# 2. Start infrastructure (postgres + redis + searxng)
make up          # starts Docker services; api and frontend are optional

# 3. Apply DB migrations
alembic upgrade head

# 4. Start the API
python -m app.main --mode api
```

Other run modes:

```bash
python -m app.main --mode once --no-email   # one-shot research run, no email
python -m app.main --mode schedule          # run the scheduler daemon
```

Full stack with Docker: `make up` — see `Makefile` for all targets.

---

## Running tests

```bash
# All tests (unit + integration)
pytest tests/ -v

# Specific integration suite
pytest tests/test_orchestrator_integration.py -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

**Key constraints for tests:**

- Most tests use `enable_session_persistence=False` on `OrchestratorNodes` — do not introduce real DB calls in unit tests.
- Use `AsyncMock` for DB session and `MagicMock` for LLM clients in unit tests.
- Integration tests in `tests/test_orchestrator_integration.py` must not require a live LLM or real DB connection; they mock both.
- The `supervisor` node does **not** call the LLM — it only routes state. The `planner` node calls the LLM.

---

## LangGraph workflow

The orchestrator graph (`app/agents/orchestrator/graph.py`) follows this topology:

```
supervisor → planner → dispatcher_parallel → collector → validator
                                                              ↓
                          human_approval ← ─ ─ ─ ─ ─ ─ ─ ─ ─
                                ↓
                           analyzer → synthesizer → emailer → END
```

- **Retry loops**: planner retries up to `max_plan_retries` (default 3) if no valid plan is produced.
- **Validation retry**: validator retries the dispatcher (sequential) up to `max_iterations` if quality threshold is not met.
- **Checkpointing**: configured via `OrchestratorGraphBuilder(enable_checkpointing=True, checkpoint_backend="postgres"|"memory")`. Pass config through `OrchestratorConfig`, not by passing a raw checkpointer to `build()`.

`OrchestratorState` is a `TypedDict`. All nodes receive and return the full state dict; never mutate state in place — return a new dict or selectively update keys.

---

## Adding a new agent

1. Create `app/agents/<name>/` with `agent.py`, `graph.py`, `nodes.py`, `state.py`, `prompts.py`.
2. Subclass `BaseAgent` from `app/agents/base/base_agent.py`. Implement `name`, `description`, `setup()`, `execute()`, `cleanup()`.
3. Register in `app/agents/registry.py`.
4. Write tests in `tests/test_<name>.py` with `enable_session_persistence=False`.

---

## Adding a new tool

1. Create `app/tools/<name>.py`, subclass the tool base from `app/tools/base.py`.
2. Register in `app/tools/registry_init.py`.
3. If the tool uses an external API, add the key to `app/config/settings.py` as an optional field and document it in `.env.example`.
4. Add a test in `tests/test_tools.py`.

---

## Configuration model

Two tiers:

| Tier | Where | What goes here |
|---|---|---|
| Bootstrap | `.env` / Docker env | DB URL, Redis URL, CORS, `ADMIN_API_TOKEN`, `CONFIG_ENCRYPTION_KEY`, first-boot LLM hint |
| Runtime | DB (`app_config` table via `Settings` UI) | LLM provider/model, API keys, Gmail OAuth, newsletter settings, search providers |

Runtime secrets are **encrypted** with `CONFIG_ENCRYPTION_KEY` (Fernet). The app reads them back to use them — do not hash them.

---

## Database migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "describe the change"

# Apply
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

Migrations live in `alembic/versions/` and are numbered sequentially (`001_`, `002_`, …).

---

## Docker

- `make up` — starts postgres, redis, searxng, api (port 8000), frontend (port 3000).
- `make up-ollama` — same + ollama + model pull.
- `make hard-clean` — removes containers, images, and `.volumes/` data directories.
- The API container runs `alembic upgrade head` on startup before launching uvicorn.
- `once` and `scheduler` services use Docker Compose profiles (`--profile manual`, `--profile scheduler`).

---

## LLM providers

| Key | Provider | Notes |
|---|---|---|
| `ollama` | Local Ollama | Dynamic catalogue; only available if `make up-ollama` and models are pulled |
| `zai` | ZAI (`glm-4.5-flash`) | Primary cloud LLM in the project author's setup |
| `openrouter` | OpenRouter | Curated catalogue |
| `openai` | OpenAI | Curated catalogue |

Default for tests and CI: none required — all LLM calls are mocked.

---

## CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

| Job | Trigger | What it does |
|---|---|---|
| `lint` | push + PR | ruff check, mypy |
| `test` | push + PR | pytest with postgres service, coverage upload |
| `docker-build` | push only | build + push to GHCR |
| `docker-smoke` | after docker-build | start api container, hit `/health` |

Secrets required in GitHub Actions:
- `GITHUB_TOKEN` — automatically provided (for GHCR push)
- No other secrets needed for lint/test jobs

---

## Key conventions

- Async throughout. All node functions, API handlers, and service methods are `async def`.
- Logging: always use `get_logger(__name__)` from `app.core.logging`. Never use `print`.
- Do not import from `app.db` at module level in agent/tool code — all DB access goes through the session manager or repository layer.
- Return types: `AgentResult.create_success(...)` / `AgentResult.create_error(...)` — never raise from `execute()`.
- The `SearchMemoryTool` is auto-invoked at the start of `OrchestratorAgent.execute()` to enrich the task with context from previous sessions. This is transparent to callers.

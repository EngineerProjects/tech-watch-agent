# tech-watch-agent

Plateforme de veille technologique multi-agents pour lancer des recherches, agréger des sources, produire des synthèses et livrer des rapports par API, exécution ponctuelle ou planification.

## Vue d’ensemble

Le projet combine plusieurs briques:
- un orchestrateur LangGraph qui planifie puis exécute les étapes de recherche
- un agent de deep research pour les tâches plus lourdes
- un pipeline newsletter historique encore disponible en mode `v1`
- une API FastAPI pour lancer, suivre et reprendre les sessions
- un stockage PostgreSQL + pgvector pour les articles, sessions et embeddings

## Fonctionnalités principales

- Orchestrateur `v2` avec workflow `plan -> research -> analysis -> synthesis -> email`
- Deep research avec sous-tâches parallèles et extraction de PDF
- Persistance de session avec `PlanVersion` et `SessionCheckpoint`
- Reprise de sessions interrompues via l’API
- Outils web et social via registry extensible
- Support multi-provider LLM: `openrouter`, `ollama`, `zai`, `openai`
- Fallback automatique des providers via `LLMHealthManager`
- Livraison email via Gmail
- Exécution locale ou Docker

## Stack

- Python 3.11+
- FastAPI
- LangGraph
- PostgreSQL + pgvector
- Redis
- SQLAlchemy + Alembic
- Docker Compose

## Démarrage rapide

### Prérequis

- Python 3.11+
- Docker et Docker Compose
- PostgreSQL avec extension `pgvector` si exécution hors Docker
- Redis si exécution hors Docker

### Configuration

Crée le fichier d’environnement à partir du template:

```bash
cp .env.example .env
```

Variables importantes:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/techwatch
DATABASE_SYNC_URL=postgresql://postgres:postgres@localhost:5433/techwatch

LLM_PROVIDER=openrouter
LLM_API_KEY=
LLM_MODEL=

NEWSLETTER_TOPICS=AI news,Machine Learning breakthroughs,Tech startups

SENDER_EMAIL=
RECIPIENT_EMAILS=
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
```

Notes:
- en Docker, `.env` doit rester à la racine du dépôt
- les credentials Gmail ne sont pas montés par défaut dans les conteneurs
- pour Ollama depuis Docker, le conteneur peut joindre l’hôte via `host.docker.internal`

## Exécution avec Docker

Le compose principal est [`docker/docker-compose.yml`](docker/docker-compose.yml).

```bash
make up-build
```

Services disponibles:
- `postgres`
- `redis`
- `api`
- `once` via le profil `manual`
- `scheduler` via le profil `scheduler`

Commandes utiles:

```bash
make ps
make logs SERVICE=api
make doctor
make down
```

L’API est exposée sur `http://localhost:8000`.
La documentation OpenAPI est disponible sur `http://localhost:8000/docs`.

## Exécution locale

```bash
pip install -e .
alembic upgrade head
python -m app.main --mode api
```

Autres modes:

```bash
python -m app.main --mode once --no-email
python -m app.main --mode once --v1 --no-email
python -m app.main --mode schedule
python -m app.main --config-check
```

## Makefile

Le [`Makefile`](Makefile) centralise les commandes de dev, Docker, validation et nettoyage.

Commandes recommandées:

```bash
make help
make check
make test-unit
make test-integration
make lint
make typecheck
make db-history
make db-current
```

Nettoyage:

```bash
make clean
make clean-docker
make clean-docker-cache
make clean-system
make nuke
```

`make nuke` supprime les artefacts locaux et le cache Docker inutilisé. À utiliser volontairement.

## API

Routes principales:

- `GET /health`, `GET /status`, `GET /stats`
- `POST /orchestrator/run`, `POST /orchestrator/task`, `POST /orchestrator/schedule`, `GET /orchestrator/status`
- `POST /research`, `GET /research/history`
- `POST /newsletter/generate`, `POST /newsletter/generate/sync`, `GET /newsletter/history`, `GET /newsletter/stats`
- `GET /sessions`, `GET /sessions/interruptible`, `GET /sessions/{id}`, `GET /sessions/{id}/plan`, `GET /sessions/{id}/checkpoints`, `GET /sessions/{id}/checkpoint/latest`, `POST /sessions/{id}/resume`
- `GET /articles`, `GET /articles/{id}`
- `POST /users`, `GET /users/{id}`, `GET /users/{id}/topics`, `POST /users/{id}/topics`
- `GET /tools`, `GET /tools/{tool_name}`, `POST /tools/execute`
- `GET /llm/providers`, `GET /llm/providers/{name}`, `GET /llm/providers/{name}/health`, `POST /llm/providers/switch`

## Providers LLM

| Provider | Base URL par défaut | Modèle par défaut | Clé API |
|---|---|---|---|
| `openrouter` | `https://openrouter.ai/api/v1` | `openai/gpt-4.1-mini` | oui |
| `ollama` | `http://localhost:11434/v1` | `llama3.2` | non |
| `zai` | `https://api.z.ai/api/paas/v4` | `glm-4.7-flash` | oui |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | oui |

## Structure

```text
app/
  agents/         Agents et orchestration
  api/            Routes FastAPI
  config/         Chargement des settings
  db/             Modèles et accès base
  delivery/       Livraison email
  rag/            Vector store et recherche
  scheduler/      Exécution planifiée
  services/       Services métier
  tools/          Registry et outils
alembic/          Migrations
docker/           Dockerfile et compose
tests/            Tests unitaires et intégration
```

## Fichiers clés

- [`app/agents/orchestrator/nodes.py`](app/agents/orchestrator/nodes.py)
- [`app/services/session_manager.py`](app/services/session_manager.py)
- [`app/api/routers/sessions.py`](app/api/routers/sessions.py)
- [`app/services/llm/health.py`](app/services/llm/health.py)
- [`docker/Dockerfile`](docker/Dockerfile)
- [`docker/docker-compose.yml`](docker/docker-compose.yml)

## Développement

Le projet contient une suite de tests conséquente, avec un focus particulier sur l’orchestrateur et la persistance de session. Avant un changement large, la séquence la plus utile est généralement:

```bash
make lint
make typecheck
make test-unit
make test-integration
```

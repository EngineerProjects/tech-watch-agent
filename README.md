# tech-watch-agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-121212)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

**Plateforme de veille technologique multi-agents** pour planifier des recherches, agréger des sources, produire des synthèses et livrer des rapports via API, exécution ponctuelle ou scheduler.

> Un backend de veille pensé pour passer d'une idée de recherche à un rapport structuré, traçable et reprenable, sans recoller manuellement des résultats issus de dix outils différents.

## Points forts

| Point fort | Valeur |
|---|---|
| Orchestration | pipeline structuré avec planification, exécution, analyse et synthèse |
| Reprise | sessions persistées avec versions de plan et checkpoints |
| Recherche | outils web, social, PDF et deep research agent |
| Déploiement | exécution locale, Docker Compose et scheduler |

## Pourquoi ce projet

`tech-watch-agent` vise un cas simple à formuler mais pénible à industrialiser:

- surveiller plusieurs sources hétérogènes
- lancer des recherches plus profondes sur certains sujets
- conserver les résultats pour réutilisation et RAG
- produire des rapports propres et exploitables
- reprendre une session interrompue sans tout relancer

Le projet s’appuie sur un orchestrateur LangGraph, un système d’outils extensible, une API FastAPI, et une base PostgreSQL avec `pgvector`.

## En un coup d’œil

| Domaine | Ce qui est en place |
|---|---|
| Orchestration | workflow `plan -> research -> analysis -> synthesis -> email` |
| Agents | orchestrateur `v2`, deep research, pipeline newsletter `v1` conservé |
| Persistance | `SessionManager`, `PlanVersion`, `SessionCheckpoint` |
| Mémoire | compaction de mémoire de travail, articles complets conservés pour le RAG |
| Outils | registry extensible, outils web, social, PDF et delivery |
| LLM | `openrouter`, `ollama`, `zai`, `openai` avec fallback santé |
| API | endpoints pour sessions, orchestrateur, recherche, outils et providers |
| Runtime | local, Docker Compose, scheduler |

## Modes d'exécution

| Mode | Commande | Usage |
|---|---|---|
| API | `python -m app.main --mode api` | exposer les endpoints FastAPI |
| One-shot V2 | `python -m app.main --mode once --no-email` | lancer le pipeline orchestrateur |
| One-shot V1 | `python -m app.main --mode once --v1 --no-email` | utiliser le pipeline legacy |
| Scheduler | `python -m app.main --mode schedule` | lancer les exécutions planifiées |
| Docker | `make up-build` | démarrer la stack complète |

## Architecture

```mermaid
flowchart TD
    A[API / CLI / Scheduler] --> B[Orchestrator V2]
    B --> C[Planner]
    C --> D[Execution Plan]
    D --> E[Dispatcher]
    E --> F[Tool Registry]
    E --> G[Deep Research Agent]
    E --> H[Newsletter V1 Path]
    F --> I[Web Tools]
    F --> J[Social Tools]
    F --> K[PDF / Delivery Tools]
    E --> L[Collector]
    L --> M[Analyzer]
    M --> N[Synthesizer]
    N --> O[Email / API Result]
    B --> P[SessionManager]
    P --> Q[(PostgreSQL + pgvector)]
```

### Hiérarchie des agents

```text
Orchestrator (V2)
├── planner
├── dispatcher
├── collector
├── analyzer
├── synthesizer
├── Deep Research (sub-agent)
│   └── supervisor -> parallel researchers
└── Newsletter V1 (legacy path)
```

### Flux mémoire

```text
research results
  -> collector
  -> persist_articles()
  -> PostgreSQL (articles)
  -> vector store / embeddings
  -> synthesis
  -> persisted session + checkpoints
```

## Ce que le projet couvre

### Recherche et collecte

- recherche multi-source via registry d’outils
- exécution parallèle des étapes de recherche
- extraction de contenu web et PDF
- collecte persistée pour réutilisation ultérieure

### Analyse et restitution

- synthèse structurée en sortie
- livraison via API ou email
- conservation des résultats pour audit ou reprise
- séparation nette entre mémoire de travail et données articles

## Fonctionnalités principales

### Agents

- **Orchestrateur V2**: décompose la tâche, construit un plan, exécute les étapes, agrège les résultats puis génère une synthèse finale.
- **Deep Research**: prend les investigations plus coûteuses avec extraction de PDF et sous-recherche parallèle.
- **Newsletter V1**: reste disponible pour compatibilité et exécutions ciblées.

### Persistance et reprise

- persistance par phase de session
- historique de versions de plan
- checkpoints pour reprise d’exécution
- endpoints de reprise exposés par l’API

### Outils

- web search
- Scrapling
- Crawl4AI
- OpenAlex
- PDF downloader
- GitHub
- Reddit
- ArXiv
- YouTube
- outils email et prévisualisation

### LLM et résilience

- support de plusieurs providers
- health checks runtime
- fallback automatique géré par `LLMHealthManager`
- compatibilité `Z.ai` avec support du `reasoning_content`

## Stack technique

- **Python 3.11+**
- **FastAPI**
- **LangGraph**
- **PostgreSQL + pgvector**
- **Redis**
- **SQLAlchemy + Alembic**
- **Docker Compose**

## Démarrage rapide

### 1. Configuration

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
- `.env` doit rester à la racine du dépôt
- les credentials Gmail ne sont pas montés par défaut dans Docker
- depuis Docker, Ollama est joignable via `host.docker.internal`

### 2. Lancement avec Docker

Le compose principal est [`docker/docker-compose.yml`](docker/docker-compose.yml).

```bash
make up-build
```

Pour un démarrage plus explicite:

```bash
docker compose -f docker/docker-compose.yml up --build
```

Services disponibles:

| Service | Rôle |
|---|---|
| `postgres` | base PostgreSQL avec `pgvector` |
| `redis` | cache et support runtime |
| `api` | serveur FastAPI principal |
| `once` | exécution ponctuelle, profil `manual` |
| `scheduler` | exécution planifiée, profil `scheduler` |

Commandes utiles:

```bash
make ps
make logs SERVICE=api
make doctor
make down
```

Accès:
- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`

### 3. Lancement en local

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

Le [`Makefile`](Makefile) sert de point d’entrée unique pour le dev, les tests, Docker et le nettoyage.

### Boucle de dev

```bash
make help
make lint
make typecheck
make test-unit
make test-integration
make check
```

### Docker

```bash
make config
make build
make up-build
make logs SERVICE=api
make doctor
```

### Nettoyage

```bash
make clean
make clean-docker
make clean-docker-cache
make clean-system
make nuke
```

`make nuke` supprime les artefacts locaux et le cache Docker inutilisé. C’est volontairement agressif.

## Parcours recommandé

### Pour découvrir le projet

```bash
make up-build
make doctor
```

Puis ouvre `http://localhost:8000/docs`.

### Pour développer

```bash
make lint
make typecheck
make test-unit
make test-integration
```

### Pour repartir proprement

```bash
make clean
make clean-docker-cache
```

## API

### Health et observabilité

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | état global du service |
| `GET` | `/status` | statut applicatif |
| `GET` | `/stats` | statistiques exposées par l’API |

### Orchestrateur

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/orchestrator/run` | lance le pipeline principal |
| `POST` | `/orchestrator/task` | lance une tâche avec plus de contrôle |
| `POST` | `/orchestrator/schedule` | déclenche une planification |
| `GET` | `/orchestrator/status` | état de l’orchestrateur |

### Deep Research

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/research` | démarre une session de recherche approfondie |
| `GET` | `/research/history` | historique des recherches |

### Newsletter

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/newsletter/generate` | génération asynchrone |
| `POST` | `/newsletter/generate/sync` | génération synchrone |
| `GET` | `/newsletter/history` | historique |
| `GET` | `/newsletter/stats` | statistiques |

### Sessions

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/sessions` | liste les sessions |
| `GET` | `/sessions/interruptible` | liste les sessions reprenables |
| `GET` | `/sessions/{id}` | détail d’une session |
| `GET` | `/sessions/{id}/plan` | historique des versions de plan |
| `GET` | `/sessions/{id}/checkpoints` | checkpoints disponibles |
| `GET` | `/sessions/{id}/checkpoint/latest` | dernier checkpoint |
| `POST` | `/sessions/{id}/resume` | reprise d’une session interrompue |

### Données, outils et providers

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/articles` | liste les articles |
| `GET` | `/articles/{id}` | détail d’un article |
| `POST` | `/users` | crée un utilisateur |
| `GET` | `/users/{id}` | récupère un utilisateur |
| `GET` | `/users/{id}/topics` | topics utilisateur |
| `POST` | `/users/{id}/topics` | ajoute un topic |
| `GET` | `/tools` | liste les tools enregistrés |
| `GET` | `/tools/{tool_name}` | détail d’un tool |
| `POST` | `/tools/execute` | exécute un tool |
| `GET` | `/llm/providers` | liste les providers |
| `GET` | `/llm/providers/{name}` | détail d’un provider |
| `GET` | `/llm/providers/{name}/health` | healthcheck d’un provider |
| `POST` | `/llm/providers/switch` | switch runtime de provider |

## Providers LLM

| Provider | Base URL par défaut | Modèle par défaut | Clé API |
|---|---|---|---|
| `openrouter` | `https://openrouter.ai/api/v1` | `openai/gpt-4.1-mini` | oui |
| `ollama` | `http://localhost:11434/v1` | `llama3.2` | non |
| `zai` | `https://api.z.ai/api/paas/v4` | `glm-4.7-flash` | oui |
| `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | oui |

## Structure du projet

```text
app/
├── agents/
│   ├── base/
│   ├── orchestrator/
│   │   ├── nodes.py
│   │   ├── state.py
│   │   └── prompts.py
│   ├── deep_research/
│   └── newsletter/
├── api/
│   └── routers/
├── config/
├── core/
├── db/
├── delivery/
├── rag/
├── scheduler/
├── services/
│   ├── embedding/
│   └── llm/
├── tools/
│   ├── social/
│   └── web/
alembic/
docker/
tests/
```

### Fichiers clés

- [`app/agents/orchestrator/nodes.py`](app/agents/orchestrator/nodes.py)
- [`app/agents/orchestrator/prompts.py`](app/agents/orchestrator/prompts.py)
- [`app/services/session_manager.py`](app/services/session_manager.py)
- [`app/services/llm/health.py`](app/services/llm/health.py)
- [`app/api/routers/sessions.py`](app/api/routers/sessions.py)
- [`docker/Dockerfile`](docker/Dockerfile)
- [`docker/docker-compose.yml`](docker/docker-compose.yml)
- [`tests/test_orchestrator_integration.py`](tests/test_orchestrator_integration.py)

## Développement

Avant un changement large, la séquence la plus utile reste:

```bash
make lint
make typecheck
make test-unit
make test-integration
```

Pour l’environnement Docker:

```bash
make up-build
make doctor
make clean-docker-cache
```

## Feuille de route

- dashboard web pour piloter les sessions et consulter les rapports
- multi-utilisateurs avec auth, topics et permissions
- optimisation continue de l’image Docker et de la CI

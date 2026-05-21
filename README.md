# tech-watch-agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-121212)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

**Plateforme de veille technologique multi-agents** — de l'idée de recherche au rapport structuré, en passant par la collecte multi-source, l'analyse et la livraison.

---

## Ce que ça fait

- Reçoit une tâche ("veille sur les LLM open-source cette semaine")
- Construit un plan de recherche automatiquement
- Interroge plusieurs sources en parallèle (web, arXiv, GitHub, Reddit, YouTube, PDF…)
- Analyse, synthétise et produit un rapport structuré
- Livre par email ou rend disponible via API / dashboard
- Conserve tout en base (sessions, articles, checkpoints) pour reprise et RAG

---

## Démarrage rapide

### Prérequis

- Docker Compose
- Une instance PostgreSQL avec pgvector accessible (voir `docker/env.docker`)
- Un fichier `.env` à la racine (copier depuis `docker/env.docker`)

### Lancement

```bash
make up-build
```

Accès :
- Frontend React/Vite : `http://localhost:3000`
- Dashboard legacy FastAPI/Jinja : `http://localhost:8000/ui`
- API docs : `http://localhost:8000/docs`
- Health : `http://localhost:8000/health`

### Services Docker

| Service | Rôle | Profil |
|---|---|---|
| `redis` | cache et runtime | toujours actif |
| `api` | serveur FastAPI + dashboard | toujours actif |
| `once` | exécution ponctuelle | `manual` |
| `scheduler` | exécution planifiée | `scheduler` |

> La base de données PostgreSQL n'est pas dans le compose — le projet se connecte à une instance externe via `host.docker.internal`. Configurer `DATABASE_URL` dans `.env`.

### Variables importantes

```env
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/techwatch
DATABASE_SYNC_URL=postgresql://user:password@host:5432/techwatch

LLM_PROVIDER=ollama          # openrouter | ollama | zai | openai
LLM_MODEL=llama3.2
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_API_KEY=

NEWSLETTER_TOPICS=AI news,Machine Learning,Tech startups
SENDER_EMAIL=your@email.com
RECIPIENT_EMAILS=dest@email.com
```

### Lancement local (sans Docker)

```bash
pip install -e .
alembic upgrade head
python -m app.main --mode api
```

Autres modes :

```bash
python -m app.main --mode once --no-email
python -m app.main --mode once --v1 --no-email
python -m app.main --mode schedule
```

---

## Architecture

```mermaid
flowchart TD
    A[Dashboard / API / Scheduler] --> B[Orchestrator V2]
    B --> C[Planner]
    C --> D[Plan d'exécution]
    D --> E[Dispatcher]
    E --> F[Tool Registry]
    E --> G[Deep Research Agent]
    F --> H[Web / Social / PDF / Email]
    E --> I[Collector]
    I --> J[Analyzer]
    J --> K[Synthesizer]
    K --> L[Rapport final]
    B --> M[SessionManager]
    M --> N[(PostgreSQL + pgvector)]
```

```text
Orchestrator V2
├── planner
├── dispatcher
│   ├── Tool Registry  (web, social, PDF, email…)
│   └── Deep Research  (supervisor → researchers parallèles)
├── collector
├── analyzer
├── synthesizer
└── Newsletter V1      (pipeline legacy conservé)
```

---

## Providers LLM

| Provider | Modèle par défaut | Clé API |
|---|---|---|
| `openrouter` | `openai/gpt-4.1-mini` | oui |
| `ollama` | `llama3.2` | non |
| `zai` | `glm-4.7-flash` | oui |
| `openai` | `gpt-4o-mini` | oui |

---

## API

### Orchestrateur

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/orchestrator/run` | lance le pipeline principal |
| `POST` | `/orchestrator/task` | lance une tâche avec contrôle fin |
| `GET` | `/orchestrator/status` | état courant |

### Sessions

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/sessions` | liste des sessions |
| `GET` | `/sessions/{id}` | détail et rapport |
| `GET` | `/sessions/{id}/plan` | versions de plan |
| `GET` | `/sessions/{id}/checkpoints` | checkpoints |
| `POST` | `/sessions/{id}/resume` | reprise |

### Newsletter

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/newsletter/generate` | génération asynchrone |
| `POST` | `/newsletter/generate/sync` | génération synchrone |
| `GET` | `/newsletter/history` | historique |

### Outils et providers

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/tools` | liste les outils enregistrés |
| `POST` | `/tools/execute` | exécute un outil |
| `GET` | `/llm/providers` | liste les providers |
| `POST` | `/llm/providers/switch` | switch runtime |

---

## Makefile

```bash
make help           # liste toutes les commandes

# Dev
make lint
make typecheck
make test-unit
make test-integration
make check          # lint + typecheck + tests

# Docker
make up-build
make logs SERVICE=api
make doctor
make down

# Nettoyage
make clean
make clean-logs
make nuke           # supprime tout (artefacts locaux + cache Docker)
```

---

## Structure

```text
app/
├── agents/
│   ├── orchestrator/   # pipeline principal (nodes, state, prompts)
│   ├── deep_research/
│   └── newsletter/
├── api/
│   └── routers/
├── dashboard/          # router HTMX + Jinja2
├── templates/          # pages et partials HTML
├── config/
├── db/
├── delivery/           # Gmail client, renderer, service unifié
├── rag/
├── scheduler/
├── services/
│   ├── embedding/
│   └── llm/
└── tools/
    ├── social/
    └── web/
alembic/
docker/
.volumes/               # données runtime (logs, redis) — non versionné
tests/
```

---

## Feuille de route

- refonte du frontend dashboard (UI plus lisible, meilleure ergonomie)
- multi-utilisateurs avec auth et topics par user (usage interne, non prioritaire)
- durcissement CI et optimisation image Docker

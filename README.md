# tech-watch-agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-121212)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![CI](https://github.com/EngineerProjects/tech-watch-agent/actions/workflows/ci-python.yml/badge.svg)

Plateforme de veille technologique multi-agents : planification intelligente, collecte multi-source, synthèse structurée, déduplication inter-sessions, livraison email par profils programmés.

![Architecture](docs/captures/image.png)

---

## Cibles UI

<table>
  <tr>
    <td width="50%"><img src="docs/cibles/Accueil.png" alt="Accueil" /></td>
    <td width="50%"><img src="docs/cibles/Sessions.png" alt="Sessions" /></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/cibles/Session_en_cours.png" alt="Session en cours" /></td>
    <td width="50%"><img src="docs/cibles/Newsletter.png" alt="Newsletter" /></td>
  </tr>
</table>

---

## Vue d'ensemble

`tech-watch-agent` orchestre un pipeline de veille complet :

- définition de tâches ad hoc ou de profils récurrents,
- génération d'un plan de recherche enrichi par la mémoire des sessions passées,
- exécution parallèle d'outils web, académiques et code,
- déduplication des articles déjà connus entre sessions,
- synthèse d'un rapport structuré,
- validation humaine optionnelle avant synthèse (mode interactif),
- persistance complète des sessions, sources, steps et mémoire vectorielle,
- livraison par email avec groupes de destinataires réutilisables.

---

## Fonctionnalités principales

**Orchestration**
- Pipeline multi-agents avec LangGraph : supervisor → planner → dispatcher → collector → validator → synthesizer → emailer
- Planner enrichi par la mémoire vectorielle : évite de répéter les angles déjà couverts dans les sessions précédentes
- Mode interactif : pause après la collecte, approbation ou rejet humain avant synthèse
- Création de session avec ID stable avant le démarrage du flux SSE

**Recherche**
- `free_search` — chemin gratuit/self-hosted via SearXNG
- `web_search` — providers API activés (Tavily, Exa, LangSearch…)
- `research_search` — mode académique et code avec parallélisation propre
- Déduplication inter-sessions : les articles déjà persistés sont déprioritisés, les nouvelles sources remontent

**Profils et planification**
- Watch Profiles : sujet, topics, profondeur, format, langue, groupes email associés
- Scheduler persistant via APScheduler + PostgreSQL : `weekly`, `monthly`, `once`, `custom`
- Exécution immédiate possible depuis l'interface

**Livraison**
- Transport Gmail configurable dans l'UI (OAuth)
- Groupes d'emails réutilisables rattachés aux profils
- Newsletter unifiée : utilise le même pipeline orchestrateur (plan → recherche → synthèse → envoi)

**Interface**
- SPA React avec streaming SSE en temps réel
- Pages : Sessions, Watch Profiles, Email Groups, Newsletter, Sources, Settings
- Streaming avec keepalive, affichage du plan d'exécution en direct, banner d'approbation humaine

**Qualité**
- 200 tests automatisés (pytest-asyncio strict mode)
- CI Python (ruff + pytest) et CI Frontend (tsc + vite build) indépendants
- Stack PostgreSQL uniquement (Redis retiré)

---

## Démarrage rapide

### Prérequis

- Docker Compose
- Un fichier `.env` à la racine pour surcharger les valeurs par défaut (optionnel)

Le bootstrap minimal est dans `docker/env.docker`.

### Lancer la stack

```bash
make up
```

Accès principaux :

| URL | Service |
|---|---|
| `http://localhost:3000` | Frontend React |
| `http://localhost:8000` | API FastAPI |
| `http://localhost:8000/docs` | Documentation API interactive |
| `http://localhost:8000/health` | Healthcheck |

### Services Docker

| Service | Rôle | Démarrage |
|---|---|---|
| `postgres` | PostgreSQL + pgvector | `make up` |
| `searxng` | Moteur de recherche self-hosted | `make up` |
| `api` | API FastAPI | `make up` |
| `frontend` | SPA React (nginx) | `make up` |
| `once` | Exécution ponctuelle | `make up-once` |
| `scheduler` | Profils programmés | `make up-scheduler` |
| `ollama` | LLM local (optionnel) | `make up-ollama` |

---

## Configuration

### Bootstrap `.env`

```env
POSTGRES_DB=techwatch
POSTGRES_USER=techwatch
POSTGRES_PASSWORD=techwatch
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://techwatch:techwatch@postgres:5432/techwatch
DATABASE_SYNC_URL=postgresql://techwatch:techwatch@postgres:5432/techwatch

FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ADMIN_API_TOKEN=change-me

# Chiffrement des secrets runtime
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
CONFIG_ENCRYPTION_KEY=

# Premier boot optionnel avant configuration via l'UI
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=
LLM_API_KEY=
```

### Configuration runtime (via l'UI)

Tout le reste se configure dans `Settings` et est persisté en base :

- Provider LLM, modèle principal et fallbacks
- Provider d'embeddings
- Clés API search (Tavily, Exa, ArXiv…)
- Gmail OAuth (client + token)
- Groupes d'emails et profils de veille

Les secrets runtime sont **chiffrés** (Fernet), pas hashés.

---

## Architecture

```mermaid
flowchart TD
    UI["Frontend React"] --> API["FastAPI"]

    API --> CFG[("Config runtime DB")]
    API --> P[("Watch Profiles")]
    API --> G[("Email Groups")]
    API --> ORCH["Orchestrator"]

    ORCH --> PLAN["Planner\n(+ mémoire vectorielle)"]
    ORCH --> DISP["Dispatcher"]
    ORCH --> APPR["Human Approval\n(mode interactif)"]
    ORCH --> SYN["Synthesizer"]

    DISP --> FREE["free_search (SearXNG)"]
    DISP --> WEB["web_search (APIs)"]
    DISP --> RS["research_search"]
    DISP --> TOOLS["GitHub / PDF / Social"]

    SYN --> DELIV["ReportDeliveryService"]
    DELIV --> GMAIL["Gmail"]

    ORCH --> SM["SessionManager"]
    SM --> DB[("PostgreSQL + pgvector")]

    P --> SCHED["APScheduler\n(job store PostgreSQL)"]
    SCHED --> ORCH
```

```text
app/
├── agents/
│   ├── orchestrator/      pipeline principal (LangGraph)
│   ├── deep_research/     recherche approfondie
│   └── newsletter/        agent newsletter (legacy)
├── api/
│   └── routers/           sessions, profiles, orchestrator, newsletter…
├── config/                settings runtime + chiffrement
├── core/                  modèles, brief, context
├── db/                    models SQLAlchemy, repositories, migrations
├── delivery/              transport Gmail
├── rag/                   VectorStore pgvector
├── scheduler/             APScheduler persistent
├── services/              streaming SSE, session manager, article ranker
└── tools/                 web, academic, social, memory, PDF…
```

---

## Providers LLM

| Provider | Découverte modèles | Clé API |
|---|---|---|
| `ollama` | dynamique | non |
| `openrouter` | catalogue curé | oui |
| `zai` | catalogue curé | oui |
| `openai` | catalogue curé | oui |

Les embeddings suivent le même principe (pgvector avec modèles détectés ou configurés).

---

## API principale

### Orchestrateur

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/orchestrator/sessions` | Crée une session, retourne l'ID stable |
| `GET` | `/orchestrator/stream` | Flux SSE temps réel |
| `POST` | `/orchestrator/sessions/{id}/approve` | Approuve et reprend après pause |
| `POST` | `/orchestrator/sessions/{id}/reject` | Rejette et marque comme échoué |
| `POST` | `/orchestrator/run` | Exécution synchrone complète |
| `GET` | `/orchestrator/status` | État courant |

### Sessions

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/sessions` | Liste des sessions |
| `GET` | `/sessions/{id}` | Détail, steps, rapport |
| `DELETE` | `/sessions/{id}` | Suppression |

### Watch Profiles

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/watch-profiles/` | Liste des profils |
| `POST` | `/watch-profiles/` | Création |
| `PATCH` | `/watch-profiles/{id}` | Mise à jour |
| `POST` | `/watch-profiles/{id}/run` | Exécution immédiate |
| `DELETE` | `/watch-profiles/{id}` | Suppression |

### Email Groups

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/email-groups/` | Liste |
| `POST` | `/email-groups/` | Création |
| `PATCH` | `/email-groups/{id}` | Mise à jour |
| `DELETE` | `/email-groups/{id}` | Suppression |

### Providers et outils

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/llm/providers` | Catalogue providers + modèles |
| `POST` | `/llm/ollama/pull` | Pull d'un modèle Ollama |
| `GET` | `/tools` | Inventaire des tools |
| `POST` | `/tools/execute` | Exécution d'un tool |
| `PATCH` | `/config` | Mise à jour runtime |

---

## Makefile

```bash
make help          # liste des commandes disponibles
make build         # build des images Docker
make up            # stack complète (postgres, searxng, api, frontend)
make up-ollama     # avec Ollama local
make up-once       # exécution ponctuelle
make up-scheduler  # profils programmés
make down          # arrêt
make logs          # logs de tous les services
make api-logs      # logs de l'API uniquement
make soft-clean    # arrêt + suppression des conteneurs
make hard-clean    # suppression complète volumes + images
```

---

## Développement local sans Docker

```bash
# Installation avec uv (recommandé)
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"
source .venv/bin/activate

# Ou avec pip
pip install -e ".[dev]"

alembic upgrade head
python -m app.main --mode api
```

Frontend :

```bash
cd frontend
npm install
npm run dev     # dev server sur http://localhost:5173
npm run build   # build de production
```

Autres modes API :

```bash
python -m app.main --mode once --no-email
python -m app.main --mode schedule
```

---

## Tests

```bash
pytest tests/ -v
```

La suite de tests requiert PostgreSQL (pgvector). En CI, le service est fourni automatiquement. En local, pointez `DATABASE_URL` et `DATABASE_SYNC_URL` vers votre instance.

---

## Notes de déploiement

- `alembic upgrade head` est la seule voie d'évolution du schéma.
- Le frontend appelle l'API via `/api` derrière nginx en production.
- En production, définissez explicitement `ADMIN_API_TOKEN`, `CONFIG_ENCRYPTION_KEY` et `CORS_ORIGINS`.
- SearXNG fait partie de la stack Docker du projet.
- Ollama reste optionnel et volontairement séparé du chemin par défaut.

---

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) — workflow de contribution
- [SECURITY.md](SECURITY.md) — remontée responsable des vulnérabilités
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — règles de conduite

---

## Contribution

Les contributions sont bienvenues. Avant d'ouvrir une PR, lisez [CONTRIBUTING.md](CONTRIBUTING.md).

Les PRs vers `main` requièrent que les checks CI passent (Python lint + tests, Frontend build).

---

## Licence

Ce projet est distribué sous licence [Apache-2.0](LICENSE).

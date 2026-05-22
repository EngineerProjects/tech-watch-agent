# tech-watch-agent

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Orchestration-121212)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-336791?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Plateforme de veille technologique multi-agents: planification, collecte multi-source, synthèse, stockage persistant et livraison email pilotée par profils.

![Architecture cible](docs/captures/image.png)

---

## Cibles UI

<table>
  <tr>
    <td width="50%"><img src="docs/cibles/Accueil.png" alt="Cible Accueil" /></td>
    <td width="50%"><img src="docs/cibles/Sessions.png" alt="Cible Sessions" /></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/cibles/Session_en_cours.png" alt="Cible Session en cours" /></td>
    <td width="50%"><img src="docs/cibles/Newsletter.png" alt="Cible Newsletter" /></td>
  </tr>
</table>

---

## Vue d'ensemble

`tech-watch-agent` orchestre un pipeline de veille complet:

- définition d'une tâche ou d'un profil récurrent,
- génération d'un plan de recherche,
- exécution parallèle d'outils web, académiques et code,
- synthèse d'un rapport structuré,
- persistance des sessions, sources, steps et mémoire vectorielle,
- livraison optionnelle par email.

Le produit expose deux surfaces:

- un frontend React pour l'usage principal,
- un dashboard legacy FastAPI/Jinja conservé pour l'administration légère.

---

## Fonctionnalités principales

- Orchestrateur multi-agents avec planification et synthèse structurée.
- Recherche séparée par mode:
  - `free_search` pour le chemin gratuit/self-hosted via `SearXNG`
  - `web_search` pour les providers API activés
  - `research_search` pour les cas académiques et code
- Stockage PostgreSQL + `pgvector` pour sessions, sources, steps et mémoire sémantique.
- Configuration runtime via l'application, stockée en base et chiffrée si `CONFIG_ENCRYPTION_KEY` est présent.
- Profils de veille programmés avec groupes d'emails réutilisables.
- Frontend React, API FastAPI, frontend Dockerisé et stack locale autonome.

---

## Démarrage rapide

### Prérequis

- Docker Compose
- un fichier `.env` à la racine uniquement si vous voulez surcharger le bootstrap par défaut

Le bootstrap minimal fourni par le projet est dans `docker/env.docker`.

### Lancer la stack

```bash
make up
```

Accès principaux:

- Frontend React: `http://localhost:3000`
- API FastAPI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Dashboard legacy: `http://localhost:8000/ui`
- Healthcheck: `http://localhost:8000/health`

### Services Docker

| Service | Rôle | Démarrage |
|---|---|---|
| `postgres` | base PostgreSQL + `pgvector` | `make up` |
| `redis` | cache / runtime | `make up` |
| `searxng` | moteur de recherche gratuit/self-hosted | `make up` |
| `api` | API FastAPI + dashboard legacy | `make up` |
| `frontend` | SPA React servie par nginx | `make up` |
| `once` | exécution ponctuelle | `make up-once` |
| `scheduler` | profils programmés | `make up-scheduler` |
| `ollama` | optionnel, local-only | `make up-ollama` |

Par défaut, `ollama` n'est pas lancé pour garder une stack légère. Le provider peut rester sélectionnable dans l'application, mais le catalogue local n'existe que si `ollama` tourne réellement et contient des modèles installés.

---

## Configuration

### Ce qui reste dans `.env`

Le `.env` doit rester un bootstrap d'infrastructure et de sécurité:

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
CONFIG_ENCRYPTION_KEY=...

# Optionnel pour un premier boot avant configuration runtime via l'UI
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=
```

### Ce qui est configuré dans l'application

Le runtime normal se configure ensuite dans `Settings` et est sauvegardé en base:

- provider LLM, modèle principal et fallbacks,
- provider d'embeddings et modèle d'embedding,
- clés API search / lecture / providers spécialisés,
- Gmail OAuth client/token,
- paramètres newsletter par défaut,
- groupes d'emails et rattachement aux profils,
- options d'extraction / crawling.

Les secrets runtime doivent être **chiffrés**, pas hashés, car l'application doit pouvoir les relire pour fonctionner.

---

## Modèle produit

### Profils et planification

La planification vit au niveau des `watch_profiles`, pas dans une configuration globale.

Chaque profil porte:

- son sujet,
- ses topics,
- sa profondeur et son format,
- ses sources préférées,
- sa fréquence (`weekly`, `once`, `monthly`, `custom`),
- ses groupes d'emails associés.

### Email delivery

Le transport Gmail reste globalement configuré dans `Settings`, mais les destinataires opérationnels sont maintenant portés par des groupes réutilisables.

Flux cible:

1. configuration Gmail dans `Settings`,
2. création de groupes dans `Email Groups`,
3. rattachement de groupes à un profil,
4. exécution d'un profil,
5. résolution automatique des destinataires de ce profil au moment de l'envoi.

---

## Architecture

```mermaid
flowchart TD
    UI["Frontend React / Dashboard legacy"] --> API["FastAPI API"]

    API --> CFG[("AppConfig runtime DB")]
    API --> P[("Watch Profiles")]
    API --> G[("Email Groups")]
    API --> ORCH["Orchestrator V2"]

    ORCH --> PLAN["Planner"]
    ORCH --> DISP["Dispatcher"]

    DISP --> FREE["free_search"]
    DISP --> WEB["web_search"]
    DISP --> RS["research_search"]
    DISP --> TOOLS["Social / PDF / Readers / GitHub"]

    ORCH --> SYN["Synthesizer"]
    SYN --> DELIV["ReportDeliveryService"]
    DELIV --> GMAIL["GmailDeliveryClient"]

    ORCH --> SM["SessionManager"]
    SM --> DB[("PostgreSQL + pgvector")]

    P --> G
    FREE --> SX["SearXNG"]
    WEB --> APIS["API search providers"]
    RS --> ACAD["Academic + code providers"]
```

```text
Frontend / API
├── Settings                -> configuration runtime DB
├── Email Groups            -> groupes de destinataires réutilisables
├── Sessions / Profiles     -> création, planification, rattachement email
└── Orchestrator V2
    ├── planner
    ├── dispatcher
    │   ├── free_search
    │   ├── web_search
    │   ├── research_search
    │   └── autres outils spécialisés
    ├── synthesizer
    ├── delivery
    └── persistence
```

---

## Providers LLM et embeddings

### LLM

| Provider | Découverte | Clé API |
|---|---|---|
| `ollama` | dynamique uniquement | non |
| `openrouter` | catalogue curé | oui |
| `zai` | catalogue curé | oui |
| `openai` | catalogue curé | oui |

`ollama` n'est jamais hardcodé côté catalogue. S'il n'y a aucun modèle local, le catalogue est vide.

### Embeddings

Les embeddings suivent le même principe:

- modèles curés pour `openai` et `openrouter`,
- support `z.ai` si configuré,
- détection dynamique pour `ollama`.

---

## Recherche

### `free_search`

Chemin gratuit et auto-hébergé via `SearXNG`.

### `web_search`

Agrège uniquement les providers API activés dans le runtime, par exemple:

- Tavily
- Exa
- LangSearch
- autres providers API disponibles

### `research_search`

Mode spécialisé pour sujets académiques et code:

- `SearXNG` en première couche de découverte,
- providers académiques ou code en renfort selon le focus,
- parallélisation possible sans mélanger les chemins gratuits et payants de façon opaque.

---

## API principale

### Orchestrateur

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/orchestrator/run` | lance le pipeline principal |
| `GET` | `/orchestrator/stream` | flux SSE pour exécution live |
| `POST` | `/orchestrator/task` | exécution avec contrôle fin |
| `GET` | `/orchestrator/status` | état courant |

### Sessions

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/sessions` | liste des sessions |
| `GET` | `/sessions/{id}` | détail, steps, rapport |
| `DELETE` | `/sessions/{id}` | suppression |

### Watch profiles

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/watch-profiles/` | liste des profils |
| `POST` | `/watch-profiles/` | création |
| `PATCH` | `/watch-profiles/{id}` | mise à jour |
| `POST` | `/watch-profiles/{id}/run` | exécution immédiate |
| `DELETE` | `/watch-profiles/{id}` | suppression |

### Email groups

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/email-groups/` | liste des groupes |
| `POST` | `/email-groups/` | création |
| `GET` | `/email-groups/{id}` | détail |
| `PATCH` | `/email-groups/{id}` | mise à jour |
| `DELETE` | `/email-groups/{id}` | suppression |

### Providers et outils

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/llm/providers` | catalogue providers + modèles |
| `POST` | `/llm/ollama/pull` | pull d'un modèle Ollama |
| `GET` | `/tools` | inventaire des tools |
| `POST` | `/tools/execute` | exécution d'un tool |
| `PATCH` | `/config` | mise à jour runtime |

---

## Makefile

```bash
make help
make build
make up
make up-ollama
make up-once
make up-scheduler
make down
make ps
make logs
make api-logs
make soft-clean
make hard-clean
```

---

## Développement local sans Docker

```bash
pip install -e ".[dev]"
alembic upgrade head
python -m app.main --mode api
```

Autres modes:

```bash
python -m app.main --mode once --no-email
python -m app.main --mode once --v1 --no-email
python -m app.main --mode schedule
```

---

## Structure du dépôt

```text
app/
├── agents/
│   ├── orchestrator/
│   ├── deep_research/
│   └── newsletter/
├── api/
│   └── routers/
├── dashboard/
├── templates/
├── config/
├── core/
├── db/
├── delivery/
├── rag/
├── scheduler/
├── services/
├── tools/
└── templates/
alembic/
docker/
frontend/
tests/
```

---

## Notes de déploiement

- `alembic upgrade head` reste la seule voie normale d'évolution du schéma.
- le frontend appelle l'API via `/api` derrière nginx.
- en production, définissez au minimum `ADMIN_API_TOKEN`, `CONFIG_ENCRYPTION_KEY` et `CORS_ORIGINS` explicitement.
- `SearXNG` fait partie de la stack du projet.
- `ollama` reste optionnel et volontairement séparé du chemin par défaut.

---

## État actuel

Le socle produit est maintenant aligné sur un modèle plus propre:

- configuration runtime via UI + DB,
- profils programmés comme centre de gravité du produit,
- livraison email par groupes réutilisables,
- recherche séparée par modes,
- stack Docker projet autonome pour `postgres`, `redis`, `searxng`, `api`, `frontend`.


---

## Documentation utile

- [CONTRIBUTING.md](CONTRIBUTING.md) : workflow de contribution
- [SECURITY.md](SECURITY.md) : remontée responsable des vulnérabilités
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) : règles de conduite du projet
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) : état actuel du projet
- [frontend/README.md](frontend/README.md) : notes spécifiques au frontend

---

## Contribution

Les contributions sont bienvenues, tant qu'elles respectent le modèle produit actuel et gardent frontend, API, persistance et documentation alignés.

Avant d'ouvrir une PR, lisez [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Licence

Ce projet est distribué sous licence [Apache-2.0](LICENSE).

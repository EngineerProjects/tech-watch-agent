# Migration Plan: `newsletter-agent` -> `tech-watch-agent` V1

## Scope

Objectif de cette étape: partir de `sources/newsletter-agent` pour obtenir une V1 exécutable, sans copier aveuglément tout le dépôt source.

## What exists in `newsletter-agent`

Le dépôt source est structuré autour de ces blocs:

- `main.py`: CLI de lancement.
- `config.py`: configuration centralisée via variables d'environnement.
- `scheduler/newsletter_scheduler.py`: orchestration crawl -> agents -> email.
- `crawlers/web_crawler.py`: récupération d'articles via Crawl4AI, recherche DuckDuckGo, parsing HTML et RSS.
- `agents/newsletter_agents.py`: pipeline LangGraph à 4 étapes.
- `agents/llm_client.py`: client OpenRouter HTTP.
- `email_service/gmail_client.py`: envoi Gmail + rendu HTML.
- `api/fastapi_server.py`: API/dashboard minimal.
- `utils/logger.py`: logging.
- `docker/`: image et compose basiques.
- `tests/`: tests unitaires partiels.

## Issues in the source repo

Le dépôt de référence est utile, mais ne doit pas être recopié tel quel:

- Configuration non typée et mutable via variables de classe.
- Couplage fort entre scheduler, crawl, agents et email.
- Client LLM spécialisé OpenRouter au lieu d'une abstraction OpenAI-compatible.
- API FastAPI avec état global en mémoire.
- HTML d'email, logique Gmail et authentification dans une seule classe.
- `web_crawler.py` mélange recherche, crawl, parsing, scoring, RSS et fallback HTTP.
- Dépendances importées inutilement ou incohérences:
  - `langchain.schema` importé mais inutilisé dans `agents/newsletter_agents.py`
  - `json` importé mais inutilisé
  - `crawl4ai` symbols inutilisés (`LLMConfig`, `LLMExtractionStrategy`)
  - `_extract_content_from_url()` utilise `requests` sans import local
- Le scheduler repose sur `schedule`, acceptable en V1 CLI, mais pas suffisant comme orchestration long terme.
- Les tests vérifient surtout des mocks et ne couvrent pas une exécution bout en bout.

## Copy strategy

On distingue trois catégories.

### 1. Copy concept, rewrite implementation

Ces fichiers sont utiles comme base fonctionnelle, mais seront réécrits proprement dans `app/`:

- `sources/newsletter-agent/config.py`
  - À transformer en settings typés Pydantic dans `app/config/settings.py`.
- `sources/newsletter-agent/agents/llm_client.py`
  - À transformer en client LLM générique OpenAI-compatible dans `app/services/llm.py`.
- `sources/newsletter-agent/agents/newsletter_agents.py`
  - À transformer en graphe LangGraph modulaire dans `app/agents/newsletter/graph.py`.
- `sources/newsletter-agent/crawlers/web_crawler.py`
  - À découper en `app/tools/web/search.py`, `app/tools/web/crawl.py`, `app/services/article_ranker.py`, `app/services/article_ingestion.py`.
- `sources/newsletter-agent/email_service/gmail_client.py`
  - À découper en `app/delivery/gmail_client.py` et `app/delivery/newsletter_renderer.py`.
- `sources/newsletter-agent/scheduler/newsletter_scheduler.py`
  - À transformer en orchestration V1 dans `app/scheduler/service.py`.
- `sources/newsletter-agent/api/fastapi_server.py`
  - À réimplémenter en API propre dans `app/api/main.py` avec endpoints simples.
- `sources/newsletter-agent/main.py`
  - À transformer en point d'entrée projet dans `app/main.py`.
- `sources/newsletter-agent/utils/logger.py`
  - À transformer en logging réutilisable dans `app/core/logging.py`.

### 2. Copy with adaptation

Ces éléments peuvent être repris presque tels quels, avec nettoyage léger:

- `sources/newsletter-agent/.env.example`
  - Base utile pour notre `.env.example`, renommée et normalisée.
- `sources/newsletter-agent/docker/Dockerfile`
  - Bonne base minimale, à adapter au nouveau packaging.
- `sources/newsletter-agent/docker/docker-compose.yml`
  - À simplifier puis étendre plus tard avec Postgres, pgvector et Redis.
- Idée de template newsletter HTML de `email_service/gmail_client.py`
  - À reprendre conceptuellement, pas en copié-collé direct.
- Cas de tests de `tests/test_agents.py` et `tests/test_crawler.py`
  - À réécrire sur la nouvelle structure.

### 3. Do not copy

Ces éléments ne doivent pas être migrés tels quels:

- `sources/newsletter-agent/logs/`
  - Données d'exécution, pas du code.
- `sources/newsletter-agent/setup.py`
  - Le projet cible sera piloté par `pyproject.toml`.
- `sources/newsletter-agent/__init__.py` vides
  - Sans valeur directe.
- Dashboard HTML inline de `api/fastapi_server.py`
  - Remplacé par endpoints JSON + page minimale si nécessaire.
- État global en mémoire de l'API
  - À éviter.

## Exact V1 mapping

Mapping cible pour la prochaine étape de migration:

- `app/config/settings.py`
  - Source: `config.py`
  - Rôle: paramètres typés, parsing des listes, validation de base.
- `app/core/logging.py`
  - Source: `utils/logger.py`
  - Rôle: config logging commune.
- `app/services/llm.py`
  - Source: `agents/llm_client.py`
  - Rôle: client HTTP OpenAI-compatible.
- `app/agents/newsletter/state.py`
  - Source: `agents/newsletter_agents.py`
  - Rôle: état typé du workflow.
- `app/agents/newsletter/nodes.py`
  - Source: `agents/newsletter_agents.py`
  - Rôle: researcher, analyst, editor.
- `app/agents/newsletter/graph.py`
  - Source: `agents/newsletter_agents.py`
  - Rôle: assemblage LangGraph.
- `app/tools/web/search.py`
  - Source: `crawlers/web_crawler.py`
  - Rôle: découverte d'URLs.
- `app/tools/web/crawl.py`
  - Source: `crawlers/web_crawler.py`
  - Rôle: crawl Crawl4AI + fallback HTTP.
- `app/services/article_ranker.py`
  - Source: `crawlers/web_crawler.py`
  - Rôle: filtrage/scoring de pertinence.
- `app/services/article_service.py`
  - Source: `crawlers/web_crawler.py`
  - Rôle: orchestration fetch topic -> articles.
- `app/delivery/newsletter_renderer.py`
  - Source: `email_service/gmail_client.py`
  - Rôle: conversion markdown -> HTML email.
- `app/delivery/gmail_client.py`
  - Source: `email_service/gmail_client.py`
  - Rôle: authentification et envoi Gmail.
- `app/scheduler/service.py`
  - Source: `scheduler/newsletter_scheduler.py`
  - Rôle: run once + planification simple.
- `app/api/main.py`
  - Source: `api/fastapi_server.py`
  - Rôle: endpoints de santé, déclenchement manuel, statut.
- `app/main.py`
  - Source: `main.py`
  - Rôle: CLI de démarrage.

## V1 functional boundary

Pour garder la V1 exécutable rapidement, le périmètre doit être:

- génération ponctuelle `run once`
- scheduling simple
- collecte web limitée mais robuste
- pipeline LangGraph court
- rendu newsletter HTML
- envoi Gmail
- API FastAPI minimale

Ce qui attendra l'étape suivante:

- Postgres + pgvector
- Redis
- Celery ou Temporal
- deep research
- RAG
- dashboard riche
- plugins spécialisés GitHub/arXiv/HN/Reddit/RSS/YouTube

## Recommendation for the next implementation step

Migrer d'abord le socle exécutable suivant:

1. `settings.py`
2. `logging.py`
3. `llm.py`
4. `article_service` + outils web
5. `newsletter` LangGraph
6. `newsletter_renderer`
7. `gmail_client`
8. `scheduler/service.py`
9. `app/main.py`
10. tests unitaires minimaux sur settings, renderer et ranking

Cette séquence permet d'obtenir une V1 CLI fonctionnelle avant d'ajouter l'API.

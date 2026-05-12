# Tech Watch Agent

## But du projet

Plateforme de veille technologique automatisée basée sur des agents pour:
- planifier des recherches
- interroger plusieurs outils web et social
- analyser et synthétiser les résultats
- persister les sessions et les articles
- livrer des rapports via API, exécution ponctuelle ou scheduler

## État actuel

### Implémenté

- Orchestrateur `v2` avec workflow `plan -> research -> analysis -> synthesis -> email`
- Agent de deep research exploitable depuis l’orchestrateur
- Pipeline newsletter `v1` conservé pour compatibilité
- `AgentRegistry` et pattern agent-as-tool
- Persistance de session par phase avec `SessionManager`
- Versioning de plan avec `PlanVersion`
- Resume de session avec `SessionCheckpoint`
- Memory compaction limitée à la mémoire de travail
- Support LLM multi-provider: `openrouter`, `ollama`, `zai`, `openai`
- `LLMHealthManager` avec fallback automatique
- Registry d’outils extensible
- Outils web, social et delivery déjà branchés
- API FastAPI avec endpoints pour orchestrateur, sessions, recherche, outils et providers
- Stack Docker opérationnelle avec `Dockerfile`, `docker-compose` et CI

### Contraintes importantes

- ne pas faire de refactor destructif sans raison claire
- garder l’architecture modulaire
- privilégier un code typé, testable et exploitable en production
- ne jamais compacter les articles stockés pour le RAG
- faire des commits ciblés avant les changements importants

## Priorités probables

- dashboard web pour piloter les sessions et consulter les rapports
- multi-utilisateurs avec auth, topics et permissions
- durcissement progressif de la chaîne Docker et de la CI

## Commandes utiles

```bash
make help
make check
make test-unit
make test-integration
make up-build
make doctor
make clean
make nuke
```

Exécution directe:

```bash
python -m app.main --mode api
python -m app.main --mode once --no-email
python -m app.main --mode once --v1 --no-email
python -m app.main --mode schedule
```

## Fichiers de référence

- `app/agents/orchestrator/nodes.py`
- `app/agents/orchestrator/prompts.py`
- `app/services/session_manager.py`
- `app/services/llm/health.py`
- `app/api/routers/sessions.py`
- `docker/Dockerfile`
- `docker/docker-compose.yml`
- `tests/test_orchestrator_integration.py`

# Tech Watch Agent - Projet de veille technologique automatisée

## État du projet - Session en cours

### ✅ Déjà implémenté

#### Architecture Agents
- **AgentRegistry** : Registry centralisé pour gérer tous les agents
- **AgentAsTool** : Pattern pour utiliser les agents comme tools dans l'orchestrateur
- **Orchestrateur V2** : Workflow complet avec plan → research → analyse → synthesis → email
- **Deep Research** : Agent de recherche profonde (version simplifiée fonctionnelle)
- **Newsletter Agent** : Agent V1 legacy pour génération de newsletters

#### Session Persistence & Memory
- **SessionManager** : Persistence par phase (PLAN → RESEARCH → SYNTHESIS)
- **PlanVersion** : Audit trail pour toutes les révisions de plan
- **SessionCheckpoint** : Resume pour sessions interrompues
- **Memory Compaction** : Compacte la mémoire de travail (NOT articles pour RAG)

#### Configuration LLM
- **Multi-provider** : OpenRouter, Ollama, Z.ai, OpenAI
- **LLMHealthManager** : Auto-fallback automatique (Z.ai → Ollama → OpenRouter)
- **Fix parsing** : Support de `reasoning_content` pour les modèles Z.ai

#### Tests
- **145+ tests unitaires** - tous passent
- **25 integration tests** pour l'orchestrateur - tous passent

#### Intégrations outils
- **Tools registry** : Système de plugins extensible avec catégories
- **Web tools** : Search, Crawl4AI, Scrapling, OpenAlex, PDF Downloader
- **Social tools** : GitHub, Reddit, ArXiv, Research Papers, YouTube
- **Delivery tools** : EmailTool, EmailPreviewTool (Gmail)
- **Tools disponibles** : 15+ outils enregistrés

#### API Endpoints (25+)
- **Session Resume** : 7 endpoints pour gestion et resume de sessions
- **Orchestrator** : Run pipeline complet, gestion des tâches
- **Newsletter** : Génération et historique
- **Deep Research** : Sessions de recherche approfondie
- **LLM Providers** : Health checks et switching runtime

#### Prompts Enhancés
- **Claude Code-inspired** : Meilleure coordination et définitions de rôles
- **Strict JSON validation** : Plan mode strict avec 3 retry attempts
- **Valid tool names** : Liste explicite pour éviter les noms invalides
- **Conflict detection** : group_parallel_steps, analyze_step_dependencies

---

## Objectifs actuels

### En cours
- [ ] **Docker integration** : CI/CD avec GitHub Actions + Docker Compose

### Prochaines étapes (à définir après audit)
- [ ] Dashboard web - FastAPI interface pour sessions, reports, stats
- [ ] Multi-utilisateurs - Auth, topics personalisés, permissions

---

## Stack technique

- **Python 3.11+** / FastAPI / LangGraph
- **PostgreSQL** + pgvector / Redis
- **Docker** configuré
- **LLM**: Z.ai (gratuit) ou OpenRouter
- **CI/CD**: GitHub Actions

---

## Règles de travail

1. **Pas de refactor destructif** sans justification
2. **Commit systématique** avant chaque changement important
3. **Tests en premier** pour valider les fonctionnalités
4. **Architecture modulaire** à maintenir
5. **Code production-ready** : typé, documenté, testable
6. **Ne pas compacter les articles** : Garder les articles complets pour RAG

---

## Commandes de test

```bash
# Tests unitaires
pytest tests/ -v

# Tests integration orchestrateur
pytest tests/test_orchestrator_integration.py -v

# Test orchestrateur
python -c "
import asyncio
from app.agents import initialize_agents
from app.agents.orchestrator.agent import create_orchestrator_agent
initialize_agents()
asyncio.run(create_orchestrator_agent().execute({'task': 'Test', 'send_email': False}))
"
```

---

## Fichiers clés

| Fichier | Description |
|---------|-------------|
| `app/agents/orchestrator/nodes.py` | Orchestrateur avec session persistence |
| `app/services/session_manager.py` | Session management avec versioning/checkpoint |
| `app/api/routers/sessions.py` | Session resume API endpoints |
| `app/agents/orchestrator/prompts.py` | Prompts enhancés (Claude Code-inspired) |
| `app/services/llm/health.py` | LLM health manager avec auto-fallback |
| `tests/test_orchestrator_integration.py` | 25 integration tests |
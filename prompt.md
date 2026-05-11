# Tech Watch Agent - Projet de veille technologique automatisée

## État du projet - Session en cours

### ✅ Déjà implémenté

#### Architecture Agents
- **AgentRegistry** : Registry centralisé pour gérer tous les agents
- **AgentAsTool** : Pattern pour utiliser les agents comme tools dans l'orchestrateur
- **Orchestrateur V2** : Workflow complet avec plan → research → analyse → synthesis → email
- **Deep Research** : Agent de recherche profonde (version simplifiée fonctionnelle)
- **Newsletter Agent** : Agent V1 legacy pour génération de newsletters

#### Configuration LLM
- **Z.ai** : Provider gratuit configuré (glm-4.5-flash)
- **Fix parsing** : Support de `reasoning_content` pour les modèles Z.ai

#### Tests
- **18 tests unitaires** pour AgentRegistry - tous passent

#### Intégrations outils
- **Tools registry** : Système de plugins extensible
- **Web tools** : Search, Crawl4AI, Scrapling, OpenAlex
- **Social tools** : GitHub, Reddit, ArXiv, Research Papers
- **Tools disponibles** : 10+ outils enregistrés

---

## Objectifs actuels

### Phase 1: Audit et test
1. **Audit du code** : Analyser l'existant pour identifier les problèmes
2. **Tests réels** : Exécuter des workflows complets et observer le comportement
3. **Corrections** : Identifier et corriger les bugs/mauvaises pratiques
4. **Mettre à jour le readme** : Mettre à jour le readme avec les informations actuelles, ce qui est déjà fait, et ce qui reste à faire.
5. **Identifier les améliorations potentielles**

### Prochaines étapes (à définir après audit)
- Amélioration de la mémoire/RAG
- Multi-utilisateurs
- Workflows complexes
- Amélioration des prompts pour avoir de meilleures réponses.
- Dashboard web

---

## Stack technique

- **Python 3.11+** / FastAPI / LangGraph
- **PostgreSQL** + pgvector / Redis
- **Docker** configuré
- **LLM**: Z.ai (gratuit) ou OpenRouter

---

## Règles de travail

1. **Pas de refactor destructif** sans justification
2. **Commit systématique** avant chaque changement important
3. **Tests en premier** pour valider les fonctionnalités
4. **Architecture modulaire** à maintenir
5. **Code production-ready** : typé, documenté, testable

---

## Commande de test

```bash
# Test deep research simple
python -c "
import asyncio
from app.agents.deep_research.simple_agent import create_simple_deep_research_agent
asyncio.run(create_simple_deep_research_agent().execute({'query': 'Test'}))
"

# Test orchestrateur
python -c "
import asyncio
from app.agents import initialize_agents
from app.agents.orchestrator.agent import create_orchestrator_agent
initialize_agents()
asyncio.run(create_orchestrator_agent().execute({'task': 'Test', 'send_email': False}))
"
```
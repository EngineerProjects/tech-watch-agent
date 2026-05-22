# Prompt de travail : Audit Complet & Alignement de Déploiement

## Contexte du Projet
**Tech Watch Agent** est une plateforme de veille technologique automatisée multi-agents.
L'objectif est d'atteindre un niveau "Premium Cockpit" tant sur le plan fonctionnel que visuel.

### Capacités attendues :
- **Planification :** Générer un plan de recherche structuré à partir d'une tâche libre.
- **Collecte multi-sources :** Interroger arXiv, GitHub, Reddit, YouTube, PDF, Web (Exa, Tavily, SearXNG).
- **Analyse & Synthèse :** Transformer les données brutes en rapports markdown éditoriaux.
- **Persistance & RAG :** Sauvegarder les sessions, articles et checkpoints pour reprise et recherche sémantique.
- **Livraison :** API, Email (Newsletter) et Dashboard React temps réel (Streaming SSE).

---

## Tâche : Audit Exhaustif (Code, Architecture & DevOps)

Fais une analyse profonde de l'état actuel du dépôt et produis un rapport structuré.

### 1. Audit du Code & Incohérences
- **Backend (FastAPI/LangGraph) :** Les nœuds de l'orchestrateur sont-ils tous robustes ? Le streaming SSE est-il parfaitement câblé entre le nœud `synthesizer` et l'endpoint `/orchestrator/stream` ?
- **Frontend (React/TS) :** Les types sont-ils cohérents avec les modèles Pydantic du backend ? Y a-t-il du code mort ou des mocks qui devraient être remplacés par des appels API réels ?
- **Base de données :** Le schéma Alembic est-il synchrone avec les modèles SQLAlchemy ? La gestion de la mémoire sémantique (pgvector) est-elle opérationnelle ? et est ce que le schema est vraiment logique et penser pour fonctionner correctement en parfaite harmonie avec le frontend sur le long terme ?

### 2. Analyse du Déploiement (Docker)
Analyse le dossier `docker/` et les fichiers racine.
- **Intégration Frontend :** Propose une stratégie pour intégrer le nouveau dossier `frontend/` dans le `docker-compose.yml`.
- **Câblage :** Assure-toi que les variables d'environnement (API_URL) sont correctement passées entre le frontend et le backend en environnement conteneurisé.
- **Optimisation :** Dockerfile multi-stage pour le frontend (build vite + nginx/serve).

### 3. Identification des Manques (Gaps)
- Liste tout ce qui est **incomplet**.
- Liste tout ce qui est **simulé (mocké)** mais devrait être réel.
- Liste les **failles de sécurité** potentielles (gestion des secrets, CORS, etc.).

---

## Livrable attendu
Un rapport détaillé sous forme de tableau ou de liste à puces incluant :
1. **Statut de santé par module** (Agents, API, DB, UI, DevOps).
2. **Liste des incohérences prioritaires**.
3. **Plan d'amélioration technique** (Quoi faire et comment).
4. **Configuration Docker cible** pour un déploiement Full-Stack.

*Une fois cet audit terminé et validé, nous passerons à la phase de correction et de déploiement.*

# Contribuer à tech-watch-agent

Merci de vouloir contribuer.

Ce dépôt contient une plateforme de veille multi-agents avec un backend FastAPI, un frontend React, une stack Docker locale, un scheduler et un sous-système RAG. Avant d'ouvrir une PR, prenez le temps d'aligner vos changements avec l'état actuel du produit.

## Principes

- privilégier des changements ciblés et cohérents avec l'architecture existante ;
- éviter les régressions de contrat entre frontend, API et persistance ;
- documenter toute évolution de comportement visible ;
- ne jamais committer de secret, de token ou de fichier `.env` personnel.

## Préparer l'environnement

### Option 1 — Docker

```bash
make up
```

Services principaux :

- frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- docs OpenAPI: `http://localhost:8000/docs`

### Option 2 — local Python + frontend séparé

```bash
pip install -e ".[dev]"
alembic upgrade head
python -m app.main --mode api
```

Puis, dans `frontend/`:

```bash
npm install
npm run dev
```

## Structure à connaître

- `app/api/` : routes FastAPI et contrats API
- `app/agents/` : orchestrateur, deep research, newsletter
- `app/services/` : services d'infrastructure et de domaine
- `app/db/` : modèles et repositories SQLAlchemy
- `app/tools/` : moteurs de recherche, fetchers, outils sociaux et mémoire
- `frontend/src/` : interface React principale
- `docker/` : stack locale et images
- `tests/` : tests Python

## Règles de contribution

### 1. Faites évoluer les trois couches ensemble si nécessaire

Si vous changez un comportement produit, vérifiez l'impact sur :

- types frontend,
- schémas/routers API,
- modèles DB / repositories,
- documentation utilisateur ou contributeur.

### 2. Gardez la configuration runtime dans le bon périmètre

Le `.env` ne doit contenir que le bootstrap infrastructure/sécurité.
La configuration métier et les secrets runtime doivent vivre dans la DB runtime, via l'application.

### 3. Respectez le modèle produit actuel

- la planification vit dans les `watch_profiles` ;
- les destinataires email vivent dans les `email_groups` ;
- `Settings` configure le transport, pas les destinataires opérationnels ;
- `SearXNG` porte le chemin gratuit/self-hosted ;
- `web_search` et `research_search` gèrent les autres providers.

## Vérifications minimales avant PR

### Backend Python

```bash
python3 -m py_compile app/api/main.py app/api/routers/*.py app/db/*.py app/delivery/*.py app/scheduler/*.py
python3 -m pytest tests/test_delivery_service.py tests/test_api.py -q
```

### Frontend

```bash
cd frontend
bunx tsc --noEmit
npm run build
```

### Migration DB

Si vous touchez aux modèles SQLAlchemy :

- ajoutez une migration Alembic explicite,
- vérifiez que le code et la migration racontent la même histoire,
- ne réintroduisez pas de création implicite du schéma au runtime.

## Pull requests

Une bonne PR doit contenir :

- un objectif clair ;
- les impacts visibles ;
- les fichiers ou zones concernées ;
- les vérifications réellement exécutées ;
- les limites connues ou ce qui reste à faire.

## Documentation

Mettez à jour la documentation si vous changez :

- l'architecture produit,
- les flows utilisateurs,
- les endpoints,
- la configuration,
- le modèle de données,
- le déploiement.

## Sécurité

Ne publiez jamais :

- `.env`
- `.env.personal`
- tokens Gmail / OAuth
- clés API
- captures contenant des secrets

Si vous découvrez une faille ou un comportement sensible, ouvrez un ticket privé ou contactez le mainteneur avant de publier les détails.

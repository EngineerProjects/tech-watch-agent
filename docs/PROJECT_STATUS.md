# Project Status

Ce document décrit l'état actuel du projet tel qu'il est publié aujourd'hui.

## Produit

Le centre de gravité du produit est maintenant le frontend React.

Le modèle actuel est le suivant :

- `Settings` pilote la configuration runtime et les secrets chiffrés ;
- `watch_profiles` pilotent la planification ;
- `email_groups` pilotent les destinataires opérationnels ;
- l'orchestrateur V2 exécute la recherche, la synthèse et la livraison ;
- PostgreSQL + `pgvector` portent la persistance et la mémoire sémantique.

## Recherche

Le projet sépare la recherche par mode :

- `free_search` : chemin gratuit / self-hosted, centré sur `SearXNG`
- `web_search` : providers API activés
- `research_search` : cas académiques et code

## Delivery

Le transport email est configuré globalement, mais les destinataires ne sont plus globaux.

Flux normal :

1. config Gmail dans `Settings`
2. création de groupes dans `Email Groups`
3. rattachement des groupes à un profil
4. exécution manuelle ou programmée d'un profil
5. résolution des destinataires au runtime

## Déploiement local

La stack par défaut comprend :

- `postgres`
- `redis`
- `searxng`
- `api`
- `frontend`

`ollama` reste optionnel.

## Surface legacy

Le dashboard Jinja existe encore pour l'administration légère, mais ce n'est plus la surface principale du produit.

## Points d'attention connus

- le bundle frontend est encore monolithique et pourrait être découpé davantage ;
- certains tests plus larges restent dépendants d'environnements externes ;
- la surface legacy doit rester cohérente avec la logique produit moderne, sans redevenir la source de vérité UX.

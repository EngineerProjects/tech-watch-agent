# Tech Watch Agent

## But

Construire une plateforme personnelle de veille technologique automatisée multi-agents qui permet de:

- programmer plusieurs veilles récurrentes
- choisir leur cadence d'exécution
- lancer et suivre les runs automatiquement
- agréger sources, analyses et rapports
- persister les sessions, checkpoints et contexte pour reprise et RAG
- livrer les résultats via API, dashboard et newsletter

## Produit cible

Le produit doit ressembler à un cockpit premium de veille technologique, pas à un backoffice CRUD.

Les pages de référence sont dans:

- `/home/amiche/Projects/tech-watch-agent/docs/img/Accueil.png`
- `/home/amiche/Projects/tech-watch-agent/docs/img/Sessions.png`
- `/home/amiche/Projects/tech-watch-agent/docs/img/Session_en_cours.png`
- `/home/amiche/Projects/tech-watch-agent/docs/img/Topics.png`
- `/home/amiche/Projects/tech-watch-agent/docs/img/Newsletter.png`
- `/home/amiche/Projects/tech-watch-agent/docs/img/Paramètres.png`

Le brief UX de référence est:

- `/home/amiche/Projects/tech-watch-agent/docs/ux-dashboard-brief.md`

Le design system de référence est:

- `/home/amiche/Projects/tech-watch-agent/docs/design_system.md`

## UX attendue

### Sessions

La page `Sessions` doit être une grille de cards.
Chaque card représente une veille programmée avec:

- sujet ou nom
- statut
- cadence
- prochain run
- dernier run
- métriques utiles

Les statuts à rendre visibles:

- en cours
- programmée
- terminée
- échouée
- en pause si utile

### Détail d'une session

Quand on clique sur une session, on ouvre un workspace en 3 colonnes:

- gauche: timeline / plan d'exécution
- centre: rapport agent
- droite: sources et métadonnées

Si la session est en cours, l'interface doit supporter un vrai streaming:

- étape active en direct
- progression visible
- sources qui apparaissent au fil du run
- rapport markdown qui se construit progressivement

Le rendu markdown doit être beau, lisible et stable pendant le streaming.

## Direction technique

### Backend

Conserver et renforcer:

- FastAPI
- orchestrateur multi-agents
- scheduler
- base de données
- persistance des sessions et checkpoints
- outils de collecte, ranking, mémoire et newsletter

### Frontend

La direction cible est désormais:

- frontend séparé en `React + TypeScript + Vite`
- backend FastAPI conservé pour l'API et le streaming
- communication live via `SSE` ou `WebSocket`

Le frontend actuel `Jinja + Alpine + HTMX` peut dépanner, mais n'est plus la stack idéale pour atteindre la qualité cible sur les pages sessions et session detail.

## Priorités produit / tech

1. Stabiliser le coeur backend: sessions, reprise, mémoire, outils, persistance.
2. Exposer les bons endpoints API pour le dashboard cible.
3. Refondre le dashboard en commençant par `Sessions` puis `Session detail`.
4. Implémenter un vrai flux live pour timeline, sources et rapport streamé.
5. Refaire ensuite `Accueil`, `Topics`, `Newsletter` et `Paramètres`.

## Règle de travail

Chaque modification doit être évaluée contre cette question:

> Est-ce que cela rapproche réellement Tech Watch Agent du cockpit de veille montré dans les maquettes et décrit dans `docs/ux-dashboard-brief.md` ?

Si non, ce n'est probablement pas la priorité.

Toute décision frontend/UI doit aussi être cohérente avec `docs/design_system.md`.

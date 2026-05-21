Tu dois investiguer en profondeur le problème de recherche web dans Tech Watch Agent.

Contexte :
Les problèmes frontend principaux ont été corrigés, mais il reste un problème critique : les étapes de recherche retournent souvent 0 résultat ou échouent, notamment avec des erreurs comme :

ArXiv API error: 301

L’application donne l’impression que les outils de recherche en ligne ne fonctionnent pas correctement ou que l’intégration backend est mal câblée.

L’objectif de cette mission est de rendre la recherche web fiable, efficace et réellement exploitable.

Priorité principale :
Faire fonctionner SearXNG de manière sérieuse, stable et efficace comme provider de recherche par défaut, car il est gratuit et auto-hébergeable.

Objectif global :
Construire une couche de recherche robuste capable de :
- rechercher sur le web,
- récupérer des résultats pertinents,
- normaliser les résultats,
- dédupliquer les sources,
- extraire le contenu utile,
- scorer la pertinence,
- sauvegarder les sources,
- alimenter correctement les étapes de recherche,
- afficher les sources dans le frontend,
- produire des rapports fiables.

Chemins du projet à analyser :

/home/amiche/Projects/tech-watch-agent/app

/home/amiche/Projects/tech-watch-agent/frontend

/home/amiche/Projects/tech-watch-agent/docs

/home/amiche/Projects/tech-watch-agent/docs/errors  (ici tu verra la capture de l'erreur dont je parles)

Problèmes observés :
- Les recherches retournent souvent 0 résultat.
- Certaines étapes sont terminées mais sans contenu exploitable.
- Les sources ne sont pas toujours collectées.
- Les sources ne sont pas toujours persistées.
- Le rapport reste vide ou partiel si les providers ne retournent rien.
- L’erreur ArXiv API 301 indique probablement une mauvaise URL, une redirection non suivie, ou un client mal configuré.
- La recherche web semble fragile.
- Le système ne fait peut-être pas assez de fallback entre providers.
- Le backend ne distingue peut-être pas correctement :
  - aucun résultat,
  - erreur provider,
  - erreur parsing,
  - erreur extraction,
  - erreur persistance.
- L’utilisateur ne peut pas savoir pourquoi la recherche échoue.

Mission principale :
Auditer et corriger toute la couche de recherche.

Tu dois analyser :
- les providers actuellement disponibles,
- la configuration SearXNG,
- la configuration Tavily,
- la configuration ArXiv,
- la configuration Firecrawl ou Jina Reader si présents,
- le code de recherche web,
- le code de normalisation des résultats,
- le code de scraping/fetch,
- le code de persistance des sources,
- le code utilisé par les agents pendant les étapes de recherche.

SearXNG doit devenir le provider par défaut.

Tu dois vérifier :
- si SearXNG est installé ou non,
- si une instance SearXNG est attendue,
- quelle URL est utilisée,
- si l’API JSON de SearXNG est bien appelée,
- si le format=json est bien utilisé,
- si les résultats sont correctement parsés,
- si les moteurs SearXNG nécessaires sont actifs,
- si les erreurs HTTP sont bien gérées,
- si les timeouts sont corrects,
- si les headers sont corrects,
- si les redirections sont suivies,
- si les résultats sont normalisés dans le format interne de l’application.

Tu peux t’inspirer de projets open-source existants.

Clone et analyse notamment ce projet dans un dossier local dédié, par exemple :

/home/amiche/Projects/tech-watch-agent/sources

Projet à cloner :

https://github.com/ihor-sokoliuk/mcp-searxng

But :
Comprendre comment ce projet interagit efficacement avec SearXNG, puis réimplémenter les bonnes idées directement dans le backend Python de Tech Watch Agent.

Important :
Je ne veux pas forcément lancer plusieurs serveurs externes ou dépendre d’un MCP séparé si ce n’est pas nécessaire.

Le but est de :
- comprendre leur approche,
- récupérer les bonnes pratiques,
- adapter l’intégration proprement dans mon code Python,
- éviter une architecture inutilement complexe.

Tu peux aussi chercher et analyser d’autres projets open-source pertinents liés à :
- SearXNG Python integration,
- SearXNG search clients,
- web research agents,
- search result aggregation,
- Tavily fallback,
- Jina Reader extraction,
- Firecrawl extraction,
- LangChain/LangGraph web search tools,
- GPT Researcher search providers.

Mais l’objectif n’est pas de copier aveuglément.
L’objectif est de construire une intégration propre, fiable et adaptée au projet.

Architecture souhaitée :
Mettre en place une couche de recherche multi-provider.

Provider principal :
- SearXNG

Providers secondaires / fallback :
- Tavily
- Jina Reader
- Firecrawl si disponible
- ArXiv pour les papers plus tard
- autres providers déjà présents dans le projet

Comportement attendu :
- SearXNG est utilisé en premier.
- Si SearXNG échoue, le système essaie Tavily si configuré.
- Si plusieurs providers sont actifs, le système peut agréger les résultats.
- Les résultats sont dédupliqués par URL canonique.
- Les résultats sont scorés.
- Les résultats sont normalisés.
- Les erreurs sont loggées clairement.
- Les sources valides sont persistées.
- Le frontend peut afficher les sources collectées.

Il faut créer ou améliorer un format interne unique pour les résultats de recherche.

Exemple de structure attendue :

SearchResult:
- title
- url
- snippet
- source_provider
- source_type
- domain
- published_at
- relevance_score
- raw_metadata
- fetched_content
- markdown_content
- status
- error_message

Il faut aussi distinguer :
- search result,
- fetched source,
- extracted document,
- source utilisée dans le rapport.

Tu dois vérifier si la base de données permet réellement de stocker ces informations.

Si ce n’est pas le cas, propose ou implémente les changements nécessaires :
- table sources,
- table search_results si utile,
- relation session → sources,
- relation step → sources,
- statut de source,
- provider utilisé,
- contenu extrait,
- metadata,
- erreurs.

Focus scraping / fetch :
Après avoir obtenu des URLs via SearXNG, le système doit pouvoir récupérer le contenu utile.

Vérifie :
- comment les pages sont fetchées,
- si les redirections sont suivies,
- si les headers User-Agent sont corrects,
- si les timeouts sont raisonnables,
- si les erreurs 403/404/429 sont gérées,
- si le HTML est nettoyé,
- si le contenu est converti en Markdown,
- si le texte final est suffisamment propre pour être donné à l’agent.

Si nécessaire, propose une stratégie :
- fetch direct avec httpx,
- extraction avec BeautifulSoup / readability-lxml / trafilatura,
- fallback Jina Reader,
- fallback Firecrawl si configuré.

Priorité :
Avoir un système fiable, simple et efficace, pas une usine à gaz.

Audit ArXiv :
L’erreur ArXiv API error: 301 doit être investiguée.

Vérifie :
- l’URL utilisée,
- si l’endpoint arXiv est correct,
- si le client suit les redirections,
- si le protocole http/https est correct,
- si les headers sont corrects,
- si le parsing XML/Atom fonctionne,
- si les erreurs sont correctement propagées.

Mais les research papers seront traités en profondeur plus tard.
Pour l’instant, la priorité reste la recherche web générale via SearXNG.

Audit frontend :
Vérifie que le frontend affiche correctement :
- sources en cours de collecte,
- sources trouvées,
- sources utilisées,
- erreurs provider,
- aucun résultat,
- provider fallback,
- statut de chaque étape.

La sidebar Sources doit afficher les vraies sources persistées.

Elle doit pouvoir afficher :
- title,
- domain,
- provider,
- relevance,
- status,
- bouton ouvrir URL,
- erreur si la source n’a pas pu être fetchée.

Audit backend :
Vérifie :
- où les agents appellent les providers,
- si les providers retournent un format homogène,
- si les erreurs sont catchées trop silencieusement,
- si des exceptions vident les résultats,
- si les étapes sont marquées completed malgré un échec provider,
- si un step avec 0 résultat doit être completed, failed ou warning,
- si le statut global de session reflète vraiment les résultats.

Comportement attendu des statuts :
- Si un provider échoue mais qu’un fallback réussit : step completed avec warning éventuel.
- Si aucun provider ne retourne de résultat : step completed_empty ou warning, mais pas success trompeur.
- Si tous les providers échouent techniquement : step failed.
- Si des sources sont trouvées mais non fetchées : afficher partiellement les sources avec statut.
- Si des sources sont fetchées et analysées : les associer au step et à la session.

Logs attendus :
Ajouter des logs clairs pour chaque recherche :
- query utilisée,
- provider utilisé,
- nombre de résultats bruts,
- nombre de résultats après déduplication,
- nombre de sources fetchées,
- nombre de sources persistées,
- erreurs éventuelles,
- fallback utilisé.

Rapport attendu :
À la fin, produis un rapport clair avec :

- diagnostic du problème actuel,
- pourquoi les recherches retournent 0 résultat,
- pourquoi ArXiv retourne 301,
- état actuel de SearXNG,
- état actuel de Tavily,
- état actuel des autres providers,
- problèmes de configuration,
- problèmes de code,
- problèmes de persistance,
- problèmes d’affichage frontend,
- recommandations concrètes,
- fichiers à modifier,
- plan d’action.

Plan d’action attendu :
Propose puis implémente si possible :

1. Stabiliser SearXNG comme provider par défaut.
2. Ajouter une interface provider propre.
3. Normaliser les résultats.
4. Ajouter déduplication et scoring.
5. Ajouter fetch + extraction fiable.
6. Ajouter fallback Tavily/Jina/Firecrawl.
7. Sauvegarder toutes les sources.
8. Relier les sources aux steps et sessions.
9. Exposer les sources via API.
10. Afficher correctement les sources dans le frontend.
11. Ajouter logs et erreurs visibles.
12. Corriger l’erreur ArXiv 301.
13. Ajouter des tests simples pour vérifier que la recherche retourne réellement des résultats.

Important :
Ne te contente pas de patcher superficiellement.
Il faut comprendre pourquoi la recherche ne fonctionne pas réellement, puis construire une intégration robuste.

Priorité absolue :
Faire fonctionner SearXNG correctement, efficacement, et de manière intégrée au backend Python existant.

Le but final est que lorsqu’une session de veille est lancée :
- les requêtes produisent de vrais résultats,
- les sources apparaissent dans l’interface,
- les étapes ont du contenu,
- le rapport final est alimenté,
- et l’utilisateur peut faire confiance au pipeline de recherche.
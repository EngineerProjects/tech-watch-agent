# Open Source Readiness Audit

Date: 2026-05-22

## Résumé

Le projet est désormais dans un état publiable, avec une base technique cohérente et une documentation de contribution minimale.

Le dépôt est prêt pour une publication open source dans un état **beta**.

## Points forts actuels

- architecture produit clarifiée autour de `watch_profiles`, `email_groups` et `Settings` runtime ;
- séparation nette des modes de recherche (`free_search`, `web_search`, `research_search`) ;
- configuration runtime DB documentée ;
- schéma de livraison email réaligné avec le produit ;
- stack Docker locale exploitable ;
- frontend principal documenté ;
- licence, contribution et sécurité ajoutées.

## Nettoyage effectué

- suppression des artefacts de travail internes non destinés au public ;
- suppression des doublons de schémas/images obsolètes ;
- nettoyage de la documentation legacy pour éviter de raconter un ancien modèle ;
- ajout de métadonnées package pour publication.

## Fichiers de gouvernance ajoutés

- `LICENSE`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/PROJECT_STATUS.md`

## Risques ou limites encore connus

- le bundle frontend reste volumineux et pourrait être découpé davantage ;
- certains tests d'intégration complets dépendent encore de services externes ;
- le dashboard legacy existe encore et doit rester secondaire ;
- le projet n'expose pas encore de politique formelle de releases ou de versioning public.

## Recommandations pour la suite

1. Ajouter un changelog public (`CHANGELOG.md`).
2. Définir une stratégie de versioning (`SemVer` simple suffit).
3. Ajouter des workflows CI publics pour lint/build/tests ciblés.
4. Ajouter éventuellement un `CODE_OF_CONDUCT.md` si vous voulez une surface contribution plus standardisée.
5. Publier une roadmap publique légère si vous voulez encourager les contributions externes.

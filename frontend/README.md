# Frontend Tech Watch Agent

Le frontend React/TypeScript du projet vit dans ce dossier, mais la documentation canonique reste au niveau racine.

## Voir en priorité

- [README racine](../README.md)
- [Guide de contribution](../CONTRIBUTING.md)
- [État actuel du projet](../docs/PROJECT_STATUS.md)

## Développement local

```bash
npm install
npm run dev
```

Par défaut, le frontend appelle `http://localhost:8000`.

Pour changer l'API cible :

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

## Vérification

```bash
bunx tsc --noEmit
npm run build
```

## Notes

- Les appels API passent par `src/services/api.ts`.
- Le streaming live utilise `EventSource` sur `/orchestrator/stream`.
- En Docker/Nginx, `VITE_API_URL=/api` est l'option recommandée.

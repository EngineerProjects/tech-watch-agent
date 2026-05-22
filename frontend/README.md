# Frontend Tech Watch Agent

Interface React + TypeScript du projet `tech-watch-agent`.

## Development

```bash
bun install
bun run dev
```

Par defaut, le frontend appelle `http://localhost:8000`. Pour changer l'API cible:

```bash
VITE_API_URL=http://localhost:8000 bun run dev
```

## Verification

```bash
bunx tsc --noEmit
bun run build
```

## Notes

- Les appels API passent par `frontend/src/services/api.ts`.
- Le streaming live utilise `EventSource` sur `/orchestrator/stream`.
- En Docker/Nginx, `VITE_API_URL=/api` est l'option recommandee.

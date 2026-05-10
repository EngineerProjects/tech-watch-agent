# tech-watch-agent

Plateforme open source de veille technologique automatisée par agents IA.

## Workspace

- `sources/` contient uniquement les dépôts de référence et ne doit pas être modifié.
- `app/` contiendra le code applicatif propre au projet.
- `docs/` documente les décisions d'architecture et de migration.

## Étape en cours

Base V1 en cours d'extraction depuis `sources/newsletter-agent` avec migration sélective.

## Lancer la V1

Installer les dépendances localement:

```bash
python3 -m pip install -e .
```

Préparer l'environnement:

```bash
cp .env.example .env
```

Vérifier la configuration:

```bash
python3 -m app.main --config-check
```

Générer une newsletter sans envoi email:

```bash
python3 -m app.main --mode once --no-email
```

Démarrer l'API:

```bash
python3 -m app.main --mode api
```

Avec Docker:

```bash
docker compose -f docker/docker-compose.yml up --build tech-watch-api
```

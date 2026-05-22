COMPOSE := docker compose -f docker/docker-compose.yml
PROJECT_VOLUMES := .volumes/postgres .volumes/redis .volumes/logs .volumes/searxng-cache .volumes/ollama

.PHONY: help build up up-ollama up-once up-scheduler down ps logs api-logs soft-clean hard-clean

help:
	@printf "Available targets:\n"
	@printf "  make build        Build Tech Watch images\n"
	@printf "  make up           Start api + frontend + postgres + redis + searxng\n"
	@printf "  make up-ollama    Start the stack with local Ollama + auto-pulled models\n"
	@printf "  make up-once      Run the one-shot manual job profile\n"
	@printf "  make up-scheduler Start the scheduler profile\n"
	@printf "  make down         Stop the Tech Watch stack\n"
	@printf "  make ps           Show Tech Watch service status\n"
	@printf "  make logs         Follow all Tech Watch logs\n"
	@printf "  make api-logs     Follow API logs only\n"
	@printf "  make soft-clean   Stop and remove Tech Watch containers/networks, keep project data\n"
	@printf "  make hard-clean   Remove Tech Watch containers, images, and local project data\n"

build:
	$(COMPOSE) build api frontend once scheduler

up:
	$(COMPOSE) up -d --build postgres redis searxng api frontend

up-ollama:
	LLM_BASE_URL=http://ollama:11434/v1 $(COMPOSE) --profile ollama up -d --build postgres redis searxng ollama ollama-init api frontend

up-once:
	$(COMPOSE) --profile manual up once

up-scheduler:
	$(COMPOSE) --profile scheduler up -d scheduler

down:
	$(COMPOSE) down --remove-orphans

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=150

api-logs:
	$(COMPOSE) logs -f --tail=150 api

soft-clean:
	$(COMPOSE) down --remove-orphans || true

hard-clean:
	$(COMPOSE) down --remove-orphans --volumes --rmi local || true
	rm -rf $(PROJECT_VOLUMES)

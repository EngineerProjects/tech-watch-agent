# Tech Watch Agent - Makefile for Docker operations

.PHONY: help build up down logs ps clean test docker-build

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Docker operations
build: ## Build Docker images
	docker compose -f docker/docker-compose.yml build

docker-build: ## Build and push Docker image to registry
	docker build -t tech-watch-agent:latest -f docker/Dockerfile .
	docker tag tech-watch-agent:latest ghcr.io/$(shell gh repo view --json owner,repo --jq '.owner.login + "/" + .repo.name'):latest
	docker push ghcr.io/$(shell gh repo view --json owner,repo --jq '.owner.login + "/" + .repo.name'):latest

up: ## Start all services
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop all services
	docker compose -f docker/docker-compose.yml down

logs: ## Show logs (use: make logs SERVICE=api)
	docker compose -f docker/docker-compose.yml logs -f $(SERVICE)

ps: ## Show running containers
	docker compose -f docker/docker-compose.yml ps

clean: ## Clean up volumes and containers
	docker compose -f docker/docker-compose.yml down -v --remove-orphans
	docker system prune -f

restart: ## Restart services (use: make restart SERVICE=api)
	docker compose -f docker/docker-compose.yml restart $(SERVICE)

# Development
dev-api: ## Start API in development mode
	docker compose -f docker/docker-compose.yml up -d api

dev-once: ## Run once mode
	docker compose -f docker/docker-compose.yml --profile manual up once

dev-scheduler: ## Start scheduler
	docker compose -f docker/docker-compose.yml --profile scheduler up -d scheduler

# Testing
test-docker: ## Run tests in Docker
	docker compose -f docker/docker-compose.yml run --rm api pytest tests/

# Database
db-migrate: ## Run database migrations
	docker compose -f docker/docker-compose.yml exec api alembic upgrade head

db-reset: ## Reset database (WARNING: destroys data)
	docker compose -f docker/docker-compose.yml down -v
	docker compose -f docker/docker-compose.yml up -d postgres
	sleep 5
	docker compose -f docker/docker-compose.yml up -d api

# Health
health: ## Check service health
	@curl -s http://localhost:8000/health | jq . || echo "API not responding"

# Shell
shell: ## Open shell in API container
	docker compose -f docker/docker-compose.yml exec api /bin/bash
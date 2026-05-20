# Tech Watch Agent - Developer Makefile

.DEFAULT_GOAL := help

COMPOSE_FILE ?= docker/docker-compose.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)
SERVICE ?= api
PYTHON ?= python3
PYTEST ?= pytest
RUFF ?= ruff
MYPY ?= mypy

.PHONY: help install build rebuild docker-build up up-build down destroy restart logs ps config \
	dev-api dev-once dev-scheduler shell health doctor \
	test test-unit test-integration test-cov test-docker lint lint-fix format typecheck check \
	db-migrate db-downgrade db-history db-current db-reset \
	clean clean-py clean-test clean-build clean-logs clean-docker clean-docker-cache \
	clean-images clean-volumes clean-networks clean-system nuke

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies locally
	pip install -e .

config: ## Validate Docker Compose configuration
	$(COMPOSE) config

build: ## Build Docker images
	$(COMPOSE) build

rebuild: ## Rebuild Docker images without cache
	$(COMPOSE) build --no-cache

docker-build: ## Build and push Docker image to registry
	docker build -t tech-watch-agent:latest -f docker/Dockerfile .
	docker tag tech-watch-agent:latest ghcr.io/$(shell gh repo view --json owner,repo --jq '.owner.login + "/" + .repo.name'):latest
	docker push ghcr.io/$(shell gh repo view --json owner,repo --jq '.owner.login + "/" + .repo.name'):latest

up: ## Start core services in detached mode
	$(COMPOSE) up -d

up-build: ## Build and start services
	$(COMPOSE) up -d --build

down: ## Stop services without removing volumes
	$(COMPOSE) down

destroy: ## Stop services and remove volumes/orphans
	$(COMPOSE) down -v --remove-orphans

restart: ## Restart a service (use: make restart SERVICE=api)
	$(COMPOSE) restart $(SERVICE)

logs: ## Show logs for a service (use: make logs SERVICE=api)
	$(COMPOSE) logs -f $(SERVICE)

ps: ## Show running compose services
	$(COMPOSE) ps

dev-api: ## Start only the API service
	$(COMPOSE) up -d api

dev-once: ## Run one-shot newsletter generation
	$(COMPOSE) --profile manual up once

dev-scheduler: ## Start the scheduler profile
	$(COMPOSE) --profile scheduler up -d scheduler

shell: ## Open a shell in the API container
	$(COMPOSE) exec api /bin/sh

health: ## Check API health endpoint
	@curl -fsS http://localhost:8000/health | jq . || echo "API not responding"

doctor: ## Show compose status and recent API logs
	$(COMPOSE) ps
	$(COMPOSE) logs --tail=100 api

lint: ## Run Ruff linter
	$(RUFF) check .

lint-fix: ## Run Ruff with automatic fixes
	$(RUFF) check . --fix

format: ## Format Python code with Ruff
	$(RUFF) format .

typecheck: ## Run mypy on the app package
	$(MYPY) app/ --ignore-missing-imports

check: ## Run lint, typecheck, and unit tests
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test-unit

test: test-unit ## Alias for unit test suite

test-unit: ## Run the main pytest suite
	$(PYTEST) tests/ -v

test-integration: ## Run orchestrator integration tests
	$(PYTEST) tests/test_orchestrator_integration.py -v

test-cov: ## Run pytest with coverage
	$(PYTEST) tests/ -v --cov=app --cov-report=term-missing

test-docker: ## Run tests in Docker
	$(COMPOSE) run --rm api pytest tests/

db-migrate: ## Apply Alembic migrations to head
	alembic upgrade head

db-downgrade: ## Roll back one Alembic revision
	alembic downgrade -1

db-history: ## Show Alembic migration history
	alembic history

db-current: ## Show current Alembic revision
	alembic current

db-reset: ## Restart API after clearing Redis (DB is on devinfra — reset there if needed)
	$(COMPOSE) down
	$(COMPOSE) up -d redis
	sleep 3
	$(COMPOSE) up -d api

clean: clean-py clean-test clean-build ## Clean local Python, test, and build artifacts

clean-py: ## Remove Python caches and bytecode
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

clean-test: ## Remove pytest, coverage, mypy, and Ruff caches
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache .ruff_cache .tox .nox

clean-build: ## Remove packaging artifacts
	rm -rf build dist .eggs
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +

clean-logs: ## Remove runtime data in .volumes/logs
	rm -rf .volumes/logs && mkdir -p .volumes/logs

clean-docker: ## Remove compose services, volumes, and orphans
	$(COMPOSE) down -v --remove-orphans

clean-docker-cache: ## Remove Docker build cache
	docker builder prune -af

clean-images: ## Remove dangling and unused Docker images
	docker image prune -af

clean-volumes: ## Remove unused Docker volumes
	docker volume prune -f

clean-networks: ## Remove unused Docker networks
	docker network prune -f

clean-system: ## Remove unused Docker containers, images, cache, and volumes
	docker system prune -af --volumes

nuke: clean clean-logs clean-docker clean-docker-cache clean-system ## Full local and Docker cleanup

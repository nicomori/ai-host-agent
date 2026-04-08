.PHONY: help up down logs test build push shell lint format clean demo demo-local

PROJECT := ai-host-agent
COMPOSE  := docker compose

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start all services (detached)
	$(COMPOSE) up -d --build

down: ## Stop all services
	$(COMPOSE) down

logs: ## Tail API logs
	$(COMPOSE) logs -f api

logs-all: ## Tail all service logs
	$(COMPOSE) logs -f

test: ## Run pytest suite
	$(COMPOSE) exec api pytest tests/ -v --cov=src --cov-report=term-missing

test-unit: ## Run only unit tests
	$(COMPOSE) exec api pytest tests/unit/ -v

test-integration: ## Run only integration tests
	$(COMPOSE) exec api pytest tests/integration/ -v

build: ## Build Docker image (runtime stage)
	docker build --target runtime -t $(PROJECT):latest .

push: ## Push image to registry
	docker push $(PROJECT):latest

shell: ## Open bash inside api container
	$(COMPOSE) exec api bash

lint: ## Run ruff linter
	$(COMPOSE) exec api ruff check src/ tests/

format: ## Auto-format with ruff
	$(COMPOSE) exec api ruff format src/ tests/

clean: ## Remove containers, volumes, images
	$(COMPOSE) down -v --rmi local
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true

ps: ## Show running services
	$(COMPOSE) ps

db-shell: ## Open psql shell
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-hostai} -d $${POSTGRES_DB:-hostai}

redis-cli: ## Open redis-cli
	$(COMPOSE) exec redis redis-cli

demo: ## Run portfolio demo (Docker)
	$(COMPOSE) exec api python scripts/demo.py --all

demo-local: ## Run portfolio demo (local Python, no Docker)
	python scripts/demo.py --all

# =============================================================================
# LibraryMind — Developer task runner
#
# Run `make help` to list all targets.
# =============================================================================

SHELL := /bin/bash
PYTHON ?= python
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.DEFAULT_GOAL := help

# ─── meta ────────────────────────────────────────────────────────────────────
.PHONY: help
help: ## Show this help.
	@awk 'BEGIN { FS = ":.*##"; printf "\nLibraryMind — make targets:\n\n" } \
		/^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Setup
.PHONY: venv install install-dev
venv: ## Create a virtual environment in .venv/.
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

install: venv ## Install runtime dependencies.
	$(PIP) install .

install-dev: venv ## Install runtime + dev dependencies + pre-commit hooks.
	$(PIP) install -e ".[dev]"
	$(VENV)/bin/pre-commit install --install-hooks

##@ Quality
.PHONY: lint format typecheck check
lint: ## Run Ruff (with auto-fix).
	$(VENV)/bin/ruff check --fix app scripts tests

format: ## Format with Ruff + Black.
	$(VENV)/bin/ruff format app scripts tests
	$(VENV)/bin/black app scripts tests

typecheck: ## Run Mypy.
	$(VENV)/bin/mypy app

check: ## Run all quality gates (no auto-fix).
	$(VENV)/bin/ruff check app scripts tests
	$(VENV)/bin/black --check app scripts tests
	$(VENV)/bin/mypy app

##@ Test
.PHONY: test test-fast cov
test: ## Run the full test suite with coverage.
	$(VENV)/bin/pytest

test-fast: ## Run tests, stop on first failure.
	$(VENV)/bin/pytest -x

cov: ## Open the HTML coverage report.
	$(VENV)/bin/pytest --cov-report=html
	@echo "Open htmlcov/index.html in your browser."

##@ Run
.PHONY: run seed
run: ## Run the API with uvicorn auto-reload.
	$(VENV)/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed: ## Seed the vector store from app/data/books.json (Phase 3+).
	$(PY) -m scripts.seed_vector_store

##@ Docker
.PHONY: docker-up docker-down docker-logs docker-rebuild
docker-up: ## Start the dev stack (api + redis).
	docker compose up --build -d

docker-down: ## Stop the dev stack and remove volumes.
	docker compose down -v

docker-logs: ## Tail logs from all services.
	docker compose logs -f

docker-rebuild: ## Rebuild images without cache.
	docker compose build --no-cache

##@ Housekeeping
.PHONY: clean
clean: ## Remove caches and build artefacts.
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov .coverage coverage.xml dist build *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

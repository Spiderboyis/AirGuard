# AirGuard developer commands. Run `make help` for the list.

SHELL := /bin/bash
.DEFAULT_GOAL := help

PY        ?= python3.12
VENV      := .venv
VPY       := $(VENV)/bin/python
SUPABASE  := npx --yes supabase@2.120.0
OLLAMA_MODEL ?= qwen3:1.7b

# Use Podman's Docker-compatible socket for the Supabase CLI when Docker isn't running.
PODMAN_SOCK := /run/user/$(shell id -u)/podman/podman.sock
ifeq ($(DOCKER_HOST),)
ifneq ($(wildcard $(PODMAN_SOCK)),)
export DOCKER_HOST := unix://$(PODMAN_SOCK)
endif
endif

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------------------------
.PHONY: setup
setup: ## Install Python and Node dependencies and pull the local LLM
	test -d $(VENV) || $(PY) -m venv $(VENV)
	$(VPY) -m pip install -q --upgrade pip
	$(VPY) -m pip install -q -e "backend[dev]"
	npm --prefix frontend install
	test -f .env || cp .env.example .env
	test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
	-ollama pull $(OLLAMA_MODEL)

# ---------------------------------------------------------------------------------------------
# Database (local Supabase)
# ---------------------------------------------------------------------------------------------
.PHONY: db-start db-stop db-reset db-migrate db-status setup-sql
db-start: ## Start local Supabase (Postgres, API, Studio) and apply migrations
	$(SUPABASE) start

db-stop: ## Stop local Supabase (data is kept)
	$(SUPABASE) stop

db-reset: ## Recreate the local database from migrations (deletes all data)
	$(SUPABASE) db reset

db-migrate: ## Apply new migrations to the running local database
	$(SUPABASE) migration up

db-status: ## Show local Supabase URLs
	$(SUPABASE) status

setup-sql: ## Regenerate supabase/setup.sql from the migrations
	$(PY) scripts/build_setup_sql.py

# ---------------------------------------------------------------------------------------------
# Data and model
# ---------------------------------------------------------------------------------------------
.PHONY: backfill train forecast hourly snapshot
backfill: ## Load a year of PM2.5, weather, CAMS and fire history (~20 min)
	cd backend && ../$(VPY) -m airguard.jobs.backfill --days 365

train: ## Train the forecast models and write the backtest
	cd backend && ../$(VPY) -m airguard.ml.train

forecast: ## Fetch the latest data and issue a fresh forecast (once)
	cd backend && ../$(VPY) -m airguard.jobs.hourly

hourly: ## Keep forecasts fresh: run the hourly job in a loop
	cd backend && ../$(VPY) -m airguard.jobs.hourly --loop

snapshot: ## Freeze the current forecast and demo trips for a reproducible demo
	cd backend && ../$(VPY) -m airguard.jobs.snapshot

# ---------------------------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------------------------
.PHONY: start stop api web dev
start: db-start dev ## Start the database, then the API and web app

stop: ## Stop everything: web app, API, hourly job, local LLM and the database
	-pkill -f "airguard.api.main:app" || true
	-pkill -f "$(CURDIR)/frontend/node_modules/.bin/next" || true
	-pkill -f "airguard.jobs.hourly" || true
	-ollama stop $(OLLAMA_MODEL) 2>/dev/null || true
	$(SUPABASE) stop
	@echo "AirGuard stopped. Your data is kept; 'make start' brings it back."

api: ## Run the API on :8000
	cd backend && ../$(VPY) -m uvicorn airguard.api.main:app --reload --port 8000

web: ## Run the web app on :3000
	npm --prefix frontend run dev

dev: ## Run API and web app together
	$(MAKE) -j2 api web

# ---------------------------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------------------------
.PHONY: test lint contracts check
test: ## Run backend tests
	cd backend && ../$(VPY) -m pytest

lint: ## Lint backend and frontend
	$(VENV)/bin/ruff check backend
	npm --prefix frontend run lint
	npm --prefix frontend run typecheck

contracts: ## Export the OpenAPI contract and regenerate frontend types
	$(VPY) scripts/export_openapi.py
	npm --prefix frontend run gen:types

check: test lint ## Everything CI runs
	$(PY) scripts/build_setup_sql.py --check

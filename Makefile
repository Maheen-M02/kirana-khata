# Kirana Khata — dev commands. On Windows run these from Git Bash (not PowerShell/WSL).
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

UV   ?= uv
PNPM ?= pnpm
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend \
        lint lint-backend lint-frontend fmt migrate smoke-voice docker-up docker-down

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  %-16s %s\n",$$1,$$2}'

install: ## Install backend (uv) and frontend (pnpm) deps
	cd backend && $(UV) sync
	cd frontend && $(PNPM) install --frozen-lockfile

dev: ## Run backend :8000 and frontend :3000 together (Ctrl-C stops both)
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory dev-backend & \
	$(MAKE) --no-print-directory dev-frontend & \
	wait

dev-backend:
	cd backend && $(UV) run alembic upgrade head && \
	$(UV) run uvicorn app.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT)

dev-frontend:
	cd frontend && $(PNPM) dev -p $(FRONTEND_PORT)

test: test-backend test-frontend ## pytest + vitest (fakes only; never hits paid APIs)

test-backend:
	cd backend && $(UV) run pytest

test-frontend:
	cd frontend && $(PNPM) test

lint: lint-backend lint-frontend ## ruff + mypy + eslint + tsc

lint-backend:
	cd backend && $(UV) run ruff check . && $(UV) run ruff format --check . && $(UV) run mypy

lint-frontend:
	cd frontend && $(PNPM) lint && $(PNPM) typecheck

fmt: ## Auto-format backend
	cd backend && $(UV) run ruff format . && $(UV) run ruff check --fix .

migrate: ## Apply DB migrations
	cd backend && $(UV) run alembic upgrade head

smoke-voice: ## Live STT -> NLU -> TTS round trip (SPENDS CREDITS). Usage: make smoke-voice FILE=sample.wav
	@test -n "$(FILE)" || { echo "Usage: make smoke-voice FILE=path/to/clip.wav"; exit 2; }
	@test -f backend/scripts/smoke_voice.py || { echo "smoke-voice lands in Phase 1"; exit 2; }
	cd backend && $(UV) run python -m scripts.smoke_voice "$(abspath $(FILE))"

docker-up: ## Backend + Postgres via docker compose
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down

# Kirana Khata — dev commands. On Windows run these from Git Bash (not PowerShell/WSL).
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Windows consoles default to cp1252; Devanagari transcripts must print and log cleanly.
export PYTHONUTF8 := 1
export PYTHONIOENCODING := utf-8

UV   ?= uv
PNPM ?= pnpm
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend \
        lint lint-backend lint-frontend fmt migrate seed smoke-voice tts-say test-live eval-nlu evon-warm docker-up docker-down

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

test-backend:  ## set TEST_DATABASE_URL=postgresql://... to also run ledger tests on Postgres
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

seed: ## Demo shop + customers (idempotent; run after migrate)
	cd backend && $(UV) run alembic upgrade head && $(UV) run python -m scripts.seed_demo

smoke-voice: ## Live STT -> TTS round trip (SPENDS CREDITS). make smoke-voice FILE=clip.webm [ARGS="--record"]
	@test -n "$(FILE)" || { echo "Usage: make smoke-voice FILE=path/to/clip [ARGS=...]"; exit 2; }
	cd backend && $(UV) run python -m scripts.smoke_voice "$(abspath $(FILE))" $(ARGS)

tts-say: ## Live TTS only (SPENDS 1 CREDIT unless cached). make tts-say TEXT="..." [ARGS="--voice X"]
	@test -n "$(TEXT)" || { echo 'Usage: make tts-say TEXT="Entry ho gayi."'; exit 2; }
	cd backend && $(UV) run python -m scripts.smoke_voice --say "$(TEXT)" $(ARGS)

test-live: ## Opt-in real Gnani tests (SPENDS CREDITS)
	cd backend && $(UV) run pytest -m live -s

eval-nlu: ## Golden NLU report on the rules parser (offline, free)
	cd backend && $(UV) run pytest tests/unit/nlu/test_golden_and_templates.py -k gate -s -q

evon-warm: ## Ping Evon /models (wakes a scaled-to-zero GPU)
	@set -a; . ./.env; set +a; curl -sf -m 600 -H "Authorization: Bearer $$EVON_API_KEY" "$$EVON_BASE_URL/models" && echo " <- Evon is up" || echo "Evon not reachable at $$EVON_BASE_URL"

docker-up: ## Backend + Postgres via docker compose
	docker compose -f infra/docker-compose.yml up --build

docker-down:
	docker compose -f infra/docker-compose.yml down

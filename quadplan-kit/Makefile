# Quarterly (QuadPlan) developer commands. See CLAUDE.md.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
UV ?= uv
WEB := apps/web
NPM := npm --prefix $(WEB)
COMPOSE := docker compose

.PHONY: help install env up down ps logs scraper-up lint typecheck test test-py test-web \
        golden check e2e evals migrate seed seed-forum-demo api-client api-client-check format

help:
	@grep -E '^[a-z-]+:' Makefile | cut -d: -f1 | sort | tr '\n' ' '; echo

install:
	$(UV) sync --all-packages
	$(NPM) ci

env:
	@test -f .env || (cp .env.example .env && echo "created .env from .env.example")
	@grep -q '^ENVIRONMENT=' .env || echo "note: .env has no ENVIRONMENT line; add ENVIRONMENT=development for local work (the API refuses development settings otherwise)"

up: env
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) ps

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs --tail=100

scraper-up: env
	$(COMPOSE) --profile scraper up -d --build --wait scraper
	$(COMPOSE) --profile scraper ps scraper

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(NPM) run lint

typecheck:
	$(UV) run mypy --strict packages/planner_core/planner_core packages/llm_gateway/llm_gateway
	$(UV) run mypy services/api/api services/worker/worker services/scraper/scraper
	$(NPM) run typecheck

test: test-py test-web

test-py:
	$(UV) run pytest packages/planner_core/tests --cov=planner_core --cov-report=term-missing:skip-covered --cov-fail-under=95
	$(UV) run pytest packages/llm_gateway/tests services/api/tests services/worker/tests services/scraper/tests

test-web:
	$(NPM) run test

golden:
	$(UV) run python -m api.cli golden

check: lint typecheck api-client-check test golden
	@echo "make check: all passed"

e2e:
	$(NPM) run e2e

evals:
	@echo "evals: no eval sets yet (prompt 07); never run against the real API without asking"

migrate: env
	@if [ -f services/api/alembic.ini ]; then cd services/api && $(UV) run alembic upgrade head; else echo "migrate: no migrations yet"; fi

seed: env
	$(UV) run python -m api.cli seed

# Development only: FAKE instructors ("Demo Instructor A".."E") and forum pages on five real
# courses, so the forum can be tried without schedule data. Never part of data/seed.
# `make seed-forum-demo ARGS=--remove` deletes them again.
seed-forum-demo: env
	$(UV) run python -m api.cli seed-forum-demo $(ARGS)

# Regenerate the OpenAPI document and the TypeScript types the frontend uses.
api-client:
	$(UV) run python -m api.cli schemas --out docs/schemas
	$(UV) run python -m api.openapi_dump > $(WEB)/src/api/openapi.json
	cd $(WEB) && npx openapi-typescript src/api/openapi.json -o src/api/schema.d.ts

# Fails when the committed client is out of date with the API.
api-client-check:
	@tmp=$$(mktemp -d); \
	$(UV) run python -m api.openapi_dump > $$tmp/openapi.json; \
	diff -q $$tmp/openapi.json $(WEB)/src/api/openapi.json >/dev/null || { echo "api-client-check: openapi.json is stale; run make api-client"; exit 1; }; \
	(cd $(WEB) && npx openapi-typescript $$tmp/openapi.json -o $$tmp/schema.d.ts >/dev/null 2>&1); \
	diff -q $$tmp/schema.d.ts $(WEB)/src/api/schema.d.ts >/dev/null || { echo "api-client-check: schema.d.ts is stale; run make api-client"; exit 1; }; \
	mkdir -p $$tmp/schemas && $(UV) run python -m api.cli schemas --out $$tmp/schemas >/dev/null; \
	diff -r -q $$tmp/schemas docs/schemas >/dev/null || { echo "api-client-check: docs/schemas is stale; run make api-client"; exit 1; }; \
	echo "api-client-check: generated client and JSON Schemas are up to date"

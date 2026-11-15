# Quarterly (QuadPlan) developer commands. See CLAUDE.md.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
UV ?= uv
WEB := apps/web
NPM := npm --prefix $(WEB)
COMPOSE := docker compose

.PHONY: attributes help install env up down ps logs scraper-up lint typecheck test test-py test-web \
        golden check e2e e2e-stack screenshots evals migrate seed seed-forum-demo api-client api-client-check format \
        loadtest

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

# Both end-to-end suites: the MSW suite (apps/web/e2e, mocked API), then journeys A-D against
# the real Docker stack (e2e-stack). Fails if either fails.
e2e:
	$(NPM) run e2e
	$(MAKE) e2e-stack

# Journeys A-D (SPEC "Core user journeys", apps/web/e2e-stack/) against the real stack: seed
# data, the request-driven fake LLM (LLM_FAKE=e2e, never a provider) and console email, from
# docker-compose.e2e.yml. Note: this (re)starts the shared `quarterly` stack with those settings;
# `make up` restores the normal ones. STACK_URL (default http://localhost:5173) picks the web.
E2E_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.e2e.yml
e2e-stack: env
	$(E2E_COMPOSE) up -d --build --wait
	$(MAKE) migrate
	$(MAKE) seed
	$(MAKE) seed-forum-demo
	# The forum AI summaries (journey D), written inside the api container so the fake LLM answers.
	$(E2E_COMPOSE) exec -T api python -m api.cli attributes
	$(NPM) run e2e:stack

# Design review screenshots: every page at 1440 and 390px wide into docs/screenshots/
# (apps/web/e2e/screenshots.spec.ts). Uses E2E_PORT like `make e2e`.
screenshots:
	SCREENSHOTS=1 $(NPM) run e2e -- e2e/screenshots.spec.ts

# Agent evals against the real API (costs money; Richard runs them). Runs the free checks,
# prints the estimate, and refuses to go on unless CONFIRM_SPEND=yes. Spending cap:
# EVAL_COST_CAP_USD (default 20). The script refuses on its own too.
evals:
	@$(UV) run python evals/run.py --offline
	@$(UV) run python evals/run.py --estimate
	@test "$(CONFIRM_SPEND)" = "yes" || { echo "evals: not calling the real API. Ask Richard, then run: CONFIRM_SPEND=yes make evals"; exit 1; }
	CONFIRM_SPEND=yes $(UV) run python evals/run.py

# The nightly forum -> attributes job (prompt 11), run by hand.
attributes: env
	$(UV) run python -m api.cli attributes

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

# Prompt 12 load test (locust via uvx; never against a shared or production server):
# POST /verify at 50 requests/second (p95 < 500 ms) and forum page reads at 100/second.
# Needs an account for the forum reads: LOAD_LOGIN=<username> LOAD_PASSWORD=<password>.
loadtest:
	$(UV) run python loadtest/make_plans.py
	LOAD_HOST=$${LOAD_HOST:-http://localhost:8000} $(UV) run python loadtest/run.py

# Prompt 09: pilot ingestion. Runs E1-E4 on the hand-seeded programs and reports node-level
# agreement with the seed (docs/ingest-pilot/). `make ingest-pilot ARGS=--fake` is free (FakeLLM
# answers from the seed). A real run costs money: it prints the estimate and refuses unless
# CONFIRM_SPEND=yes and LLM_LIVE=true; spending cap INGEST_COST_CAP_USD (default 25).
.PHONY: ingest-pilot
ingest-pilot:
	@$(UV) run python -m worker.ingest.pilot $(ARGS)

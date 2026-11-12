# Progress

## Prompt 00 · Bootstrap — done (2026-11-12)

**What exists**
- uv workspace (Python 3.12): `packages/planner_core`, `packages/llm_gateway`, `services/api`, `services/worker`, `services/scraper`; ruff, mypy (`--strict` for planner_core and llm_gateway), pytest, Hypothesis, coverage gate 95% on planner_core.
- FastAPI `/health` (checks Postgres and Redis, 503 when degraded) and `/version`; Arq worker with a `noop` job; scraper container that launches Chromium once, marks itself healthy and idles (no jobs).
- React 18 + TypeScript (Vite) with Tailwind v4 + shadcn/ui (`components.json`, `Button`), TanStack Query, a placeholder page for every row of SPEC "Sitemap and every page", vitest and Playwright.
- `docker-compose.yml`: postgres:16, redis:7, minio, api, worker, web with healthchecks and named volumes; scraper under the `scraper` profile (`make scraper-up`) because it is a heavy Chromium image and CLAUDE.md lists the `make up` services without it.
- `Makefile` with every CLAUDE.md target plus `install`, `api-client`, `api-client-check`, `scraper-up`. `golden`, `e2e` (one smoke test per route), `evals` exist.
- CI: `.github/workflows/ci.yml` at the git root (the project lives in `quadplan-kit/`), runs `make install && make check` with Postgres and Redis service containers.
- `llm_routing.yaml` with the SPEC "Model routing" table (nothing reads it yet).

**Evidence (2026-11-12):** `make up` → db, redis, minio, api, worker, web all `(healthy)`; `curl /health` → `{"status":"ok","db":true,"redis":true}`; worker `noop` round-trip → `ok`; every web route → HTTP 200 through nginx; `make e2e` → 20 passed; `make check` passed; `make scraper-up` → healthy, "chromium 158.0.8127.18 ready".

**Deviations and additions (with reasons)**
- MinIO: Docker Hub and quay.io no longer serve MinIO community images (pull denied), so Compose uses `cgr.dev/chainguard/minio` pinned by digest.
- No request logs: uvicorn runs with `--no-access-log`, nginx with `access_log off` and `error_log ... crit` (CLAUDE.md: never log IPs).
- Libraries not named in the spec: `pydantic-settings` (typed env config), `react-router-dom` (routing), `openapi-fetch` (runtime for the openapi-typescript client), `clsx`/`tailwind-merge`/`class-variance-authority`/`@radix-ui/react-slot` (shadcn/ui runtime), `eslint-plugin-jsx-a11y` (accessibility lint), Testing Library + jsdom (vitest DOM), `httpx` (FastAPI TestClient), `fakeredis` (Redis in unit tests), `pytest-cov` (coverage gate).
- Pre-added so parallel prompts 02-04 do not fight over lockfiles: `ortools`, `argon2-cffi`, `cryptography`, `@dnd-kit/*`, `msw`, `@axe-core/playwright`.
- Naming per decision 12: user-facing "Quarterly"; Compose project and database `quarterly`.


## Prompt 01 · Contracts — done (2026-11-12)

- **planner_core models** (`models.py`): Atom, Expr, the four node kinds, Selector, Constraints, Policy, Source; PlanState, PlanItem, Credit, all 12 goal types, RuleSet, CollegePolicy, Catalog, Report, Issue (V01-V12), Certificate, NodeProgress, VerifyOptions, the change-set ops. Pure helpers: `terms`, `dsl` (node paths, human form), `hashing` (`plan_hash`, `rules_hash`), `changes.apply_ops`. `verify` and `check_certificate` are stubs for prompt 02. JSON Schemas are in `docs/schemas/`.
- **Database:** SQLAlchemy 2 models for every SPEC table plus `course_list` and `college_policy`; one Alembic migration (`0001`) that enables `ltree` and `pg_trgm` and indexes course code and title (trigram), term, `course_instructor`, `plan_hash`. Accounts follow decision 5 (email stored only on `account`).
- **Seed format** under `data/seed/<catalog_year>/`, with `make seed` validating and upserting idempotently; fake fixture `TEST`/`FAKE` courses, catalog year 2099-00. Golden plan format and runner (`make golden`; reports SKIP until the verifier exists).
- **API surface:** every endpoint as a 501 stub with request and response schemas; SSE agent endpoints document `AgentEvent`. `make api-client` regenerates the OpenAPI document, `schema.d.ts` and the JSON Schemas; `make check` fails if they are stale.
- **Docs:** `docs/CONTRACTS.md` (endpoint table and the decisions that are not obvious).
- **Tests:** migration up, down and up again; models match the migration; day-level dates only on user tables; email only on `account`; YAML examples from the spec round-trip; invalid DSL rejected; loader runs twice on the fixture without changes; golden runner; API surface and 501 stubs.
- Removed `@cloudflare/blindrsa-ts` (no blind signatures after decision 5).

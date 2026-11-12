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

**Next:** prompt 01 (contracts).

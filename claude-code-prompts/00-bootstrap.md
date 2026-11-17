# Prompt 00 · Bootstrap

> Recommended: Opus 5.5, effort `high`. Start in plan mode (Shift+Tab until "plan mode on"), approve the plan, then let it implement.

---

You are starting the QuadPlan repository. Read `CLAUDE.md`, then these sections of `docs/SPEC.md`: "Summary and decisions to confirm" and "System architecture and tech stack".

Goal: a running skeleton of every service, wired together, with the quality checks in place. No business logic yet.

Do:
1. `git init` if needed. Create the layout in SPEC "Repository layout". Add `docs/PROGRESS.md` and `docs/OPEN_QUESTIONS.md`.
2. Python 3.12 workspace (uv preferred) with `packages/planner_core`, `packages/llm_gateway`, `services/api`, `services/worker`, `services/scraper`. Tooling: ruff, mypy, pytest, hypothesis.
3. FastAPI app with `/health` and `/version`. Arq worker with one no-op job. Scraper container with Playwright and Chromium installed, no jobs.
4. React + TypeScript (Vite) app with a route for every row of SPEC "Sitemap and every page", each rendering a placeholder. Tailwind + shadcn/ui, TanStack Query, vitest, Playwright.
5. `docker-compose.yml`: postgres:16, redis:7, minio, api, worker, web, with healthchecks and named volumes. `.env.example` with ANTHROPIC_API_KEY, OPENROUTER_API_KEY, DATABASE_URL, REDIS_URL, MINIO_*, SERVER_HMAC_KEY, ISSUANCE_HMAC_KEY, SESSION_SECRET.
6. `Makefile` with every target named in `CLAUDE.md`. `golden`, `e2e` and `evals` may print "no tests yet" and exit 0 for now.
7. GitHub Actions workflow that runs `make check`.
8. `llm_routing.yaml` holding the table in SPEC "Model routing" (task -> model id, effort, max tokens, fallback). Nothing reads it yet.

Done when: `make up` shows every service healthy, `make check` passes, and the web app shows the placeholder routes. Paste the command outputs. Then use the `spec-reviewer` subagent on the diff and fix correctness findings. Update `docs/PROGRESS.md`.

Do not add auth, data, or libraries the spec does not name without listing them and why in `docs/PROGRESS.md`.

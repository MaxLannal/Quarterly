# QuadPlan

UChicago course planner (agent-assisted, formally verified) + anonymous course x instructor forum.
The full spec is `docs/SPEC.md`. Read only the sections your task needs; do not load the whole file by default.

## Commands
- `make up` / `make down` - start/stop the Docker Compose stack (db, redis, api, worker, web, minio)
- `make check` - lint + typecheck + unit tests + golden plans (must pass before you say a task is done)
- `make test`, `make lint`, `make typecheck`, `make golden`, `make e2e`
- `make migrate` - Alembic upgrade head; `make seed` - load `data/seed/`

## Layout
apps/web (React+TS) · services/api (FastAPI) · services/worker (Arq) · services/scraper (Playwright)
packages/planner_core (DSL, verifier, solver, certificate checker) · packages/llm_gateway
data/seed (hand-verified YAML) · data/golden (must-pass / must-fail plans) · prompts/ (app agent prompts, versioned)

## Hard rules
- IMPORTANT: `packages/planner_core` never imports the DB, the web framework, an HTTP client or an LLM client. Pydantic in, Pydantic out.
- A plan is "valid" only if `check_certificate()` accepts the solver's certificate.
- Agents never write to the database. They draft `change_set` rows (status `proposed`) or `review_item` rows. Applying is a user action.
- Never log email addresses or IP addresses. A user's email is stored only in `account.email` (decision 5), never copied to other tables, logs or analytics. No exact timestamps for users: day-level dates only.
- Model IDs live only in `llm_routing.yaml`. Never hard-code a model name elsewhere.
- Never invent catalog facts. Every seeded rule carries a verbatim `source.quote`; if unsure, add a TODO to `docs/OPEN_QUESTIONS.md` instead of guessing.
- Secrets come from `.env` (see `.env.example`). Never commit `.env`.
- Frontend types come from the generated OpenAPI client (`make api-client`); no hand-written fetch types.

## Current phase: working demo (Richard, 2026-11-14)
- Catalog-rule questions do not block work. Take the strict reading (do not count the course) and show the student a warning explaining why. Record the choice and a suggested default under "Deferred until before deployment" in `docs/OPEN_QUESTIONS.md`, then build. These are resolved just before deployment.
- A default decides how to read a quote; it never replaces a missing quote. Product, security and privacy questions still go to Richard.
- The hand check of `data/seed/REVIEW.md` is deferred until before deployment.
- Do not send any request to the Claude or OpenRouter APIs (no evals, test runs or agent runs) until Richard says so (2026-11-14). Build and test LLM code against fake clients only.

## Questions for Richard
- Anywhere you leave Richard a question (`docs/OPEN_QUESTIONS.md`, `docs/PROGRESS.md`, review notes, chat), write it in plain, jargon-free language that a non-engineer can follow.
- Always include your suggested answer, or two or three options with what each one means in practice.

## Style
- Python 3.12, ruff, mypy (`--strict` for planner_core and llm_gateway), pytest + Hypothesis.
- TypeScript strict, eslint, vitest, Playwright for e2e. Accessible markup: real buttons, labels, 44px targets.
- UI work: read `docs/DESIGN.md` first (Richard's design guidelines); it wins over the SPEC on look and feel.

## Finishing a task
1. Run `make check` and show the output.
2. Ask the `spec-reviewer` subagent to review the diff against docs/SPEC.md; fix correctness gaps only.
3. Update `docs/PROGRESS.md` with what changed and what is next.

# Quarterly

UChicago course planner (agent-assisted, formally verified) + anonymous course × instructor forum. "QuadPlan" in older docs is the retired working name. Owner: Richard (product decisions, writes `docs/FEEDBACK.md`). Collaborators work on branches and open pull requests.

## Read first, in this order
1. `docs/FEEDBACK.md`: the owner's requests. **New** and **In progress** are the work queue; **Done** (with an index) shows what was asked and how it was resolved; **Later** holds deferred items and suggested follow-ups.
2. `PRODUCT.md`: users, purpose, positioning, product principles. Short.
3. `docs/PROGRESS.md`: the "Current state" block at the top, then the log below it if you need history.
4. `docs/OPEN_QUESTIONS.md`: the "Start here" block lists what still waits on the owner. Items are cited by id in code comments (e.g. P05-7, DF-S1): search the file for an id you meet.
5. `docs/SPEC.md`: the spec. Read only the sections your task needs (it is long). `docs/SPEC-CHANGES.md` lists every change since; **`docs/FEEDBACK.md` wins over SPEC, DESIGN and the prompt files where they conflict.**
6. UI work: `docs/DESIGN.md` (wins over SPEC on look and feel; read its final "Changes approved in FEEDBACK" section) and `docs/DESIGN-REVIEW.md` (known deferred design issues). API work: `docs/CONTRACTS.md`.

`claude-code-prompts/` are the prompts the project was built from (history, not instructions). `prompts/` are the app's own agent prompts.

## Commands
- `make install`; `make up` / `make down` (Compose: db, redis, minio, api, worker, web; `down` keeps data); `make migrate && make seed` (schema, then `data/seed/`); `make seed-forum-demo` (fake forum data).
- `make check`: ruff, eslint, mypy, tsc, Python and web unit tests, golden plans. **Must pass before a task is done.**
- `make e2e`: browser tests on mock data (MSW), then journeys A-D on the Docker stack with fake AI. It **switches the running stack to fake AI**: run `make up` afterwards to restore the real one. While it builds images, do not edit frontend files.
- `make api-client` after any API change (frontend types come only from the generated client). `make screenshots` (`SCREENSHOTS_DIR=after`). `make help` lists all targets.
- App: http://localhost:5173, API: http://localhost:8000.

## Layout
`apps/web` (React + TS, Vite, Tailwind v4, TanStack Query, dnd-kit; `e2e/` mock-data tests, `e2e-stack/` journeys) · `services/api` (FastAPI, SQLAlchemy, Alembic, agent orchestration in `api/agents/`) · `services/worker` (Arq) · `services/scraper` (Playwright, off) · `packages/planner_core` (DSL, verifier V01-V12, CP-SAT generator, certificate checker) · `packages/llm_gateway` (routing, budgets, fallback, fakes) · `data/seed/2026-27` (catalog YAML) · `data/golden` (must-pass / must-fail plans) · `prompts/` · `evals/` · `docs/`.

## Hard rules
- IMPORTANT: `packages/planner_core` never imports the DB, the web framework, an HTTP client or an LLM client. Pydantic in, Pydantic out.
- A plan is "valid" only if `check_certificate()` accepts the solver's certificate.
- Agents never write to the database. They draft `change_set` rows (status `proposed`) or `review_item` rows. Applying is a user action.
- Never log email addresses or IP addresses. A user's email is stored only in `account.email`, never copied to other tables, logs or analytics. Day-level dates only for users. No request from a visitor's browser leaves the site's own origin (fonts, icons, weather are served by Quarterly).
- Model IDs live only in `llm_routing.yaml`. Never hard-code a model name elsewhere.
- Never invent catalog facts. Every seeded rule carries a verbatim `source.quote`; if unsure, add the question to `docs/OPEN_QUESTIONS.md` instead of guessing.
- Secrets come from `.env` (see `.env.example`). Never commit `.env`; never print keys.
- No paid model calls (evals, live tests, ingestion runs) without the owner's OK. Tests use `FakeLLM`; a root `conftest.py` forces `LLM_LIVE=false` for tests. The app's own AI runs only with `LLM_LIVE=true` and a key in `.env`.

## Current phase: working demo (Richard, 2026-11-14)
- Catalog-rule questions do not block work: take the strict reading (do not count the course), show the student a warning explaining why, record the choice and a suggested default under "Deferred until before deployment" in `docs/OPEN_QUESTIONS.md`, then build. A default decides how to read a quote; it never replaces a missing quote.
- Product, security and privacy questions go to the owner. The hand check of `data/seed/REVIEW.md` is deferred until before deployment.

## Known traps (learned the hard way)
- **No Prettier config.** Do not run Prettier: it rewraps files to 80 columns. Follow the surrounding style; eslint and tsc are the checks.
- **Rate limits are shared on one machine.** Logged-out plan generation is 3 per address per day (`api/routers/agents.py`). The journeys clear `rl:*` keys at start and end; if the app says "Plan generation failed", check `redis-cli --scan --pattern 'rl:*'`.
- **The solver has 4 s in the app** (`SOLVER_SECONDS`). Journey B's infeasibility proof takes about 3.8 s; journey C's "years 2-3 before year 4" check depends on time-limited choices (OPEN_QUESTIONS E2E-2) and sometimes fails.
- **`credit_only` courses** (TRNC 10100, transfer general credit) are never generator candidates or elective choices. A repeatable course with no offering data otherwise looks like a free elective for any quarter.
- **LLM output limits:** size `max_tokens` for thinking plus the largest tool call. A reply cut off at `max_tokens` ends the run (`AgentError` reason `truncated`); the advisor's 800 was too small (now 4000).
- Docker disk fills after many rebuilds: `docker image prune -f`.

## Working with the owner
- Read `docs/FEEDBACK.md` at the start of every task. Move items you take to **In progress**; when finished, keep the owner's text and add "Resolved in <commit>: <one line>" (or "Needs Richard: <question>"), then move it to **Done**. When behaviour changes, update `docs/SPEC.md` and add a row to `docs/SPEC-CHANGES.md`.
- Questions for the owner (anywhere: OPEN_QUESTIONS, PROGRESS, chat) are in plain, jargon-free language, each with a suggested answer or two or three options and what each means in practice.

## Style
- Python 3.12, ruff, mypy (`--strict` for planner_core and llm_gateway), pytest + Hypothesis.
- TypeScript strict, eslint, vitest, Playwright. Accessible markup: real buttons and labels, 44px targets, 4.5:1 contrast, visible focus, keyboard paths, `prefers-reduced-motion`.

## Finishing a task
1. Run `make check` (and `make e2e` if the UI or a journey changed) and show the output.
2. Ask the `spec-reviewer` subagent (`.claude/agents/`) to review the diff against docs/SPEC.md; fix correctness gaps only.
3. Update `docs/PROGRESS.md` (and FEEDBACK.md if an item was resolved).

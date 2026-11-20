# Progress

> **Current state (2026-11-20).** On branch `feature/best-of-uchicago`: the course-title chapel homepage, now titled "The Best of UChicago, within your reach." with a question bar for the new Ask chatbot, plus the campus companion (Ask, a companion on every page, the dashboard with the interviewing guide and routes, the feed, the Commons). See "Campus companion" at the end of this file, `docs/BEST-OF-UCHICAGO-PLAN.md`, and OPEN_QUESTIONS CC-1 to CC-8.
>
> **Earlier state (2026-11-16).** Every prompt (00-13) has been run (the schedule scraper stays switched off until the University allows scraping); the owner's FEEDBACK items are all resolved (index at the top of "Done" in `docs/FEEDBACK.md`). The latest work, at the end of this file: the design pass with Impeccable (D1-D11, `docs/DESIGN-REVIEW.md`), TRNC 10100 transfer credit, and the advisor's cut-off replies (output limit 800 to 4000; a cut-off reply now stops the run). The project moved from `quadplan-kit/` to the repository root for GitHub.
>
> `make check` and `make e2e` pass (journey C's preference check is flaky, OPEN_QUESTIONS E2E-2). AI features run only with `LLM_LIVE=true`. Open decisions: the "Start here" block of `docs/OPEN_QUESTIONS.md`. Suggested next steps: "Later" in `docs/FEEDBACK.md`.
>
> The log below is chronological, one section per prompt or goal.

## Prompt 00 · Bootstrap — done (2026-11-12)

**What exists**
- uv workspace (Python 3.12): `packages/planner_core`, `packages/llm_gateway`, `services/api`, `services/worker`, `services/scraper`; ruff, mypy (`--strict` for planner_core and llm_gateway), pytest, Hypothesis, coverage gate 95% on planner_core.
- FastAPI `/health` (checks Postgres and Redis, 503 when degraded) and `/version`; Arq worker with a `noop` job; scraper container that launches Chromium once, marks itself healthy and idles (no jobs).
- React 18 + TypeScript (Vite) with Tailwind v4 + shadcn/ui (`components.json`, `Button`), TanStack Query, a placeholder page for every row of SPEC "Sitemap and every page", vitest and Playwright.
- `docker-compose.yml`: postgres:16, redis:7, minio, api, worker, web with healthchecks and named volumes; scraper under the `scraper` profile (`make scraper-up`) because it is a heavy Chromium image and CLAUDE.md lists the `make up` services without it.
- `Makefile` with every CLAUDE.md target plus `install`, `api-client`, `api-client-check`, `scraper-up`. `golden`, `e2e` (one smoke test per route), `evals` exist.
- CI: `.github/workflows/ci.yml` at the git root (the project then lived in `quadplan-kit/`; moved to the repository root on 2026-11-16), runs `make install && make check` with Postgres and Redis service containers.
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

## Milestone M1 · planner without AI — ready for Richard's review (2026-11-12)

M1 was run with `claude-code-prompts/MASTER-orchestrator.md`. Prompts 00 and 01 were built and committed on `main` first. Then prompts 02-05 ran in parallel, each in its own git worktree, and were merged into `main` one by one.

**What works now**
- **Planner** (`/plan`): a 4-year grid (Autumn/Winter/Spring, collapsible Summer, optional Year 5) on the real 2026-27 seed data.
  - Drag and drop, plus a keyboard "Move to..." menu; lock, mark completed, remove.
  - A requirement rail with per-node progress from the verifier.
  - A debounced (300 ms) `POST /verify` after every edit. The badge shows Valid / warnings / errors, and an issue highlights the cards it is about.
  - Logged-out plans live in localStorage and are imported on login (import is 501 until plans CRUD exists).
- **Verifier** (`planner_core`): checks V01-V12, a CP-SAT program model, the 12 goal predicates, and a certificate builder. `check_certificate` is under 300 lines and imports no solver. `POST /verify` loads rules from Postgres, runs `verify_checked` (verify plus the checker), and caches results in Redis. A plan shows "Valid" only when the checker accepts its certificate.
- **Catalog API:** course search (code or title, typo-tolerant), course detail (prerequisites in plain English, needs and unlocks, offerings, counts toward), course lists, programs with their rule trees, and eligible courses per node.
- **Accounts:** decision 5, email + password. Sign-up (email → 6-digit code → username + password), login, password reset, sessions in Redis with CSRF, rate limits, account export and delete, and a `/privacy` page. The security review findings (1 medium, 3 low) are all fixed.
- **Seed data** for catalog year 2026-27, fetched 2026-11-12: College policy, the Core, CS BA/BS, three CS Bx/MS options, Math BA/BS, Economics BA, and two civilization programs abroad. Every rule node carries a verbatim quote (1,620 quotes, all re-checked against their pages). There are 115 golden plans.

**Screenshots (real API, real seed data):** `docs/screenshots/planner.png`, `docs/screenshots/planner-issues.png`, `docs/screenshots/course-page.png`, `docs/screenshots/program-page.png`.

**For Richard to check before prompt 06:** `data/seed/REVIEW.md` (one table per program: node, rule in plain English, quote, URL, needs_review) and `docs/OPEN_QUESTIONS.md`. Seed program versions have status `review`. They show to students only because `SHOW_UNPUBLISHED_PROGRAMS=true` in development.

### Prompt 02 · Verifier — done
Built V01-V12, the CP-SAT model (two phases: an exact solve, then max-satisfied under a deterministic work limit when that is infeasible), all 12 goal predicates, and the certificate builder plus checker. The checker passed a fuzz test against brute force: 1,600 random cases, 827 of them cross-checked. Semantics are recorded in `docs/CONTRACTS.md` "Verifier semantics": V05 skips empty quarters and Summer, V09 stays an error on partial plans with distance messages, share limits are reported as V08, and a certificate needs V03 and V07 to hold. Benchmark (60 courses, 201 nodes, 3 programs): median 127 ms for a complete plan, `check_certificate` 7 ms, against a 300 ms budget.

### Prompt 03 · Frontend — done
App shell, planner, Generate popup (form + SSE results with Apply / View diff), Advisor panel (messages, citation chips, proposal cards), a 5-step onboarding, course search and course page (prerequisite mini-graph, offerings, attribute card), and the program explorer and program page. A TypeScript port of `apply_ops` and the term helpers. The app calls the real API by default. MSW mocks, typed from the generated client, are used in vitest and e2e, and when `VITE_MOCK_API=1`. Endpoints that stay 501 in M1 show "not available yet". axe found 0 violations on the planner.

### Prompt 04 · Accounts (decision 5) — done
Backend in `services/api/api/auth/`: domain checks, hashed codes in Redis, argon2id, `__Host-` session cookies with rotation, CSRF on every cookie-authenticated state-changing request, Redis rate limits (keyed hashes, 24 h), and a process-wide log filter that redacts emails and IPs. Tests prove no email or IP reaches the logs, and that an email reaches only `account.email`. The `security-privacy-reviewer` found no high issues; its medium (no long-run cap on code guessing) and its three lows (login race, ban evasion by deletion, the production check failing open) are fixed. Integration: nginx forwards the client address (`TRUSTED_PROXY_HOPS=1`), and Redis runs without persistence so the counters never reach disk.

### Prompt 05 · Seed data and golden plans — done
`data/seed/2026-27/`: 1,273 courses (including 366 copies of cross-listed partners), 176 course lists, 11 programs, 112 rule nodes, and the College policy. 55 `needs_review` rule rows, plus 53 hand-encoded prerequisites flagged for review. 261 prerequisite sentences are kept verbatim but not formalized, none of them on courses a requirement names directly. `data/golden/`: 115 plans, at least 5 must-pass and 5 must-fail per program. Not encoded yet (open questions): Economics specializations, physical-sciences three-course combinations, placement-dependent rules, the CS curriculum-area breadth rule, and study-abroad language courses.

### M1 integration
- Catalog read endpoints (`services/api/api/repo/catalog.py`), built by a separate agent because prompts 02-05 left them as stubs and the planner needs them.
- Golden-runner fix: the seed is parsed once per run, not once per plan.
- Golden triage: the first run against the real verifier gave 106 of 115 passing. The 9 failures were fixed as follows:
  - **Bx/MS "at most two 20000-level" cap:** it counted a cross-listed 3xxxx enrollment as 20000-level. Added an opt-in `max_from.as_enrolled` (open question M1-1).
  - **Repeatable courses:** each enrollment of a `repeatable` course now counts. The Core Grey track takes HUMA 19100 twice (M1-2).
  - **V12:** it now also fires when the program would be met with letter grades (M1-3).
  - **cmsc-bxms-1 fail-05:** the plan was wrong and was corrected (M1-4).
  - Every verifier fix has a unit test. `CORE_VERSION` went to 0.1.1, which invalidates cached reports.
- Screenshots come from `apps/web/scripts/screenshots.mjs`, run against the Docker build with the real API.
- Known UI nits, not fixed: the course page's "Counts toward" lists Mathematics BA/BS twice, and a rail label reads "from from the list".

### How this run deviated from the kit
- The six subagents in `.claude/agents/` are not registered in this Claude Code session, because the session's root is the parent folder. Each was run as a general agent that read its definition file and used the model and effort it names: Fable 5.2 for the verifier and accounts work (prompt 04 asks for Fable), Opus for the rest.
- Subagents cannot start other subagents. So each parallel agent reviewed its own diff against `spec-reviewer.md`. The orchestrator ran the independent `spec-reviewer` on prompts 00 and 01 and on the whole M1 scope, and the `security-privacy-reviewer` on prompt 04.
- Decision 5 changed (Richard, 2026-11-12): prompt 04 was built as email + password, not blind signatures.
- Some merged commits carry a `Co-Authored-By: Claude Fable 5.2` trailer, because those agents ran on Fable.

### M1 gate (final run on `main`)
Run on `main` at `dbd2a56` (2026-11-12). Every command exited 0.
- `make up`: api, db, minio, redis, web and worker are `(healthy)`; the scraper, in its own profile, is also healthy.
- `make seed`: loaded terms=24, courses=1273, crosslist_groups=261, relations=7, requisites=833, offering_patterns=2762, course_lists=176, programs=11, college_policy=1.
- `make check`: ruff and mypy clean; generated client and JSON Schemas up to date. planner_core: 154 passed, coverage 99.72%. API and services: 194 passed. Web vitest: 59 passed. Golden: PASS=115.
- `make golden`: PASS=115, with at least 5 must-pass and 5 must-fail plans for each of the 11 programs.
- `make e2e`: 36 passed in Playwright, including axe on the planner and a phone-width check.

### Final spec review (whole M1 scope)
- The first full-scope review found 2 should-fix issues, no blockers:
  - Share limits, `requires`/`excludes` and `max_from` caps had no `source.quote` in the seed.
  - Three open questions were stale.
- Both were fixed in `dbd2a56`:
  - 19 verbatim quotes were added; each was fetched again and checked.
  - The loader now rejects these rules when they have no source.
  - The three stale items are marked resolved.
- The closing review of that fix reported: **"No unresolved correctness findings."**

## Richard's review of M1 (2026-11-14)
- Every open question now has its answer recorded under it in `docs/OPEN_QUESTIONS.md`. The work these answers create is listed there under "Work these answers create"; none of it is started.
- New working rule for the demo phase, now also in CLAUDE.md: a catalog question gets a strict default plus a warning, is logged as deferred, and work continues.
- The hand check of `data/seed/REVIEW.md` is deferred until before deployment. Seed program versions stay in `review` status.
- The Claude API and OpenRouter API keys are set. **On hold:** nothing sends them requests until Richard says so; LLM code is tested against fake clients only.
- Fable is overkill for the app (Richard): program formalizer E3 moved to Opus 5.5, its second run E3b to Sonnet 5.5 (`llm_routing.yaml`, SPEC "Model routing").
- Questions for Richard are now written in plain language with a suggested answer or options (CLAUDE.md "Questions for Richard").

**Planned, on hold until API calls are allowed: choose the cheapest model and effort per task.**
- **Free savings first:** cache the fixed prompts, and send offline jobs through the Batch API (50% off).
- **Then compare settings** by cost per correctly finished task.
- **Start with E1** (prerequisite sentence → rule). About 780 hand-encoded prerequisites in the seed serve as the answer key, so scoring is automatic.
  - Candidates: Haiku 5.5 at low, medium and high effort; Sonnet 5.5 at low and medium; Opus 5.5 at low.
  - Sample: 200 pairs × 3 runs.
  - Rough cost: $15–40, about half with the Batch API.

**Next:** start prompt 06 (generator) only when Richard says go.

## Prompt 06 · Deterministic plan generator and change sets (2026-11-14)

**What was built**
- **`planner_core.generator.generate`** (pure, no LLM): a placement model on top of the V07 program model.
  - It decides where each floating course goes: the student's unlocked planned courses in the quarters being planned, plus a pool of catalog courses.
  - It respects prerequisite order, `p_offered` >= 0.3 unless the student accepts the course, full-time loads and the overload rule, and graduation totals. Locked and completed courses stay put.
  - It returns up to 3 variants, each differing from earlier ones in at least 4 placements.
  - Every variant goes through `verify` + `check_certificate`; a rejected variant is dropped and logged as an `ALERT`.
- **Goal compiler** (`goalcompile.py`): goals become hard bounds, rewards, penalties, a pinned block or precedence rules, exactly as the SPEC goal table says.
- **Default preferences** (`preferences.py`): interest match, then forum `recommend_rate`, then lower course level. An agent's ranking (prompt 07) can override them.
- **Plain-English explanations** for impossible requests. Every hard goal and limit is an assumption literal, and the minimal conflicting set is named. Examples:
  - "Graduating by Spring 2028 needs N more courses than your remaining quarters allow."
  - "Completing cmsc-bs isn't possible … Still missing: … Some of these courses need a placement result."
- **Saved plans API:** create, read, update, delete, duplicate, import and compare plans, plus item edits guarded by the plan hash.
- **Change sets:** create, list, apply (only while the plan hash matches; otherwise marked `stale`, re-previewed, 409), apply selected quarters, and discard.
- **`POST /plans/{id}/generate?mode=deterministic`** stores each variant as a proposed change set. **`POST /plans/generate`** does the same for browser-only plans, without saving.
- **Generate popup:** wired behind `VITE_GENERATOR_MODE` (default `deterministic` until prompt 07). It shows the variants, or the explanation when nothing fits.

**Spec review:** the `spec-reviewer` found 9 gaps, and all are fixed:
- A hard profile (CS + Math + Bx/MS) timed out. A feasibility-first solve, plus a staged fallback, now finds a plan.
- Explanations were not minimal. An exact capacity check now runs before solving, and literals are shrunk in a better order.
- Two profiles had wrong inputs (abroad quarters, a CHEM course code). They are corrected, and every profile now asserts its exact outcome.
- `PATCH /plans/{id}` silently dropped course edits. It now saves items, and item ids stay stable.
- Re-previews of stale change sets broke on new item ids. Fixed by the stable ids.
- The preference order did not strictly follow interest, then recommend rate, then level. The weights are rescaled.
- Work on the generate endpoints was unbounded. The time budget is clamped, plan size is bounded, and there is a per-account daily limit.
- A valid change set was marked stale when only the client's hash was old. It now returns 409 without touching the change set.
- The popup ignored saved plans. It now uses the saved plan's endpoints when the plan is unchanged since it was saved.

**Evidence:**
- `make check` passed: planner_core 170 tests at 97.10% coverage; 224 API and service tests; 61 web tests; golden 115/115.
- All 20 profiles finish in under 5 s, each with its exact outcome:
  - 15 give verified plans, among them CS + Math + Bx/MS and both study-abroad blocks.
  - 5 give explanations naming the exact limits: no placement, two transfers, graduating early, three courses a quarter.
- `make e2e` 36 passed.

**Try it** (stack up with `make up && make seed`):
```bash
curl -s -X POST 'localhost:8000/plans/generate?mode=deterministic' -H 'Content-Type: application/json' \
  -d '{"plan":{"catalog_year":"2026-27","entry_term":"2026-AU","placements":["MATH 15100"],"programs":[{"program_id":"core"},{"program_id":"cmsc-bs"}]},"options":{"variants":2}}' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print([(v["label"], v["report"]["status"], len(v["change_set"]["ops"])) for v in r["variants"]], r["infeasible"])'
```
In the app:
1. Open http://localhost:5173/onboarding.
2. In step 2, add a credit: Kind **Placement**, Description `MATH 15100`, units 0.
3. In step 3, choose the programs **core** and **cmsc-bs**.
4. Finish, then click **Generate plan** and then **Generate**.

Without the placement, the popup explains that the calculus requirement needs a placement result.

## Step 2 · Design foundation from DESIGN.md (2026-11-14)

**How DESIGN.md was applied.** The full mapping is in `docs/DESIGN-IMPLEMENTATION.md`.
- **Tokens:** every color, type style, radius, shadow and layout width in `docs/DESIGN.md` is a CSS custom property, wired into the Tailwind v4 theme (`apps/web/src/index.css`, `@theme`). That covers 43 colors, 14 type styles, the radii and two elevation levels. Tailwind's default palette, sizes, radii and shadows are switched off, so a class can only name a design token, and components contain no raw hex values.
- **Fonts:** Newsreader (display) and Inter (text) are bundled from npm (`@fontsource*`) and served from `/assets`. The app makes no CDN or third-party request; an e2e test loads 13 pages and fails on any outside request.
- **Components:**
  - `components/ui`: Button variants (the primary pill is drawn 40px tall inside a 44px hit area), inputs, select, textarea and field, badges, notices, cards, a local SVG orb, avatar, dialog, menu, tabs and icons.
  - `components/layout`: top nav (it folds into a menu button below 768px), footer, page container and header, section, empty and loading states.
- **Pages:** every page and feature is restyled with those components. That includes home, onboarding, the planner (grid, cards, requirement rail, right rail, Generate popup, Advisor), course search and course page, programs, plans and compare, sign-up, login, account and the static pages. Behavior is unchanged: no existing test changed.
- **Accessibility:** contrast and visible focus as required; an e2e test measures that every control is at least 44px; the "Move to..." keyboard menu is kept; axe reports 0 violations on the planner, home and course pages.
- **Conflicts** between DESIGN.md and the SPEC (the behavior was kept) are in `docs/OPEN_QUESTIONS.md` as DF-1 to DF-11, each with a suggested answer.

**Evidence:** `make check` passed; `make e2e` 41 passed.

**Prepared for steps 3 and 4:**
- `llm_gateway.api` is the contract shared by prompts 07, 08 and 11: `LLM.structured(task, ...)`, `FakeLLM` for tests, and `get_llm()`, which refuses every call until prompt 07 configures a client.
- Pre-added dependencies: `anthropic` and `openai` (gateway), `markdown-it-py` and `nh3` (sanitized forum markdown).

## Step 3 · Prompts 07 and 08, in parallel (2026-11-14)

- **Prompt 07 (`agent-engineer`):**
  - `llm_gateway`: routing from `llm_routing.yaml`, an Anthropic backend with OpenRouter as fallback, an agent loop with budgets, a repair turn, cost logging, and a FakeLLM that replays tool calls.
  - A1 plan-generator agent around the prompt 06 solver, with fallbacks and SSE progress.
  - A2 advisor chat with a scope classifier, read-only tools, a draft-only `propose_change_set`, a deterministic confirmation parser, citations checked against tool results, and 30-day history.
  - Evals built (A1 50 profiles; A2 60/20/10/10). `make evals` needs `CONFIRM_SPEND=yes` and is Richard's to run.
  - Real calls happen only with `LLM_LIVE=true`; it is off. With no model, generation uses its fallbacks: default preferences and no rationale.
- **Prompt 08 (forum):**
  - Pages, reviews and discussions, nested comments in `ltree`, votes with Best/Top/New/Controversial/Hot ranking in SQL, per-page pseudonyms with HMAC `author_ref`, and day-level dates.
  - Markdown sanitized on the server; a regex scrub plus A4 moderation (3 s timeout, then hold for review); reports, an admin moderation queue, and suspension after 3 upheld removals.
  - A dev-only `make seed-forum-demo` adds fake "Demo Instructor A-E" pages.
  - axe finds no violations on the forum, thread and moderation pages.
- **Both** build their UI from the step-2 components and tokens.
- **Merge:** conflicts were in the mocks index, config, the API surface test and open questions. A CSRF token is now restored after a page reload, which fixed plan saves after a reload. Evidence: `make check` passed; `make e2e` 52 passed.

## Step 4 · Prompt 11: forum ratings into course attributes (2026-11-14)

- A nightly job (Arq cron at 03:30; `make attributes` by hand) turns reviews into course and course x instructor values with a Bayesian average:
  - prior weight 5 against the department average, or 2 against the AI's first guess;
  - text-extracted values and reviews older than 4 years weigh 0.5;
  - a 95% interval;
  - forum numbers published only from 3 ratings up, with the estimate shown below that.
- A3 extraction (quotes and numbers checked), "What students say" summaries (at most 120 words, `[n]` citations checked, published only when A4 moderation says `ok`), and cold-start estimates. All are tested with FakeLLM. With no model, the job runs on the structured ratings alone.
- The forum page shows the summary with links to the cited posts; the course page and planner read the new values.
- Questions Q8-Q11 in `docs/OPEN_QUESTIONS.md`.
- **Review fixes for steps 3 and 4** (spec and security reviews of 07 and 08):
  - logged-out users get no forum tools in the agents, and chat text is scrubbed of emails and phone numbers before it is stored or sent;
  - citation chip labels are built by the server, not written by the model;
  - the moderation wrapper escapes its closing tag in any letter case; A4 moderation gets 1024 output tokens;
  - only removals still in force count toward suspensions, and an account cannot be deleted for 30 days after one (P08-12);
  - the plan generator no longer times out on large plans when the machine is busy. Cause: CP-SAT uses a single search worker whenever a model has assumptions, and that one search was luck-dependent (CS + Math + Bx/MS took 1.7 s to over 4 s). The goals are now fixed as constraints on a copy of the model, so all 8 workers search (0.2-0.9 s). Assumptions are used only to explain an impossible request. The time budget now runs to a deadline: finding a first plan may use all of it, and improving it or finding further variants gets what is left. Plans with four or more programs go straight to the staged solve;
  - vitest waits up to 5 s for async UI (was 1 s), so `make check` on a busy machine no longer fails on timing.
- **Final review fixes (spec and security reviews of the whole goal, through step 4):**
  - forum numbers need 3 different posts (not 3 mentions); a discussion post adds at most one value per number (the median of its mentions); review text is not mined, since its ratings already count (Q13);
  - an edited post is read again and its old quotes stop counting; deleting or blanking a post (or an account with its posts) deletes its stored quotes;
  - a "What students say" summary that cites a post no longer visible is hidden at once (forum page and advisor tool) and deleted and rewritten that night;
  - a page's starting point is the department average, as the SPEC says;
  - quotes the model returns HTML-escaped still match the post;
  - the nightly job runs in a thread with a 1-hour limit, and the worker redacts its logs; database errors never log query values;
  - the browser's chat history is scrubbed before it reaches the model;
  - an older admin removal no longer counts again after the automatic check removes the same post; the 30-day deletion wait is checked after the password;
  - the generator no longer calls a request impossible when only its staged shortcut dead-ends, and explaining an impossible request stays within the time limit;
  - A3 summary and cold-start calls use low effort with 2000 output tokens, so answers are not cut off.
  - after the final reviews: editing, blanking or deleting a post that a summary cites deletes that summary at once (it is rewritten that night); text values count once per person per page, so posting three times does not reach the 3-rating minimum; explaining an impossible request finds its conflicting limits with all the time left, so a busy machine no longer adds an extra limit to the explanation; the curator console has screenshots too.

## Step 5 · Design review at 1440 and 390 (2026-11-14)

- Every page reviewed at desktop (1440×900) and phone (390×844) width against `docs/DESIGN.md`; per-page findings and fixes are in `docs/DESIGN-IMPLEMENTATION.md` ("Design review at 1440 and 390 (step 5)"). Main fixes: planner course cards (full-width body, issues no longer squeezed), the nav marks the current section on every page, the footer lines up with the top bar, forum section heads in the display serif, two-up course filters on phones, plan cards in two rows, no stray gaps from empty error regions, 44px targets on dense links, plain "Coming soon" copy instead of build notes.
- Deferred review findings closed: advisor `post` / `summary` / `attribute` citation chips now link (thread, forum page, course page; a plain pill when logged out); forum radio rows use the shared `ChoiceRow` (as do onboarding, the Generate dialog and the program picker); the forum `Sort` type comes from the generated OpenAPI schema.
- Screenshots: `make screenshots` (`SCREENSHOTS=1`) writes 47 PNGs to `docs/screenshots/` (23 pages at both widths, plus the phone menu).
- axe at both widths on the planner (with Generate and Advisor open), the forum page and the thread: no serious or critical violations (`e2e/design.spec.ts`).
- New questions DF-12 (About page text) and DF-13 (reaching the advisor on a phone).

## Goal wrap-up: prompts 06, 07, 08, 11 and the design work (2026-11-14)

**What was built**
- **Plan generator (06):** a CP-SAT generator that returns up to three verified plans (each re-checked by `check_certificate`), or explains in plain English which limits conflict. Change sets carry stale-plan protection.
  - API: `POST /plans/generate` and `/plans/{id}/generate`.
  - Profiles: 20 student profiles run in under 5 s.
- **Design foundation (step 2) and design review (step 5):** see below.
- **AI layer (07):** an LLM gateway with routing in `llm_routing.yaml`, the A1 plan-generator agent and the A2 advisor chat, all streaming progress.
  - Every call is tested with a fake model. Real calls happen only with `LLM_LIVE=true`, which is off.
- **Forum (08):** course × instructor pages, reviews, discussions, nested comments, votes, reports, an automatic moderation check, and an admin queue.
  - Pseudonyms are per page, and dates are day-level.
- **Forum numbers (11):** a nightly job turns reviews into course and course × instructor numbers using a Bayesian average.
  - "What students say" summaries are checked and moderated before they are shown.
  - AI first guesses fill in for courses without enough reviews.
- **Reviews:** the final spec and security reviews of the whole goal (`500ea7b^..96cdb54`) have no open high or medium findings. Everything they found was fixed, with tests (see the step 4 and step 5 notes above).

**How DESIGN.md was applied** (details in `docs/DESIGN-IMPLEMENTATION.md`)
- **Tokens:** every DESIGN.md color, type style, radius and shadow is a Tailwind theme token. Tailwind's own palette is switched off, so components can only use design tokens.
- **Fonts:** Newsreader and Inter are bundled with the app; no request goes to another site (an e2e test checks this).
- **Components:** shared parts in `components/ui` (buttons, fields, `ChoiceRow`, cards, dialogs, tabs, notices) and `components/layout` (top nav with a phone menu, footer, page header, empty and loading states) are used on every page.
- **Step 5:** every page was reviewed at 1440×900 and 390×844 and fixed:
  - nav "current section";
  - footer alignment;
  - planner course-card layout;
  - phone filters;
  - 44px link targets;
  - `ChoiceRow` everywhere;
  - advisor citation chips that link.
  
  Screenshots of every page at both widths are in `docs/screenshots/` (`make screenshots`).
- **Accessibility:** real buttons and labels, 44px targets (measured by an e2e test), and visible focus. axe finds no serious or critical issues on the planner (with the Generate dialog and the Advisor open), the forum page and the thread, at both widths.

**Gate on `main` (96cdb54)**
- `make check`: lint and types clean; planner_core 172, API 404, web 90 passed; golden 115.
- `make e2e`: 56 passed (the 49 screenshot tests are skipped unless `SCREENSHOTS=1`).
- 9 axe tests passed.

**Try it.** Start with `make up && make migrate && make seed && make seed-forum-demo`. Use `.env` from `.env.example`: `ENVIRONMENT=development`, `EMAIL_BACKEND=console`, and `LLM_LIVE=false`.

*Plan generation, without AI:*
```bash
curl -s -X POST 'localhost:8000/plans/generate?mode=deterministic' -H 'Content-Type: application/json' \
  -d '{"plan":{"catalog_year":"2026-27","entry_term":"2026-AU","placements":["MATH 15100"],"programs":[{"program_id":"core"},{"program_id":"cmsc-bs"}]},"options":{"variants":2}}' \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print([(v["label"], v["report"]["status"], len(v["change_set"]["ops"])) for v in r["variants"]], r["infeasible"])'
# -> [('Option A', 'valid', 42), ('Option B', 'valid', 42)] None
```
In the app:
1. Open http://localhost:5173/onboarding.
2. In step 2 add a credit: Kind **Placement**, Description `MATH 15100`.
3. In step 3 pick **core** and **cmsc-bs**.
4. Finish, then click **Generate plan**, then **Generate**.

*Plan generation through the agent:*
```bash
curl -s -N -X POST localhost:8000/agents/generate -H 'Content-Type: application/json' \
  -d '{"plan":{"catalog_year":"2026-27","entry_term":"2026-AU","placements":["MATH 15100"],"programs":[{"program_id":"core"},{"program_id":"cmsc-bs"}]},"request":"Lighter workload, graduate on time"}'
```
With `LLM_LIVE=false` it streams its steps, says "Using the default elective ranking", and still returns two verified options.

*Advisor chat:* open the planner's **Advisor** tab and ask "Is CMSC 14100 hard?". With `LLM_LIVE=false` it answers "The advisor can't answer right now. You can still edit your plan by hand."
- To try the real advisor (it costs money, so it is Richard's call):
  1. Set `LLM_LIVE=true` and `ANTHROPIC_API_KEY` in `.env`.
  2. Run `make up`.
  3. Ask again.
- Logged-out users get answers without forum content.

*Forum:*
1. Open http://localhost:5173/signup and use any `@uchicago.edu` address. The 6-digit code is printed in the API log (the address is not): `docker compose logs api | grep signup_code`.
2. Open http://localhost:5173/courses/CMSC%2014100/i/demo-instructor-a. The demo pages are fake (Demo Instructor A–E). Post a review or a discussion, vote, comment and report.
3. Admin queue: run `docker compose exec db psql -U quarterly -d quarterly -c "UPDATE account SET role = 'admin' WHERE username = '<your username>';"`, then open http://localhost:5173/admin/moderation.

*Forum numbers:* `make attributes` turns the demo reviews into course numbers; without AI it uses the star ratings alone. For example, `curl -s 'localhost:8000/courses/CMSC%2014100'` then shows workload, difficulty and recommend rate with `"method": "forum"`.

**Note from this run:** `make up` could not rebuild the Docker images today. Docker Desktop timed out reaching Docker Hub and ghcr.io, and a plain `docker pull python:3.12-slim` hung as well. So the commands above were checked against the current code with the API run directly (`uvicorn` on port 8001) and the stack's database and Redis. `make up` rebuilds as soon as Docker can reach the registries again.

**Questions for Richard from this goal** (each has a suggested answer in `docs/OPEN_QUESTIONS.md`):
- P08-12: the 30-day wait before deleting an account after a moderator removes a post.
- P08-13: logged-out students get AI answers without forum content.
- Q12: the planner uses per-course numbers until the class schedule says who teaches.
- Q13: how forum numbers count posts and people.
- DF-12: what the About page should say.
- DF-13: how a phone user reaches the advisor.
- The older screenshots `planner.png`, `planner-issues.png`, `course-page.png` and `program-page.png` (from before this goal, on real catalog data) are still in `docs/screenshots/`. They hold no personal data. Keep or delete them as you prefer.

### Fix after the wrap-up: login on the Docker site (2026-11-14)

- **Symptom (Richard):** on http://localhost:5173 the UI looked old and logging in did not work.
- **Cause 1, a real bug:** the app kept two separate records of who is logged in. Login updated one. The top bar, planner, "My plans" and the import of a logged-out plan read the other, which kept its cached "logged out" answer. So after a successful login the top bar still said "Log in" and the planner acted logged out until a reload.
  - Fix: `apps/web/src/lib/session.ts` now reads the one auth store that login, sign-up and logout update.
  - Test: `e2e/auth.spec.ts` checks that the top bar shows the account right after login. It fails on the old code.
- **Cause 2, stale pages:** nginx sent no cache headers, so browsers could keep showing an old build for hours after a rebuild.
  - Fix: `apps/web/docker/nginx.conf` now sends `no-cache` for the page and caches the fingerprinted `/assets/` files for good.
  - After this change, one hard reload (Cmd+Shift+R) clears any old copy.
- **Checked on Docker:** the served bundle is byte-identical to a fresh build of `main`. A real Chromium logs in and lands on the planner with the account in the top bar.
- **Safari note:** the session cookie is marked `Secure`. Safari does not keep `Secure` cookies on plain `http://localhost` (Chrome and Firefox do), so log in with Chrome or Firefox locally. Option: `SESSION_COOKIE_SECURE=false` in `.env` for local development only; the API refuses that setting outside development.
- **Evidence:** `make check` passed (web 90); `make e2e` 56 passed.

## Richard's answers built (2026-11-14)

Richard answered the questions from the steps 1-5 run (recorded in `docs/OPEN_QUESTIONS.md`, "Answers to the questions from the steps 1-5 run"). What changed:
- **No check before publishing (P08-1):** posts, comments and edits appear at once, after emails and phone numbers are removed. Anyone can report a post; an admin removes it from the moderation queue. Removing a post also deletes its extracted quotes and the page's "What students say" summary, which is rewritten that night. The AI check now runs only on those AI-written summaries.
- **Manual suspensions only (P08-3):** removing posts never suspends anyone by itself. When removing, an admin may choose to suspend the author for 7, 30 or 90 days, without learning who the author is. The length is recorded with the decision.
- **Optional review questions (Q11):** "How fast it moved" and "How strictly it was graded" (1-5, optional, with a Clear button). Averages and charts count only the reviews that answered. The nightly job publishes them as course numbers, and the "protect my GPA" goal uses grading strictness.
- **Cross-listed courses (P08-5):** one forum page per cross-listed course and instructor, shown under every code ("Also listed as ..."). Course numbers are the same for every code. The advisor finds the page under any code.
- **Transfer students (Q6):** transfer credit counts toward the 3800 units by enrollment, and at least 1800 units must be taken at UChicago. The rule is in the verifier (a new "Units at the College" row), the generator and the seed. Its source is Richard's answer, quoted verbatim and marked for review until the catalog sentence is found. The CS BA transfer profile now gets a verified plan.
- **Smaller items:**
  - the Log in / Sign up links bring students back to the page they came from (P08-10), and only paths on this site are accepted;
  - deleting a plan asks "Delete this plan? Yes, delete / Cancel" (DF-7);
  - the About page has the three disclaimers (DF-12);
  - on phones the planner has jump buttons to Requirements, Plan, and Issues and advisor (DF-13);
  - DESIGN.md lists the warning and info background colors (DF-6);
  - the privacy page explains the suspension trace (P08-2).
- **Reviews:** a spec review and a security review of these changes found no high findings. One medium (the advisor's forum tools ignored cross-listed codes) and all the lows were fixed, each with tests. They covered:
  - return links everywhere;
  - privacy wording;
  - REVIEW.md rows for the two Q6 fields;
  - stricter return-link checks;
  - derived data deleted on removal;
  - a 90-day cap;
  - cross-listing chains.
  One new question for Richard: **P08-14** (suspended students and account deletion; ending a suspension early).
- **Evidence:** `make check` passed (planner_core 174, API 407, web 104, golden 115); `make e2e` 58 passed (49 screenshot tests skipped); screenshots refreshed (`make screenshots`).


## FEEDBACK F2-F6 · Planner UI — done (2026-11-14)

- **F2 Summer first:** the web term helpers mirror `planner_core.terms` (an academic year runs Summer, Autumn, Winter, Spring). Each year in the grid opens with its Summer (still hidden until "Show Summer"); nothing follows the last Spring.
- **F3 Years:** the grid ends at the plan's graduation quarter (`graduation_term`; by default the Spring of the last year left, so three years for a second-year transfer). "Graduating in" (Autumn, Winter or Spring), "Add a year" and "Remove last year" (refused while that year has courses). Years are named by class year ("Second year"). Local plans saved with the old `years: 5` open with five years. Onboarding's review step shows the years and graduation quarter.
- **F4 Layout:** a toolbar (Requirements, Goals, Check plan, AI advisor, Save, Generate plan); a right-hand drawer with the requirement tree (bold code, small name, subtle "2 of 3"), goals and the plan check (full screen on a phone); errors shown only as a small count on "Check plan"; the AI advisor as a sheet from the top, labelled "Generative AI", with chat bubbles and a typing indicator.
- **F5 Text:** filler lines removed (list in `docs/DESIGN-IMPLEMENTATION.md`, "FEEDBACK UI"); the footer says Quarterly is not affiliated with the University of Chicago; the planner says "Not official advising. Check with your adviser."
- **F6 Motion:** CSS-only entrances for dialogs, the drawer, the advisor, new list items and placed cards, plus button press feedback; none under reduced motion.
- Also: `docs/schemas` regenerated (they lagged the `graduation_term` commit); drag and drop now drops on the quarter under the pointer (planner and onboarding).
- **Evidence:** `make check` passed (planner_core 178, API 408, web 116, golden 115); `make e2e` 68 passed (55 screenshot tests skipped); `e2e/feedback-ui.spec.ts` covers each item; screenshots refreshed, new `plan-drawer`, `plan-check`, `plan-years`.
- **Next:** F2-F6 to move in `docs/FEEDBACK.md`; DF-13 (phone jump buttons) is superseded by the drawer.


## Prompt 09 · Catalog ingestion pipeline and review console (2026-11-15)

Built and tested with FAKE catalog pages and a fake model only (no request to the Claude, Anthropic or OpenRouter APIs, and none to the College Catalog). Code: `services/worker/worker/ingest/`, prompts `prompts/e1_prereq.md`, `e2_enumerator.md`, `e3_formalizer.md`, `e3b_formalizer.md`, `e4_backtranslation.md`, the review API in `services/api/api/review/`, the page `apps/web/src/pages/AdminReviewPage.tsx`. Contracts: `docs/CONTRACTS.md` "Catalog ingestion (prompt 09)". Questions: `docs/OPEN_QUESTIONS.md` "Prompt 09".

- **Crawler:** catalog index, A-Z index, program and course pages, and the College's counts page. It obeys robots.txt, waits at least a second between requests, says who it is with the contact address from `CATALOG_CONTACT_EMAIL` (it will not start without one), and stores every response in MinIO with a `source_snapshot` row and its sha256. Tested against a local server serving FAKE CourseLeaf pages (`services/worker/tests/fixtures/catalog/`).
- **Course blocks** are read by plain code into staged course, cross-listing and relation rows. Each subject becomes one review item showing what is new, changed or removed since last year; nothing is written until a curator accepts it.
- **E1** (prerequisite sentence to rule), **E2** (list of programs; the run stops if the count does not match at least two independent lists), **E3** (program rules, run twice with a reordered prompt and a different model, tools `read_snapshot`, `lookup_course`, `get_course_list`, `validate_rules` up to 5 times, `run_golden`, `submit_rules`) and **E4** (writes the rules back in English and lists differences from the page).
- **Checks (a)-(g)**, including the word-for-word quote check, and a **diff against last year's published rules**: unchanged programs are marked "Unchanged since last year" (still published by a person, P09-1); changed ones list what changed.
- **Review console** at `/admin/review` (replaces the "Coming soon" page): each rule beside the catalog's own words, flags where the second run disagrees, where something changed or where the English check found a difference, the check results, Accept / Edit / Reject per item, and "Publish this version". Admins only, with the CSRF token, like the moderation queue. The three admin endpoints that answered 501 now work.
- **Jobs:** a yearly run (1 August) and a monthly check for changed pages (the 15th). Both do nothing unless `CATALOG_INGEST_ENABLED=true` (off by default, in `.env.example`).

### Pilot ingestion (for Richard)

**What it does.** It runs the four catalog agents on the 11 programs we wrote by hand (`data/seed/2026-27/programs/`) and compares what the agents produce with our hand-written rules, piece by piece (each requirement, group of courses or limit is one "node"). The target is that at least 95% of the nodes match. The report lists every node that does not match, so we can see whether the agent or our hand copy is wrong. It also checks the agents' reading of 86 prerequisite sentences and their list of programs. Apart from keeping a copy of the catalog pages it reads, nothing is written to the database, and nothing is shown to students.

**The free version (safe to run any time).** A stand-in model answers with our own hand-written rules, on pages built from our own quotes. It checks that the whole pipeline and the report work, so it always shows 100%; it says nothing about how good the real model is.

    make ingest-pilot ARGS=--fake

Result today: 146 of 146 nodes match (100%), 86 of 86 prerequisite sentences match (28 of them would still go to a person, because they name courses outside our seed or cannot be written as a rule), all 11 programs found. Report: `docs/ingest-pilot/report-fake.md`. One check is flagged: the Mathematics BS needs 21 courses by the "9 to 19 courses" rule (P09-2).

**The real version (costs money; only when you say so).**

1. Put `ANTHROPIC_API_KEY` and `CATALOG_CONTACT_EMAIL` (see P09-3) in `.env`, and start the stack with `make up` (the fetched pages are kept in MinIO and the database).
2. See the estimate without spending anything: `make ingest-pilot ARGS=--estimate` (about $16 at list prices for the 11 programs).
3. Run it: `CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot`

It refuses to call a model unless both `CONFIRM_SPEND=yes` and `LLM_LIVE=true` are set, prints the estimate first, and stops once it has spent $25 (change with `INGEST_COST_CAP_USD=10`, for example). It fetches 17 catalog and study-abroad pages, one per second. The report goes to `docs/ingest-pilot/report-live.md`. To try a single program first (about $2): `CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot ARGS=--programs=econ-ba`.

**Evidence (after merging main with prompt 10):** `make check` passed (planner_core 178; API, worker, scraper and gateway 531; web 120; golden 115); `make e2e` 72 passed (55 screenshot tests skipped), including `e2e/review.spec.ts` (accept and publish, accessibility, admins only). New tests: `services/worker/tests/test_ingest_*.py` (crawler against a local FAKE catalog server, parsing, checks, the four agents with FakeLLM, the pipeline, the pilot and jobs, and a database run) and `services/api/tests/test_review_api.py`.

**Not built yet:** the other curator-console parts the SPEC lists (ingestion-run history, a rule editor with live validation, LLM cost by task); E2 reads only the catalog and the College's counts page (study-abroad and department pages are not crawled); a real run of any agent.

**Next:** Richard decides P09-1 to P09-9 and whether to run the real pilot; then the first yearly run on a copy of the database.

## Schedule pipeline (prompt 10, 2026-11-15)

**What works (tested on fixtures only):**
- The Class Search scraper code exists but is switched off (`SCHEDULE_SCRAPER_ENABLED=false`, the default). It refuses to run until it is switched on and `CLASS_SEARCH_URL` is set. No request has ever been sent to Class Search or any University site.
- A deterministic parser turns saved result pages into course sections (term, course, section, component, instructors, meetings, capacity, status). It raises an error on an unfamiliar layout instead of quietly returning nothing.
- Checks:
  - unknown course codes become review items;
  - instructor names that are close but not certain become review items, never merged automatically;
  - a department whose section count moves more than 30% from the same quarter last year raises an alert.
- Updates: forum pages (through the cross-listing-aware `ensure_page`) and the "how likely is this course offered" numbers: (k+1)/5 from history, 1 for a posted schedule, 0.95 for an accepted department plan.
- Department pages: an AI extraction step (tested with a fake model) for CS course-info. Every offering must carry a verbatim quote from the page, checked by code, and the result goes to review.
- Self-repair: when parsing fails, an AI step proposes new selectors. A proposal must reproduce the last good counts on stored pages, and it always goes to review, never applied automatically.
- A weekly worker job that does nothing while the switch is off.
- Tests: 31 scraper tests.

**What is blocked:** reading the real Class Search. The pages used are **synthetic** (`services/scraper/fixtures/SYNTHETIC_*`, clearly labelled), because no real pages have been saved and the University has not given permission. See P10-1 in `docs/OPEN_QUESTIONS.md` for how to save real pages from your browser.

## End-to-end journeys A-D on the real stack (2026-11-15)

**What changed:**
- `make e2e` now runs both suites: the mocked one (`apps/web/e2e`), then `make e2e-stack`, which starts the Docker stack with `docker-compose.e2e.yml`, migrates, seeds, loads the fake forum demo, runs the forum summary job with the fake model, and runs `apps/web/e2e-stack/` (journeys A-D from the SPEC). The fake model (`LLM_FAKE=e2e`) answers every agent request; nothing reaches Claude or OpenRouter. Sign-up codes are read from the API log (console email).
- Fix: after sign-up, the plans made while logged out are imported into the account, but Save then made a second copy. The import now remembers which account plan each one became, so Save updates it. Test: `localPlans.test.ts`; journey A checks there is exactly one account plan.
- Fix: the "Study abroad" goal now uses the study-abroad program already on the plan (it always used the first one listed, Córdoba). Test: `goals.test.ts`; journey C.
- Fix: the web server cut off the AI agents' live progress after 60 seconds of silence, and one agent step may take up to 75 seconds with a real model. The agent routes now wait up to 5 minutes (`apps/web/docker/nginx.conf`). The earlier "Plan generation failed" in the stack was the full disk, not this.

**What the app does not do yet (found by the journeys):**
- A3: the Core is not pre-placed as requirement slots; the grid starts empty.
- A4: generated options are named "Option A/B/C", not names like "Exploratory CS".
- B3: no control for the goal "Bx/MS application in Winter of 3rd year".
- B4: for a second-year transfer with CS BS + Math BS + Bx/MS, no plan fits; the app lists exactly which rules conflict (shared-course limits, the unit limit per quarter, units and quarters to graduate, offering patterns).
- C: the SPEC example says "Paris, Spring Y2", but the catalog offers the Paris program in Autumn only, so the journey uses Autumn of year 2. The goal shows the program's internal id ("civ-abroad-paris-mdd") instead of its name.
- D: the demo forum has no instructor on MATH 20700, so the journey uses CMSC 14100 with Demo Instructor A.

**Next:** pick which gaps to build; the journeys record each one as a "gap" note on the test.

## Goal wrap-up: FEEDBACK, prompts 09, 10, 12 (2026-11-15)

### What was built
1. **Every FEEDBACK item is resolved** (each marked "Resolved in <commit>" in `docs/FEEDBACK.md`, with its tests or screenshots):
   - Generate plan names what to fix instead of "this is a bug".
   - Summer comes before Autumn in each academic year.
   - Years follow the years left (three for a second-year transfer), with add-a-year, remove-the-last-year and graduating early.
   - Planner redesign: a right-hand drawer with the requirement tree, subtle errors behind "Check plan", and the AI advisor as a chat that opens from the top and is labelled "Generative AI".
   - Filler text removed.
   - Gentle motion, switched off under reduced motion.
   - An "End suspension" button for admins.

   SPEC changes are listed in `docs/SPEC-CHANGES.md`.
2. **Catalog ingestion (prompt 09):** crawler, course parser, the E1-E4 AI steps (tested with a fake model only), checks (a)-(g), the year-over-year diff, the review console at `/admin/review`, and `make ingest-pilot`. Its free `--fake` run agrees with the hand seed on 146/146 rule nodes.
3. **Schedule pipeline (prompt 10):** built and tested on clearly labelled synthetic pages. The scraper is off (`SCHEDULE_SCRAPER_ENABLED=false`) and has never contacted Class Search.
4. **Hardening (prompt 12):**
   - Journeys A-D run in a real browser against the full Docker stack, with a stand-in AI (`LLM_FAKE=e2e`), as part of `make e2e`.
   - A load test (`make loadtest`).
   - Encrypted nightly backups (`scripts/backup.sh`, restore tested).
   - A single-VM deployment guide with Caddy (`docs/DEPLOY.md`).
   - An hourly AI-spend alarm.
   - A not-affiliated line in every page footer, no University logos, and "Not official advising" on the planner.
   - Final security and spec reviews.

### Load test (prompt 12, final run on the Docker stack through nginx, 2026-11-15)
`make loadtest` (`loadtest/run.py`):
- `POST /verify`: 49.6 requests/second, median 27 ms, p95 240 ms. The target is 50/s with p95 under 500 ms: **met**.
- Forum page reads: 99.3 requests/second with 0 failures. The target is 100/s: **met**. The p95 was 550-560 ms on this laptop; the prompt sets no latency target for forum reads.

Earlier runs on the busy laptop varied (P12-1), so run it again on the real server (launch checklist step 8).

### Final reviews (2026-11-15)
- **spec-reviewer (whole spec):**
  - one high finding: behind Caddy every visitor shared one rate limit. Fixed in 7122207 (nginx appends to `X-Forwarded-For`; production `TRUSTED_PROXY_HOPS=2`; tested);
  - lows fixed: chat-history purge cron, privacy wording, planner notice wording, backup checksum tool, load-test wording;
  - the load-test target is logged as P12-1.
- **security-privacy-reviewer (whole repository):**
  - four medium findings, all fixed in 7122207 and f744faa: the same rate-limit finding; the graduation quarter capped at 6 years; the rules cache limited to real catalog years; no client IPs in Caddy's error log;
  - six lows fixed in f744faa: the end-suspension guard; no admin usernames on program pages; safe source links in the review console; https crawling; backup umask and off-site expiry; pilot spend logged.
- **No high or medium finding is left open.**
- **Re-review at 34457b1 (both reviewers again, 2026-11-15):** every earlier finding checked at HEAD.
  - spec-reviewer: no high or medium. Two lows fixed in a1f15f0: the planner stops at 7 years, like the API; the SPEC privacy row now matches the proxies that keep no logs (recorded in SPEC-CHANGES).
  - security-privacy-reviewer: two mediums, both fixed:
    - **N1:** Caddy's proxy warnings (for example when a student leaves an advisor stream) still carried the visitor's IP address. Confirmed on Caddy 2.8 in a throwaway container. Caddy's log now drops the address fields and request headers from every line (tested the same way: no address left).
    - **N2:** the development compose file published the database, Redis, MinIO and the API on every network interface. They now bind to 127.0.0.1. The production override sets `ENVIRONMENT=production`. DEPLOY.md sets `COMPOSE_FILE`, and the checklist no longer says `make up` on the server.
  - Lows fixed: a typed "[author suspended" note is refused; a made-up catalog year never loads whole tables; the crawler fetches https pages only; /privacy and DEPLOY.md cover backups and restores.
  - New privacy questions for Richard: P12-2 (the suspensions list) and P12-3 (restores).
- **Final full-repository reviews at 57c6723 (2026-11-15):**
  - spec-reviewer: one medium, fixed in 42daec8. The https-only crawler skipped the seed's `http://` catalog pages, so the paid pilot would have had no pages for 9 of 11 programs. The crawler now fetches them over https; a test runs the live page fetch on the seed's addresses with a mock server. Lows fixed: privacy wording, the E3 model row in SPEC-CHANGES, the missing E3 and A4 eval sets listed below.
  - security-privacy-reviewer: six mediums, all fixed with tests or a reproduction:
    - **A:** a made-up catalog year made `/verify` call itself in a loop, with the cache on as in Docker.
    - **B:** Caddy's error text still held the visitor's address and port; now masked (reproduced and re-tested on Caddy 2.8).
    - **C:** Postgres wrote the email of a duplicate sign-up to its log; errors are now terse and never echo the statement (checked on a throwaway server).
    - **D:** one slow email pattern froze an API process for 9 s on a long post; now 0.06 s.
    - **E:** a burst of logins could use about 10 GB of memory; at most 4 password checks run at once per process, and the rest get "busy, try again".
    - **F:** all IPv6 visitors would share one rate limit; DEPLOY.md now uses an IPv4 record only, with steps to add IPv6, and IPv6 is counted per /64.
  - Lows fixed: chats are deleted with their plan or account; the solver time on `/verify` is capped at 5 s; the health check reuses the connection pool; `SHOW_UNPUBLISHED_PROGRAMS` is refused in production; data links render only for http(s); a minimal Content-Security-Policy; /privacy now says what the AI features send to the provider.

### Specified in the SPEC but not built yet (final spec review, 2026-11-15)
- **Planner and generator:**
  - the Core is not pre-placed as requirement slots (journey A3);
  - variants are "Option A/B/C", not names like "Exploratory CS";
  - no control for the "Bx/MS application by a term" goal (B3);
  - the study-abroad goal label shows the program id;
  - no read-only shared snapshot;
  - long solves are not moved to a background worker with a "verifying" badge;
  - no "move the plan to a newer catalog year" action;
  - no "Report an error" button on requirement nodes;
  - Compare uses plans on this device and shows no server metrics.
- **Program pages:** no sample path (`sample_path` is never filled).
- **Accounts:** passkeys (optional in the SPEC).
- **Forum:** no detection of vote bursts on a page; no takedown contact on the site.
- **Curator console:** no ingestion-run history with diffs, no rule editor with live checks and golden tests, no LLM cost by task, and SQLAdmin is not mounted.
- **Ingestion and schedule:**
  - E2 does not crawl the study-abroad list, the joint-degree pages or department sites;
  - the department-offerings extractor covers CS only;
  - no study-abroad pipeline;
  - the real Class Search parser is blocked (permission and real pages), so there is no weekly scrape;
  - no Registrar feed.
- **Seed coverage** (open questions):
  - Economics specializations;
  - physical-sciences combinations;
  - placement-dependent rules;
  - the CS curriculum-area breadth rule;
  - study-abroad language courses;
  - the catalog sentence for the Q6 transfer rule.
- **Agents:**
  - no real-model run of any agent yet (API hold);
  - evals do not run nightly in CI;
  - only the A1 and A2 eval sets exist: no E3 formalizer eval (15 programs with gold trees; the pilot covers 11) and no A4 moderation eval (200 labelled posts, at least 95% recall on identifying information), and evals do not yet gate a prompt-version change;
  - forum evidence in advisor answers is untested with a real model.
- **Ops:** the spend alarm writes a log line but notifies no one.

### Needs Richard (decisions or actions only you can take)
- **Spend money:**
  - run the AI evals and the pilot ingestion (commands below);
  - choose a server and domain;
  - choose an email provider for verification codes (`EMAIL_BACKEND=smtp`).
- **University permission:** reading the public Class Search (P10-1). Until then the schedule scraper stays off and the parser works only on synthetic pages; save a few real result pages if you get permission.
- **Catalog sources:** the transfer rule (1800 units here; transfer credit counts toward 3800) cites your answer, not the catalog. Find the catalog sentence before launch (Q6, `data/seed/REVIEW.md`). The `data/seed/REVIEW.md` hand check is still deferred.
- **New questions** in `docs/OPEN_QUESTIONS.md`, each with a suggested answer:
  - P09-1 to P09-9 (ingestion);
  - P10-1 to P10-5 (schedule);
  - P12-1 (re-run the load test on the real server);
  - P12-2 (the admin suspensions list can link two removed posts) and P12-3 (a restore brings back recently deleted accounts): privacy choices for you.
- **Security of your `.env`:** the two API key lines are written `NAME= value` with a space after `=`. Shells that read the file then try to run the key as a command, and print it in the error (this happened once in this session's local output). Remove the space. Consider rotating both keys.

### Launch checklist (in order)
1. On your own computer (never on the server): `git pull`, then `make check` and `make e2e`. Both should end with exit code 0. `make e2e` also runs journeys A-D on the Docker stack.
2. Fix `.env`: no space after `=`; real keys; `ENVIRONMENT=production` values from `docs/DEPLOY.md`.
3. **AI evals** (costs money; prints an estimate first, stops at $20):
   ```bash
   make up
   make evals                                       # free checks + the estimate only
   CONFIRM_SPEND=yes make evals                     # the real run (A1 50 profiles, A2 100 cases)
   CONFIRM_SPEND=yes uv run python evals/run.py --only a2   # or just the advisor half, ~$2
   ```
4. **Pilot ingestion** (costs money; prints an estimate first, stops at $25):
   ```bash
   make ingest-pilot ARGS=--fake                    # free rehearsal (should report 100%)
   make ingest-pilot ARGS=--estimate                # estimate only, nothing spent (~$16)
   # put CATALOG_CONTACT_EMAIL in .env, then:
   CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot ARGS=--programs=econ-ba   # one program, ~$2
   CONFIRM_SPEND=yes LLM_LIVE=true make ingest-pilot                           # all 11; report: docs/ingest-pilot/report-live.md
   ```
   The goal is at least 95% node agreement with the hand seed. Read every disagreement in the report.
5. Turn on the real AI for students only after the evals pass: `LLM_LIVE=true` in the server's `.env`, then restart with the production command in step 7 (with `COMPOSE_FILE` set as in `docs/DEPLOY.md`, `make up` on the server does the same).
6. Publish each program in `/admin/review` (students see only published programs; set `SHOW_UNPUBLISHED_PROGRAMS=false`).
7. Deploy per `docs/DEPLOY.md`:
   - `docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait`;
   - seed;
   - make yourself admin;
   - set up the nightly `scripts/backup.sh` cron;
   - test a restore once.
8. On the server, run the load test (P12-1):
   ```bash
   LOAD_LOGIN=<user> LOAD_PASSWORD=<pw> LOAD_HOST=https://<domain>/api make loadtest
   ```
   Targets: verify 50/s with p95 < 500 ms; forum reads 100/s.
9. Keep `SCHEDULE_SCRAPER_ENABLED=false` and `CATALOG_INGEST_ENABLED=false` until you decide otherwise.

## FEEDBACK of 2026-11-16 (step 1 of the live-test goal)
- **Summer catalog (3254069):** `python -m api.seed.summer` reads the Summer Session course finder; 152 offerings in `data/seed/2026-27/summer_courses.yaml`; catalog courses the Summer Session offers are offered in Summer; 44 summer-only courses documented but not plannable (DF-S1).
- **Summer sequences (f546d06):** a prerequisite in the same Summer quarter counts (verifier, checker, generator).
- **Short issue messages (49cb235):** one short line per issue with a "View prerequisite" link; the full text under "Details".
- **Minor issues (49cb235):** "My Plan" heading with a pencil to rename; "Ask Quarterly" without the badge; course page overview and prerequisite graph window.
- **Credits panel and compact layout (8385842):** edit test, placement and transfer credits from the planner; smaller radii and tighter spacing (DESIGN.md updated).
- Proof: `e2e/feedback-1116.spec.ts`, `docs/screenshots/fb1116-*.png`, unit tests named in FEEDBACK.md.

## Live agent tests (prompt 13, 2026-11-16)
- `llm_gateway.live`: LiveBudgetGuard (worst-case check before every call, $4.50 total and per-phase caps, sticky refusal), ledger `evals/live/ledger.jsonl`, recordings `evals/live/recordings/<test id>.json`, ReplayLLM, secret scan. Tested with fake providers before any live call.
- Harness `evals/live/run.py` (phases 0-5); report `docs/LIVE-TEST-REPORT.md`. Ledger total **$1.7249**.
- Verdict: every plan the live agents produced (18 generations, 26 variants) passed `verify` and `check_certificate`; the chat apply path keeps errors visible with no certificate; injections caused no write.
- Five bugs found and fixed, each with a regression test first: E1 JSON-string answers; advisor tool schemas rejected by the API (every advisor turn failed); scope classifier, A1 rationale and Opus preference output limits too tight.
- Needs Richard: P13-1 (Sonnet 5.5 vs Opus 5.5 for A1). Not run (budget): the Opus re-run after the fix.
- Known flake (2026-11-16): journey C once failed under heavy machine load. The generator's time-limited solve returned another valid plan that also holds HIST 10102, and the test checks which courses the verifier credits to the Core's civilization requirement; the next run passed. If it recurs, make the test accept any plan where the Paris courses are eligible for that requirement.
- `make up` and `make e2e-stack` now recreate the web container after the API, so nginx never keeps a dead API address (every journey once got 502s after a rebuild).


## FEEDBACK of 2026-11-16, second batch (goal 3: 13:43-14:40 CST)
Four items and half of the fifth resolved; TRNC 10100 is in progress (below).
- **Course picker for credits (0abe529, 2eda4c9):** "Counts as course" is a search-and-choose field; typed text that was not chosen is refused.
- **Catalog menu (0abe529):** one "Catalog" menu item with a Courses/Programs switch; course search shows only a centred search box until you search.
- **Colour strips (86c961d):** each colour is a kind of requirement, the same on every plan (major maroon, second major blue, Core yellow, minor green, study abroad orange, Bx/MS mauve, pre-professional dark green, none grey). Labels and reasons in FEEDBACK.md.
- **ASCII chapel scene (25e36f5):** live scene beside the homepage text; time of day and Hyde Park weather (via our own cached `GET /weather`, so no visitor request leaves the site); trees sway under a sweeping pointer; a click sends a shooting star at night or birds by day; still under reduced motion. Files: `apps/web/public/ascii-scene/`, converter and docs in `tools/ascii-scene/`.
- **Minor issues (b44c09a):** a card's open menu sits in front of the cards below. **TRNC 10100: in progress.** Added in b44c09a, then taken out: with it in the catalog the plan generator timed out in journeys A-C (a `credit_only` tag that keeps it out of the generator fixed C only). Its row was deleted from the dev database. Called directly on the real catalog, the generator is equally fast with and without TRNC (0.9 s vs 1.0 s), so TRNC may not be the cause. Next: run the journeys without TRNC; if they still fail, look elsewhere and add TRNC back.
- Tests: `make check` passes; `make e2e` passed after items 1-4 (the browser suite and journeys A-D); for the menu fix the browser suite passed (85).
- Test fixes along the way: the drawer drag test retries a missed drag (OPEN_QUESTIONS E2E-1); journey C's two preference checks no longer fail on the generator's time-limited choices (E2E-2).
- Before launch (OPEN_QUESTIONS DF-A1): replace the watermarked demo photo behind the chapel scene; Open-Meteo's free service is non-commercial only.
- Next: Richard's next FEEDBACK items; the deferred catalog questions before deployment.

## Design pass with Impeccable (goal 4, 2026-11-16, 16:31-)
- **Baseline:** stack up with fake AI (`LLM_FAKE=e2e`); 55 screenshots of every page at 1440 and 390 px in `docs/screenshots/before/` (56f73c6).
- **D1-D10** (FEEDBACK "Minor design changes", numbered for tracking): home without subhead, note and caption, Open-Meteo credit on /about (6584a4a); 96px Newsreader 400 wordmark (9e045fc); compact footer, 44px on touch (60e867c); Newsreader 500 top-bar wordmark (75dfd83); small sliding Courses/Programs switch (7401744); quiet top-bar search (9447e95); denser, darker chapel (5e59e65); "Graduating in" as text with a pencil (c3bda96); one-column credit form (5ddae6c); maroon hero orb (1d0c891). DESIGN.md gained a dated note of these approved departures; nothing else in it changed.
- **D11 full review:** `docs/DESIGN-REVIEW.md`. Critique by three isolated reviewers plus an isolated evidence agent (detector clean; axe WCAG 2.2 AA clean on 38 page states). 62 findings: 8 P1, 38 P2, 16 P3; all P1 fixed, 57 fixed in all plus PL-4 in part, 5 deferred with reasons, 0 need Richard. Highlights: the plan's verdict beside its name; plan-check items keep what is missing; Generate options say what Apply changes and warn on errors; the advisor compares "now" with "after"; the course page says which numbers are estimates; the Forum page leads with courses; program pages link every course code; credits confirm removal; one search box per page; no labels above headings.
- **Polish / harden / adapt:** a second screenshot pass fixed seven more defects; 16px fields on touch screens; long forum titles wrap; the phone planner toolbar is two rows.
- **Checks:** axe on home, planner (drawer, Generate, advisor), course search and forum at 1440 and 390: no serious or critical violations (`e2e/design.spec.ts`, 8 passed); after-screenshots in `docs/screenshots/after/` (55).
- **Deferred:** A-4 (401 on the logged-out session check is API behaviour), PL-4 rest (merge the panel buttons: Richard's F4 toolbar), PL-6 (a glossary for "Difficulty"), AD-2 (advisor as a desktop side panel: F4), CS-3 (choice lists need data the page does not load), FO-4 (how untitled reviews are named).
- Note: Prettier is not configured for this repo; earlier runs of it this session rewrapped some touched files (HomePage, Footer, TopNav and others) to 80 columns. Lint and types pass; no behaviour changed.

## TRNC 10100 finished (2026-11-16, 18:45-)
- TRNC 10100 "Transfer General Credit" is back in the 2026-27 catalog (from b44c09a), tagged `credit_only` (784bdb1).
- Cause of the earlier journey failures, found by running journey A's generation inside the API: TRNC has no offering data and is repeatable, so the generator treated it as a free elective for any quarter and sometimes placed it in a variant. That put transfer credit into planned quarters and slowed solves (journeys A and C failed; B is already close to its 4 s limit).
- Fix: `planner_core.generator` skips `credit_only` courses as candidates, and the API's elective-choice step skips them too. Test: `test_never_places_a_credit_only_course` (control: untagged it is placed). Journeys A-D pass with TRNC in the catalog; four in-app runs of journey A's plan never place it.
- Possible follow-up: the course page's "Add to plan" still shows for TRNC (the course API sends no tags); a student who adds it to a quarter gets a "not on the schedule" warning from the plan check.


## Full course catalog from the original crawl (2026-11-16, 22:30-)
- **Gap:** the hand-checked seed had 1,274 of the catalog's courses; the original crawl (the prototype's `data/`, fetched 2026-11-08, never committed) has 6,472 entries plus their cross-listed codes. 43 subjects had no courses at all.
- **Import:** `scripts/import_crawl_courses.py` adds only the codes the seed lacks, into one file, `data/seed/2026-27/courses/zz_crawl_import.yaml` (10,027 courses: 5,297 catalog entries and 4,730 cross-listed codes). The 85 hand-checked files are untouched.
  - Every `source.quote` was found verbatim (whitespace collapsed) on the saved page it cites; none had to be skipped. Cross-listed codes quote the page's "Equivalent Course(s)" line, as the seed does.
  - Every added course is `needs_review: true`. Prerequisites stay text (`prereq_text`); no structured `prereq` rules were written, so the plan check's prerequisite warnings cover only the hand-checked courses.
  - `terms_offered` is set only when "Terms Offered" is a plain list of quarters and does not say "not offered" this year (8,185 of 10,027).
  - Left out: 208 sequence headers (`ANTH 20701-20702-20703`); their parts are entries of their own.
- **Loader fix:** `seed.loader._upsert` sent all rows in one statement, past Postgres's 65,535-parameter limit at about 5,000 courses. It now inserts in batches (`MAX_PARAMS`).
- **Checks:** seed loads 11,301 courses, 2,699 cross-list groups, 4,012 requisite texts, 27,513 offering patterns. No crawl code is missing from the database. Deterministic generation (core + cmsc-bs) gives two valid plans in about 1 s. `api.cli golden`: PASS=115. ruff clean on the changed files.
- **Not run:** `make check` and `make e2e` (journeys A-D use the generator's 4 s limit, which a larger catalog could affect).

## Campus companion (2026-11-20, branch `feature/best-of-uchicago`)

Max's request in one overnight pass (`docs/BEST-OF-UCHICAGO-PLAN.md` has the plan, the data model and the API contract). The lead built the foundation and the homepage; four parallel agents built the features against the contract; the lead integrated and checked.

- **Homepage:** the chapel patch (`quarterly-course-chapel.patch`) applied as is; title "The Best of UChicago, *within your reach.*" (three lines rising in, a hand-drawn maroon swash); the question bar `features/home/AskBar.tsx` is a combobox: typed text asks `/ask`, an exact course code opens the course, matching courses, a catalog search and "ask it in the Forum" are offered. Every one of the 11,301 courses of 2026-27 opens its page (checked through the API), including the 1,600 in the drawing.
- **Shared look:** `components/brand/TypeScape.tsx` draws a figure with real course titles in the chapel's manner (arch for Ask, orrery for the dashboard, river for the feed, cloister for the Commons); a title under the pointer shows its code and opens its course; still under reduced motion. `TypeHero` / `PageTitle` give every new page its header.
- **Data:** migration 0004 (`student_profile`, `pathway`, `commons_thread`, `commons_reply`, `commons_pseudonym`, `commons_vote`, `commons_report`). `api/agents/live.py` streams live tool steps while an agent runs and checks course codes against the catalog; `api/agents/campus_tools.py` is the shared read-tool set.
- **Ask (`/ask`) and the companion:** `POST /agents/ask` (task `a5_campus_ask`), live trace, cited answers with course cards and follow-ups, conversations in the browser (cleared on logout); the companion orb on every page with Chat (page context, profile) and For you (`GET /me/updates`, digest `a10_updates_digest`). Campus guide `data/campus/guide.yaml` (CC-2).
- **Dashboard (`/me`):** profile (`GET/PATCH /me/profile`; the email is read from the account), the immersive guide (`POST /agents/interview`, `a6_interview`) that proposes facts the student keeps, routes at the bottom (`/me/routes`, drafts by `POST /agents/routes`, `a7_routes`; choose one or keep all open; open a route in the planner).
- **Feed (`/feed`):** 16 categories covering every subject, course spotlights with generated SVG art and books from `data/feed/books.yaml` (CC-3), student comments, word clouds, programs and open questions; For you / Explore / Following; floating words, a ticker, AI notes (`POST /agents/feed-notes`, `a8_feed_notes`).
- **Commons (`/forum`):** questions on courses answered first by the bot (`POST /commons/threads/{id}/bot`, `a9_commons_bot`, live steps, citations, @quarterly summons), nested replies to depth 4, votes, accept, edit, delete, report, follow, typing presence and a new-reply banner, a markdown composer with course mentions and drafts; per-thread anonymous handles (`commons_ref`). Demo questions: `make seed-commons-demo` (CC-8).
- **Account:** `/account/export` includes the profile, routes and Commons content; deletion clears Commons refs (FK cascade for profile and routes).
- **Fallbacks:** every agent has a deterministic version used when the AI is off, unavailable or over its daily limit.
- **Tests:** API tests per feature (`test_ask_api`, `test_updates_api`, `test_profile_api`, `test_routes_api`, `test_interview_api`, `test_feed_*`, `test_commons*`), web tests in each feature folder. `conftest.py` now also switches off the `.env` caches for tests (`RULES_CACHE_TTL_S`, `PAGE_CACHE_TTL_S`), which had made `test_reseeding_invalidates_the_cache` fail on machines with the Docker `.env`.
- **Spec review fixes (same day):** the Commons bot reads no forum reviews (its answer is public); its stored answer keeps only links to this site or uchicago.edu and is scrubbed (`safe_answer`, tested); a second request can no longer store a second bot answer (the answer is looked up again after the lock); the updates digest has a daily limit (40 model calls per account); choosing two routes at once no longer fails (rows locked); the feed's notes skip unpublished programs. The homepage shows the top bar's course search on wide screens (the hero bar asks), and the "Try" chips have 44px targets (hidden on phones).
- **Redesign "Maroon and night" (same day, Max's reference login card):** every page is a white rounded sheet on a maroon-and-black background, with bigger type, bold sans headlines (Newsreader italic accents), pill buttons and fields, split headers with a generated art panel (`GradientArt` + TypeScape `theme="night"`), and sign-in/sign-up after the reference (`docs/DESIGN.md` "Maroon and night"). e2e expectations follow it (sign-in title, fonts, 46px pills, 15px captions).
- **Then:** Commons reports in the admin moderation queue (CC-7, `test_commons_moderation.py`); an e2e spec for the new pages (`e2e/campus.spec.ts`: the question bar to Ask, the art header, the companion, the feed, a Commons thread, the dashboard, the redesigned sign-in).
- **Not done:** eval sets for the new prompts (they need paid model calls, so the owner's OK).

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

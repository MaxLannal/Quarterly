# QuadPlan — UChicago Course Planner + Course Forum

*Product & technical spec (working name). Written for humans and for coding agents.*

Version: 2026-11-12. Exported from the shared Claude doc; edit either, but keep them in sync.

## Summary and decisions to confirm

QuadPlan is a UChicago-only website with two halves that share one course database. The **Planner** helps a student go from "I don't know my first class" to a full, goal-aware 4-year plan; an AI agent proposes, and a deterministic verifier proves every plan is valid. The **Forum** is an anonymous, Reddit-style discussion space with one page per course × instructor; its ratings feed back into each course's attributes (workload, difficulty, intellectual intensity), which the Planner then uses.

The design rests on one rule: **agents propose, code disposes.** Agents read messy sources and talk to students; deterministic code (schemas, a requirements checker, a constraint solver) decides what is true and what gets saved.

Where your brief left a choice open, I picked a default. Change any row and tell your coding agent.

| # | Decision | Default chosen | Main alternative |
| --- | --- | --- | --- |
| 1 | Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 | Django + DRF (what theCourseForum uses; built-in admin) |
| 2 | Frontend | React + TypeScript (Vite), TanStack Query, dnd-kit, Tailwind + shadcn/ui | Next.js, if public course pages need SEO |
| 3 | Database | PostgreSQL 16 (JSONB for rule trees, ltree for comment threads, full-text search) + Redis | SQLite for a throwaway demo |
| 4 | Solver | Google OR-Tools CP-SAT for requirement matching and plan generation | Hand-written max-flow (matching only) |
| 5 | Anonymity | Email and password is stored on the backend | Email and password is stored on the backend |
| 6 | Logged-out access | Catalog facts, planner (local only), aggregate course attributes; posts and summaries need login | Hide all forum-derived numbers behind login |
| 7 | v1 scope | College undergrads; catalog year 2026–27; Core + CS (BA/BS, Bx/MS) + Math (BA/BS) + Economics + 2 study-abroad civ programs | All programs at launch |
| 8 | Section data | Ask the Registrar for a feed first; fall back to a Playwright scraper of the public Class Search plus department offering pages | Meta's Muse or another VM browser agent (not recommended for a pipeline; see Ingestion) |
| 9 | Official course feedback | Not ingested (behind login; owned by the University) | Ask the Registrar for permission |
| 10 | LLM routing | Anthropic API direct; OpenRouter as a fallback behind the same interface | OpenRouter only |
| 11 | Chat write access | Agent drafts a change set; it is applied only after an explicit confirmation the server checks against that exact draft | Agent edits the plan freely |
| 12 | Name | "Quarterly", "Quarterly Planner" and "Quarterly Forumn" for now | We will go with this name for now. Please ignore all "QuadPlan" entries and use the above names |

## Product overview

QuadPlan answers two questions UChicago's official tools leave open: **"what should I take, given what I want?"** and **"what is this class actually like with this professor?"**

### Problem 1: planning starts from a blank page

The College's My Planner (Stellic) gives every undergraduate a four-year layout, a degree audit, schedule tools and pre-registration ranking. It does not recommend courses; advice comes from advisers, and its closest automated behavior is sorting courses into requirements to use the fewest courses ([My Planner FAQ](https://college.uchicago.edu/advising/my-planner-faq)). A new student still has to work out their first quarter alone, and nothing accounts for personal goals such as a lighter quarter, a Bx/MS application, or a civilization quarter abroad.

The rules are intricate. A degree needs 4200 units: the Core (1500 units), at least one major (900–1900 units) and electives ([Degree Requirements](https://college.uchicago.edu/advising/degree-requirements)). Full-time is 300 or 400 units a quarter, and a 500-unit overload is approved only in narrow cases ([Enrollment Policies](https://college.uchicago.edu/advising/enrollment-policies)). Minors cannot share courses with the Core (except Language Competence) or a major ([Minors](https://uchicago-preview.courseleaf.com/thecollege/minors/minors.pdf)).

### Problem 2: course feedback is thin and scattered

Official course feedback is a Registrar-run survey students fill in each quarter ([Course Feedback](https://registrar.uchicago.edu/registration/college-process/course-feedback)). Comments tend to be cautious and hard to compare across instructors. Student-built tools come and go: the Maroon reported in November 2025 on Cramwell AI (ratings plus a chatbot) and noted that UChicago Genie's domain is gone ([Chicago Maroon](https://chicagomaroon.com/49530/feature/new-website-cramwell-ai-helps-students-find-easy-courses-and-professors-for-upcoming-quarter/)).

### What QuadPlan does differently

- **Plans are proven, not suggested.** Every plan, whether a student or the agent made it, is checked by a deterministic verifier that outputs a certificate: which course satisfies which requirement, which earlier course satisfies each prerequisite.
- **Goals are first-class.** Students attach goals to their whole career or to specific quarters ("Spring of 3rd year abroad", "Winter ≤ 45 hrs/week"). The generator optimizes for them and the verifier checks them.
- **Course attributes are explicit and sourced.** Each course and course × instructor pair carries workload, difficulty and intellectual-intensity scores, with a confidence level and the evidence behind them.
- **The forum is structured.** One page per course × instructor, Reddit-style threads, votes, and structured ratings that update the attributes.

### Users

| Persona | Situation | What they need first |
| --- | --- | --- |
| Incoming first-year | No credits, vague interests | A sensible first quarter and a few candidate paths |
| Transfer student | Transfer credits, fewer quarters left, 2nd-year status | Which credits count, what is still possible (e.g. Bx/MS) |
| Declared ambitious major | CS + Math, wants Bx/MS or a PhD path | Hard-course sequencing, overload checks, application timing |
| Goal-constrained student | Pre-med, athlete, study abroad, early graduation | Plans that respect fixed quarters and loads |
| Forum reader / writer | Choosing between sections or instructors | Honest, comparable experiences |

### Scope

**v1 (prototype):** catalog year 2026–27; Core, CS (BA/BS and Bx/MS), Math (BA/BS), Economics, two civilization-abroad programs; planner with verifier, plan generator, advisor chat; forum for courses in those departments; anonymous accounts.

**Later:** every program in the catalog, multiple catalog years, transfer/AP credit import, section-level weekly schedules, mobile layout polish, department-maintained corrections.

**Non-goals:** registering students for classes, replacing the official audit or advisers, publishing grades or official evaluations, and identifying anyone.

## Core user journeys

Every journey ends in the same place: a plan on the 4-year grid with a green verifier badge, or a precise list of what is still wrong.

**A. Incoming first-year with no plan**

1. Lands on the home page, clicks **Start planning**, and creates an account (Issue #16: planning starts with sign-up).
2. The registration form asks the class year, the expected graduation quarter and the intended programs; credits go in the dashboard's Academic background (or on the form for a transfer or later-year student). The dashboard agent's questions (goals, scheduling, learning preferences) can wait.
3. The planner offers "set up a plan from your information": it opens with the student record's programs and the Core pre-placed as requirement slots ("HUMA sequence, quarter 1–3") instead of courses.
4. Clicks **Generate plan** → popup with sliders and toggles → the agent returns 2–3 variants ("Exploratory CS", "Econ-leaning", "Balanced"), each verified, each with a one-line rationale per quarter.
5. Accepts one, swaps a course by drag-and-drop; the verifier re-runs in under a second.
6. The plan is saved to the account.

**B. Transfer student targeting CS BS + Math BS and Bx/MS**

1. Enters transfer credits; QuadPlan maps known equivalents and flags unknown ones for manual mapping.
2. Selects programs: CS BS, Math BS, CS Bx/MS (research option).
3. Adds goals: "Bx/MS application in Winter of 3rd year" and "no more than one 'very hard' course per quarter".
4. Generates a plan; the verifier shows the overload rules, the double-count limits between the two majors, and whether the remaining quarters are enough.
5. Opens the advisor chat: "Is Honors Analysis worth it if I want ML research?" The agent answers with course attributes and forum evidence, then offers a change set; the student confirms to apply it.

**C. Goal-constrained student (study abroad + lighter senior year)**

1. Pins "Paris civilization program, Spring Y2" as a block; the block counts as the civ sequence and fills the quarter.
2. Sets "Y4 ≤ 3 courses per quarter".
3. The generator moves heavy major courses into Y2–Y3 and checks offering patterns ("usually Autumn only").

**D. Forum reader and writer**

1. Searches "MATH 20700", opens the course page, sees aggregate attributes and the instructors who teach it.
2. Clicks an instructor → the course × instructor page: rating summary, an AI summary with citations to posts, and threads sorted by Best.
3. Logs in to read and post. Writes a review (structured ratings + text) under a per-thread pseudonym such as "Quiet Heron"; upvotes a helpful answer.

## System architecture and tech stack

One PostgreSQL database sits at the center; a small pure-Python package, `planner_core`, holds every rule that decides correctness, and both the API and the background workers import it. Everything runs in Docker Compose on a laptop and on a single small cloud VM.

```text
Architecture (see the diagram in the shared doc)

                 Browser (React + TS SPA)
                          | REST + SSE
                          v
 Worker (Arq + cron) <-- API (FastAPI) --> llm_gateway --> Anthropic API (primary)
   |        |   jobs      |        |                    \-> OpenRouter (fallback)
   | queue  |             | verify | SQL
   v        \----------> planner_core (TRUSTED: verifier V01-V12, CP-SAT solver,
 Redis 7                  certificate checker; no DB, no network, no LLM)
                                   |
                          PostgreSQL 16 (catalog, rules, plans, forum)

 Public sources (catalog, class schedules) --fetch--> Scraper (Playwright) --snapshots--> MinIO
```

Workers call the same `llm_gateway` and `planner_core` as the API, so an agent's output is checked by exactly the code that checks a student's own edits.

| Service | Technology | Responsibility |
| --- | --- | --- |
| `web` | React 18 + TypeScript (Vite), TanStack Query, dnd-kit, Tailwind + shadcn/ui | Every page; planner grid; forum UI |
| `api` | FastAPI (uvicorn), SQLAlchemy 2, Pydantic v2 | REST API, Server-Sent Events for agent progress, auth, rate limits |
| `planner_core` | Pure Python package, OR-Tools CP-SAT | Requirements DSL, verifier, certificate checker, plan solver; no database or network access |
| `llm_gateway` | Python package: Anthropic SDK + OpenAI SDK pointed at OpenRouter | Model routing, retries, prompt caching, cost logging, structured-output validation |
| `worker` | Arq (Redis-backed jobs) | Agent runs, ingestion, nightly forum → attribute aggregation, moderation |
| `scheduler` | Arq cron | Annual catalog run, quarterly section run, nightly jobs |
| `scraper` | Playwright (Python), headless Chromium | Public Class Search and department pages; saves raw snapshots |
| `db` | PostgreSQL 16 | All data; JSONB for rule trees; `ltree` for comment paths; full-text search |
| `redis` | Redis 7 | Job queue, rate limiting, cache |
| `storage` | MinIO (S3-compatible) | Raw HTML/PDF snapshots of every source page |
| `admin` | SQLAdmin mounted in `api`, plus a React review queue | Curator tools: diff review, rule editor, moderation |

### Repository layout

```text
quadplan/
  apps/web/                 React + TS single-page app
  services/api/             FastAPI: routers catalog, programs, plans, verify, agents, forum, auth, admin
  services/worker/          Arq jobs: agents, ingestion, aggregation, moderation
  services/scraper/         Playwright jobs, snapshot writer
  packages/planner_core/    DSL models, verifier, certificate checker, CP-SAT solver
  packages/llm_gateway/     provider clients, model routing, cost log
  data/seed/                hand-verified YAML: courses, programs, terms (v1 pilot)
  data/golden/              golden plans per program: must-pass and must-fail
  docs/SPEC.md              this document, exported
  docker-compose.yml
```

### Cross-cutting rules for coding agents

- **One contract.** The API publishes OpenAPI; the frontend client is generated from it (`openapi-typescript`). No hand-written fetch types.
- **Small trusted core.** `planner_core` takes Pydantic models in and returns Pydantic models out. It never imports the database, the web framework or an LLM client.
- **Agents use the same doors as people.** Agent tools call the service layer, which runs the same validators as UI requests. No agent writes SQL.
- **Everything is versioned.** Catalog data is keyed by catalog year; every derived fact keeps a pointer to its source snapshot.
- **Logged-out state is local.** A logged-out student's plan lives in browser storage and is imported into the account at login.
- **Every LLM call is logged** (task, model, prompt version, tokens, cost, latency, outcome) with no user identifier.

Why FastAPI rather than Django: agent runs are long and streamed, Pydantic models can be shared with `planner_core`, and OpenAPI comes for free. Django would win on the built-in admin; SQLAdmin covers most of that gap.

## Sitemap and every page

The site has 16 page types; the planner, the generate popup, the advisor chat and the course × instructor page carry most of the product. Login is needed only to save plans and to enter the forum.

Mockups of six key screens, with sample data, are on the design canvas: [QuadPlan — screen mockups](https://claude.ai/artifact/U46qMrKwDcMToNGW5bWJQR) (planner with advisor chat, generate popup, course page, course × instructor forum, onboarding goals, anonymous sign-up).

**Top bar (issue #15):** four tabs, in this order: **Dashboard** (`/me`), **Planner** (`/plan`), **Catalog** (`/courses`) and **Forum** (`/forum`). The homepage is not a tab; the "Quarterly" wordmark links to it. There is no floating companion on any page.

| Route | Page | Login | Purpose |
| --- | --- | --- | --- |
| `/` | Home | No | Not a tab: the wordmark in the top bar links here. Title "The Best of UChicago, *within your reach.*"; "Start planning" (a link to `/signup` when logged out, `/plan` when logged in, issue #16) and "Explore the catalog" (a link to `/courses`, issue #19) (no question bar and no "Try" questions since issue #15; the top bar's course search shows here on every screen size); behind them Rockefeller Chapel fills the first screen, drawn with the titles of real catalog courses (`/home/course-chapel.json`, built by `tools/course-chapel/build.py`); in maroon, black and white; letters have depth and follow the pointer, the sun moves over the carved stone, clouds and a soft glint drift across it on their own, a lens lifts and magnifies the letters under the pointer, the title under the mouse shows its code and opens its course page; still under reduced motion or without a GPU |
| `/ask` | (redirect) | No | Redirects to `/plan`. The Ask page and its chatbot were removed (issue #15): the planner page is the only place a student talks to the planner agent ("Ask Quarterly") |
| `/me` | Your dashboard | Yes | The student record (Issue #14, #16): a Profile card (name, class year, email read from the account, intended programs, program progress, "Complete your profile"); the General Information in four groups (Academic background, Goals, Scheduling, Learning preferences), each answer editable in place or through the dashboard agent (`POST /agents/interview`), which asks the step-2 questions one at a time with their options as buttons and proposes each answer for the student to accept; "Your plan", a read-only summary of the primary plan with a link to the planner; "Export my information (.md)" (`GET /me/profile/export.md`). No routes and no "At a glance" (removed in issue #15: the planner makes every plan proposal) and no "What's new" (issue #16 D5) |
| `/feed` | (redirect) | No | Redirects to `/courses`. The Feed page was removed (issue #19): its course spotlights and student quotes are browse rows of the Catalog; its floating words, ticker, focus chips, book shelf, word clouds, open questions, program cards and AI notes (`POST /agents/feed-notes`, task `a8_feed_notes`) are gone |
| `/forum`, `/forum/new`, `/forum/t/{id}` | The forum (reviews and the Commons) | Read: no (reviews and ratings: yes); write: yes | `/forum` (issue #20, see Forum, "The forum page"): ratings, statistics and rankings in the left third (logged-in students only), and course reviews and Commons discussions in one list, newest first, in the right two thirds; a "New post" button opens `/forum/new`. A discussion is a Commons question and its replies: a short AI answer first (at most 60 words, `POST /commons/threads/{id}/bot`), then students: nested replies, votes, accept, edit, delete, report, follow, typing presence, a markdown composer with course mentions and drafts. Reviews are still written on the course x instructor pages (`/instructors`) |
| `/onboarding` | (redirect) | No | Redirects to `/me`: the registration form asks the entry term, credits and programs; the dashboard agent asks the scheduling questions |
| `/plan` | Planner | No (local) / Yes (to save) | 4-year grid, requirements, verifier, generate, chat |
| `/plans` | My plans | Yes | List, rename, duplicate, set primary |
| `/plans/compare` | Compare plans | Yes | Side-by-side diff of two plans with metrics |
| `/courses` | Catalog | No | The Catalog tab (issue #19). The course search box and its filters (department, level, quarter, Core area, workload, difficulty) as before, and a Courses / Programs switch to `/programs`. Before a search, browse rows (`GET /catalog/browse`): **Newly released courses** (only when some are known: the hand-written list `data/catalog/new_courses.yaml`, each entry with a verbatim source quote, plus, once the database holds an earlier catalog year, the courses that year did not have), **Course spotlights** (from the old Feed: matched to a logged-in student's profile and followed courses, else a curated mix rotated daily) and **What students say** (Commons replies for everyone; forum reviews and discussions only for a logged-in reader). After a search, the list of results. Every course in the rows and the results shows its student rating summary to a logged-in student (`GET /course-ratings`, the course page's rule); a logged-out visitor sees one "Log in to see student ratings" line |
| `/courses/{code}` | Course page | No (forum parts need login) | Facts, prerequisites, offerings, attributes, instructors |
| `/courses/{code}/i/{instructor}` | Course × instructor forum | Yes | Ratings, AI summary, reviews and discussion |
| `/courses/{code}/i/{instructor}/t/{id}` | Thread | Yes | A post with nested comments |
| `/instructors` and `/instructors/{slug}` | Instructor directory and page | Yes | Courses taught, per-course ratings |
| `/programs` | Program explorer | No | Every major, minor, Bx/MS, joint program, study-abroad block |
| `/programs/{id}` | Program page | No | Requirement tree in plain English, source, sample path |
| `/signup`, `/login` | Account creation and login | No | Anonymous account flow (see Accounts) |
| `/account` | Account | Yes | Change password, export, delete |
| `/guidelines`, `/privacy`, `/about` | Static | No | Community rules, what we store, disclaimers |
| `/admin/*` | Curator console | Admin | Ingestion runs, review queue, rule editor, moderation, LLM cost |

### Planner (`/plan`)

- **Top bar:** plan name, catalog year, program chips ("CS BS", "Math BS", "CS Bx/MS"), **Generate plan** button, a quiet **Check plan** button with a small count badge (errors stay subtle: most students are building a partial plan), Save, and a one-line "Not official advising" notice.
- **Right drawer (slides in from the right; full screen on a phone):** Requirements, Issues and Goals. Requirements is a vertical tree per program (program → nodes → courses), each course shown as its code in bold with its name in small text and a subtle "n of m" per node; any course can be dragged onto the grid. Issues opens from **Check plan**.
- **Center, the grid (the main width):** one row per academic year, from the entry quarter to the graduation quarter. An academic year runs Summer, Autumn, Winter, Spring: the summer *before* autumn belongs to it (Summer 2026 is in 2026–27), and there is no summer after the last spring. Summer is collapsed by default. Years are labelled by class year ("Second year" for a second-year transfer's first year). The plan's `graduation_term` sets its end: by default the Spring of the last year counted from the entry level (four years for a first-year, three for a second-year transfer); **Add a year**, **Remove last year** (only when it is empty) and **Graduating in** (an Autumn, Winter or Spring) change it. A course card shows code, short title, units, a color stripe for the requirement it fills, estimated hours/week and difficulty dots. Each quarter footer shows units, total hours/week, a difficulty index and that quarter's goal chips.
- **Advisor (opens from the top, separate from the drawer):** clearly labelled generative AI ("Generative AI"; "Answers are written by an AI and can be wrong"), with a chat layout: student and AI message bubbles, a typing indicator while streaming, citation chips and proposal cards.
- **Motion:** subtle transitions for the drawer, the advisor, dialogs and course cards, all off under `prefers-reduced-motion`.
- **Interactions:** drag to add/move; a drop shows inline warnings at once (missing prerequisite, not usually offered that quarter); right-click to lock, mark completed, or remove. Every edit triggers a debounced full verification (target under 500 ms).
- **States:** empty (requirement slots shown as dashed cards), verifying, valid, warnings, errors; read-only when viewing a shared snapshot.
- **API:** `GET /plans/{id}`, `PATCH /plans/{id}/items`, `POST /verify`, `POST /agents/generate` (SSE), `POST /agents/chat` (SSE), `POST /plans/{id}/changesets/{cs}/apply`.

### Generate-plan popup

A form, never a free-text prompt, so every input maps to a typed parameter.

1. **Scope:** whole plan, remaining quarters, or selected quarters. Locked and completed courses are kept.
2. **Load and difficulty:** a career-wide slider (lighter ↔ heavier) with optional per-quarter overrides; maximum courses per quarter; allow a 500-unit quarter only where rules permit.
3. **Goals:** pre-filled from the Goals tab, editable (graduate by, study abroad block, Bx/MS application, pre-med sequence, protect GPA, "challenge me").
4. **Interests:** tags ("ML", "philosophy of mind", "Chinese") used to pick electives.
5. **Variants:** 1–3.

Then a progress view streams the agent's steps ("Loading requirements → Choosing electives → Solving → Verifying → Writing rationale"). The result shows each variant as a diff against the current plan, its verifier badge, metrics (average hours, hardest quarter) and a one-line rationale per quarter. Buttons: **Apply**, **See changes** (with **Choose quarters to apply** inside it), **Discard**. Above them, a line says which quarters Apply changes, and an option that still has errors says so.

### Advisor chat (right rail)

- Answers planning questions only; off-topic requests get a one-line refusal.
- Every factual claim carries a citation chip: a course attribute ("MATH 20700 · workload 18 h/wk · n=34") or a forum post.
- Changes arrive as a **proposal card**: a list of add/move/remove operations, plus the verifier's verdict on the plan after the change. **Apply** applies it; typing an explicit confirmation ("I agree to add MATH 20700 to Autumn Y2") also works, and the server checks it matches the card.

### Course page (`/courses/{code}`)

Header (code, title, units, cross-listings, Core/major tags, "Add to plan"); description; prerequisites as readable text plus a small graph of what it needs and what it unlocks; offerings by term with instructor, and predicted future quarters with confidence; attribute card (workload h/week, difficulty, intellectual intensity, pace, each with n, confidence and source); instructor list linking to forum pages; "Counts toward" list of program requirements.

### Course × instructor forum page

Header with course, instructor and terms taught; rating distribution bars; an AI "What students say" summary with numbered citations to posts and its update date; tabs **Reviews** and **Discussion**; sort Best / New / Top / Controversial; filter by term; composer for a review (structured ratings required) or a discussion post. Each post shows the per-thread pseudonym, optional "took it in Autumn 2025" badge, score, Reply and Report.

### Instructor page

Name, department and the courses they teach (from the public catalog and schedule), each with its aggregate ratings. No personal information beyond what the University publishes.

### Program explorer and program page

Programs grouped by type (major, minor, Bx/MS and joint degrees, specializations/tracks, pre-professional paths, study-abroad blocks). A program page renders its rule tree in plain English, links to the exact catalog source and year, shows the curator's verification date and one sample path, and has "Add to my plan".

### Onboarding (`/onboarding`)

Replaced by the two-step registration (Issue #16): `/onboarding` redirects to `/me`. Its entry term, credits and programs moved into the registration form; its goals became the dashboard agent's scheduling questions (quarters away, courses per quarter).

### The General Information and `student.md` (Issue #14)

The General Information questions are written once, in `data/profile/questions.yaml`: id, group, field, short label, text, type (single, multi, scale, list, table), options and step (1 = the registration form, 2 = the dashboard agent). The registration form, the dashboard and the dashboard agent read them from `GET /profile/questions`. The answers form the student record: `student_profile` plus `student_credit` and `student_course` (see Data model). There are no freeform fields, no resume and no GPA; each taken course keeps an optional grade.

| Group | Questions |
| --- | --- |
| Academic background | Class year; expected graduation term; intended programs; and, for a student who transferred or is not in the first year, the entry term, the entry year level, credits and taken courses |
| Goals | Plans after graduation (industry, graduate school, medical or law school, undecided); graduation pace (early, on time, flexible); interest in research and, if yes, research areas |
| Scheduling | Courses per quarter; quarters away (study abroad, internship, leave) |
| Learning preferences | Class formats (seminar, lecture, lab, online); theory or application (1 to 10) |

`student.md` is generated from the record (`render_student_md()`): a "General Information" section with the four groups as headings, in this order, one line per question with its short label, "Not answered" for an empty answer; then, in the export and for the planner agent, "Working information": the Markdown notes the planner chat keeps per student (a line that applies to one plan only starts with the plan name; Issue #17 writes them). It never contains the email or the username. The agents read it instead of the old profile summary; the student downloads it from the dashboard (`GET /me/profile/export.md`) and it is part of `/account/export`.

### Sign-up and login

Sign-up has four steps: enter a `@uchicago.edu` address → enter the 6-digit code → choose a username and password (passkey optional later) → "About you", the registration form: the step-1 General Information questions (class year, expected graduation term, intended programs) and the checkbox "I transferred, or I am not in my first year.", which adds the entry term, the entry year level, credits and taken courses. Then the student either answers the dashboard agent's questions now or skips them (they can start later from the dashboard with "Complete your profile"), and goes to the page they came from, or `/plan`. Login is username or email plus password; \"Forgot password\" sends a reset code by email. Nothing on either page asks for a name.

### Curator console (`/admin`)

Ingestion runs with status and diffs; a review queue showing source text beside the extracted rule tree (accept, edit, reject); a rule editor with live validation and golden-plan tests; the moderation queue; LLM usage and cost by task.

## Data model

The model has nine groups of tables; the catalog, schedule and program groups are keyed by catalog year or term so that old plans stay checkable against the rules they were made under. Field lists are the minimum; coding agents may add timestamps and indexes.

### Catalog

| Table | Key fields | Notes |
| --- | --- | --- |
| `catalog_year` | `id` ("2026-27"), `published_at` | Students follow the year of their entry term by default |
| `course` | `id`, `subject`, `number`, `title`, `units` (default 100), `description`, `catalog_year`, `core_tags[]`, `tags[]`, `repeatable`, `source_id` | `code` = `subject + " " + number`. The tag `credit_only` marks credit a student receives but never enrols in (TRNC 10100, transfer general credit): a credit can map to it, and its units count toward the degree total, but the plan generator never places it in a quarter and never offers it as an elective choice |
| `crosslist_group` | `group_id`, `course_id` | Cross-listed codes count as one course |
| `course_relation` | `course_a`, `course_b`, `kind` (`equivalent`, `mutually_exclusive`, `replaces`) | For example, credit for only one of two intro sequences |
| `requisite` | `course_id`, `catalog_year`, `prereq` (JSONB, DSL), `coreq` (JSONB), `restrictions` (JSONB), `raw_text` | `raw_text` is the catalog sentence the rule came from |

### Schedule

| Table | Key fields | Notes |
| --- | --- | --- |
| `term` | `id` ("2026-AU"), `year`, `quarter` (AU, WI, SP, SU), `start`, `end` |  |
| `instructor` | `id`, `slug`, `display_name`, `department`, `aliases[]` | Names de-duplicated across sources |
| `section` | `id`, `term_id`, `course_id`, `section_no`, `component`, `instructor_ids[]`, `meetings` (JSONB), `capacity`, `status`, `source_id`, `scraped_at` |  |
| `course_instructor` | `id`, `course_id`, `instructor_id`, `first_term`, `last_term`, `n_terms` | The key of every forum page; one page per cross-listed group and instructor, shown under every code (P08-5) |
| `offering_pattern` | `course_id`, `quarter`, `p_offered`, `evidence_terms[]`, `method` | Predicted availability for future years |

### Programs

| Table | Key fields | Notes |
| --- | --- | --- |
| `program` | `id` (slug, e.g. `cmsc-bs`), `name`, `type`, `degree` (BA, BS, MS), `department`, `parent_id` | `type`: major, minor, bxms, joint, specialization, track, preprofessional, study\_abroad\_block, core |
| `program_version` | `id`, `program_id`, `catalog_year`, `rules` (JSONB, DSL), `status` (draft, review, published), `verified_by`, `verified_at`, `source_ids[]`, `checksum` | Only `published` versions reach students |
| `program_relation` | `program_a`, `program_b`, `kind` (`requires`, `excludes`, `share_limit`), `n` | E.g. Bx/MS requires the matching major; minor shares 0 courses with a major |

### Attributes

| Table | Key fields | Notes |
| --- | --- | --- |
| `attribute_def` | `key`, `scale`, `description` | Keys: `workload_hours`, `difficulty`, `intellectual_intensity`, `pace`, `grading_strictness`, `recommend_rate` |
| `attribute_value` | `subject_type` (course, course\_instructor), `subject_id`, `key`, `value`, `ci_low`, `ci_high`, `n`, `method` (prior, forum, blend), `evidence` (JSONB), `computed_at` | Evidence lists post ids and source ids |

### Provenance and review

| Table | Key fields | Notes |
| --- | --- | --- |
| `source_snapshot` | `id`, `url`, `fetched_at`, `sha256`, `storage_key`, `content_type` | Raw bytes kept in object storage |
| `extraction_run` | `id`, `kind`, `model`, `prompt_version`, `input_snapshot_ids[]`, `output` (JSONB), `status`, `cost_usd` | One row per agent extraction |
| `review_item` | `id`, `target_type`, `target_id`, `diff` (JSONB), `reason`, `status`, `decided_by`, `decided_at` | Human gate before publishing |

### Plans and goals

| Table | Key fields | Notes |
| --- | --- | --- |
| `plan` | `id`, `account_id`, `name`, `catalog_year`, `entry_term`, `entry_year_level`, `graduation_term` (nullable: the default last quarter), `is_primary`, `updated_day` | Dates rounded to the day |
| `plan_program` | `plan_id`, `program_version_id`, `options` (JSONB: track, specialization) |  |
| `plan_item` | `id`, `plan_id`, `course_id` or `slot_ref`, `term_id`, `status` (planned, in\_progress, completed, transfer, exam), `locked`, `units` | `slot_ref` is an unfilled requirement placeholder. Completed and in-progress courses live in `student_course` (Issue #14); migration 0010 removed the old per-plan copies |
| `credit` | `plan_id`, `kind` (AP, placement, transfer), `label`, `maps_to_course_id`, `units` | Not used since Issue #14: credits live in `student_credit`. Migration 0010 removed the old rows |
| `goal` | `id`, `plan_id`, `scope` (career, term), `term_id`, `type`, `params` (JSONB), `hard`, `weight` | Goal types are listed under Verification |
| `verification_report` | `plan_id`, `plan_hash`, `core_version`, `status`, `issues` (JSONB), `certificate` (JSONB) | Cached by `plan_hash` |
| `change_set` | `id`, `plan_id`, `origin` (generate, chat, user), `ops` (JSONB), `base_plan_hash`, `preview_report` (JSONB), `status` (proposed, applied, discarded, stale) | The only way an agent's suggestion reaches a plan |

### Agents and LLM usage

| Table | Key fields | Notes |
| --- | --- | --- |
| `agent_run` | `id`, `kind`, `plan_id`, `model`, `status`, `steps` (JSONB), `tokens`, `cost_usd` |  |
| `chat_message` | `run_id`, `role`, `content`, `citations` (JSONB) | Deleted after 30 days |
| `llm_call` | `task`, `model`, `prompt_version`, `in_tokens`, `out_tokens`, `cost_usd`, `latency_ms`, `ok` | No user identifier |

### Forum

| Table | Key fields | Notes |
| --- | --- | --- |
| `post` | `id`, `course_instructor_id`, `kind` (review, discussion), `author_ref`, `pseudonym_id`, `title`, `body_md`, `term_taken`, `score`, `status` (visible, held, removed), `created_day` |  |
| `review_rating` | `post_id`, `overall`, `difficulty`, `intellectual_intensity` (1–5), `workload_hours`, `would_recommend`, `grade_bucket` (optional) | One review per account per page |
| `comment` | `id`, `post_id`, `parent_id`, `path` (ltree), `author_ref`, `pseudonym_id`, `body_md`, `score`, `status` |  |
| `vote` | `voter_ref`, `target_type`, `target_id`, `value` (±1) | Unique per voter and target |
| `pseudonym` | `id`, `author_ref`, `course_instructor_id`, `handle` | Stable within a page, different across pages |
| `report`, `moderation_action` | target, reason, status, actor (model or admin) |  |
| `forum_summary` | `course_instructor_id`, `text`, `citations`, `model`, `n_posts`, `computed_at` |  |

`author_ref` and `voter_ref` are `HMAC(server_key, account_id ‖ page_id)`, so a leaked database does not show which posts across pages belong to one account.

### Accounts

| Table | Key fields | Notes |
| --- | --- | --- |
| `account` | `id`, `username`, `email` (unique, lowercase), `email_verified_day`, `password_hash` (argon2id) or passkey credential, `role` (user, curator, admin), `status`, `created_day` | Email stored per decision 5; never logged or copied to other tables |
| `student_profile` | `account_id`, the General Information answers (`class_year`, `expected_graduation_term`, `intended_programs`, `entry_term`, `entry_year_level`, `post_grad_plan`, `pace`, `wants_research`, `research_areas`, `courses_per_term`, `terms_away`, `class_formats`, `theory_vs_application`), `working_notes`, `interview` (the dashboard agent's memory), `follows`, `updates_seen` | The student record (Issue #14; `feed_categories` was dropped with the Feed, issue #19). NULL = not answered. Never holds the email |
| `student_credit` | `account_id`, `kind` (AP, placement, transfer), `label`, `maps_to_course_id`, `units` | The record's credits; every saved plan reads them (they no longer belong to one plan). A label has at most 120 characters (emails and phone numbers removed) and a credit at most 1000 units; a plan's credit is clipped to these limits when saved |
| `student_course` | `account_id`, `course_id`, `term_id`, `status` (completed, in_progress), `grade`, `grading` (letter, pass_fail), `units`, `locked` | Taken courses; each keeps the plan item's grading, units and lock, so a Pass/Fail course never counts where a letter grade is required (V12) after the record is edited on the dashboard or saved from the planner; every saved plan shows them as completed or in-progress items (id `t<id>`); saving a plan writes them back; a new plan never overwrites a record that already has some. The planner shows the record's credits and taken courses when it opens and, unless the student changed them in the planner, saves the record's current ones (so an old copy never undoes a change made on the dashboard); a save never removes taken courses from before the plan's first quarter |

## Data ingestion

Three scheduled pipelines (annual catalog, quarterly schedule, nightly forum aggregation) all follow the same path: fetch → snapshot → parse → validate → diff → human review → publish. Agents are used only where the source is prose; everything structured is parsed by plain code.

### Sources

| Source | What we take | Cadence | Method |
| --- | --- | --- | --- |
| [College Catalog](http://collegecatalog.uchicago.edu/thecollege/programsofstudy/) (CourseLeaf) | Courses, descriptions, prerequisite sentences, program requirements, Core, minors and joint-degree rules | Each new catalog year, plus a monthly change check | HTTP fetch + HTML parser; LLM for requirement prose |
| Public Class Search (guest access, linked from [my.UChicago](https://portal.uchicago.edu/ais)) | Sections, instructors, meeting times, status per term | When a quarter's schedule posts; weekly during registration | Playwright scraper, only if permitted |
| Department offering pages (e.g. [CS course info](https://course-info.cs.uchicago.edu/guava8/undergrad/index.html)) | Planned offerings for the coming year | Quarterly | HTTP + LLM extraction |
| [Study Abroad](https://college.uchicago.edu/academics/study-abroad) | Programs, quarters, which Core requirement each satisfies | Annually | HTTP + LLM extraction |
| College advising pages | Load, overload, graduation and residency rules | Annually | Curated by hand into the "College policy" rule set |
| QuadPlan forum | Ratings and text | Nightly | Aggregation job (see Forum) |

**Ask first.** The cleanest path is a data feed from the Registrar. While researching this spec, my fetch tool was refused by robots.txt on the Registrar's class-schedule page; treat that as a signal to request permission before scraping schedules. Official course feedback stays out of scope.

**On Muse.** Meta's Muse runs a personal agent in its own cloud VM with a browser ([Meta](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/)). It suits one-off browsing, not a pipeline: there is no stable API, no snapshot provenance, and consumer terms. Use a deterministic Playwright scraper, and call a Claude agent only to repair the scraper when the page layout changes.

### Annual catalog pipeline

1. **Crawl.** Fetch the catalog index, the A–Z index, every program page and every course-description page at 1 request/second with an honest user agent. Store each response as a `source_snapshot` (sha256, URL, time).
2. **Parse courses (code only).** CourseLeaf course blocks have regular fields: code, title, units, description, "Prerequisite(s)", "Equivalent Course(s)", "Note(s)". These become `course`, `crosslist_group` and `course_relation` rows.
3. **Formalize prerequisites (agent E1, Haiku 5.5).** Each prerequisite sentence becomes a DSL expression. Output must parse under the grammar, and every course it names must exist; anything else goes to review.
4. **Enumerate programs (agent E2, Opus 5.5).** From the catalog index, A–Z index, minors list, joint-degree pages, study-abroad list and department sites, produce one candidate per program with its type and URL. Completeness check: the count must reconcile with at least two independent lists (the College states 68 majors and 57 minors on its [Programs of Study](https://college.uchicago.edu/academics/programs-study) page). A mismatch blocks the run.
5. **Formalize each program (agent E3, Opus 5.5, run twice).** Input: the program snapshot, the DSL schema, the course list and three worked examples. Output: a rule tree where every node carries a verbatim quote from the source. A second, independent run uses Sonnet 5.5 with a reordered prompt.
6. **Validate.** (a) JSON schema; (b) every course reference exists; (c) every quote appears verbatim in the snapshot; (d) the two runs agree node by node, otherwise a review item; (e) agent E4 (Sonnet 5.5) renders the tree back into English and a judge lists differences from the source; (f) golden plans pass or fail as expected; (g) size sanity: majors fall within 9–19 courses ([Degree Requirements](https://college.uchicago.edu/advising/degree-requirements)).
7. **Diff against last year.** Unchanged programs carry over automatically; changed ones go to review.
8. **Human review and publish.** A curator accepts, edits or rejects in the console. Only `published` versions reach students.

### Program checklist the enumerator must fill

- Majors, with BA/BS variants and named tracks or specializations
- Minors (and the rule that they share no courses with the Core, except Language Competence, or with a major)
- Joint and 4+1-style programs: Bx/MS in Computer Science, Mathematics, Statistics, Chemistry, Computational and Applied Mathematics, Financial Mathematics; Bx/MA in Economics; Bx/MPP and Bx/MS-CAPP with Harris ([PSD joint programs](https://physicalsciences.uchicago.edu/current-students/bx-ms), [catalog A–Z](https://uchicago-preview.courseleaf.com/azindex)); the list is re-derived every year
- Pre-professional paths (pre-med and health professions) as course lists with timing goals, not as degrees
- Study abroad: one-quarter civilization programs (count as the civ sequence; at most one per student), language programs, direct enrollment
- College-wide rules: the Core, Language Competence, 4200 units with 3800 earned by enrollment, half of each major or minor in residence ([Graduation Requirements](https://college.uchicago.edu/advising/graduation-requirements))

### Quarterly schedule pipeline

1. Watch weekly for the next quarter's schedule; when it appears, iterate over subjects and snapshot every results page.
2. Parse into `section` rows. Checks: course code exists (else flag a new or topics course); instructor names match `instructor` by fuzzy match, uncertain matches go to review; section counts per department stay within ±30% of the same quarter last year, else alert.
3. Update `course_instructor` (which creates forum pages) and `offering_pattern`.
4. **Self-repair.** If parsing yields zero rows or the schema check fails, a repair agent receives the snapshot, the old parser and the error, and proposes new selectors. The new parser must reproduce the last good run's counts on stored snapshots; a curator approves the change.

### Predicting future offerings

For quarter q and course c, with k = years offered in q among the last 3:

```latex
p_{\text{offered}}(c,q) = \frac{k + 1}{3 + 2}
```

A department's published plan for next year sets p = 0.95; a posted schedule sets p = 1. The verifier warns when a plan places a course where p < 0.3.

## Requirements DSL

One small JSON format (authored as YAML) expresses both course prerequisites and program requirements. It is deliberately narrow: small enough for an LLM to emit reliably, and exact enough for a solver to check. Every node carries a verbatim quote from its source.

### Prerequisite expressions

- **Atoms:** `{course: "CMSC 14200", min_grade: "C-"}`, `{concurrent: "MATH 20300"}` (co-requisite), `{placement: "MATH 15100"}`, `{standing: "third-year"}`, `{program: "cmsc-*"}` (enrolment restriction), `{consent: "instructor"}`.
- **Combinators:** `{all: [...]}`, `{any: [...]}`, `{n_of: 2, of: [...]}`.
- **Meaning:** a `course` atom is met by a course completed, credited or planned in a strictly earlier term, or in the same term when that term is a Summer quarter (summer sessions run in sequence, so HUMA 11500 and 11600 may share one summer; FEEDBACK 2026-11-16); `concurrent` by the same or an earlier term; `placement` and `standing` by plan facts; `consent` never blocks but always produces a warning.
- **Human form,** generated for display: "CMSC 14200 and (MATH 15900 or MATH 16300)".

### Program rule trees

| Node | Meaning | Main fields |
| --- | --- | --- |
| `group` | Children combined | `all: true` or `n_of: k`, `children` |
| `slot` | One specific course or alternatives | `any_of: [codes]` |
| `select` | Choose courses from a selector | `count` or `units`, `from` (selector) |
| `bounded_parts` | Parts with min/max counts that sum to a total | `total`, `parts[{count: [min, max]}]` |

- **Selectors:** explicit codes; `subject` + `number_range` + `exclude`; `tags` (e.g. `core:arts`); `list` (a named course list stored in a `course_list` table per catalog year).
- **Node constraints:** `min_grade`, `no_pass_fail`, `same_sequence` (all from one Core sequence), `in_order`, `max_from: {selector, n}` ("at most 2 from outside CMSC"), `distinct_subjects: n`.
- **Program-level policy:** `share` limits with other programs (`{with: "type:minor", max: 0}`, `{with: "core", max: 0, except: ["language"]}`), `residency` (at least half in residence), `timing` (`apply_by`, `complete_by`), `requires` (a Bx/MS requires its major).
- **Provenance:** every node has `source: {snapshot_id, quote}`; the validator rejects a quote that is not found verbatim.

### Example: Core, Humanities/Civilization/Arts

The College's Core summary says students take one or two arts, two or three humanities and two or three civilization courses, six in total ([Core requirements](https://college.uchicago.edu/sites/default/files/documents/CoreRequirements.pdf)).

```yaml
id: core-hca
label: Humanities, Civilization Studies, and the Arts
bounded_parts:
  total: {courses: 6}
  parts:
    - {id: huma, from: {list: core-huma-sequences}, count: [2, 3], same_sequence: true}
    - {id: civ,  from: {list: core-civ-sequences},  count: [2, 3], same_sequence: true}
    - {id: arts, from: {list: core-arts},           count: [1, 2]}
constraints: {no_pass_fail: true}
source: {snapshot_id: snap_core_2026, quote: "must be taken for a total of 6 courses"}
```

### Example: a major fragment (illustrative only)

The intro sequence below matches the current catalog ([CS catalog page](http://collegecatalog.uchicago.edu/thecollege/computerscience/)); the elective node shows the shape only and is not the real rule.

```yaml
id: cmsc-bs
catalog_year: "2026-27"
rules:
  group:
    all: true
    children:
      - id: intro
        group:
          all: true
          children:
            - {slot: {any_of: ["CMSC 14100"]}}
            - {slot: {any_of: ["CMSC 14200"]}}
      - id: electives            # ILLUSTRATIVE
        select:
          count: 4
          from: {subject: CMSC, number_range: [20000, 29999], exclude: ["CMSC 29700"]}
        constraints: {min_grade: "C-", no_pass_fail: true}
policy:
  share:
    - {with: "type:minor", max: 0}
```

### Pydantic sketch for `planner_core`

```python
class Atom(BaseModel):
    kind: Literal["course", "concurrent", "placement", "standing", "program", "consent"]
    value: str
    min_grade: str | None = None

class Expr(BaseModel):
    op: Literal["all", "any", "n_of", "atom"]
    n: int | None = None
    children: list["Expr"] = []
    atom: Atom | None = None

class Node(BaseModel):
    id: str
    kind: Literal["group", "slot", "select", "bounded_parts"]
    # kind-specific fields ...
    constraints: Constraints = Constraints()
    source: Source
```

### Versioning

Rules are keyed by catalog year. A plan binds to specific `program_version` ids, so publishing a new year never silently changes an old plan; moving a plan to a newer catalog year is an explicit action that re-runs the verifier and shows the diff.

## Verification engine (non-agentic)

The verifier is a pure function, `verify(plan, rules, catalog) → report + certificate`, that runs after every edit and on every agent output; a plan shows "Valid" only when a separate, small checker accepts its certificate. No LLM is involved at any point.

### Inputs and outputs

- **Input:** `PlanState` (items with term and status, credits, chosen programs and options, goals), `RuleSet` (published program versions, College policy rules, requisites, offering patterns, attribute values), `Options` (strictness).
- **Output:** `Report` = status (`valid`, `warnings`, `errors`) + a list of `Issue {code, level, message, course_ids, term_ids, node_id, fix_hints[]}` + a `Certificate` when no errors.

### Checks

| Code | Check | Level | Method |
| --- | --- | --- | --- |
| V01 | Course exists in the plan's catalog year; cross-listed codes collapse to one | Error | Lookup |
| V02 | No duplicates (unless repeatable); no mutually exclusive pairs; exam credit forfeited when the equivalent course is taken | Error | Lookup |
| V03 | Prerequisites met by earlier terms (or the same Summer quarter); co-requisites by the same or an earlier term; consent produces a warning | Error | Expression evaluation |
| V04 | Course offered in that quarter: posted schedule wins, else `p_offered` < 0.3 warns | Warning or error | Lookup |
| V05 | 300–400 units in Autumn, Winter, Spring; 500 only where an overload reason applies (joint-degree need in 3rd year, graduation need in 4th, Reading and Research or BA thesis, a 200-unit language course) | Error, or "needs petition" warning | Arithmetic |
| V06 | No meeting-time clashes, for terms with posted sections | Warning | Interval check |
| V07 | Each program's rule tree is satisfied | Error, listing exactly what is missing | CP-SAT assignment |
| V08 | Sharing limits between programs (minor vs major, minor vs Core, Bx/MS vs major) | Error | Inside the V07 model |
| V09 | Graduation: 4200 units, 3800 by enrollment (transfer credit counts toward it), at least 1800 units taken at the College, Core and Language Competence, half of each program in residence, quarters within the allotment | Error | Arithmetic + V07 |
| V10 | Timing: Core finished by end of 2nd year (civ abroad allowed in 3rd); `apply_by` and `complete_by` | Warning | Term comparison |
| V11 | Goals (see table below): hard goals error, soft goals warn with a score | Error or warning | Predicate per goal |
| V12 | Grading: no Pass/Fail where a node forbids it | Error | Lookup |

Sources for the College-level numbers: [Enrollment Policies](https://college.uchicago.edu/advising/enrollment-policies), [Graduation Requirements](https://college.uchicago.edu/advising/graduation-requirements), [Core requirements](https://college.uchicago.edu/sites/default/files/documents/CoreRequirements.pdf).

### Program satisfaction as a constraint model (V07, V08)

Greedy matching breaks as soon as electives overlap and programs share courses, so the verifier asks OR-Tools CP-SAT for an assignment.

- **Variables:** `x[c,n] ∈ {0,1}` = course c is used for node n, created only for eligible pairs; `s[n] ∈ {0,1}` = node n satisfied; `y[c,P]` = course c used anywhere in program P.
- **Within a program:** each course fills at most one node, unless the rule says otherwise.
- **Node semantics:** `slot` → at least one of its courses; `select` → at least k courses (or U units); `group` → all children or at least k; `bounded_parts` → each part within \[min, max\] and the parts sum to the total; `same_sequence` → one indicator per sequence, exactly one chosen.
- **Across programs:** for a share limit m between P and Q, `Σ_c z[c] ≤ m` with `z[c] ≥ y[c,P] + y[c,Q] − 1`.
- **Objective:** first maximize the weighted count of satisfied nodes (so an incomplete plan reports the smallest set of missing requirements), then minimize courses used.
- **Grades:** planned courses are assumed to meet grade minimums; the report lists that assumption.

Typical instances (≤ 60 courses, ≤ 200 nodes, 3 programs) solve in tens of milliseconds.

### Certificates and the trusted checker

The solver is large and could have bugs; the checker is small and boring on purpose.

```json
{
  "plan_hash": "sha256:…",
  "rules": {"cmsc-bs@2026-27": "sha256:…", "core@2026-27": "sha256:…"},
  "assignments": [{"node": "cmsc-bs/intro/1", "courses": ["CMSC 14100"]}],
  "prereq_witnesses": [{"course": "CMSC 14200", "term": "2027-WI", "by": ["CMSC 14100@2026-AU"]}],
  "loads": [{"term": "2026-AU", "units": 400}],
  "goals": [{"goal": "g3", "value": 41.5, "limit": 45, "pass": true}]
}
```

`check_certificate(plan, rules, certificate) → bool` runs in linear time without a solver: every assigned course is in the plan and matches its node's selector; node counts and bounds hold; share limits hold; every prerequisite witness sits in an earlier term (or the same Summer quarter) and satisfies the expression; loads and goals recompute to the same values. It stays under about 300 lines so a person can review it line by line.

### Goal predicates

| Goal type | Parameters | Verified as | Used by the generator as |
| --- | --- | --- | --- |
| `course_load` | term or career; min/max courses | Count per term | Hard bound |
| `workload_hours` | max hours/week per term or career average | Sum of `workload_hours` (upper confidence bound when strict) | Hard bound or penalty |
| `difficulty_cap` | max index, or max "very hard" courses per term | Sum or count of `difficulty` | Hard bound or penalty |
| `challenge` | min difficulty index | Sum of `difficulty` | Reward |
| `protect_gpa` | none | No two high-`grading_strictness` courses in one term | Penalty |
| `graduate_by` | term | Last term ≤ target | Hard bound |
| `study_abroad` | program block, term | Block placed; no on-campus courses that term | Pinned block |
| `bxms` | program, `apply_by` term | Application prerequisites done before that term | Precedence constraint |
| `premed` | course list, `complete_by` | All listed courses done by then | Precedence constraint |
| `interest` | tags | Share of electives tagged | Reward |
| `light_quarter` | term, max courses | Count | Hard bound |
| `language` | language, level, by term | Sequence complete | Precedence constraint |

### Performance

Fast checks (V01–V06, V10–V12) take under 20 ms; the solver adds 20–300 ms. The browser debounces edits by 300 ms; reports are cached by `plan_hash`. A solve over 2 s moves to a worker and the badge shows "verifying".

### Testing

- Unit tests per check on tiny fixtures.
- Golden plans per program: at least 5 must-pass and 5 must-fail, each must-fail naming its expected issue codes, written by hand from the catalog text.
- Property-based tests (Hypothesis): every solver certificate passes `check_certificate`; mutating a valid plan (drop a course, move it earlier, add a sixth course) must produce the expected issue.
- Coverage gate: `planner_core` at 95% or higher; CI fails below it.

## Agent harnesses

There are five online and offline agents. Each has one job, a fixed tool list, a budget and an output schema, and none can write to the database except by drafting a change set or a review item.

### Model routing

Prices are list prices per million input / output tokens from the [models overview](https://platform.claude.com/docs/en/models/overview); routing lives in `llm_routing.yaml`, so you can swap models without code changes.

| Agent / task | Model | Price (in / out) | Why |
| --- | --- | --- | --- |
| E3 program formalizer (offline, yearly) | `claude-opus-5-5`, effort high | $4 / $20 | Hardest reading task. Fable is overkill: every rule is still checked by deterministic code, golden plans and human review (Richard, 2026-11-14) |
| E3b second opinion | `claude-sonnet-5-5`, effort high | $2 / $10 | A different model from E3, so the two-run diff stays independent |
| E2 program enumerator | `claude-opus-5-5` | $4 / $20 | Cross-checking many pages |
| E1 prerequisite sentence → DSL | `claude-haiku-5-5` | from $0.10 / $0.50 | High volume, short inputs |
| E4 back-translation judge, scraper repair | `claude-sonnet-5-5` | $2 / $10 | Mid-difficulty, fast |
| A1 plan generator | `claude-sonnet-5-5` (thinking between tools) | $2 / $10 | Tool use and judgment on electives; every plan is still verified and certified, so the cheaper model is enough (Richard, 2026-11-16, after the live test) |
| A2 advisor chat | `claude-sonnet-5-5` (escalate to Opus 5.5 for whole-plan comparisons) | $2 / $10 | Interactive latency |
| A3 forum extraction / summaries | Haiku 5.5 / Sonnet 5.5 |  | Nightly batch |
| A4 moderation | `claude-haiku-5-5` |  | Runs on every AI summary (not on students' posts, P08-1) |

OpenRouter is a fallback: `llm_gateway` maps each model to its OpenRouter name and retries there after two provider errors.

### Rules every harness follows

- **Loop:** Messages API with tools; the run ends when the agent calls its `submit_*` tool with a schema-valid payload, or when the budget runs out.
- **Budgets:** maximum tool calls, tokens and wall-clock time per run; exceeding any triggers the run's fallback.
- **Validation:** outputs are parsed with Pydantic; one repair turn with the validation error is allowed, then the run fails.
- **Untrusted content:** forum posts and web pages are passed inside `<untrusted_source id=…>` tags, and the system prompt says to treat them as data. An agent that reads untrusted content never holds a write tool.
- **Citations are checked:** every id an answer cites must have been returned by a tool in that run; otherwise the citation is dropped and the run is logged.
- **Prompt caching** for system prompts, the DSL schema and catalog excerpts.
- **Versioned prompts** in `prompts/*.md`; a version bump must pass that agent's eval set.

### A1. Plan generator (Generate-plan popup)

The LLM chooses *what is worth taking*; the solver decides *where it fits*; the verifier decides *whether it is valid*.

```text
Plan generator harness (see the diagram in the shared doc)

 Generate form -> 1 Load (code) -> 2 Compile goals (code) -> 3 Pick electives (LLM)
   [fail -> default preferences]                                    |
                                                                    v
 7 Proposal card  <- 6 Explain (LLM) <- 5 Verify (code) <- 4 Solve (CP-SAT, code)
 [nothing saved     [fail -> no         [fail -> alert,    [no plan -> plain-language
  before Apply]      rationale]          drop variant]      reason why]
```

Only steps 3 and 6 call a model, and each has a fallback, so a failed LLM call degrades the result instead of breaking it.

1. **Load (code).** Plan state, programs, goals, locked items, the eligible courses for each unmet requirement node, attributes and offering patterns. Anything the plan already holds that the catalog does not know (a credit mapped to an unknown code, a completed course from another catalog) stops the run with "Fix these first, then generate again: ..." naming it.
2. **Compile goals (code).** Each goal becomes solver bounds, rewards or penalties, as in the goal table above.
3. **Choose electives (LLM).** For each unmet `select` node (often 30–100 candidates), the agent uses `search_courses`, `get_course` and `get_forum_summary` to rank up to 8 preferred courses with a one-line reason, then calls `submit_preferences`. Budget: 12 tool calls.
4. **Solve (code).** CP-SAT places courses into terms: prerequisite order, `p_offered` ≥ 0.3, loads, hard goals, program satisfaction (the V07 model), locked items. Objective: preference weights + goal rewards − penalties for workload spikes. Each extra variant must differ from earlier ones in at least 4 placements.
5. **Verify (code).** Full verifier and certificate check on every variant. A failure here is a bug and raises an alert; the variant is dropped. If every variant is dropped, the student sees what the check found, never a bare "this is a bug".
6. **Explain (LLM).** The agent writes a rationale of 25 words or fewer per quarter, citing tool results. The server checks the course set is unchanged; if not, the rationale is discarded and the plan kept.
7. **Return** each variant as a proposed `change_set`, streamed over SSE.

**Fallbacks:** if step 3 fails, default preferences (interest-tag match, then forum `recommend_rate`); if step 6 fails, show the plan without rationale. If the solver finds no plan, it reports why in plain terms ("Graduating by Spring 2029 needs 5 more courses than your remaining quarters allow").

**Cost and limits:** roughly $0.25 per generation at list prices (rough estimate: \~40k cached input and \~5k output tokens on Opus 5.5). Limit 10 generations per account per day; logged-out users get 3, rate-limited by an IP counter in Redis that expires after 24 hours and is never written to disk.

### A2. Advisor chat

- **Scope gate:** a Haiku 5.5 pre-classifier labels each message `in_scope`, `off_topic`, `confirmation` or `suspicious`. Off-topic messages get a fixed one-line refusal without calling the main model.
- **Read tools:** `get_plan`, `preview_ops` (runs the verifier on hypothetical edits, saves nothing), `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `compare_courses`.
- **Draft tool:** `propose_change_set(ops)` stores a `change_set` with status `proposed` plus its verifier preview, and the UI renders a proposal card.
- **No write tool.** The model never applies anything. A change is applied only when (a) the student clicks **Apply** on a card, or (b) the student types an explicit command ("I agree to add MATH 20700 and CMSC 27100 to Autumn 2027"). A deterministic parser turns the text into operations; the server applies them only if they equal the latest proposal's operations or are themselves fully explicit, and only if the plan has not changed since (`base_plan_hash`).
- **Answers** use a schema `{text, citations[]}`; citation chips link to attribute values or forum posts.
- **History** is kept per plan for 30 days.

### E1–E4. Ingestion agents

Their steps are in Data ingestion. Harness specifics for the formalizer (E3): tools `read_snapshot(id, range)`, `lookup_course(code)`, `get_course_list(name)`, `validate_rules(yaml)` (deterministic errors back; up to 5 attempts), `run_golden(program)` and `submit_rules`. Every node must carry a verbatim quote. Output always lands in the review queue, never straight in `published`.

### A3. Forum → attributes (nightly)

- **Extraction (Haiku 5.5):** from each new post, pull workload mentions, difficulty cues, exam style and prerequisite advice, each with a quote span. A number is accepted only if its quote contains that number.
- **Summary (Sonnet 5.5):** "What students say", 120 words or fewer with \[n\] citations to post ids; rebuilt after 3 new posts or 30 days. No statements about an instructor's personal life; summaries pass the moderation classifier.
- **Cold start:** before any student data, Sonnet 5.5 estimates workload and difficulty from the description and course level with a fixed rubric. The value is labelled "estimate" and weighted as 2 ratings.
- The numeric update itself is deterministic (see Forum).

### A9. The AI's answer under a Commons question

The Commons bot (`api/agents/commons_bot.py`, task `a9_commons_bot`, prompt `prompts/a9_commons_bot.md`) writes the first answer under a forum question, in Quarterly's own voice ("Quarterly", not a mascot; issue #20, D1 option A). Its read tools are the catalog, programs, other Commons questions and the campus guide, never the login-only reviews, because the answer is public (OPEN_QUESTIONS CC-1).

- **At most 60 words** (OPEN_QUESTIONS F20-1: Richard confirmed 60 on 2026-11-24, to be tested in use and revisited if it proves too short or too long). The prompt asks for it; `submit_answer` rejects a longer answer once with the word count, so the model gets its one repair turn; a second long answer ends the run and the deterministic search answers instead (also at most 60 words). The stored answer, and any answer stored before the limit, is clipped to 60 words when shown (`api/commons/words.py`: a word is a run of characters between spaces that holds a letter or digit).
- The answer is always shown as written by an AI ("Quarterly AI", an "AI" badge, "Written by an AI and can be wrong"), on the thread page and in the `/forum` list.

### A4. Moderation

Students' posts, comments and edits are **not** checked before they are published (Richard, 2026-11-14, P08-1): a regex pass strips emails and phone numbers, then the post appears at once; guideline breaks are taken down through reports and the admin queue. Haiku 5.5 labels only AI-written text: a "What students say" summary publishes only when A4 says `ok` (labels `ok`, `personal_attack`, `identifying_info`, `harassment`, `sexual`, `misconduct_claim`, `spam`, `off_topic`).

### Evals

| Agent | Eval set | Pass bar |
| --- | --- | --- |
| A1 generator | 50 synthetic student profiles | 100% of variants verify; hard goals met; rationales cite only tool data |
| A2 chat | 60 in-scope questions with reference answers, 20 off-topic, 10 confirmation phrases, 10 prompt injections hidden in forum fixtures | All off-topic refused; no injection followed; parser exact on confirmations |
| E3 formalizer | 15 programs with hand-written gold rule trees | ≥ 95% node-level exact match before running unattended |
| A4 moderation | 200 labelled posts | ≥ 95% recall on `identifying_info` |

Evals run nightly in CI with a cost cap and gate every prompt-version bump.

## Forum

The forum follows theCourseForum's idea of one page per course × instructor ([theCourseForum](https://thecourseforum.com/about/)) but uses Reddit-style threads, votes and nested replies, with structured ratings on reviews so the text can update course attributes.

### Structure

- **Page** = one `course_instructor` pair, created automatically when the schedule pipeline first sees that instructor teach that course. Reachable from the course page and from the instructor page.
- **Posts** come in two kinds. A **review** requires structured ratings and the term taken (one review per account per page; editable). A **discussion** post is a question or topic ("Is the midterm curved?").
- **Comments** nest without a depth limit in storage; the UI collapses below depth 6.
- **Votes:** up or down on posts and comments, one per account per item, changeable.
- **Course-level view:** the course page aggregates all its instructors; there is no separate course-only thread in v1.

### Review ratings

| Field | Scale | Required |
| --- | --- | --- |
| Overall | 1–5 | Yes |
| Difficulty | 1–5 | Yes |
| Intellectual intensity | 1–5 | Yes |
| Workload | hours per week outside class, number | Yes |
| Would recommend | yes / no | Yes |
| Term taken | term picker | Yes |
| Grade received | A-range, B-range, C or lower, P/F, prefer not to say | No |
| Pace | 1–5 (slow to fast) | No (Q11) |
| Grading strictness | 1–5 (generous to strict) | No (Q11) |

### Sorting

- **Best** (default for comments): lower bound of the Wilson score interval on the up-vote share, so a 9–1 item outranks a 1–0 item.
- **Top:** net score. **New:** time. **Controversial:** many votes, near 50/50.
- **Hot** (discussion tab default): net score decayed by age, half-life 30 days, because course experiences age slowly.

```latex
\text{Best}(u, d) = \frac{\hat p + \frac{z^2}{2n} - z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \quad n = u + d,\ \hat p = \frac{u}{n},\ z = 1.96
```

### Anonymity inside the forum

- Each account gets a random two-word **pseudonym per page** ("Quiet Heron"), stable on that page so conversations stay readable, different on every other page so posts cannot be linked across pages by readers.
- Stored author references are `HMAC(server_key, account_id ‖ page_id)` (see Data model).
- Timestamps are shown as "Autumn 2026" or "3 weeks ago", never to the minute.
- No profiles, no follower counts, no karma totals shown publicly.

### Moderation and community rules

- Rules (shown in the composer): talk about the course and the teaching, not anyone's private life; no names of other students; no claims of misconduct (report those to the University instead); no slurs or harassment.
- No automatic check before publishing (P08-1): user reports and a human queue in the console take posts down.
- Suspensions are always an admin's choice (P08-3): when removing an item, the admin may suspend its author for 7, 30 or 90 days without learning who the author is; an admin can end a suspension early from the console. Bans are per account. Because each verified email can hold one account, a ban cannot be dodged by signing up again with the same address; an account cannot be deleted while suspended or within 30 days of an upheld removal (P08-12, P08-14).
- Instructors are not given a reply channel in v1; revisit with the University.

### The forum page (`/forum`)

Issue #20 (Richard, 2026-11-24: D1 option A, D2 as suggested) puts course ratings and discussions on one page, in the manner of IMDb and Reddit.

- **One list, two tables (D2).** Reviews (`post` + `review_rating`) and Commons discussions (`commons_thread` + `commons_reply`) keep their own tables. `GET /forum/items` merges them, newest day first; on one day discussions come before reviews, then the newest id. The cursor is the sort key of the last item, so a page never repeats or skips an item. Filters: item type (review, discussion), course (a review matches every code of its cross-listed course), instructor (reviews only: a discussion has no instructor), subject, text, and the Commons tag and "my questions" (discussions only). Reviews are for logged-in readers: a logged-out reader gets the public discussions only (`reviews_hidden`) and a login card.
- **The AI under each question (D1 option A).** Each discussion in the list shows the AI's first answer under the question, at most 60 words, labelled "Quarterly AI · AI · Written by an AI and can be wrong" (see A9 below).
- **Layout.** The list fills the right two thirds; the left third holds the statistics and rankings, then the notes about the forum. On a phone the statistics come above the list and the notes below it. A "New post" button (a link to `/forum/new`) replaces the ask box, so students start discussions, not chatbot questions.
- **Statistics and rankings** (`GET /forum/stats?period=quarter|year`, logged-in students only, the rule the course pages follow). Only structured ratings count: `review_rating.overall` of visible reviews posted in the period, the last 91 days (`quarter`, shown as "Last 3 months") or the last 365 days (`year`, "Last 12 months"), counted back from today. Statistics: the number of reviews and courses, and, from 3 reviews in the period, the average overall rating, the share who would recommend, and the average workload. Rankings, each line with its score and review count:
  - the top 10 courses (every instructor and every cross-listed code of a course pooled, named by its code with the most reviews);
  - for each major, its 5 best-rated courses (a course belongs to a major when it can fill one of the major's requirements, the "counts toward" rule);
  - the Humanities sequences, the sublists of the Core list `core-huma-sequences`, each pooling the reviews of its courses and their cross-listed codes;
  - the top 10 instructors (their courses pooled).

  Every score is the Bayesian average below with prior weight k = 5 and, as the prior mean m, the average overall rating of every review in the period (one prior for all subjects, so courses of different departments compare). A subject needs at least 3 reviews in the period to be ranked (the n ≥ 3 rule below).

### Forum → course attributes

Numeric attributes use a Bayesian average so a page with 2 reviews does not swing wildly. For attribute a on subject s (a course or a course × instructor pair), with prior mean m (the department-level average, or the cold-start estimate) and prior weight k = 5 ratings:

```latex
\hat a_s = \frac{k\, m + \sum_{i=1}^{n} w_i\, r_i}{k + \sum_{i=1}^{n} w_i}
```

Structured ratings have weight w = 1; values extracted from text have w = 0.5; ratings older than 4 years decay to w = 0.5. Forum-derived values are shown only when n ≥ 3; below that the course shows its estimate, labelled as such. Course-level attributes pool all instructors; the planner uses the course × instructor value when the scheduled instructor is known and the course value otherwise.

## Accounts and anonymity

*Decision 5, confirmed by Richard on 2026-11-12, replaces the earlier blind-signature design: accounts store the verified `@uchicago.edu` email and a password hash. Readers still see only per-page pseudonyms in the forum.*

A student proves once that they own a `@uchicago.edu` address and creates an account with a username and password. The email is stored on the account so the student can reset a lost password; it is never logged, never shown to other users, and never copied into forum, plan or analytics rows.

### Protocol

1. **Email.** The browser sends the address. The server checks the domain (`@uchicago.edu` only), lowercases it, checks no account already uses it, and emails a 6-digit code. The code hash lives in Redis for 10 minutes, keyed by an opaque `pending_id` returned to the browser. The address is scrubbed from logs.
2. **Code.** The browser submits `pending_id` and the code and receives a one-time registration ticket (Redis, 10 minutes) bound to the email.
3. **Registration.** The browser sends the ticket, a username and a password. The server hashes the password with argon2id, creates the account with the lowercased email and `email_verified_day`, deletes the ticket, and starts a session. One account per email.
4. **Login** is username (or email) plus password; sessions are httpOnly, Secure, SameSite=Lax cookies backed by Redis, with a CSRF token for state-changing requests. Passkeys may be a stub in v1.
5. **Password reset.** The student enters their email; if an account exists, the server emails a 6-digit code (10-minute TTL, same Redis pattern); code plus new password sets a new argon2id hash and ends other sessions. The response never reveals whether an account exists.
6. **Rate limits** on every auth endpoint (per email hash and per Redis-only, 24-hour IP counter that is never written to disk).

### What is stored

| Data | Stored? | Linkable to a person? |
| --- | --- | --- |
| Email address | Yes, only in `account.email` | Yes, by anyone with database access |
| Username, password hash (argon2id), plans | Yes | Through the email |
| Forum posts, comments, votes | Yes, with `author_ref = HMAC(server_key, account_id ‖ page_id)` | Not from a leaked database alone; yes for someone holding the server key and the database |
| IP addresses | Not by the app; rate limits use a hashed, Redis-only counter that expires within 24 hours; no proxy log (Caddy, nginx) keeps IP addresses: no access logs, and Caddy's own log drops the address fields | Weakly, for 24 hours |
| Timestamps | Day-level only | Coarse |

### Threats and honest limits

- **Leaked database:** reveals which emails have accounts and their plans; posts on different pages still cannot be joined to one account without the server key.
- **Builder or admin with database access and the server key:** can link posts to an account and so to an email. Say this plainly on `/privacy`.
- **Sock puppets:** one account per verified email.
- **Lost password:** reset by email (step 5).
- **Email provider** learns that Quarterly emailed an address. Use a transactional provider with content logging off and a minimal message.

### Account deletion

`/account` offers export (plans as JSON) and deletion. Deletion removes the account, its email, plans and sessions; the student chooses whether their posts are deleted or kept as "\[deleted account\]".

## Risks, policy and legal

The two biggest risks are a wrong rule that misleads a student and a forum post that harms an instructor; both get human review before they reach anyone. I am not a lawyer; have one review the forum terms and privacy page before launch.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A program rule is formalized wrongly | A student plans the wrong courses | Two independent runs, verbatim quotes, golden plans, human review; "Not official advising — confirm with your adviser and My Planner" on every plan; a "Report an error" button on every requirement node |
| Schedule scraping not permitted | No section data | Ask the Registrar first; fall back to department pages and offering history; the planner works at quarter level without sections |
| University objects to a review site | Shutdown pressure | Talk to the College and Student Government early; never republish official evaluations; Yale shut down Bluebook+ in 2014 over how it presented ratings ([Chicago Maroon](https://chicagomaroon.com/49530/feature/new-website-cramwell-ai-helps-students-find-easy-courses-and-professors-for-upcoming-quarter/)) |
| Defamation or harassment of instructors | Legal and ethical harm | Rules in the composer, automatic and human moderation, misconduct claims held, a takedown contact. US law generally treats user posts differently from content the platform writes itself, and **AI summaries are platform-written**: keep them neutral, cited and moderated |
| Over-claiming anonymity | Loss of trust | Precise wording on `/privacy` (emails are stored; forum pseudonyms are per page); open-source the auth code |
| Sensitive self-reported data (grades) | Privacy harm | Grade buckets optional; nothing imported from University systems |
| Prompt injection through forum text | Agent misbehaves | No agent that reads forum text can write; citations validated |
| LLM cost spikes | Budget | Per-account limits, Haiku pre-classifier, prompt caching, daily spend alarm in `llm_call` |
| Empty forum at launch | Little value | Labelled estimates, a pre-launch review drive in pilot departments; the planner is useful without the forum |
| Vote brigading | Skewed ratings | One account per verified email, vote rate limits, burst detection per page |
| Catalog edited mid-year | Stale rules | Monthly change check on catalog snapshots |

## Build roadmap and Claude Code prompt sequence

The build is 13 prompts in four milestones; prompts 2–5 and 7–8 can run in parallel in separate git worktrees once prompt 1 has fixed the contracts. The full prompt texts, a `CLAUDE.md` and subagent definitions are in the starter kit that accompanies this doc.

In Claude Code, effort levels are `low`, `medium`, `high`, `xhigh` and `max`, and subagents can set `model`, `effort` and `isolation: worktree` in their frontmatter ([Claude Code subagents](https://code.claude.com/docs/en/sub-agents.md)). "Opus 5.5 extra" below means Opus 5.5 at `xhigh`.

| # | Prompt | Builds | Model / effort | Runs |
| --- | --- | --- | --- | --- |
| 0 | Bootstrap | Repo, Docker Compose, CI, `CLAUDE.md`, health checks | Opus 5.5 / high | Alone |
| 1 | Contracts | DB schema + migrations, DSL Pydantic models, OpenAPI skeleton, seed-file format | Opus 5.5 / xhigh | Alone |
| 2 | Verifier | `planner_core`: checks V01–V12, CP-SAT model, certificate checker, tests | Fable 5.2 (or Opus 5.5 / xhigh) | Parallel |
| 3 | Frontend shell | App shell, planner grid, requirement rail, issues panel against a mock API | Opus 5.5 / high | Parallel |
| 4 | Accounts | Email verification, registration, sessions, password reset (decision 5) | Fable 5.2 | Parallel |
| 5 | Seed data | Core, CS, Math, Economics for 2026–27 with quotes; golden plans | Opus 5.5 / high, you review | Parallel |
| 6 | Generator | CP-SAT plan generator, variants, change sets, API wiring | Opus 5.5 / xhigh | Alone |
| 7 | Agents | `llm_gateway`, A1 generator agent, A2 advisor chat, eval harness | Opus 5.5 / high | Parallel |
| 8 | Forum | Pages, posts, comments, votes, pseudonyms, moderation (A4) | Opus 5.5 / high | Parallel |
| 9 | Ingestion | Catalog crawler, E1–E4, review console | Opus 5.5 / high | Alone |
| 10 | Schedule | Class Search scraper behind a feature flag, offering patterns | Sonnet 5.5 | Alone |
| 11 | Attributes | Nightly forum → attribute job, summaries (A3) | Opus 5.5 / medium | Alone |
| 12 | Hardening | End-to-end tests, security and privacy review subagents, load test | Opus 5.5 / xhigh | Alone |

**Milestones.** M1 after prompts 0–5: a working planner with the verifier on seed data and no AI. M2 after 6–7: generation and chat. M3 after 8 and 11: the forum for pilot departments. M4 after 9, 10 and 12: automated data and a pilot launch.

**Gates.** Every prompt ends by running its checks (tests, type-check, lint, golden plans) and a reviewer subagent that reads only the diff and this spec.

## Sources

- [My Planner FAQ](https://college.uchicago.edu/advising/my-planner-faq) — UChicago College
- [Enrollment Policies](https://college.uchicago.edu/advising/enrollment-policies) — UChicago College
- [Graduation Requirements & Procedures](https://college.uchicago.edu/advising/graduation-requirements) — UChicago College
- [Degree Requirements](https://college.uchicago.edu/advising/degree-requirements) — UChicago College
- [Core requirements summary (PDF)](https://college.uchicago.edu/sites/default/files/documents/CoreRequirements.pdf) — UChicago College
- [Minors (catalog PDF)](https://uchicago-preview.courseleaf.com/thecollege/minors/minors.pdf) — College Catalog
- [Programs of Study](https://college.uchicago.edu/academics/programs-study) — UChicago College
- [Catalog A–Z index](https://uchicago-preview.courseleaf.com/azindex) — College Catalog
- [Joint Bx/MS programs, Physical Sciences Division](https://physicalsciences.uchicago.edu/current-students/bx-ms)
- [Study Abroad](https://college.uchicago.edu/academics/study-abroad) — UChicago College
- [Course Feedback](https://registrar.uchicago.edu/registration/college-process/course-feedback) — University Registrar
- [my.UChicago / Class Search notice](https://portal.uchicago.edu/ais)
- [Cramwell AI article](https://chicagomaroon.com/49530/feature/new-website-cramwell-ai-helps-students-find-easy-courses-and-professors-for-upcoming-quarter/) — Chicago Maroon, Nov 2025
- [theCourseForum: About](https://thecourseforum.com/about/)
- [Introducing Muse](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/) — Meta, Sep 2026
- [Claude models overview](https://platform.claude.com/docs/en/models/overview) and [Claude Code subagents](https://code.claude.com/docs/en/sub-agents.md)

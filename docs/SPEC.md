# QuadPlan — UChicago Course Planner + Course Forum

*Product & technical spec (working name). For humans and for coding agents.*

Version: 2026-11-12. This file is an export of the shared Claude doc. You can edit either one, but keep the two in sync.

## Summary and decisions to confirm

QuadPlan is a website only for UChicago. It has two halves that share one course database:

- The **Planner** helps a student go from "I don't know my first class" to a full 4-year plan that knows the goals of the student. An AI agent proposes. A deterministic verifier proves that every plan is valid.
- The **Forum** is an anonymous, Reddit-style discussion space with one page for each course × instructor. Its ratings go back into the attributes of each course (workload, difficulty, intellectual intensity). The Planner then uses these attributes.

The design rests on one rule: **agents propose, code disposes.** Agents read messy sources and talk to students. Deterministic code (schemas, a requirements checker, a constraint solver) decides what is true and what is saved.

Where your brief left a choice open, I selected a default. If you change a row, tell your coding agent.

| # | Decision | Default chosen | Main alternative |
| --- | --- | --- | --- |
| 1 | Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2 | Django + DRF (what theCourseForum uses, with a built-in admin) |
| 2 | Frontend | React + TypeScript (Vite), TanStack Query, dnd-kit, Tailwind + shadcn/ui | Next.js, if public course pages need SEO |
| 3 | Database | PostgreSQL 16 (JSONB for rule trees, ltree for comment threads, full-text search) + Redis | SQLite for a throwaway demo |
| 4 | Solver | Google OR-Tools CP-SAT for requirement matching and plan generation | Hand-written max-flow (matching only) |
| 5 | Anonymity | Email and password is stored on the backend | Email and password is stored on the backend |
| 6 | Logged-out access | Catalog facts, planner (local only), aggregate course attributes. Posts and summaries need login. | Hide all forum-derived numbers behind login |
| 7 | v1 scope | College undergrads. Catalog year 2026–27. Core + CS (BA/BS, Bx/MS) + Math (BA/BS) + Economics + 2 study-abroad civ programs | All programs at launch |
| 8 | Section data | First, ask the Registrar for a feed. The fallback is a Playwright scraper of the public Class Search and of department offering pages. | Meta's Muse or a different VM browser agent (not recommended for a pipeline, see Ingestion) |
| 9 | Official course feedback | Not ingested (behind login, owned by the University) | Ask the Registrar for permission |
| 10 | LLM routing | Anthropic API direct. OpenRouter as a fallback behind the same interface. | OpenRouter only |
| 11 | Chat write access | The agent drafts a change set. The app applies it only after an explicit confirmation that the server checks against that exact draft. | The agent edits the plan freely |
| 12 | Name | "Quarterly", "Quarterly Planner" and "Quarterly Forumn" for now | We will go with this name for now. Please ignore all "QuadPlan" entries and use the above names |

## Product overview

QuadPlan answers two questions that the official tools of UChicago leave open: **"what should I take, given what I want?"** and **"what is this class actually like with this professor?"**

### Problem 1: planning starts from a blank page

The My Planner (Stellic) of the College gives every undergraduate a four-year layout, a degree audit, schedule tools and pre-registration ranking.

- It does not recommend courses. Advice comes from advisers.
- Its nearest automated behavior is to sort courses into requirements, so that the student uses the fewest courses ([My Planner FAQ](https://college.uchicago.edu/advising/my-planner-faq)).
- A new student must still work out the first quarter alone.
- Nothing accounts for personal goals, such as a lighter quarter, a Bx/MS application, or a civilization quarter abroad.

The rules are intricate:

- A degree needs 4200 units: the Core (1500 units), at least one major (900–1900 units) and electives ([Degree Requirements](https://college.uchicago.edu/advising/degree-requirements)).
- Full-time is 300 or 400 units in a quarter. A 500-unit overload gets approval only in narrow cases ([Enrollment Policies](https://college.uchicago.edu/advising/enrollment-policies)).
- Minors cannot share courses with the Core (except Language Competence) or with a major ([Minors](https://uchicago-preview.courseleaf.com/thecollege/minors/minors.pdf)).

### Problem 2: course feedback is thin and scattered

Official course feedback is a survey that the Registrar runs. Students fill it in each quarter ([Course Feedback](https://registrar.uchicago.edu/registration/college-process/course-feedback)). The comments are usually cautious, and it is hard to compare them across instructors.

Tools that students build come and go. In November 2025, the Maroon reported on Cramwell AI (ratings and a chatbot). It also noted that the domain of UChicago Genie is gone ([Chicago Maroon](https://chicagomaroon.com/49530/feature/new-website-cramwell-ai-helps-students-find-easy-courses-and-professors-for-upcoming-quarter/)).

### What QuadPlan does differently

- **Plans are proven, not suggested.** A deterministic verifier checks every plan, from a student or from the agent. The verifier gives a certificate: which course satisfies which requirement, and which earlier course satisfies each prerequisite.
- **Goals are first-class.** Students attach goals to their full career or to specific quarters ("Spring of 3rd year abroad", "Winter ≤ 45 hrs/week"). The generator optimizes for the goals, and the verifier checks them.
- **Course attributes are explicit and sourced.** Each course and each course × instructor pair has workload, difficulty and intellectual-intensity scores, with a confidence level and the evidence for them.
- **The forum is structured.** One page for each course × instructor, Reddit-style threads, votes, and structured ratings that update the attributes.

### Users

| Persona | Situation | What they need first |
| --- | --- | --- |
| Incoming first-year | No credits, vague interests | A sensible first quarter and a few candidate paths |
| Transfer student | Transfer credits, fewer quarters left, 2nd-year status | Which credits count, what is still possible (e.g. Bx/MS) |
| Declared ambitious major | CS + Math, wants Bx/MS or a PhD path | Hard-course sequencing, overload checks, application timing |
| Goal-constrained student | Pre-med, athlete, study abroad, early graduation | Plans that obey fixed quarters and loads |
| Forum reader / writer | Choosing between sections or instructors | Honest, comparable experiences |

### Scope

**v1 (prototype):**
- Catalog year 2026–27.
- Core, CS (BA/BS and Bx/MS), Math (BA/BS), Economics, two civilization-abroad programs.
- Planner with verifier, plan generator and advisor chat.
- Forum for courses in those departments.
- Anonymous accounts.

**Later:** every program in the catalog, multiple catalog years, transfer/AP credit import, section-level weekly schedules, mobile layout polish, corrections that departments maintain.

**Non-goals:** to register students for classes, to replace the official audit or the advisers, to publish grades or official evaluations, and to identify anyone.

## Core user journeys

Every journey ends at the same place: a plan on the 4-year grid with a green verifier badge, or a precise list of what is still wrong.

**A. Incoming first-year with no plan**

1. The student comes to the home page, clicks **Start planning**, and creates an account. (Issue #16: planning starts with sign-up.)
2. The registration form asks for the class year, the expected graduation quarter and the intended programs.
   - Credits go in the Academic background of the dashboard (or on the form for a transfer or later-year student).
   - The questions of the dashboard agent (goals, scheduling, learning preferences) can wait.
3. The planner offers "set up a plan from your information". The plan opens with the programs of the student record, and with the Core put in position as requirement slots ("HUMA sequence, quarter 1–3"), not as courses.
4. The student clicks **Generate plan** → a popup with sliders and toggles opens → the agent returns 2–3 variants ("Exploratory CS", "Econ-leaning", "Balanced"). Each variant is verified, and has a one-line rationale for each quarter.
5. The student accepts one, and changes a course by drag-and-drop. The verifier runs again in less than one second.
6. The app saves the plan to the account.

**B. Transfer student targeting CS BS + Math BS and Bx/MS**

1. The student enters transfer credits. QuadPlan maps the known equivalents and flags the unknown ones for manual mapping.
2. The student selects programs: CS BS, Math BS, CS Bx/MS (research option).
3. The student adds goals: "Bx/MS application in Winter of 3rd year" and "no more than one 'very hard' course per quarter".
4. The student generates a plan. The verifier shows the overload rules, the double-count limits between the two majors, and whether the remaining quarters are sufficient.
5. The student opens the advisor chat: "Is Honors Analysis worth it if I want ML research?" The agent answers with course attributes and forum evidence. Then it offers a change set. The student confirms to apply it.

**C. Goal-constrained student (study abroad + lighter senior year)**

1. The student pins "Paris civilization program, Spring Y2" as a block. The block counts as the civ sequence and fills the quarter.
2. The student sets "Y4 ≤ 3 courses per quarter".
3. The generator moves heavy major courses into Y2–Y3 and checks offering patterns ("usually Autumn only").

**D. Forum reader and writer**

1. The student searches "MATH 20700" and opens the course page. It shows aggregate attributes and the instructors who teach the course.
2. The student clicks an instructor → the course × instructor page: rating summary, an AI summary with citations to posts, and threads sorted by Best.
3. The student logs in to read and post. The student writes a review (structured ratings + text) under a per-thread pseudonym such as "Quiet Heron", and upvotes a helpful answer.

## System architecture and tech stack

One PostgreSQL database is at the center. A small pure-Python package, `planner_core`, holds every rule that decides correctness. Both the API and the background workers import it. Everything runs in Docker Compose, on a laptop and on one small cloud VM.

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

Workers call the same `llm_gateway` and `planner_core` as the API. Thus exactly the code that checks the own edits of a student also checks the output of an agent.

| Service | Technology | Responsibility |
| --- | --- | --- |
| `web` | React 18 + TypeScript (Vite), TanStack Query, dnd-kit, Tailwind + shadcn/ui | Every page, planner grid, forum UI |
| `api` | FastAPI (uvicorn), SQLAlchemy 2, Pydantic v2 | REST API, Server-Sent Events for agent progress, auth, rate limits |
| `planner_core` | Pure Python package, OR-Tools CP-SAT | Requirements DSL, verifier, certificate checker, plan solver. No database or network access. |
| `llm_gateway` | Python package: Anthropic SDK + OpenAI SDK pointed at OpenRouter | Model routing, retries, prompt caching, cost logging, structured-output validation |
| `worker` | Arq (Redis-backed jobs) | Agent runs, ingestion, nightly forum → attribute aggregation, moderation |
| `scheduler` | Arq cron | Annual catalog run, quarterly section run, nightly jobs |
| `scraper` | Playwright (Python), headless Chromium | Public Class Search and department pages. Saves raw snapshots. |
| `db` | PostgreSQL 16 | All data. JSONB for rule trees. `ltree` for comment paths. Full-text search. |
| `redis` | Redis 7 | Job queue, rate limiting, cache |
| `storage` | MinIO (S3-compatible) | Raw HTML/PDF snapshots of every source page |
| `admin` | SQLAdmin mounted in `api`, and a React review queue | Curator tools: diff review, rule editor, moderation |

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

- **One contract.** The API publishes OpenAPI. The frontend client is generated from it (`openapi-typescript`). Do not write fetch types by hand.
- **Small trusted core.** `planner_core` takes Pydantic models in and returns Pydantic models out. It never imports the database, the web framework or an LLM client.
- **Agents use the same doors as people.** Agent tools call the service layer, which runs the same validators as UI requests. No agent writes SQL.
- **Everything has a version.** The key of catalog data is the catalog year. Every derived fact keeps a pointer to its source snapshot.
- **The logged-out state is local.** The plan of a logged-out student is in browser storage. At login, the app imports it into the account.
- **The app logs every LLM call** (task, model, prompt version, tokens, cost, latency, outcome), with no user identifier.

Why FastAPI and not Django:

- Agent runs are long and streamed.
- Pydantic models can be shared with `planner_core`.
- OpenAPI comes free.

Django would win on the built-in admin. SQLAdmin covers most of that gap.

## Sitemap and every page

The site has 16 page types. The planner, the generate popup, the advisor chat and the course × instructor page hold most of the product. A login is necessary only to save plans and to enter the forum.

The design canvas has mockups of six key screens, with sample data: [QuadPlan — screen mockups](https://claude.ai/artifact/U46qMrKwDcMToNGW5bWJQR) (planner with advisor chat, generate popup, course page, course × instructor forum, onboarding goals, anonymous sign-up).

**Main navigation (issue #15; a sidebar since 2026-11-27, docs/DESIGN.md "Simple light"):** four tabs, in this order: **Dashboard** (`/me`), **Planner** (`/plan`), **Catalog** (`/courses`) and **Forum** (`/forum`). The homepage is not a tab. The "Quarterly" wordmark links to it. No page has a floating companion.

| Route | Page | Login | Purpose |
| --- | --- | --- | --- |
| `/` | Home | No | Not a tab: the wordmark in the top bar links here. Title "The Best of UChicago, *within your reach.*". It shows "Start planning" (a link to `/signup` when logged out, to `/plan` when logged in, issue #16) and "Explore the catalog" (a link to `/courses`, issue #19). Since issue #15, there is no question bar and there are no "Try" questions. The course search of the top bar shows here on every screen size. Under the title and buttons, a white card holds the reading room of Harper Memorial Library, drawn in code (Max, 2026-11-27; docs/DESIGN.md "Simple light"). Sunlight falls through its windows by day, and lamps light it by night (a Day / Night switch in the card's caption row, remembered on the device). With reduced motion, nothing moves. Below the card, three cards (Planner, Catalog, Forum) each link to their part. (The Rockefeller Chapel drawn with course titles is no longer on the page; its code stays until Richard decides, OPEN_QUESTIONS DG-1.) |
| `/ask` | (redirect) | No | Redirects to `/plan`. Issue #15 removed the Ask page and its chatbot. The planner page is the only place where a student talks to the planner agent ("Ask Quarterly"). |
| `/me` | Your dashboard | Yes | The student record (Issue #14, #16). It shows: a Profile card (name, class year, the email read from the account, intended programs, program progress, "Complete your profile"). The General Information in four groups (Academic background, Goals, Scheduling, Learning preferences). The student can edit each answer in place or through the dashboard agent (`POST /agents/interview`). The agent asks the step-2 questions one at a time, with their options as buttons, and proposes each answer for the student to accept. "Your plan": a read-only summary of the primary plan, with a link to the planner. "Export my information (.md)" (`GET /me/profile/export.md`). There are no routes and no "At a glance" (issue #15 removed them, because the planner makes every plan proposal). There is no "What's new" (issue #16 D5). |
| `/feed` | (redirect) | No | Redirects to `/courses`. Issue #19 removed the Feed page. Its course spotlights and student quotes are browse rows of the Catalog. Its floating words, ticker, focus chips, book shelf, word clouds, open questions, program cards and AI notes (`POST /agents/feed-notes`, task `a8_feed_notes`) are gone. |
| `/forum`, `/forum/new`, `/forum/t/{id}` | The forum (reviews and the Commons) | Read: no (reviews and ratings: yes). Write: yes. | `/forum` (issue #20, see Forum, "The forum page"): ratings, statistics and rankings in the left third (only for logged-in students), and course reviews and Commons discussions in one list, newest first, in the right two thirds. A "New post" button opens `/forum/new`. A discussion is a Commons question and its replies. First comes a short AI answer (a maximum of 60 words, `POST /commons/threads/{id}/bot`). Then come the students: nested replies, votes, accept, edit, delete, report, follow, typing presence, and a markdown composer with course mentions and drafts. Students still write reviews on the course x instructor pages (`/instructors`). |
| `/onboarding` | (redirect) | No | Redirects to `/me`. The registration form asks for the entry term, credits and programs. The dashboard agent asks the scheduling questions. |
| `/plan` | Planner | No (local) / Yes (to save) | 4-year grid, requirements, verifier, generate, chat |
| `/plans` | My plans | Yes | List, rename, duplicate, set primary |
| `/plans/compare` | Compare plans | Yes | Side-by-side diff of two plans, with metrics |
| `/courses` | Catalog | No | The Catalog tab (issue #19). The course search box and its filters (department, level, quarter, Core area, workload, difficulty) did not change. A Courses / Programs switch goes to `/programs`. Before a search, the page shows browse rows (`GET /catalog/browse`). **Newly released courses** shows only when the app knows of new courses. It uses the hand-written list `data/catalog/new_courses.yaml`, with a verbatim source quote for each entry. When the database holds an earlier catalog year, it also shows the courses that the earlier year did not have. **Course spotlights** comes from the old Feed. It matches the profile and followed courses of a logged-in student. If not, it is a curated mix that rotates daily. **What students say** shows Commons replies for everyone, and forum reviews and discussions only for a logged-in reader. After a search, the page shows the list of results. For a logged-in student, every course in the rows and the results shows its student rating summary (`GET /course-ratings`, the rule of the course page). A logged-out visitor sees one "Log in to see student ratings" line. |
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

- **Top bar:**
  - The plan name, the catalog year and the program chips ("CS BS", "Math BS", "CS Bx/MS").
  - The **Generate plan** button.
  - A quiet **Check plan** button with a small count badge. Errors stay subtle, because most students make a partial plan.
  - Save.
  - A one-line "Not official advising" notice.
- **Right drawer** (slides in from the right, full screen on a phone): Requirements, Issues and Goals.
  - Requirements is a vertical tree for each program (program → nodes → courses).
  - Each course shows its code in bold, with its name in small text. Each node shows a subtle "n of m".
  - The student can drag any course onto the grid.
  - **Check plan** opens Issues.
- **Center, the grid (the main width):**
  - One row for each academic year, from the entry quarter to the graduation quarter.
  - An academic year has the order Summer, Autumn, Winter, Spring. The summer *before* autumn is part of it (Summer 2026 is in 2026–27). There is no summer after the last spring.
  - Summer is collapsed by default.
  - The label of a year is the class year ("Second year" for the first year of a second-year transfer).
  - The `graduation_term` of the plan sets its end. By default, it is the Spring of the last year, counted from the entry level (four years for a first-year, three for a second-year transfer). **Add a year**, **Remove last year** (only when that year is empty) and **Graduating in** (an Autumn, Winter or Spring) change it.
  - Each quarter is drawn as a folder (Max, 2026-11-27; docs/DESIGN.md "Simple light"). Its name is on the tab, and a small "Now", "Next" or "Past" label sits beside it. The whole folder is the drop target.
  - Each course is a file in its quarter's folder. A course card shows the code, short title, units, a color stripe for the requirement that it fills, estimated hours/week and difficulty dots.
  - The folder's front pocket is the quarter footer. It shows the units, the course count, total hours/week, a difficulty index, the counts of errors and warnings, and a "+" button that opens "Add a course to <quarter>" (the course picker). The goal chips of the quarter sit at the foot of the folder, above the pocket.
- **Advisor** (opens from the top, separate from the drawer): it has a clear label as generative AI ("Generative AI", "Answers are written by an AI and can be wrong"). It has a chat layout: message bubbles for the student and the AI, a typing indicator during streaming, citation chips and proposal cards.
- **Motion:** subtle transitions for the drawer, the advisor, dialogs and course cards. With `prefers-reduced-motion`, all are off.
- **Interactions:**
  - Drag to add/move.
  - A drop immediately shows inline warnings (missing prerequisite, not usually offered that quarter).
  - Right-click to lock, mark completed, or remove.
  - Each edit starts a debounced full verification (target: less than 500 ms).
- **States:** empty (requirement slots show as dashed cards), verifying, valid, warnings, errors. Read-only for a shared snapshot.
- **API:** `GET /plans/{id}`, `PATCH /plans/{id}/items`, `POST /verify`, `POST /agents/generate` (SSE), `POST /agents/chat` (SSE), `POST /plans/{id}/changesets/{cs}/apply`.

### Generate-plan popup

The popup is a form, never a free-text prompt. Thus every input maps to a typed parameter.

1. **Scope:** the full plan, the remaining quarters, or selected quarters. Locked and completed courses stay.
2. **Load and difficulty:** a career-wide slider (lighter ↔ heavier), with optional overrides for each quarter. The maximum number of courses in a quarter. Permit a 500-unit quarter only where the rules permit it.
3. **Goals:** filled from the Goals tab, and editable (graduate by, study abroad block, Bx/MS application, pre-med sequence, protect GPA, "challenge me").
4. **Interests:** tags ("ML", "philosophy of mind", "Chinese") that the generator uses to select electives.
5. **Variants:** 1–3.

Then a progress view streams the steps of the agent ("Loading requirements → Choosing electives → Solving → Verifying → Writing rationale").

The result shows each variant with:

- A diff against the current plan.
- Its verifier badge.
- Metrics (average hours, hardest quarter).
- A one-line rationale for each quarter.

Buttons: **Apply**, **See changes** (with **Choose quarters to apply** inside it), **Discard**. Above them, a line tells which quarters Apply changes. An option that still has errors says so.

### Advisor chat (right rail)

- The advisor answers only planning questions. Off-topic requests get a one-line refusal.
- Each factual claim has a citation chip: a course attribute ("MATH 20700 · workload 18 h/wk · n=34") or a forum post.
- Changes come as a **proposal card**: a list of add/move/remove operations, and the verdict of the verifier on the plan after the change.
  - **Apply** applies it.
  - An explicit typed confirmation ("I agree to add MATH 20700 to Autumn Y2") also works. The server checks that it agrees with the card.

### Course page (`/courses/{code}`)

The page has these parts:

- Header: code, title, units, cross-listings, Core/major tags, "Add to plan".
- Description.
- Prerequisites as readable text, and a small graph of what the course needs and what it unlocks.
- Offerings by term with the instructor, and predicted future quarters with confidence.
- Attribute card: workload h/week, difficulty, intellectual intensity, pace, each with n, confidence and source.
- Instructor list, with links to the forum pages.
- "Counts toward": a list of program requirements.

### Course × instructor forum page

The page has these parts:

- A header with the course, the instructor and the terms taught.
- Rating distribution bars.
- An AI "What students say" summary, with numbered citations to posts and its update date.
- Tabs **Reviews** and **Discussion**.
- Sort Best / New / Top / Controversial. Filter by term.
- A composer for a review (structured ratings required) or a discussion post.
- Each post shows the per-thread pseudonym, an optional "took it in Autumn 2025" badge, the score, Reply and Report.

### Instructor page

Name, department and the courses that the instructor teaches (from the public catalog and schedule), each with its aggregate ratings. No personal information beyond what the University publishes.

### Program explorer and program page

The explorer groups programs by type: major, minor, Bx/MS and joint degrees, specializations/tracks, pre-professional paths, study-abroad blocks.

A program page does these things:

- It shows its rule tree in plain English.
- It links to the exact catalog source and year.
- It shows the verification date of the curator and one sample path.
- It has "Add to my plan".

### Onboarding (`/onboarding`)

The two-step registration (Issue #16) replaced it. `/onboarding` redirects to `/me`. Its entry term, credits and programs moved into the registration form. Its goals became the scheduling questions of the dashboard agent (quarters away, course load).

### The General Information and `student.md` (Issue #14)

The General Information questions are written one time, in `data/profile/questions.yaml`. Each question has: id, group, field, short label, text, type (single, multi, scale, list, table), options and step (1 = the registration form, 2 = the dashboard agent).

- The registration form, the dashboard and the dashboard agent read them from `GET /profile/questions`.
- The answers make the student record: `student_profile`, `student_credit` and `student_course` (see Data model).
- There are no freeform fields, no resume and no GPA. Each taken course keeps an optional grade.

| Group | Questions |
| --- | --- |
| Academic background | Class year. Expected graduation term. Intended programs. Credits (AP, placement and transfer), for every student. For a student who transferred or is not in the first year: the entry term, the entry year level and taken courses. A course in progress has no grade. |
| Goals | Plans after graduation (industry, graduate school, medical or law school, undecided). Graduation pace (early, on time, flexible). Interest in research and, if yes, research areas. |
| Scheduling | Course load: conservative (only the units that keep the student full time and graduate them on time), normal (a mix of 300-unit and 400-unit quarters) or ambitious (400 units each quarter, and 500 units in a quarter when the College approves an overload for one of its listed reasons). Quarters away (study abroad, internship, leave). |
| Learning preferences | Class formats (seminar, lecture, lab, online). Theory or application (1 to 10). |

`student.md` is generated from the record (`render_student_md()`):

1. A "General Information" section. It has the four groups as headings, in this order. Each question has one line with its short label. An empty answer shows "Not answered".
2. In the export and for the planner agent: "Working information". These are the Markdown notes that the planner chat keeps for each student. A line that applies to only one plan starts with the plan name. Issue #17 writes these notes.

`student.md` never contains the email or the username. The agents read it, in place of the old profile summary. The student downloads it from the dashboard (`GET /me/profile/export.md`). It is also part of `/account/export`.

The dashboard agent's copy of `student.md` has no grades and no Pass/Fail for the taken courses. This copy goes to the AI provider, and the agent's questions do not use grades (OPEN_QUESTIONS M21-1). The export keeps them.

A turn of the dashboard agent proposes only the field of the question that the student answered (`proposed`). The browser saves that field and nothing else when the student accepts it.

### Sign-up and login

Sign-up has four steps:

1. Enter a `@uchicago.edu` address.
2. Enter the 6-digit code.
3. Choose a username and password (passkey optional later).
4. "About you", the registration form: the step-1 General Information questions (class year, expected graduation term, intended programs, credits) and the checkbox "I transferred, or I am not in my first year.". The checkbox adds the entry term, the entry year level and taken courses. Every student can add AP, placement and transfer credits. The credits question is optional: it does not count in the share of answered questions.

Steps 2 and 3 have a "Back" button. It opens step 1 and keeps the email address (a code works one time only). Step 4 has no "Back", because step 3 made the account. The screen after step 4 ("A few more questions?") has a "Back" button that opens step 4 with the saved answers.

Then the student answers the questions of the dashboard agent now, or skips them. (The student can start them later from the dashboard with "Complete your profile".) Then the student goes to the page that they came from, or to `/plan`.

Login is username or email, and password. \"Forgot password\" sends a reset code by email. Nothing on either page asks for a name.

### Curator console (`/admin`)

- Ingestion runs with status and diffs.
- A review queue that shows the source text beside the extracted rule tree (accept, edit, reject).
- A rule editor with live validation and golden-plan tests.
- The moderation queue.
- LLM usage and cost by task.

## Data model

The model has nine groups of tables. The key of the catalog, schedule and program groups is the catalog year or the term. Thus the app can still check old plans against the rules that applied when they were made. The field lists are the minimum. Coding agents can add timestamps and indexes.

### Catalog

| Table | Key fields | Notes |
| --- | --- | --- |
| `catalog_year` | `id` ("2026-27"), `published_at` | By default, students follow the year of their entry term. |
| `course` | `id`, `subject`, `number`, `title`, `units` (default 100), `description`, `catalog_year`, `core_tags[]`, `tags[]`, `repeatable`, `source_id` | `code` = `subject + " " + number`. The tag `credit_only` marks credit that a student receives but never enrols in (TRNC 10100, transfer general credit). A credit can map to it, and its units count toward the degree total. But the plan generator never puts it in a quarter, and never offers it as an elective choice. |
| `crosslist_group` | `group_id`, `course_id` | Cross-listed codes count as one course. |
| `course_relation` | `course_a`, `course_b`, `kind` (`equivalent`, `mutually_exclusive`, `replaces`) | For example, credit for only one of two intro sequences. |
| `requisite` | `course_id`, `catalog_year`, `prereq` (JSONB, DSL), `coreq` (JSONB), `restrictions` (JSONB), `raw_text` | `raw_text` is the catalog sentence that the rule came from. |

### Schedule

| Table | Key fields | Notes |
| --- | --- | --- |
| `term` | `id` ("2026-AU"), `year`, `quarter` (AU, WI, SP, SU), `start`, `end` |  |
| `instructor` | `id`, `slug`, `display_name`, `department`, `aliases[]` | Names are de-duplicated across sources. |
| `section` | `id`, `term_id`, `course_id`, `section_no`, `component`, `instructor_ids[]`, `meetings` (JSONB), `capacity`, `status`, `source_id`, `scraped_at` |  |
| `course_instructor` | `id`, `course_id`, `instructor_id`, `first_term`, `last_term`, `n_terms` | The key of every forum page. One page for each cross-listed group and instructor, shown under every code (P08-5). |
| `offering_pattern` | `course_id`, `quarter`, `p_offered`, `evidence_terms[]`, `method` | Predicted availability for future years. |

### Programs

| Table | Key fields | Notes |
| --- | --- | --- |
| `program` | `id` (slug, e.g. `cmsc-bs`), `name`, `type`, `degree` (BA, BS, MS), `department`, `parent_id` | `type`: major, minor, bxms, joint, specialization, track, preprofessional, study\_abroad\_block, core |
| `program_version` | `id`, `program_id`, `catalog_year`, `rules` (JSONB, DSL), `status` (draft, review, published), `verified_by`, `verified_at`, `source_ids[]`, `checksum` | Only `published` versions reach students. |
| `program_relation` | `program_a`, `program_b`, `kind` (`requires`, `excludes`, `share_limit`), `n` | For example, Bx/MS requires the matching major. A minor shares 0 courses with a major. |

### Attributes

| Table | Key fields | Notes |
| --- | --- | --- |
| `attribute_def` | `key`, `scale`, `description` | Keys: `workload_hours`, `difficulty`, `intellectual_intensity`, `pace`, `grading_strictness`, `recommend_rate` |
| `attribute_value` | `subject_type` (course, course\_instructor), `subject_id`, `key`, `value`, `ci_low`, `ci_high`, `n`, `method` (prior, forum, blend), `evidence` (JSONB), `computed_at` | The evidence lists post ids and source ids. |

### Provenance and review

| Table | Key fields | Notes |
| --- | --- | --- |
| `source_snapshot` | `id`, `url`, `fetched_at`, `sha256`, `storage_key`, `content_type` | Object storage keeps the raw bytes. |
| `extraction_run` | `id`, `kind`, `model`, `prompt_version`, `input_snapshot_ids[]`, `output` (JSONB), `status`, `cost_usd` | One row for each agent extraction. |
| `review_item` | `id`, `target_type`, `target_id`, `diff` (JSONB), `reason`, `status`, `decided_by`, `decided_at` | The human gate before publication. |

### Plans and goals

| Table | Key fields | Notes |
| --- | --- | --- |
| `plan` | `id`, `account_id`, `name`, `catalog_year`, `entry_term`, `entry_year_level`, `graduation_term` (nullable: the default last quarter), `is_primary`, `updated_day` | Dates are rounded to the day. |
| `plan_program` | `plan_id`, `program_version_id`, `options` (JSONB: track, specialization) |  |
| `plan_item` | `id`, `plan_id`, `course_id` or `slot_ref`, `term_id`, `status` (planned, in\_progress, completed, transfer, exam), `locked`, `units` | `slot_ref` is a placeholder for a requirement that is not filled. Completed and in-progress courses are in `student_course` (Issue #14). Migration 0010 removed the old per-plan copies. |
| `credit` | `plan_id`, `kind` (AP, placement, transfer), `label`, `maps_to_course_id`, `units` | Not used since Issue #14. Credits are in `student_credit`. Migration 0010 removed the old rows. |
| `goal` | `id`, `plan_id`, `scope` (career, term), `term_id`, `type`, `params` (JSONB), `hard`, `weight` | Verification lists the goal types. |
| `verification_report` | `plan_id`, `plan_hash`, `core_version`, `status`, `issues` (JSONB), `certificate` (JSONB) | The cache key is `plan_hash`. |
| `change_set` | `id`, `plan_id`, `origin` (generate, chat, user), `ops` (JSONB), `base_plan_hash`, `preview_report` (JSONB), `status` (proposed, applied, discarded, stale) | The only way for the suggestion of an agent to reach a plan. |

### Agents and LLM usage

| Table | Key fields | Notes |
| --- | --- | --- |
| `agent_run` | `id`, `kind`, `plan_id`, `model`, `status`, `steps` (JSONB), `tokens`, `cost_usd` |  |
| `chat_message` | `run_id`, `role`, `content`, `citations` (JSONB) | Deleted after 30 days. |
| `llm_call` | `task`, `model`, `prompt_version`, `in_tokens`, `out_tokens`, `cost_usd`, `latency_ms`, `ok` | No user identifier. |

### Forum

| Table | Key fields | Notes |
| --- | --- | --- |
| `post` | `id`, `course_instructor_id`, `kind` (review, discussion), `author_ref`, `pseudonym_id`, `title`, `body_md`, `term_taken`, `score`, `status` (visible, held, removed), `created_day` |  |
| `review_rating` | `post_id`, `overall`, `difficulty`, `intellectual_intensity` (1–5), `workload_hours`, `would_recommend`, `grade_bucket` (optional) | One review for each account on each page. |
| `comment` | `id`, `post_id`, `parent_id`, `path` (ltree), `author_ref`, `pseudonym_id`, `body_md`, `score`, `status` |  |
| `vote` | `voter_ref`, `target_type`, `target_id`, `value` (±1) | Unique for each voter and target. |
| `pseudonym` | `id`, `author_ref`, `course_instructor_id`, `handle` | Stable within a page, different across pages. |
| `report`, `moderation_action` | target, reason, status, actor (model or admin) |  |
| `forum_summary` | `course_instructor_id`, `text`, `citations`, `model`, `n_posts`, `computed_at` |  |

`author_ref` and `voter_ref` are `HMAC(server_key, account_id ‖ page_id)`. Thus a leaked database does not show which posts across pages come from one account.

### Accounts

| Table | Key fields | Notes |
| --- | --- | --- |
| `account` | `id`, `username`, `email` (unique, lowercase), `email_verified_day`, `password_hash` (argon2id) or passkey credential, `role` (user, curator, admin), `status`, `created_day` | The email is stored as decision 5 tells. It is never logged and never copied to other tables. |
| `student_profile` | `account_id`, the General Information answers (`class_year`, `expected_graduation_term`, `intended_programs`, `entry_term`, `entry_year_level`, `post_grad_plan`, `pace`, `wants_research`, `research_areas`, `course_load`, `terms_away`, `class_formats`, `theory_vs_application`), `working_notes`, `interview` (the memory of the dashboard agent), `follows`, `updates_seen` | The student record (Issue #14. `feed_categories` was dropped with the Feed, issue #19). NULL = not answered. It never holds the email. |
| `student_credit` | `account_id`, `kind` (AP, placement, transfer), `label`, `maps_to_course_id`, `units` | The credits of the record. Every saved plan reads them (they are not part of one plan now). A label has a maximum of 120 characters (emails and phone numbers removed). A credit has a maximum of 1000 units. When a plan is saved, the app clips the credit of the plan to these limits. |
| `student_course` | `account_id`, `course_id`, `term_id`, `status` (completed, in_progress), `grade` (none for a course in progress), `grading` (letter, pass_fail), `units`, `locked` | Taken courses. Each keeps the grading, units and lock of the plan item. Thus a Pass/Fail course never counts where a letter grade is required (V12), after an edit of the record on the dashboard or a save from the planner. Every saved plan shows them as completed or in-progress items (id `t<id>`). A plan save writes them back. A new plan never overwrites a record that already has taken courses. When the planner opens, it shows the credits and taken courses of the record. Unless the student changed them in the planner, a save writes the current ones of the record. (Thus an old copy never undoes a change made on the dashboard.) A save never removes taken courses from before the first quarter of the plan. |

## Data ingestion

There are three scheduled pipelines: the annual catalog, the quarterly schedule, and the nightly forum aggregation. All three follow the same path: fetch → snapshot → parse → validate → diff → human review → publish. Agents are used only where the source is prose. Plain code parses all structured data.

### Sources

| Source | What we take | Cadence | Method |
| --- | --- | --- | --- |
| [College Catalog](http://collegecatalog.uchicago.edu/thecollege/programsofstudy/) (CourseLeaf) | Courses, descriptions, prerequisite sentences, program requirements, Core, minors and joint-degree rules | Each new catalog year, and a monthly change check | HTTP fetch + HTML parser. LLM for requirement prose. |
| Public Class Search (guest access, with a link from [my.UChicago](https://portal.uchicago.edu/ais)) | Sections, instructors, meeting times, status for each term | When the schedule of a quarter is posted. Weekly during registration. | Playwright scraper, only if permitted |
| Department offering pages (e.g. [CS course info](https://course-info.cs.uchicago.edu/guava8/undergrad/index.html)) | Planned offerings for the next year | Quarterly | HTTP + LLM extraction |
| [Study Abroad](https://college.uchicago.edu/academics/study-abroad) | Programs, quarters, which Core requirement each satisfies | Annually | HTTP + LLM extraction |
| College advising pages | Load, overload, graduation and residency rules | Annually | Curated by hand into the "College policy" rule set |
| QuadPlan forum | Ratings and text | Nightly | Aggregation job (see Forum) |

**Ask first.** The cleanest path is a data feed from the Registrar. During the research for this spec, robots.txt refused my fetch tool on the class-schedule page of the Registrar. Use that as a signal to request permission before you scrape schedules. Official course feedback stays out of scope.

**On Muse.** Meta's Muse runs a personal agent in its own cloud VM with a browser ([Meta](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/)). It is good for one-off browsing, not for a pipeline. It has no stable API, no snapshot provenance, and consumer terms. Use a deterministic Playwright scraper. Call a Claude agent only to repair the scraper when the page layout changes.

### Annual catalog pipeline

1. **Crawl.** Fetch the catalog index, the A–Z index, every program page and every course-description page. Use 1 request/second and an honest user agent. Store each response as a `source_snapshot` (sha256, URL, time).
2. **Parse courses (code only).** CourseLeaf course blocks have regular fields: code, title, units, description, "Prerequisite(s)", "Equivalent Course(s)", "Note(s)". These fields become `course`, `crosslist_group` and `course_relation` rows.
3. **Formalize prerequisites (agent E1, Haiku 5.5).** Each prerequisite sentence becomes a DSL expression. The output must parse under the grammar, and every course that it names must exist. All other output goes to review.
4. **Enumerate programs (agent E2, Opus 5.5).**
   - Sources: the catalog index, the A–Z index, the minors list, the joint-degree pages, the study-abroad list and the department sites.
   - Output: one candidate for each program, with its type and URL.
   - Completeness check: the count must agree with at least two independent lists. (The College states 68 majors and 57 minors on its [Programs of Study](https://college.uchicago.edu/academics/programs-study) page.)
   - A difference blocks the run.
5. **Formalize each program (agent E3, Opus 5.5, run two times).**
   - Input: the program snapshot, the DSL schema, the course list and three worked examples.
   - Output: a rule tree. Each node has a verbatim quote from the source.
   - A second, independent run uses Sonnet 5.5, with the prompt in a different order.
6. **Validate.**
   - (a) JSON schema.
   - (b) Every course reference exists.
   - (c) Every quote is verbatim in the snapshot.
   - (d) The two runs agree node by node. If not, a review item.
   - (e) Agent E4 (Sonnet 5.5) writes the tree back into English, and a judge lists the differences from the source.
   - (f) Golden plans pass or fail as expected.
   - (g) Size sanity: majors have 9–19 courses ([Degree Requirements](https://college.uchicago.edu/advising/degree-requirements)).
7. **Diff against last year.** Unchanged programs carry over automatically. Changed programs go to review.
8. **Human review and publish.** In the console, a curator accepts, edits or rejects. Only `published` versions reach students.

### Program checklist the enumerator must fill

- Majors, with BA/BS variants and named tracks or specializations.
- Minors (and the rule that they share no courses with the Core, except Language Competence, or with a major).
- Joint and 4+1-style programs:
  - Bx/MS in Computer Science, Mathematics, Statistics, Chemistry, Computational and Applied Mathematics, Financial Mathematics.
  - Bx/MA in Economics.
  - Bx/MPP and Bx/MS-CAPP with Harris ([PSD joint programs](https://physicalsciences.uchicago.edu/current-students/bx-ms), [catalog A–Z](https://uchicago-preview.courseleaf.com/azindex)).
  - The enumerator derives the list again every year.
- Pre-professional paths (pre-med and health professions), as course lists with timing goals, not as degrees.
- Study abroad: one-quarter civilization programs (they count as the civ sequence, a maximum of one for each student), language programs, direct enrollment.
- College-wide rules: the Core, Language Competence, 4200 units with 3800 earned by enrollment, half of each major or minor in residence ([Graduation Requirements](https://college.uchicago.edu/advising/graduation-requirements)).

### Quarterly schedule pipeline

1. Each week, look for the schedule of the next quarter. When it is available, go through the subjects and snapshot every results page.
2. Parse the pages into `section` rows. Checks:
   - The course code exists. If not, flag a new or topics course.
   - Instructor names match `instructor` by fuzzy match. Uncertain matches go to review.
   - The section count of each department stays within ±30% of the same quarter last year. If not, send an alert.
3. Update `course_instructor` (this creates forum pages) and `offering_pattern`.
4. **Self-repair.** If the parse gives zero rows or the schema check fails, a repair agent gets the snapshot, the old parser and the error. It proposes new selectors. The new parser must give the same counts as the last good run on the stored snapshots. A curator approves the change.

### Predicting future offerings

For quarter q and course c, with k = the number of years among the last 3 in which c was offered in q:

```latex
p_{\text{offered}}(c,q) = \frac{k + 1}{3 + 2}
```

- A published plan of a department for next year sets p = 0.95.
- A posted schedule sets p = 1.
- The verifier gives a warning when a plan puts a course where p < 0.3.

## Requirements DSL

One small JSON format (written as YAML) expresses both course prerequisites and program requirements. It is narrow on purpose: small enough for an LLM to write it reliably, and exact enough for a solver to check it. Every node has a verbatim quote from its source.

### Prerequisite expressions

- **Atoms:** `{course: "CMSC 14200", min_grade: "C-"}`, `{concurrent: "MATH 20300"}` (co-requisite), `{placement: "MATH 15100"}`, `{standing: "third-year"}`, `{program: "cmsc-*"}` (enrolment restriction), `{consent: "instructor"}`.
- **Combinators:** `{all: [...]}`, `{any: [...]}`, `{n_of: 2, of: [...]}`.
- **Meaning:**
  - A `course` atom is met by a course that is completed, credited or planned in a strictly earlier term. It is also met in the same term when that term is a Summer quarter. (Summer sessions run in sequence, so HUMA 11500 and 11600 can share one summer. FEEDBACK 2026-11-16.)
  - `concurrent` is met by the same term or an earlier term.
  - `placement` and `standing` are met by plan facts.
  - `consent` never blocks, but always gives a warning.
- **Human form,** generated for display: "CMSC 14200 and (MATH 15900 or MATH 16300)".

### Program rule trees

| Node | Meaning | Main fields |
| --- | --- | --- |
| `group` | Children combined | `all: true` or `n_of: k`, `children` |
| `slot` | One specific course or alternatives | `any_of: [codes]` |
| `select` | Choose courses from a selector | `count` or `units`, `from` (selector) |
| `bounded_parts` | Parts with min/max counts that add up to a total | `total`, `parts[{count: [min, max]}]` |

- **Selectors:**
  - Explicit codes.
  - `subject` + `number_range` + `exclude`.
  - `tags` (e.g. `core:arts`).
  - `list` (a named course list, stored in a `course_list` table for each catalog year).
- **Node constraints:** `min_grade`, `no_pass_fail`, `same_sequence` (all from one Core sequence), `in_order`, `max_from: {selector, n}` ("at most 2 from outside CMSC"), `distinct_subjects: n`.
- **Program-level policy:**
  - `share` limits with other programs (`{with: "type:minor", max: 0}`, `{with: "core", max: 0, except: ["language"]}`).
  - `residency` (at least half in residence).
  - `timing` (`apply_by`, `complete_by`).
  - `requires` (a Bx/MS requires its major).
- **Provenance:** every node has `source: {snapshot_id, quote}`. The validator rejects a quote that is not verbatim in the source.

### Example: Core, Humanities/Civilization/Arts

The Core summary of the College says that students take one or two arts, two or three humanities and two or three civilization courses, six in total ([Core requirements](https://college.uchicago.edu/sites/default/files/documents/CoreRequirements.pdf)).

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

The intro sequence below agrees with the current catalog ([CS catalog page](http://collegecatalog.uchicago.edu/thecollege/computerscience/)). The elective node shows only the shape. It is not the real rule.

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

The key of the rules is the catalog year. A plan binds to specific `program_version` ids. Thus the publication of a new year never silently changes an old plan. A move of a plan to a newer catalog year is an explicit action. This action runs the verifier again and shows the diff.

## Verification engine (non-agentic)

The verifier is a pure function, `verify(plan, rules, catalog) → report + certificate`. It runs after every edit and on every agent output. A plan shows "Valid" only when a separate, small checker accepts its certificate. No LLM is used at any point.

### Inputs and outputs

- **Input:**
  - `PlanState` (items with term and status, credits, chosen programs and options, goals).
  - `RuleSet` (published program versions, College policy rules, requisites, offering patterns, attribute values).
  - `Options` (strictness).
- **Output:** `Report` = status (`valid`, `warnings`, `errors`) + a list of `Issue {code, level, message, course_ids, term_ids, node_id, fix_hints[]}` + a `Certificate` when there are no errors.

### Checks

| Code | Check | Level | Method |
| --- | --- | --- | --- |
| V01 | The course exists in the catalog year of the plan. Cross-listed codes become one course. | Error | Lookup |
| V02 | No duplicates (unless repeatable). No mutually exclusive pairs. Exam credit is forfeited when the student takes the equivalent course. | Error | Lookup |
| V03 | Prerequisites are met by earlier terms (or the same Summer quarter). Co-requisites are met by the same term or an earlier term. Consent gives a warning. | Error | Expression evaluation |
| V04 | The course is offered in that quarter. A posted schedule wins. If there is none, `p_offered` < 0.3 gives a warning. | Warning or error | Lookup |
| V05 | 300–400 units in Autumn, Winter, Spring. 500 only where an overload reason applies: joint-degree need in 3rd year, graduation need in 4th year, Reading and Research or BA thesis, a 200-unit language course. | Error, or "needs petition" warning | Arithmetic |
| V06 | No meeting-time clashes, for terms with posted sections. | Warning | Interval check |
| V07 | The rule tree of each program is satisfied. | Error, which lists exactly what is missing | CP-SAT assignment |
| V08 | Sharing limits between programs (minor vs major, minor vs Core, Bx/MS vs major). | Error | Inside the V07 model |
| V09 | Graduation: 4200 units, 3800 by enrollment (transfer credit counts toward it), at least 1800 units taken at the College, Core and Language Competence, half of each program in residence, quarters within the allotment. | Error | Arithmetic + V07 |
| V10 | Timing: Core finished by the end of 2nd year (civ abroad permitted in 3rd year). `apply_by` and `complete_by`. | Warning | Term comparison |
| V11 | Goals (see the table below): hard goals give an error. Soft goals give a warning with a score. | Error or warning | Predicate for each goal |
| V12 | Grading: no Pass/Fail where a node forbids it. | Error | Lookup |

Sources for the College-level numbers: [Enrollment Policies](https://college.uchicago.edu/advising/enrollment-policies), [Graduation Requirements](https://college.uchicago.edu/advising/graduation-requirements), [Core requirements](https://college.uchicago.edu/sites/default/files/documents/CoreRequirements.pdf).

### Program satisfaction as a constraint model (V07, V08)

Greedy matching fails when electives overlap and programs share courses. Thus the verifier asks OR-Tools CP-SAT for an assignment.

- **Variables:**
  - `x[c,n] ∈ {0,1}` = course c is used for node n. The model creates it only for eligible pairs.
  - `s[n] ∈ {0,1}` = node n is satisfied.
  - `y[c,P]` = course c is used anywhere in program P.
- **Within a program:** each course fills at most one node, unless the rule says something different.
- **Node semantics:**
  - `slot` → at least one of its courses.
  - `select` → at least k courses (or U units).
  - `group` → all children, or at least k.
  - `bounded_parts` → each part within \[min, max\], and the parts add up to the total.
  - `same_sequence` → one indicator for each sequence, with exactly one chosen.
- **Across programs:** for a share limit m between P and Q, `Σ_c z[c] ≤ m` with `z[c] ≥ y[c,P] + y[c,Q] − 1`.
- **Objective:**
  1. First, maximize the weighted count of satisfied nodes. (Thus an incomplete plan reports the smallest set of missing requirements.)
  2. Then, minimize the number of courses used.
- **Grades:** the verifier assumes that planned courses meet grade minimums. The report lists that assumption.

Typical instances (≤ 60 courses, ≤ 200 nodes, 3 programs) solve in tens of milliseconds.

### Certificates and the trusted checker

The solver is large and can have bugs. The checker is small and simple on purpose.

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

`check_certificate(plan, rules, certificate) → bool` runs in linear time, without a solver. It checks these conditions:

- Every assigned course is in the plan and matches the selector of its node.
- Node counts and bounds hold.
- Share limits hold.
- Every prerequisite witness is in an earlier term (or the same Summer quarter) and satisfies the expression.
- Loads and goals compute again to the same values.

It stays under approximately 300 lines, so that a person can review it line by line.

### Goal predicates

| Goal type | Parameters | Verified as | Used by the generator as |
| --- | --- | --- | --- |
| `course_load` | term or career, min/max courses | Count for each term | Hard bound |
| `workload_hours` | max hours/week for each term, or career average | Sum of `workload_hours` (upper confidence bound when strict) | Hard bound or penalty |
| `difficulty_cap` | max index, or max "very hard" courses for each term | Sum or count of `difficulty` | Hard bound or penalty |
| `challenge` | min difficulty index | Sum of `difficulty` | Reward |
| `protect_gpa` | none | No two high-`grading_strictness` courses in one term | Penalty |
| `graduate_by` | term | Last term ≤ target | Hard bound |
| `study_abroad` | program block, term | Block placed, and no on-campus courses in that term | Pinned block |
| `bxms` | program, `apply_by` term | Application prerequisites done before that term | Precedence constraint |
| `premed` | course list, `complete_by` | All listed courses done by then | Precedence constraint |
| `interest` | tags | Share of electives with the tags | Reward |
| `light_quarter` | term, max courses | Count | Hard bound |
| `language` | language, level, by term | Sequence complete | Precedence constraint |

### Performance

- Fast checks (V01–V06, V10–V12) take less than 20 ms. The solver adds 20–300 ms.
- The browser debounces edits by 300 ms. The cache key of reports is `plan_hash`.
- A solve of more than 2 s moves to a worker, and the badge shows "verifying".

### Testing

- Unit tests for each check, on tiny fixtures.
- Golden plans for each program: at least 5 must-pass and 5 must-fail plans, written by hand from the catalog text. Each must-fail plan names its expected issue codes.
- Property-based tests (Hypothesis):
  - Every solver certificate passes `check_certificate`.
  - A change to a valid plan (drop a course, move it earlier, add a sixth course) must give the expected issue.
- Coverage gate: `planner_core` at 95% or higher. Below that, CI fails.

## Agent harnesses

There are five online and offline agents. Each agent has one job, a fixed tool list, a budget and an output schema. No agent can write to the database, except to draft a change set or a review item.

### Model routing

Prices are list prices for each million input / output tokens, from the [models overview](https://platform.claude.com/docs/en/models/overview). The routing is in `llm_routing.yaml`. Thus you can change models without code changes.

| Agent / task | Model | Price (in / out) | Why |
| --- | --- | --- | --- |
| E3 program formalizer (offline, yearly) | `claude-opus-5-5`, effort high | $4 / $20 | The hardest reading task. Fable is overkill: deterministic code, golden plans and human review still check every rule (Richard, 2026-11-14). |
| E3b second opinion | `claude-sonnet-5-5`, effort high | $2 / $10 | A model that is different from E3, so that the two-run diff stays independent. |
| E2 program enumerator | `claude-opus-5-5` | $4 / $20 | Cross-checks of many pages. |
| E1 prerequisite sentence → DSL | `claude-haiku-5-5` | from $0.10 / $0.50 | High volume, short inputs. |
| E4 back-translation judge, scraper repair | `claude-sonnet-5-5` | $2 / $10 | Medium difficulty, fast. |
| A1 plan generator | `claude-sonnet-5-5` (thinking between tools) | $2 / $10 | Tool use and judgment on electives. Every plan is still verified and certified, so the cheaper model is sufficient (Richard, 2026-11-16, after the live test). |
| A2 advisor chat | `claude-sonnet-5-5` (escalate to Opus 5.5 for whole-plan comparisons) | $2 / $10 | Interactive latency. |
| A3 forum extraction / summaries | Haiku 5.5 / Sonnet 5.5 |  | Nightly batch. |
| A4 moderation | `claude-haiku-5-5` |  | Runs on every AI summary (not on the posts of students, P08-1). |

OpenRouter is a fallback. `llm_gateway` maps each model to its OpenRouter name. After two provider errors, it tries again on OpenRouter.

### Rules every harness follows

- **Loop:** Messages API with tools. The run ends when the agent calls its `submit_*` tool with a schema-valid payload, or when the budget is spent.
- **Budgets:** a maximum number of tool calls, tokens and wall-clock time for each run. If the run goes above any of them, the fallback of the run starts.
- **Validation:** Pydantic parses the outputs. One repair turn with the validation error is permitted. After that, the run fails.
- **Untrusted content:** forum posts and web pages go to the model inside `<untrusted_source id=…>` tags. The system prompt tells the model to use them only as data. An agent that reads untrusted content never has a write tool.
- **Citations are checked:** each id that an answer cites must come from a tool in that run. If not, the citation is dropped and the run is logged.
- **Prompt caching** for system prompts, the DSL schema and catalog excerpts.
- **Versioned prompts** in `prompts/*.md`. A new version must pass the eval set of that agent.

### A1. Plan generator (Generate-plan popup)

The LLM chooses *what is worth taking*. The solver decides *where it fits*. The verifier decides *whether it is valid*.

```text
Plan generator harness (see the diagram in the shared doc)

 Generate form -> 1 Load (code) -> 2 Compile goals (code) -> 3 Pick electives (LLM)
   [fail -> default preferences]                                    |
                                                                    v
 7 Proposal card  <- 6 Explain (LLM) <- 5 Verify (code) <- 4 Solve (CP-SAT, code)
 [nothing saved     [fail -> no         [fail -> alert,    [no plan -> plain-language
  before Apply]      rationale]          drop variant]      reason why]
```

Only steps 3 and 6 call a model. Each has a fallback. Thus a failed LLM call makes the result less good, but does not break it.

1. **Load (code).** The plan state, programs, goals, locked items, the eligible courses for each unmet requirement node, attributes and offering patterns. The plan can already hold something that the catalog does not know (a credit mapped to an unknown code, a completed course from a different catalog). In that case, the run stops with "Fix these first, then generate again: ...", which names it.
2. **Compile goals (code).** Each goal becomes solver bounds, rewards or penalties, as in the goal table above.
3. **Choose electives (LLM).** For each unmet `select` node (often 30–100 candidates), the agent uses `search_courses`, `get_course` and `get_forum_summary`. It ranks a maximum of 8 preferred courses, each with a one-line reason. Then it calls `submit_preferences`. Budget: 12 tool calls.
4. **Solve (code).** CP-SAT puts courses into terms. Constraints: prerequisite order, `p_offered` ≥ 0.3, loads, hard goals, program satisfaction (the V07 model), locked items. Objective: preference weights + goal rewards − penalties for workload spikes. Each extra variant must be different from the earlier ones in at least 4 placements.
5. **Verify (code).** The full verifier and the certificate check run on every variant. A failure here is a bug. It raises an alert, and the variant is dropped. If all variants are dropped, the student sees what the check found, never only "this is a bug".
6. **Explain (LLM).** The agent writes a rationale of 25 words or fewer for each quarter, and cites tool results. The server checks that the course set did not change. If it changed, the server discards the rationale and keeps the plan.
7. **Return** each variant as a proposed `change_set`, streamed over SSE.

**Fallbacks:**
- If step 3 fails: default preferences (interest-tag match, then forum `recommend_rate`).
- If step 6 fails: show the plan without a rationale.
- If the solver finds no plan, it tells why in plain terms ("Graduating by Spring 2029 needs 5 more courses than your remaining quarters allow").

**Cost and limits:**
- Approximately $0.25 for each generation at list prices (rough estimate: \~40k cached input and \~5k output tokens on Opus 5.5).
- Limit: 10 generations for each account for each day.
- Logged-out users get 3. The rate limit uses an IP counter in Redis that expires after 24 hours and is never written to disk.

### A2. Advisor chat

- **Scope gate:** a Haiku 5.5 pre-classifier gives each message a label: `in_scope`, `off_topic`, `confirmation` or `suspicious`. Off-topic messages get a fixed one-line refusal, without a call to the main model.
- **Read tools:** `get_plan`, `preview_ops` (runs the verifier on hypothetical edits and saves nothing), `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `compare_courses`.
- **Draft tool:** `propose_change_set(ops)` stores a `change_set` with status `proposed` and its verifier preview. The UI shows a proposal card.
- **No write tool.** The model never applies anything. A change is applied only in one of two cases:
  - (a) The student clicks **Apply** on a card.
  - (b) The student types an explicit command ("I agree to add MATH 20700 and CMSC 27100 to Autumn 2027"). A deterministic parser changes the text into operations. The server applies them only if two conditions are true:
    - They are equal to the operations of the latest proposal, or they are fully explicit.
    - The plan did not change since then (`base_plan_hash`).
- **Answers** use a schema `{text, citations[]}`. Citation chips link to attribute values or forum posts.
- **History** stays for each plan for 30 days.

### E1–E4. Ingestion agents

Data ingestion gives their steps. Harness details for the formalizer (E3):

- Tools: `read_snapshot(id, range)`, `lookup_course(code)`, `get_course_list(name)`, `validate_rules(yaml)` (returns deterministic errors, a maximum of 5 attempts), `run_golden(program)` and `submit_rules`.
- Every node must have a verbatim quote.
- The output always goes to the review queue, never directly to `published`.

### A3. Forum → attributes (nightly)

- **Extraction (Haiku 5.5):** from each new post, take the workload mentions, difficulty cues, exam style and prerequisite advice, each with a quote span. A number is accepted only if its quote contains that number.
- **Summary (Sonnet 5.5):**
  - "What students say", 120 words or fewer, with \[n\] citations to post ids.
  - Made again after 3 new posts or 30 days.
  - No statements about the personal life of an instructor.
  - Summaries must pass the moderation classifier.
- **Cold start:** before there is student data, Sonnet 5.5 estimates the workload and difficulty from the description and the course level, with a fixed rubric. The value has the label "estimate", and its weight is 2 ratings.
- The numeric update itself is deterministic (see Forum).

### A9. The AI's answer under a Commons question

The Commons bot (`api/agents/commons_bot.py`, task `a9_commons_bot`, prompt `prompts/a9_commons_bot.md`) writes the first answer under a forum question. It writes in Quarterly's own voice ("Quarterly", not a mascot, issue #20, D1 option A). Its read tools are the catalog, programs, other Commons questions and the campus guide. It never reads the login-only reviews, because the answer is public (OPEN_QUESTIONS CC-1).

- **A maximum of 60 words** (OPEN_QUESTIONS F20-1: Richard confirmed 60 on 2026-11-24. The team will test it in use, and look at it again if it is too short or too long.)
  - The prompt asks for this limit.
  - `submit_answer` rejects a longer answer one time, with the word count. Thus the model gets its one repair turn.
  - A second long answer ends the run. Then the deterministic search answers (also a maximum of 60 words).
  - When shown, the stored answer is clipped to 60 words. This also applies to answers stored before the limit. (`api/commons/words.py`: a word is a run of characters between spaces that holds a letter or digit.)
- The answer always shows that an AI wrote it ("Quarterly AI", an "AI" badge, "Written by an AI and can be wrong"), on the thread page and in the `/forum` list.

### A4. Moderation

Nothing checks the posts, comments and edits of students **before** publication (Richard, 2026-11-14, P08-1):

- A regex pass removes emails and phone numbers. Then the post shows immediately.
- Reports and the admin queue remove posts that break the guidelines.

Haiku 5.5 gives labels only to AI-written text. A "What students say" summary is published only when A4 says `ok`. The labels are `ok`, `personal_attack`, `identifying_info`, `harassment`, `sexual`, `misconduct_claim`, `spam`, `off_topic`.

### Evals

| Agent | Eval set | Pass bar |
| --- | --- | --- |
| A1 generator | 50 synthetic student profiles | 100% of variants verify. Hard goals met. Rationales cite only tool data. |
| A2 chat | 60 in-scope questions with reference answers, 20 off-topic, 10 confirmation phrases, 10 prompt injections hidden in forum fixtures | All off-topic refused. No injection followed. The parser is exact on confirmations. |
| E3 formalizer | 15 programs with hand-written gold rule trees | ≥ 95% node-level exact match before it runs unattended |
| A4 moderation | 200 labelled posts | ≥ 95% recall on `identifying_info` |

Evals run nightly in CI with a cost cap. Each new prompt version must pass them.

## Forum

The forum follows the idea of theCourseForum: one page for each course × instructor ([theCourseForum](https://thecourseforum.com/about/)). But it uses Reddit-style threads, votes and nested replies. Reviews have structured ratings, so that the text can update course attributes.

### Structure

- **Page** = one `course_instructor` pair. The app creates it automatically when the schedule pipeline first sees that instructor teach that course. The course page and the instructor page link to it.
- **Posts** have two kinds:
  - A **review** requires structured ratings and the term taken (one review for each account on each page, editable).
  - A **discussion** post is a question or topic ("Is the midterm curved?").
- **Comments** nest without a depth limit in storage. The UI collapses them below depth 6.
- **Votes:** up or down on posts and comments, one for each account on each item. The account can change it.
- **Course-level view:** the course page aggregates all its instructors. In v1, there is no separate course-only thread.

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

- **Best** (the default for comments): the lower bound of the Wilson score interval on the up-vote share. Thus a 9–1 item ranks above a 1–0 item.
- **Top:** net score.
- **New:** time.
- **Controversial:** many votes, near 50/50.
- **Hot** (the default for the discussion tab): net score, decayed by age, with a half-life of 30 days. The reason: course experiences age slowly.

```latex
\text{Best}(u, d) = \frac{\hat p + \frac{z^2}{2n} - z\sqrt{\frac{\hat p(1-\hat p)}{n} + \frac{z^2}{4n^2}}}{1 + \frac{z^2}{n}}, \quad n = u + d,\ \hat p = \frac{u}{n},\ z = 1.96
```

### Anonymity inside the forum

- Each account gets a random two-word **pseudonym for each page** ("Quiet Heron").
  - It is stable on that page, so conversations stay readable.
  - It is different on every other page, so readers cannot link posts across pages.
- The stored author references are `HMAC(server_key, account_id ‖ page_id)` (see Data model).
- Timestamps show as "Autumn 2026" or "3 weeks ago", never to the minute.
- There are no public profiles, follower counts or karma totals.

### Moderation and community rules

- Rules (shown in the composer):
  - Talk about the course and the teaching, not about the private life of anyone.
  - No names of other students.
  - No claims of misconduct (report those to the University).
  - No slurs or harassment.
- There is no automatic check before publication (P08-1). User reports and a human queue in the console remove posts.
- A suspension is always the choice of an admin (P08-3):
  - When the admin removes an item, the admin can suspend its author for 7, 30 or 90 days. The admin does not learn who the author is.
  - An admin can end a suspension early from the console.
- Bans apply to accounts.
  - Each verified email can hold one account. Thus a person cannot avoid a ban with a new sign-up at the same address.
  - An account cannot be deleted during a suspension, or within 30 days of an upheld removal (P08-12, P08-14).
- In v1, instructors do not get a reply channel. Discuss this again with the University.

### The forum page (`/forum`)

Issue #20 (Richard, 2026-11-24: D1 option A, D2 as suggested) puts course ratings and discussions on one page, in the manner of IMDb and Reddit.

- **One list, two tables (D2).**
  - Reviews (`post` + `review_rating`) and Commons discussions (`commons_thread` + `commons_reply`) keep their own tables.
  - `GET /forum/items` merges them, newest day first. On one day, discussions come before reviews, then the newest id.
  - The cursor is the sort key of the last item. Thus a page never repeats or skips an item.
  - Filters:
    - Item type (review, discussion).
    - Course (a review matches every code of its cross-listed course).
    - Instructor (only reviews, because a discussion has no instructor).
    - Subject, text.
    - The Commons tag and "my questions" (only discussions).
  - Reviews are for logged-in readers. A logged-out reader gets only the public discussions (`reviews_hidden`) and a login card.
- **The AI under each question (D1 option A).** Each discussion in the list shows the first answer of the AI under the question. It has a maximum of 60 words, with the label "Quarterly AI · AI · Written by an AI and can be wrong" (see A9 below).
- **Layout.**
  - The list fills the right two thirds.
  - The left third holds the statistics and rankings, then the notes about the forum.
  - On a phone, the statistics come above the list, and the notes come below it.
  - A "New post" button (a link to `/forum/new`) replaces the ask box. Thus students start discussions, not chatbot questions.
- **Statistics and rankings** (`GET /forum/stats?period=quarter|year`). Only for logged-in students, the same rule as the course pages.
  - Only structured ratings count: `review_rating.overall` of visible reviews posted in the period. The period is the last 91 days (`quarter`, shown as "Last 3 months") or the last 365 days (`year`, "Last 12 months"), counted back from today.
  - Statistics: the number of reviews and courses. From 3 reviews in the period: the average overall rating, the share who would recommend, and the average workload.
  - Rankings. Each line shows its score and review count:
    - The top 10 courses. A course pools every instructor and every cross-listed code. Its name is the code with the most reviews.
    - For each major, its 5 best-rated courses. A course is part of a major when it can fill one of the requirements of the major (the "counts toward" rule).
    - The Humanities sequences: the sublists of the Core list `core-huma-sequences`. Each sequence pools the reviews of its courses and their cross-listed codes.
    - The top 10 instructors (their courses pooled).

  Every score is the Bayesian average below, with prior weight k = 5. The prior mean m is the average overall rating of all reviews in the period. (There is one prior for all subjects, so that courses of different departments compare.) To be ranked, a subject needs at least 3 reviews in the period (the n ≥ 3 rule below).

### Forum → course attributes

Numeric attributes use a Bayesian average, so that a page with 2 reviews does not change wildly. For attribute a on subject s (a course or a course × instructor pair), with prior mean m (the department-level average, or the cold-start estimate) and prior weight k = 5 ratings:

```latex
\hat a_s = \frac{k\, m + \sum_{i=1}^{n} w_i\, r_i}{k + \sum_{i=1}^{n} w_i}
```

- Structured ratings have weight w = 1.
- Values extracted from text have w = 0.5.
- Ratings older than 4 years decay to w = 0.5.
- Forum-derived values show only when n ≥ 3. Below that, the course shows its estimate, with a label that says so.
- Course-level attributes pool all instructors.
- The planner uses the course × instructor value when it knows the scheduled instructor. If not, it uses the course value.

## Accounts and anonymity

*Decision 5, confirmed by Richard on 2026-11-12, replaces the earlier blind-signature design: accounts store the verified `@uchicago.edu` email and a password hash. In the forum, readers still see only per-page pseudonyms.*

A student proves one time that they own a `@uchicago.edu` address. Then the student creates an account with a username and password. The account stores the email, so that the student can reset a lost password. The email is never logged, never shown to other users, and never copied into forum, plan or analytics rows.

### Protocol

1. **Email.**
   - The browser sends the address.
   - The server checks the domain (`@uchicago.edu` only), changes it to lowercase, and checks that no account already uses it.
   - The server emails a 6-digit code. The code hash stays in Redis for 10 minutes. Its key is an opaque `pending_id`, which the server returns to the browser.
   - The address is scrubbed from logs.
2. **Code.** The browser sends `pending_id` and the code. It receives a one-time registration ticket (Redis, 10 minutes) bound to the email.
3. **Registration.**
   - The browser sends the ticket, a username and a password.
   - The server hashes the password with argon2id. It creates the account with the lowercase email and `email_verified_day`. It deletes the ticket and starts a session.
   - One account for each email.
4. **Login** is username (or email) and password.
   - Sessions are httpOnly, Secure, SameSite=Lax cookies, backed by Redis.
   - Requests that change state need a CSRF token.
   - Passkeys can be a stub in v1.
5. **Password reset.**
   - The student enters their email.
   - If an account exists, the server emails a 6-digit code (10-minute TTL, the same Redis pattern).
   - The code and a new password set a new argon2id hash and end the other sessions.
   - The response never tells whether an account exists.
6. **Rate limits** on every auth endpoint: for each email hash, and for each IP with a Redis-only 24-hour counter that is never written to disk.

### What is stored

| Data | Stored? | Linkable to a person? |
| --- | --- | --- |
| Email address | Yes, only in `account.email` | Yes, by anyone with database access |
| Username, password hash (argon2id), plans | Yes | Through the email |
| Forum posts, comments, votes | Yes, with `author_ref = HMAC(server_key, account_id ‖ page_id)` | Not from a leaked database alone. Yes for someone who holds the server key and the database. |
| IP addresses | Not by the app. Rate limits use a hashed, Redis-only counter that expires within 24 hours. No proxy log (Caddy, nginx) keeps IP addresses: there are no access logs, and the Caddy log removes the address fields. | Weakly, for 24 hours |
| Timestamps | Only day-level | Coarse |

### Threats and honest limits

- **Leaked database:** it shows which emails have accounts, and their plans. Posts on different pages still cannot be joined to one account without the server key.
- **Builder or admin with database access and the server key:** this person can link posts to an account, and thus to an email. Say this plainly on `/privacy`.
- **Sock puppets:** one account for each verified email.
- **Lost password:** reset by email (step 5).
- **Email provider:** it learns that Quarterly sent an email to an address. Use a transactional provider with content logging off, and a minimal message.

### Account deletion

`/account` offers export (plans as JSON) and deletion. Deletion removes the account, its email, plans and sessions. The student chooses whether to delete their posts or keep them as "\[deleted account\]".

## Risks, policy and legal

The two largest risks are a wrong rule that misleads a student, and a forum post that harms an instructor. Both get human review before they reach anyone. I am not a lawyer. Before launch, have a lawyer review the forum terms and the privacy page.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| A program rule is formalized incorrectly | A student plans the wrong courses | Two independent runs, verbatim quotes, golden plans, human review. "Not official advising — confirm with your adviser and My Planner" on every plan. A "Report an error" button on every requirement node. |
| Schedule scraping is not permitted | No section data | Ask the Registrar first. The fallback is department pages and offering history. The planner works at quarter level without sections. |
| The University objects to a review site | Pressure to shut down | Talk to the College and Student Government early. Never publish official evaluations again. Yale shut down Bluebook+ in 2014 because of how it presented ratings ([Chicago Maroon](https://chicagomaroon.com/49530/feature/new-website-cramwell-ai-helps-students-find-easy-courses-and-professors-for-upcoming-quarter/)). |
| Defamation or harassment of instructors | Legal and ethical harm | Rules in the composer, automatic and human moderation, misconduct claims held, a takedown contact. US law usually treats user posts differently from content that the platform writes itself, and **AI summaries are platform-written**. Keep them neutral, cited and moderated. |
| Claims of more anonymity than is true | Loss of trust | Precise words on `/privacy` (emails are stored, forum pseudonyms are per page). Open-source the auth code. |
| Sensitive self-reported data (grades) | Privacy harm | Grade buckets are optional. Nothing is imported from University systems. |
| Prompt injection through forum text | The agent does wrong actions | No agent that reads forum text can write. Citations are validated. |
| LLM cost spikes | Budget | Per-account limits, Haiku pre-classifier, prompt caching, a daily spend alarm in `llm_call`. |
| Empty forum at launch | Little value | Labelled estimates, a pre-launch review drive in pilot departments. The planner is useful without the forum. |
| Vote brigading | Skewed ratings | One account for each verified email, vote rate limits, burst detection for each page. |
| The catalog changes during the year | Stale rules | A monthly change check on catalog snapshots. |

## Build roadmap and Claude Code prompt sequence

The build is 13 prompts in four milestones. After prompt 1 fixes the contracts, prompts 2–5 and 7–8 can run in parallel in separate git worktrees. The starter kit that comes with this doc has the full prompt texts, a `CLAUDE.md` and the subagent definitions.

In Claude Code, the effort levels are `low`, `medium`, `high`, `xhigh` and `max`. Subagents can set `model`, `effort` and `isolation: worktree` in their frontmatter ([Claude Code subagents](https://code.claude.com/docs/en/sub-agents.md)). "Opus 5.5 extra" below means Opus 5.5 at `xhigh`.

| # | Prompt | Builds | Model / effort | Runs |
| --- | --- | --- | --- | --- |
| 0 | Bootstrap | Repo, Docker Compose, CI, `CLAUDE.md`, health checks | Opus 5.5 / high | Alone |
| 1 | Contracts | DB schema + migrations, DSL Pydantic models, OpenAPI skeleton, seed-file format | Opus 5.5 / xhigh | Alone |
| 2 | Verifier | `planner_core`: checks V01–V12, CP-SAT model, certificate checker, tests | Fable 5.2 (or Opus 5.5 / xhigh) | Parallel |
| 3 | Frontend shell | App shell, planner grid, requirement rail, issues panel against a mock API | Opus 5.5 / high | Parallel |
| 4 | Accounts | Email verification, registration, sessions, password reset (decision 5) | Fable 5.2 | Parallel |
| 5 | Seed data | Core, CS, Math, Economics for 2026–27 with quotes, golden plans | Opus 5.5 / high, you review | Parallel |
| 6 | Generator | CP-SAT plan generator, variants, change sets, API wiring | Opus 5.5 / xhigh | Alone |
| 7 | Agents | `llm_gateway`, A1 generator agent, A2 advisor chat, eval harness | Opus 5.5 / high | Parallel |
| 8 | Forum | Pages, posts, comments, votes, pseudonyms, moderation (A4) | Opus 5.5 / high | Parallel |
| 9 | Ingestion | Catalog crawler, E1–E4, review console | Opus 5.5 / high | Alone |
| 10 | Schedule | Class Search scraper behind a feature flag, offering patterns | Sonnet 5.5 | Alone |
| 11 | Attributes | Nightly forum → attribute job, summaries (A3) | Opus 5.5 / medium | Alone |
| 12 | Hardening | End-to-end tests, security and privacy review subagents, load test | Opus 5.5 / xhigh | Alone |

**Milestones.**
- M1 after prompts 0–5: a working planner with the verifier on seed data, and no AI.
- M2 after 6–7: generation and chat.
- M3 after 8 and 11: the forum for pilot departments.
- M4 after 9, 10 and 12: automated data and a pilot launch.

**Gates.** Every prompt ends with these steps:
1. Run its checks (tests, type-check, lint, golden plans).
2. Run a reviewer subagent that reads only the diff and this spec.

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

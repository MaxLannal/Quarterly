# "The Best of UChicago, within your reach": build plan (2026-11-20)

> **Later changes (2026-11-24).** This is the plan as built on 2026-11-20 (history). GitHub issue #15 then removed the Ask page (`/ask` opens the planner), the homepage's question bar, the floating companion with its digest, and the dashboard's routes (`/me/routes`, `POST /agents/routes`, the `pathway` table). Issue #19 then moved the Feed's course spotlights and student quotes into the Catalog page (`/courses`) and removed the Feed (`/feed` opens the Catalog), its book shelf and its AI notes. See `docs/SPEC.md` "Sitemap and every page" for the current pages.

The owner of this pass (Max) asked, in one message, for:

1. The new homepage (Rockefeller Chapel drawn with course titles, `quarterly-course-chapel.patch`),
   titled **"The Best of UChicago, within your reach."**; every course in it can be clicked into.
2. The homepage bar becomes an **agent harness**: students type a *question*, not a course search,
   and land on a UChicago chatbot page (`/ask`) connected to the existing API (catalog, programs,
   forum, the LLM gateway).
3. A **personal dashboard** (`/me`): class year, email, interests, research areas; an immersive
   interviewing agent that asks about interests (including the humanities: "just to pass, or to
   enjoy something specific, and what?"), career plans and future domains (e.g. quantum computing);
   everything compiled into an engaging page the student can always return to, where the agent
   "remembers" them.
4. **Routes**: the AI drafts several course routes / pathways / concentrations, stored at the bottom
   of the dashboard; the student can choose one, change it, or keep all open without committing.
5. An **AI companion** on every page, with access to the student's profile, giving advice and
   surfacing updates from new forum posts, comments and reviews.
6. A **feed** (`/feed`) about all kinds of courses: course spotlights with illustrations, related
   books, student comments; moving and floating words; categories the student picks; the AI
   personalises it.
7. A **forum panel** for discussion (`/forum`): anyone logged in asks a question about a course; a
   bot answers below; mature typing, commenting, voting, editing, mentions, drafts, live presence.
8. Titles and backgrounds of the new pages in the same aesthetic as the chapel: real course titles
   as texture, maroon / ink / paper, Newsreader display type. Creative, not boring.

## Ground rules kept from CLAUDE.md

- Model ids only in `llm_routing.yaml`; every new agent names a task there.
- Agents never write plans, programs or catalog rows. The interviewer *proposes* profile changes;
  the student keeps them (the browser calls `PATCH /me/profile`). Route drafts are saved only when
  the student keeps them. The Commons bot's answer is stored by the harness as clearly labelled AI
  content, like the forum's AI summaries.
- No invented catalog facts: every course code an agent returns is checked against the database
  and dropped if unknown. Course links come from the database. Books on the feed come from a
  hand-written shelf (`data/feed/books.yaml`) of real books, labelled "not a syllabus".
- Email stays in `account.email` only: the dashboard reads it from the account, it is never
  copied into `student_profile`.
- Day-level dates for users; no visitor request leaves the origin (illustrations are generated SVG,
  no remote images, no web fonts from CDNs).
- Every AI-written text is labelled ("Written by an AI and can be wrong").
- Tests use `FakeLLM`; every agent has a deterministic fallback so the feature works with no model.
- Accessible: real buttons and labels, 44px targets, visible focus, `prefers-reduced-motion` stops
  every animation (floating words, chapel, typescapes).

## Architecture

### Data (migration `0004_campus_companion`)

| Table | Purpose |
|---|---|
| `student_profile` | one row per account: class year, interests, research areas, humanities goal + topics + note, career plans + paths, future domains, constraints, workload preference, feed categories, portrait (headline, summary, themes), interview memory (topics covered, last turns), follows (threads, courses), updates cursor |
| `pathway` | AI-drafted or hand-made routes: title, tagline, summary, kind, program ids, courses by year/quarter with a role and note, milestones, fit scores, status `open` / `chosen` / `archived` (at most one `chosen` per account) |
| `commons_thread` | a question, optionally about one course; title, markdown body, tags, score, reply count, accepted reply, bot state |
| `commons_reply` | a reply or nested comment (`parent_id`, `depth`), human or bot, with citations for the bot |
| `commons_pseudonym` | per-thread random handle of an author (like the forum's per-page pseudonyms) |
| `commons_vote` | +1 / -1 on a thread or reply by a `voter_ref` |
| `commons_report` | reports, for the moderation queue |

Identity in the Commons: `commons_ref(account_id, thread_id)` (HMAC, like `author_ref`), so
readers cannot link one account's posts across threads.

### API (all new endpoints)

| Method | Path | What |
|---|---|---|
| POST | `/agents/ask` | SSE: the campus chatbot (Ask page and companion). Live `step` events per tool, then `answer` (text, citations, course links, follow-up questions), `done` |
| GET | `/me/updates` | what is new for this student: Commons threads and replies, forum posts and comments, on followed threads, followed courses and interests |
| POST | `/me/updates/seen` | move the student's updates cursor |
| GET / PATCH | `/me/profile` | the dashboard's profile (plus username, email and account day read from the account) |
| POST | `/agents/interview` | SSE: the interviewing guide; each turn has text, quick replies, the topic, a proposed profile patch, progress |
| GET / POST | `/me/routes` | the student's routes (list, keep a draft or make one by hand) |
| PATCH / DELETE | `/me/routes/{route_id}` | choose, keep open, archive, rename, note, delete |
| POST | `/agents/routes` | SSE: draft 3 routes from the profile (steps, `route` events, done) |
| GET | `/feed` | the feed: course spotlights, student comments, books, word clouds, programs, open questions; `tab`, `categories`, `cursor` |
| GET | `/feed/categories` | the feed's categories (subject families) |
| POST | `/agents/feed-notes` | AI "why this is in your feed" notes and a headline for the visible items (cached per account per day) |
| GET / POST | `/commons/threads` | list (sort hot/new/top/unanswered, course, subject, tag, q, cursor) and ask |
| GET / PATCH / DELETE | `/commons/threads/{thread_id}` | thread with its reply tree; edit; delete |
| POST | `/commons/threads/{thread_id}/replies` | answer or comment (nested via `parent_id`) |
| PATCH / DELETE | `/commons/replies/{reply_id}` | edit; delete |
| POST | `/commons/votes` | vote on a thread or reply |
| POST | `/commons/threads/{thread_id}/accept` | the asker accepts a reply |
| POST | `/commons/threads/{thread_id}/bot` | SSE: the bot writes (or rewrites) its answer |
| POST | `/commons/threads/{thread_id}/typing` | "I am typing" (Redis, 8 s) |
| GET | `/commons/threads/{thread_id}/presence` | how many others are typing, the newest reply id |
| POST | `/commons/threads/{thread_id}/follow` | follow / unfollow (stored in the profile) |
| POST | `/commons/reports` | report a thread or reply |

LLM tasks (in `llm_routing.yaml`): `a5_campus_ask`, `a6_interview`, `a7_routes`,
`a8_feed_notes`, `a9_commons_bot`, `a10_updates_digest`.

### Web

| Route | Page |
|---|---|
| `/` | Chapel hero; title "The Best of UChicago, *within your reach.*"; the **question bar** (agent harness: typed text shows "Ask Quarterly" plus live course matches; Enter asks; a course code jumps to its page) |
| `/ask` | full chatbot page: conversations kept in the browser, live tool trace, cited answers with course chips, follow-ups, stop / retry / copy / new chat; "gothic window" typescape behind the title |
| `/me` | dashboard: identity card (username, email, class year), portrait (interests constellation, research areas, humanities compass, career and future domains), the interviewing guide (immersive full-screen mode), what's new, and **Routes** at the bottom (choose / keep open / archive / open in planner) |
| `/feed` | personalised feed: For you / Explore / Following, category chips, course spotlights with generated illustrations and related books, comment cards, word-cloud cards, floating words in the background, a ticker of titles, AI curator notes |
| `/forum`, `/forum/new`, `/forum/t/:id` | the Commons: question list, ask form, thread page with bot answer, nested replies, votes, accept, edit, delete, report, follow, typing presence, live new-reply banner, markdown composer (toolbar, preview, course mentions, drafts, Ctrl/Cmd+Enter) |
| everywhere | the companion: a floating orb that opens a side panel (Chat with page context and profile; Updates from the forum) |

Nav: Ask · Feed · Plan · Catalog · Forum (the Forum item opens the Commons; course × instructor
reviews stay at `/instructors`, linked from the Commons header). The account avatar opens `/me`.

Shared look: `TypeScape` (canvas) fills a shape with rows of real course titles from
`/home/course-chapel.json`, maroon and ink on paper, with depth, slow drift and a pointer
magnifier; a title under the pointer shows its code and opens its course. Shapes: `arch` (Ask),
`orbit` (dashboard), `river` (feed), `arcade` (forum). `PageTitle`: an uppercase kicker, a
Newsreader headline with an italic maroon accent, and a subline.

## Work split

| Who | Owns |
|---|---|
| Lead | patch + homepage + question bar, nav, routes, migration/models, contracts, `TypeScape` / `PageTitle`, shared stream helper, integration, `make check`, browser QA, docs |
| Agent "ask" | `/agents/ask`, `/me/updates*`, Ask page, companion |
| Agent "me" | profile, interview agent, routes agent, dashboard page |
| Agent "feed" | feed backend (categories, items, books shelf, notes agent), feed page, illustrations, floating words |
| Agent "commons" | Commons backend (threads, replies, votes, pseudonyms, bot, presence, reports, account export/delete), Commons pages, composer |

Each agent owns its own files (listed in its brief), writes tests next to the existing ones, and
does not edit another agent's files. Shared files are prepared by the lead before the agents
start: `api/main.py` (routers registered), `api/db/models.py` (all tables),
`migrations/versions/0004_*`, `llm_routing.yaml` (tasks), `tests/test_api_surface.py` (endpoints),
`apps/web/src/routes.tsx`, `src/mocks/handlers.ts` (per-feature mock files).

## Definition of done

- `make check` passes (ruff, eslint, mypy, tsc, unit tests, golden plans, client up to date).
- Every page works on the running stack with the real AI and with the AI off (fallbacks).
- Browser QA at 1440 and 390 wide: no console errors, no sideways scroll, reduced motion respected.
- Docs: SPEC-CHANGES row, PROGRESS entry, OPEN_QUESTIONS for decisions the owner should confirm.

# "The Best of UChicago, within your reach": build plan (2026-11-20)

> **Later changes (2026-11-24).** This file is the plan as built on 2026-11-20 (history). After that date:
>
> - GitHub issue #15 removed these parts: the Ask page (`/ask` opens the planner), the question bar of the homepage, the floating companion with its digest, and the routes of the dashboard (`/me/routes`, `POST /agents/routes`, the `pathway` table).
> - Issue #19 moved the course spotlights and student quotes of the Feed into the Catalog page (`/courses`). It removed the Feed (`/feed` opens the Catalog), its book shelf and its AI notes.
>
> For the current pages, see `docs/SPEC.md` "Sitemap and every page".

The owner of this pass (Max) asked for these items in one message:

1. The new homepage: Rockefeller Chapel drawn with course titles (`quarterly-course-chapel.patch`).
   Its title is **"The Best of UChicago, within your reach."**. A click on each course in it opens that course.
2. The homepage bar becomes an **agent harness**. Students type a *question*, not a course search.
   Then they go to a UChicago chatbot page (`/ask`). This page connects to the existing API
   (catalog, programs, forum, the LLM gateway).
3. A **personal dashboard** (`/me`):
   - Class year, email, interests, research areas.
   - An immersive interviewing agent. The agent asks about interests, career plans and future
     domains (for example, quantum computing). For the humanities, it asks: "just to pass, or to
     enjoy something specific, and what?".
   - The page compiles all of this into an engaging page. The student can always come back to this
     page, and there the agent "remembers" them.
4. **Routes**: The AI drafts several course routes / pathways / concentrations. The dashboard keeps
   them at the bottom. The student can choose one, change it, or keep all open without a commitment.
5. An **AI companion** on every page. It can read the profile of the student. It gives advice and
   shows updates from new forum posts, comments and reviews.
6. A **feed** (`/feed`) about all kinds of courses:
   - Course spotlights with illustrations, related books and student comments.
   - Moving and floating words.
   - Categories that the student selects.
   - The AI personalises the feed.
7. A **forum panel** for discussion (`/forum`):
   - Each logged-in person can ask a question about a course.
   - A bot answers below the question.
   - Mature typing, comments, votes, edits, mentions, drafts and live presence.
8. The titles and backgrounds of the new pages use the same aesthetic as the chapel: real course
   titles as texture, maroon / ink / paper, Newsreader display type. Creative, not boring.

## Ground rules kept from CLAUDE.md

- Model ids are only in `llm_routing.yaml`. Each new agent names a task there.
- Agents never write plans, programs or catalog rows.
  - The interviewer *proposes* profile changes. The student keeps them (the browser calls `PATCH /me/profile`).
  - The harness saves route drafts only when the student keeps them.
  - The harness stores the answer of the Commons bot as AI content with a clear label, the same as the AI summaries of the forum.
- No invented catalog facts:
  - The harness checks every course code that an agent returns against the database. It drops each unknown code.
  - Course links come from the database.
  - Books on the feed come from a hand-written shelf of real books (`data/feed/books.yaml`), with the label "not a syllabus".
- The email stays only in `account.email`. The dashboard reads it from the account. The code never copies it into `student_profile`.
- Dates for users are day-level only.
- No visitor request leaves the origin. Illustrations are generated SVG. There are no remote images and no web fonts from CDNs.
- Every text that an AI writes has a label ("Written by an AI and can be wrong").
- Tests use `FakeLLM`. Each agent has a deterministic fallback, so the feature works with no model.
- Accessible: real buttons and labels, 44px targets, visible focus. `prefers-reduced-motion` stops
  every animation (floating words, chapel, typescapes).

## Architecture

### Data (migration `0004_campus_companion`)

| Table | Purpose |
|---|---|
| `student_profile` | One row for each account: class year, interests, research areas, humanities goal + topics + note, career plans + paths, future domains, constraints, workload preference, feed categories, portrait (headline, summary, themes), interview memory (topics covered, last turns), follows (threads, courses), updates cursor. |
| `pathway` | Routes that the AI drafts or that the student makes by hand: title, tagline, summary, kind, program ids, courses by year/quarter with a role and note, milestones, fit scores, status `open` / `chosen` / `archived` (a maximum of one `chosen` for each account). |
| `commons_thread` | A question, optionally about one course: title, markdown body, tags, score, reply count, accepted reply, bot state. |
| `commons_reply` | A reply or nested comment (`parent_id`, `depth`), from a human or from the bot, with citations for the bot. |
| `commons_pseudonym` | The random handle of an author in one thread (the same as the per-page pseudonyms of the forum). |
| `commons_vote` | +1 / -1 on a thread or reply by a `voter_ref`. |
| `commons_report` | Reports, for the moderation queue. |

Identity in the Commons: `commons_ref(account_id, thread_id)` (HMAC, the same as `author_ref`).
Thus readers cannot link the posts of one account across threads.

### API (all new endpoints)

| Method | Path | What |
|---|---|---|
| POST | `/agents/ask` | SSE: the campus chatbot (Ask page and companion). Live `step` events for each tool, then `answer` (text, citations, course links, follow-up questions), then `done`. |
| GET | `/me/updates` | What is new for this student: Commons threads and replies, and forum posts and comments, on followed threads, followed courses and interests. |
| POST | `/me/updates/seen` | Move the updates cursor of the student. |
| GET / PATCH | `/me/profile` | The profile of the dashboard (and the username, email and account day, which it reads from the account). |
| POST | `/agents/interview` | SSE: the interviewing guide. Each turn has text, quick replies, the topic, a proposed profile patch and progress. |
| GET / POST | `/me/routes` | The routes of the student (list, keep a draft, or make one by hand). |
| PATCH / DELETE | `/me/routes/{route_id}` | Choose, keep open, archive, rename, note, delete. |
| POST | `/agents/routes` | SSE: draft 3 routes from the profile (steps, `route` events, done). |
| GET | `/feed` | The feed: course spotlights, student comments, books, word clouds, programs, open questions. Parameters: `tab`, `categories`, `cursor`. |
| GET | `/feed/categories` | The categories of the feed (subject families). |
| POST | `/agents/feed-notes` | AI "why this is in your feed" notes and a headline for the visible items (cache: one for each account for each day). |
| GET / POST | `/commons/threads` | List (sort hot/new/top/unanswered, course, subject, tag, q, cursor) and ask. |
| GET / PATCH / DELETE | `/commons/threads/{thread_id}` | Thread with its reply tree. Edit. Delete. |
| POST | `/commons/threads/{thread_id}/replies` | Answer or comment (nested through `parent_id`). |
| PATCH / DELETE | `/commons/replies/{reply_id}` | Edit. Delete. |
| POST | `/commons/votes` | Vote on a thread or reply. |
| POST | `/commons/threads/{thread_id}/accept` | The asker accepts a reply. |
| POST | `/commons/threads/{thread_id}/bot` | SSE: the bot writes (or writes again) its answer. |
| POST | `/commons/threads/{thread_id}/typing` | "I am typing" (Redis, 8 s). |
| GET | `/commons/threads/{thread_id}/presence` | The number of other people who are typing, and the newest reply id. |
| POST | `/commons/threads/{thread_id}/follow` | Follow / unfollow (the profile stores it). |
| POST | `/commons/reports` | Report a thread or reply. |

LLM tasks (in `llm_routing.yaml`): `a5_campus_ask`, `a6_interview`, `a7_routes`,
`a8_feed_notes`, `a9_commons_bot`, `a10_updates_digest`.

### Web

| Route | Page |
|---|---|
| `/` | Chapel hero. Title "The Best of UChicago, *within your reach.*". The **question bar** is an agent harness: typed text shows "Ask Quarterly" and live course matches. Enter asks. A course code opens its page. |
| `/ask` | Full chatbot page: conversations kept in the browser, live tool trace, cited answers with course chips, follow-ups, stop / retry / copy / new chat. A "gothic window" typescape is behind the title. |
| `/me` | Dashboard: identity card (username, email, class year), portrait (interests constellation, research areas, humanities compass, career and future domains), the interviewing guide (immersive full-screen mode), what's new, and **Routes** at the bottom (choose / keep open / archive / open in planner). |
| `/feed` | Personalised feed: For you / Explore / Following, category chips, course spotlights with generated illustrations and related books, comment cards, word-cloud cards, floating words in the background, a ticker of titles, AI curator notes. |
| `/forum`, `/forum/new`, `/forum/t/:id` | The Commons: question list, ask form, thread page with bot answer, nested replies, votes, accept, edit, delete, report, follow, typing presence, live new-reply banner, markdown composer (toolbar, preview, course mentions, drafts, Ctrl/Cmd+Enter). |
| everywhere | The companion: a floating orb that opens a side panel. The panel has Chat (with page context and profile) and Updates (from the forum). |

Nav: Ask · Feed · Plan · Catalog · Forum. The Forum item opens the Commons. Course × instructor
reviews stay at `/instructors`, with a link from the Commons header. The account avatar opens `/me`.

Shared look:

- `TypeScape` (canvas) fills a shape with rows of real course titles from
  `/home/course-chapel.json`. It uses maroon and ink on paper, with depth, slow drift and a pointer
  magnifier. A title under the pointer shows its code. A click on the title opens its course.
- Shapes: `arch` (Ask), `orbit` (dashboard), `river` (feed), `arcade` (forum).
- `PageTitle`: an uppercase kicker, a Newsreader headline with an italic maroon accent, and a subline.

## Work split

| Who | Owns |
|---|---|
| Lead | patch + homepage + question bar, nav, routes, migration/models, contracts, `TypeScape` / `PageTitle`, shared stream helper, integration, `make check`, browser QA, docs |
| Agent "ask" | `/agents/ask`, `/me/updates*`, Ask page, companion |
| Agent "me" | profile, interview agent, routes agent, dashboard page |
| Agent "feed" | feed backend (categories, items, books shelf, notes agent), feed page, illustrations, floating words |
| Agent "commons" | Commons backend (threads, replies, votes, pseudonyms, bot, presence, reports, account export/delete), Commons pages, composer |

Rules for each agent:

- The agent owns its own files (its brief lists them).
- The agent writes tests next to the existing tests.
- The agent does not edit the files of a different agent.

The lead prepares the shared files before the agents start:

- `api/main.py` (routers registered)
- `api/db/models.py` (all tables)
- `migrations/versions/0004_*`
- `llm_routing.yaml` (tasks)
- `tests/test_api_surface.py` (endpoints)
- `apps/web/src/routes.tsx`
- `src/mocks/handlers.ts` (mock files for each feature)

## Definition of done

- `make check` passes (ruff, eslint, mypy, tsc, unit tests, golden plans, client up to date).
- Every page works on the running stack with the real AI, and with the AI off (fallbacks).
- Browser QA at 1440 and 390 wide: no console errors, no sideways scroll, reduced motion respected.
- Docs: a SPEC-CHANGES row, a PROGRESS entry, and OPEN_QUESTIONS items for decisions that the owner should confirm.

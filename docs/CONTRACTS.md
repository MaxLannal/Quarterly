# Contracts (prompt 01)

These contracts are frozen, so that prompts 02-05 can run in parallel. To change a contract, do these steps:

1. Change the contract one time.
2. Generate the client again (`make api-client`).
3. Tell every parallel worker.

Sources of truth:

- **planner_core models**: `packages/planner_core/planner_core/models.py` (JSON Schemas in `docs/schemas/`).
- **Database**: `services/api/api/db/models.py` + `services/api/api/migrations/versions/0001_initial_schema.py`. A test fails if they drift apart.
- **API**: the FastAPI routers in `services/api/api/routers/`. The OpenAPI is in `apps/web/src/api/openapi.json`. The TypeScript types are in `apps/web/src/api/schema.d.ts` (`make api-client`). If the types are stale, `make check` fails.
- **Seed and golden files**: `services/api/api/seed/models.py`.

## Endpoints

All stubs return `501 {"detail": "Not implemented yet (prompt NN)"}` after request validation. Thus a malformed body still gets a 422. "Builds in" is the prompt that is expected to implement the endpoint.

| Method | Path | Request | Response | Login | Builds in |
| --- | --- | --- | --- | --- | --- |
| GET | `/health`, `/version` | | `HealthOut`, `VersionOut` | No | 00 (done) |
| GET | `/catalog-years` | | `CatalogYearOut[]` | No | M1 integration |
| GET | `/terms?catalog_year` | | `Term[]` | No | M1 integration |
| GET | `/courses?q&subject&level&quarter&core_tag&max_workload_hours&max_difficulty&catalog_year&limit&offset` | | `Page[CourseSummary]` | No | M1 integration |
| GET | `/courses/{code}?catalog_year` | | `CourseDetail` | No | M1 integration |
| GET | `/course-lists/{name}?catalog_year` | | `CourseList` | No | M1 integration |
| GET | `/programs?catalog_year&type` | | `ProgramSummary[]` | No | M1 integration |
| GET | `/programs/{program_id}?catalog_year` | | `ProgramDetail` (rule tree, policy, sources) | No | M1 integration |
| GET | `/programs/{program_id}/eligible?node` | | `CourseSummary[]` | No | M1 integration |
| GET | `/instructors?q`, `/instructors/{slug}` | | `Page[InstructorSummary]`, `InstructorDetail` (per-course `ratings` only when logged in) | No (P03-12: names public) | 08 (done) |
| GET / POST | `/plans` | `PlanCreate` | `PlanSummary[]` / `PlanOut` | Yes | 04/06 |
| POST | `/plans/import` | `PlanImport` (logged-out plans) | `PlanSummary[]` | Yes | 04/06 |
| GET | `/plans/compare?a&b` | | `PlanComparison` | Yes | 06 |
| GET / PATCH / DELETE | `/plans/{plan_id}` | `PlanUpdate` | `PlanOut` / 204 | Yes | 04/06 |
| POST | `/plans/{plan_id}/duplicate` | | `PlanOut` | Yes | 04/06 |
| PATCH | `/plans/{plan_id}/items` | `ItemsPatch {base_plan_hash, ops[]}` | `PlanOut` | Yes | 04/06 |
| GET | `/plans/{plan_id}/changesets` | | `ChangeSet[]` | Yes | 06 |
| POST | `/plans/{plan_id}/changesets/{changeset_id}/apply` | `ChangeSetApply` (`terms` = apply selected quarters) | `PlanOut` | Yes | 06 |
| POST | `/plans/{plan_id}/changesets/{changeset_id}/discard` | | `ChangeSet` | Yes | 06 |
| POST | `/plans/generate?mode=deterministic` | `GenerateLocal {plan, options: GenerateOptions}` | `GenerateOut` (change sets without ids, nothing saved) | No (rate-limited) | 06 |
| POST | `/plans/{plan_id}/generate?mode=deterministic` | `GenerateOptions` | `GenerateOut` (each variant stored as a proposed change set) | Yes | 06 |
| POST | `/verify` | `VerifyRequest {plan: PlanState, options}` | `Report` | No | 02 |
| POST | `/agents/planner` | `PlannerRequest` | SSE stream of `PlannerEvent` (replaces `/agents/generate` and `/agents/chat`) | No (rate-limited) | Issue #17 |
| GET | `/agents/planner/history?plan_id` | | `ChatHistory` (kept while the plan exists) | Yes | Issue #17 |
| DELETE | `/agents/planner/history?plan_id` | | 204 (Clear chat) | Yes | Issue #18 |
| GET | `/me/profile/proposals` | | `list[ProfileProposalOut]` (answers from the planner chat, status `proposed`) | Yes | Issue #17 |
| POST | `/me/profile/proposals` | `ProfileProposalCreate` (`{field, value}`, a field of the question file) | `ProfileProposalOut` (the import on login) | Yes | Issue #17 |
| POST | `/me/profile/proposals/{id}/accept` | | `ProfileOut` | Yes | Issue #17 |
| POST | `/me/profile/proposals/{id}/reject` | | 204 | Yes | Issue #17 |
| GET | `/forum/pages?course&instructor`, `/forum/pages/{page_id}` | | `ForumPageOut` | Yes | 08 |
| GET / POST | `/forum/pages/{page_id}/posts?kind&sort&term` | `PostCreate` | `Page[PostOut]` / `PostOut` | Yes | 08 |
| GET / PATCH / DELETE | `/forum/posts/{post_id}` | `PostUpdate` | `PostDetail` / `PostOut` / 204 | Yes | 08 |
| POST | `/forum/posts/{post_id}/comments` | `CommentCreate` | `CommentOut` | Yes | 08 |
| POST | `/forum/votes` | `VoteIn` | `VoteOut` | Yes | 08 |
| POST | `/forum/reports` | `ForumReportIn` | `ForumReportOut` (202) | Yes | 08 |
| GET | `/forum/courses/{code}` | | `CourseForumOut` (the page of every instructor, with pooled ratings) | Yes | 08 (added) |
| GET | `/forum/items?type&course&instructor&subject&tag&q&mine&cursor&limit` | | `ForumItemList` (reviews and Commons discussions, newest first) | No (reviews only with a login) | issue #20 |
| GET | `/forum/stats?period=quarter\|year` | | `ForumStats` (Bayesian rankings, k = 5, n ≥ 3) | Yes | issue #20 |
| GET | `/admin/moderation` | | `Page[ModerationItemOut]` | Admin | 08 (added) |
| POST | `/admin/moderation/{target_type}/{target_id}/decision` | `ModerationDecision` | `ModerationResult` | Admin | 08 (added) |
| POST | `/auth/email` | `EmailStart` | `EmailStarted {pending_id}` (202) | No | 04 |
| POST | `/auth/verify-code` | `VerifyCode` | `RegistrationTicket` | No | 04 |
| POST | `/auth/register` | `Register {ticket, username, password}` | `SessionOut` | No | 04 |
| POST | `/auth/login`, `/auth/logout`. GET `/auth/session` | `Login` | `SessionOut` / 204 | - | 04 |
| POST | `/auth/password-reset/start`, `/auth/password-reset/finish` | `PasswordResetStart`, `PasswordResetFinish` | 202 / 204 | No | 04 |
| GET | `/account/export` | | `AccountExport` | Yes | 04 |
| POST | `/account/password`, `/account/delete` | `PasswordChange`, `AccountDelete` | 204 | Yes | 04 |
| GET | `/admin/review-items?status` | | `Page[ReviewItemOut]` | Admin | 09 |
| POST | `/admin/review-items/{item_id}/decision` | `ReviewDecision` | `ReviewItemOut` | Admin | 09 |
| POST | `/admin/program-versions/{version_id}/publish` | | `ProgramVersionOut` | Admin | 09 |
| GET | `/profile/questions` | | `QuestionSet` (the General Information questions, `data/profile/questions.yaml`) | No | Issue #14 |
| GET / PATCH | `/me/profile` | `ProfilePatch` (partial. `credits` and `taken_courses` replace the full list. 422 for unknown programs or courses.) | `ProfileOut` (the student record: General Information answers, `answered`, `completeness`) | Yes | Issue #14 |
| GET | `/me/profile/export.md` | | `student.md` (`text/markdown` download, with the working information, never the email or username) | Yes | Issue #14 |
| POST | `/agents/interview` | `InterviewRequest` | SSE stream of `InterviewEvent` (turn: `topic` = a step-2 question id or `wrapup`, `quick_replies` = its option labels + "Skip", `answered` + `proposed` = the mapped answer to accept, `retry`) | Yes | Issue #16 |

The frontend calls these endpoints under `/api/...`. The Vite dev proxy and nginx remove the prefix.

## Decisions that are not obvious

**Canonical DSL form with YAML shorthands.**
- Authors write the YAML of the spec: `{course: X}`, `{all: [...]}`, `{n_of: 2, of: [...]}`, a bare `"CMSC 14100"`, `{id: intro, group: {...}}`.
- The models normalise the YAML to one canonical JSON (`Expr {op, n, children, atom}`, and nodes with a `kind` discriminator). Thus `model_validate(model_dump())` is stable, and the hashes are reproducible.
- Unknown keys are errors (`extra="forbid"`). This catches typos in hand-written YAML.
- Keys that are Python keywords keep the spelling of the spec on the wire: `from`, `with`, `except`, `list`, `pass`.

**Node ids and paths.**
- The `id` of a node is optional. A missing id becomes the 1-based position among the siblings.
- The path of a node is the program id plus the child ids (`cmsc-bs/intro/1`, the same as the certificate example of the spec). The path of the root is the program id.
- The address of a part of a `bounded_parts` node is `<node path>/<part id>`.
- `plan_item.slot_ref`, `Issue.node_id`, `Assignment.node` and `NodeProgress.node_id` all use these paths.
- Helpers: `planner_core.dsl.iter_nodes / iter_parts / node_paths`.

**Selector semantics.**
- A course matches when it is not excluded and every criterion that is set holds:
  - `codes` (any).
  - `subject`.
  - `number_range` (inclusive, 5-digit number).
  - `tags` (any).
  - `list` (named list, sublists included).
  - `union` (any sub-selector).
- The tag set of a course is its `tags` plus `core:<t>` for each of its `core_tags`. Thus `tags: [core:arts]` matches a course with `core_tags: [arts]`.
- Matching and exclusion work on cross-list groups. Thus a cross-listed code matches wherever its partner matches.
- Union is the only way to say "A or B" across criteria.
- One exception, opt-in: a `max_from` limit with `as_enrolled: true` counts a course only when the code written in the plan itself meets the `subject`, `number_range` and `tags` of the selector. (`codes`, `list` and `exclude` still work on the group.) Thus "at most two from the 20000 level" does not count a cross-listed course that the student took under its 30000-level number.

**Sequences.**
- `same_sequence` must know which courses make a sequence.
- `course_list` gets `sublists`. A list such as `core-huma-sequences` has one sublist for each sequence.
- `same_sequence` means that every course that the node uses comes from one sublist.
- The DB column is `course_list.sublists text[]`, next to `course_ids bigint[]`.

**RuleSet vs Catalog.**
- `verify(plan, rules, catalog, options)` takes the *rules* (program versions, College policy, requisites) separately from the *catalog facts* (courses, cross-lists, relations, course lists, terms, offering patterns, sections, attribute values).
- The reason: rules have versions and go into the hashes of certificates. Catalog facts are lookup tables.
- `check_certificate(plan, rules, catalog, certificate)` also takes the catalog. To match a course to a selector, it needs the subject, number, tags and list membership.

**College policy as data.**
- `CollegePolicy` holds the College-wide numbers: 4200/3800 units, 300-400 full-time, 500 overload and its reasons, Core timing, residency.
- Each non-null value must have a source in `sources[field]`.
- A null value means "not encoded yet". The check reports it as an assumption, and does not guess.
- An added `college_policy` table stores the policy (one row for each catalog year).
- Overload reasons can state the plan year, a qualifying course selector or a minimum course size. Thus V05 can check them.

**Goals are a discriminated union** on `type` (all 12 goal types in the table of the spec). Each type has typed parameters.
- The DB keeps `type` + `params` JSONB.
- Term-scoped goals must set `term`. Career goals must not set it.
- Goal deadlines accept relative terms (`Y3-WI`) or absolute terms. `planner_core.terms.resolve_term_ref` converts them.

**Report extras.**
- In addition to the status, issues and certificate of the spec, `Report` has these fields:
  - `progress`: have/need for each node, for the requirement rail of the planner.
  - `assumptions`: for example, planned courses that the verifier assumes meet grade minimums.
  - `plan_hash` / `core_version`: the cache key.
- `VerifyOptions.checks` limits which V-codes run. Golden plans that test one program in isolation use it to skip loads (V05) and graduation totals (V09).

**Hashes.**
- `plan_hash` is the SHA-256 of the canonical JSON of a `PlanState`, with the item ids removed and the lists sorted. Thus a new order or new numbers for the items do not change it.
- `rules_hash` is the hash of a `ProgramRules`.
- Certificate keys are `<program id>@<catalog year>`.

**Change sets.**
- The ops are `add`, `move`, `remove`, `lock` and `unlock`.
- An op targets an existing item by exactly one of `item_id`, `course` or `slot_ref`, plus a term to tell repeated courses apart.
- `planner_core.changes.apply_ops` is the only implementation. A locked item cannot move and cannot be removed. An ambiguous or missing target raises `ChangeOpError`.
- The server applies a change set only if the hash of the plan is still `base_plan_hash`.

**Seed format.**
- `data/seed/<catalog_year>/` holds these files:
  - `terms.yaml`.
  - `courses.yaml` and/or `courses/*.yaml` (`SeedCourse`: the CourseLeaf block fields, plus `prereq` in the DSL, `prereq_text` verbatim, `crosslists`/`equivalents`/`mutually_exclusive`/`replaces`, `terms_offered`, and a required `source`).
  - `course_lists.yaml`.
  - `college_policy.yaml`.
  - `programs/*.yaml` (`ProgramSeed` = `ProgramRules` + name, type, degree, department, status, sources).
- `make seed` validates everything, then upserts idempotently. The validation rules:
  - Every program node and part needs a `source`.
  - Every referenced course and list must exist. Unknown courses in prerequisites are warnings.
  - Every program-level share limit and every `max_from` cap (on nodes and parts) also needs its own `source`.
  - A non-empty `policy.requires` / `policy.excludes` needs `requires_source` / `excludes_source`.
- The fake fixture is in `services/api/tests/fixtures/seed/2099-00/`.

**Offerings from "Terms Offered".**
- Until schedule data exists, the catalog "Terms Offered" line of a course becomes `offering_pattern` rows with `method: catalog`.
- p = 0.95 for listed quarters (the same as a published plan of a department). p = 0.05 for unlisted Autumn/Winter/Spring.
- Courses without the line get no pattern (no V04 warning).
- This mapping is an open question.

**Golden plans.** `data/golden/<program>/*.yaml` (`GoldenPlan`):
- `expect: pass` means no error-level issues, and a certificate that `check_certificate` accepts.
- `expect: fail` lists `expected_codes`. Each code must appear.
- The runner gives the verifier the College policy and the programs that the plan lists (the Core only if listed).
- While `verify` is a stub, the runner reports the plans as SKIP.

**Accounts (decision 5).**
- `account.email` (unique, lowercase) is the only column that holds an email. A migration test enforces this.
- There are no blind-signature tables.
- User rows use only day-level dates (`*_day`). A test also enforces this.

**Program versions.**
- There is one `program_version` for each program for each catalog year (unique).
- Only `published` versions reach students.
- The seed loader writes the status from the YAML (default `review`).

## Forum (prompt 08)

Code: `services/api/api/forum/`. Tests: `services/api/tests/test_forum_api.py`, `test_forum_privacy.py`.

- **Pages.**
  - A forum page is a `course_instructor` row (`page_id`).
  - `api.forum.pages.ensure_page(db, course_id, instructor_id, term_id)` creates the page when it first sees the pair, and makes its term range wider. The schedule pipeline (prompt 10) must call it.
  - There is one page for each course *code* and instructor. A course row of a different catalog year uses the existing page again.
  - `GET /courses/{code}` now lists `instructors` (public names, P03-12).
- **Identity.**
  - `author_ref`, `voter_ref` and `reporter_ref` are all `api.auth.hashing.author_ref(account_id, page_id)`.
  - No forum row holds an account id.
  - Pseudonyms are random two-word handles, one for each (ref, page), unique on the page.
- **Visibility.**
  - Readers see `visible` items.
  - Authors also see their own `held` / `removed` items, with `mine: true` and a `moderation_note`.
  - The hidden items of other people answer 404 (reads, votes, comments, reports).
  - A hidden comment with visible replies stays in the thread as a `[removed]` / `[awaiting moderation]` placeholder, with the pseudonym `[hidden]`.
- **Contract additions (all additive).**
  - `PostOut` / `CommentOut`: `body_html` (rendered on the server and sanitized, the only HTML that the client inserts), `mine`, `moderation_note`.
  - `PostOut.edited_day`.
  - `PostUpdate.term_taken`.
  - `ForumPageOut.ratings` (`RatingSummary`).
  - `InstructorCourse.ratings`.
  - The three endpoints above.
- **Comments** come back depth-first, with siblings in Best order. `depth` = `nlevel(path) - 1` (top level 0). Paths are ltree labels of comment ids.
- **Sorting** (SQL, `api/forum/sorting.py`):
  - Best = Wilson lower bound (z = 1.96).
  - Top = net score.
  - New = day, then id.
  - Controversial = (u + d) ^ (min/max) when both are positive.
  - Hot = score * 0.5 ^ (age_days / 30).
  - Ties: the newer id first.
- **Moderation.**
  - Posts, comments and edits are published immediately after the scrub (emails, phone numbers). Nothing checks them first (Richard, 2026-11-14, P08-1).
  - Reports and the admin queue remove posts that break the guidelines.
  - A4 (`a4_moderation`, `prompts/a4_moderation.md`, text inside `<untrusted_source>`, 3 s wall clock) now labels only the AI-written "What students say" summaries. A summary is published only on `ok`.
  - Items that an earlier version held or rejected keep their status and author note.
- **Queue and suspension.** Only admins.
  - The queue lists items with an open report (and each held item from before).
  - `approve` keeps the item and dismisses the open reports. `remove` takes the item away and upholds the reports.
  - Suspensions are only manual (P08-3). `remove` with `suspend_days` (1-365) sets `account.suspended_until` of the author to today + that number of days. It never makes an existing suspension shorter.
  - `approve` with `suspend_days` is a 422.
  - To find the author, the code computes `author_ref` again for every account, only when the admin asks for a suspension. The admin learns only `author_suspended`.
  - A suspended account can log in and read, but cannot post, comment or vote.
- **Cross-listed courses (P08-5, Richard 2026-11-14).** There is one forum page for each cross-listed group and instructor.
  - `pages.crosslisted_codes(code)` gives the code and every code that shares a `crosslist_group` with it (any catalog year).
  - These functions use it: `ensure_page`, `find_page`, `terms_taught`, `pages_of_code` (course view, course page instructors, the forum tools of the advisor) and the nightly course values.
  - `ForumPageOut.also_listed_as` gives the other codes.
  - When a page exists under any sibling code, the code uses that page again (lowest id first).
  - Pages created separately for two sibling codes before this rule do not merge automatically. No such pages exist today (the demo seed uses single codes).
- **Optional review questions (Q11, Richard 2026-11-14).**
  - `review_rating.pace` and `review_rating.grading_strictness` (1-5, nullable, migration `0002`).
  - `ReviewRatingIn` takes them as optional.
  - `RatingSummary` and the rating distributions use only the reviews that answered for the average.
  - The nightly job publishes `pace` and `grading_strictness` attribute values from the reviews that answered. n counts those posts. The usual minimum of 3 applies.
  - The "protect my GPA" goal of the generator reads `grading_strictness`.
- **Rate limits** (for each account, Redis only): 10 posts / hour and 30 / day, 30 edits or deletes / hour, 60 comments / hour, 300 votes / hour, 20 reports / day. Also a loose per-IP limit on every forum write.
- **The `/forum` page (issue #20).**
  - `api/forum/board.py` merges reviews and Commons threads for `GET /forum/items`. The tables stay separate (D2).
  - Order: `created_day` descending. Then, on the same day, discussions before reviews. Then id descending.
  - `next_cursor` is the key of the last item, `YYYY-MM-DD.<0 review|1 discussion>.<id>`. The code reads each source with a keyset condition after the cursor. Thus concurrent posts never move a page.
  - `ForumItemList.reviews_hidden` is true for a logged-out reader. This reader gets only discussions.
  - `tag` and `mine` select only discussions. `instructor` selects only reviews.
  - A discussion item has `ai_answer_html`: the top-level bot reply, clipped to 60 words.
  - `api/forum/stats.py` makes `GET /forum/stats` from the visible reviews posted in the last 91 (`quarter`) or 365 (`year`) days.
    - Score = (5 m + Σ overall) / (5 + n), where m = the mean overall rating of the period.
    - Subjects with n < 3 are not included. Below 3 reviews, the average, recommend share and workload of the period are null.
    - A course pools its cross-listed codes (two instructors can have pages under different codes). Its name is the code with the most reviews.
    - Majors: programs of type `major` (published, or all with `SHOW_UNPUBLISHED_PROGRAMS`) of catalog year 2026-27, matched with `SelectorMatcher.fills`.
    - Humanities: the sublists of `core-huma-sequences`, with cross-listed codes.
    - Each process keeps the result for `PAGE_CACHE_TTL_S`.
  - Tests: `test_forum_board.py`.
- **Storage note.** `review_rating.grade_bucket` is `varchar(16)`. The code stores "prefer not to say" as `undisclosed` and maps it back on read. No migration was necessary.
- **Demo data.** `make seed-forum-demo` (development only) adds FAKE instructors "Demo Instructor A".."E" (`demo-instructor-a`..) on CMSC 14100, CMSC 14200, MATH 15100, ECON 20000 and HUMA 11000, and a few fake posts. `ARGS=--remove` deletes them. They are never part of `data/seed`.

## Verifier semantics (prompt 02)

Entry points in `planner_core`:

- `verify(plan, rules, catalog, options) -> Report` (pure, deterministic).
- `check_certificate(plan, rules, catalog, certificate) -> bool` (the trusted checker). `certificate_problems` gives the reasons.
- `verify_checked(...) -> (Report, problems)`, which runs both.

Each part of the app that shows "Valid" must use `verify_checked` (`POST /verify` uses it). The docstring of each module states the rules that it implements. This section is the summary.

**Status and certificate.**
- `Report.status` is `errors` if any issue is an error. If not, it is `warnings` if any issue is a warning. If not, it is `valid`. `info` issues never change it.
- The verifier attaches a certificate only when the certificate can be complete:
  - No reported errors.
  - The prerequisites and program requirements hold.
  - Every listed program has rules.
  - Every hard goal holds.
- `options.checks` filters which issues are reported. It does not filter what the certificate attests.
  - The verifier evaluates prerequisites (V03) and program satisfaction (V07, V08) for the certificate, even when they are not in `options.checks`.
  - Thus a must-pass golden plan can skip V05 or V09 and still get a certificate. A plan with a hidden V03 or V07 failure gets no certificate.
- `verify_checked` then runs the checker. If the checker rejects the certificate:
  - The certificate is dropped.
  - The status becomes `errors`, and a V07 error says so.
  - The API logs an alert and does not cache the report.
- A report without errors and without a certificate (a restricted run that hides a failed V03/V07/V08) proves nothing. Thus `verify_checked` changes its status to `warnings`, with a note.
- `include_certificate: false` only hides the certificate.

**Which programs.**
- The verifier checks only the programs in `plan.programs`.
- A listed program without rules is a V01 error.
- The verifier does not read `PlanProgram.options` (track, specialization). Tracks are programs of their own.

**Courses.**
- A cross-list group is one course everywhere.
- `equivalent` and `replaces` relations make two courses interchangeable for prerequisites and for "done by" deadlines, but not for selectors.
- Enrolled statuses (`planned`, `in_progress`, `completed`) add to the quarter load. They count as "by enrollment" and "in residence". `transfer` and `exam` items and `credits` do not.
- A credit with `maps_to` counts as that course, taken before every term.
- A placeholder (`slot_ref`) counts 100 units (or its `units`) toward loads and totals. It fills nothing.
- A course that is not `repeatable` counts one time toward program requirements, however often the plan lists it. (V02 reports the repeat.)
- Each enrolment of a `repeatable` course is a separate course for program requirements. (A "two-quarter series" under one number is `count: 2` from that code.)
  - The n-th enrolment can be used in a unit only where the (n-1)-th enrolment is used.
  - A certificate that lists the code n times in a unit means its first n enrolments.

| Code | Reading |
| --- | --- |
| V01 | Error for each of these: an unknown course, an unknown credit target, a listed program without rules, a placeholder that names no node of the programs of the plan, or rules/catalog of a different catalog year. |
| V02 | Error, as the spec lists V02, for each of these: the same course (cross-list group) two times, unless `repeatable`. Two courses related as `mutually_exclusive`, `equivalent` or `replaces`. Exam or placement credit for a course that the student also takes ("credit forfeited"). |
| V03 | Checked only for `planned` and `in_progress` items. (Completed, transfer and exam items are history.) `course`: a strictly earlier term, or the same term when it is a Summer quarter (summer sessions run in sequence). `concurrent`, and every course atom inside `coreq`: the same term or an earlier term. `placement`: in `plan.placements`, or a placement credit. `standing`: the class year in that term (plan year + `entry_year_level` - 1) is at least the named one. `program`: a glob on the program ids of the plan. `consent`: a warning, never blocks. With `any` / `n_of`, the branches that need the fewest consents win. A recorded grade below `min_grade` fails. If there is no grade yet, the verifier assumes that it meets the minimum (listed in `assumptions`). `restrictions` are errors, the same as prerequisites. |
| V04 | Only `planned` items. A term is "posted" when it has any section. A course with no (non-cancelled) section in a posted term is an error. If not posted, `p_offered` < 0.3 is a warning. A course with no offering pattern at all gets no flag. A course with patterns, but none for that quarter, counts as 0. |
| V05 | Autumn, Winter and Spring quarters **that have at least one course** must have `full_time_min_units`..`full_time_max_units`. **Empty quarters and Summer get no flag.** Thus a plan in progress is not an error only because it is not finished. Above the maximum and up to `overload_units`: a reason claimed in `plan.overload_reasons` whose conditions hold (class year, a course that matches the selector, a course of at least `min_course_units`) gives a "needs petition" warning. All other cases are errors, and the hints give the reasons that would apply. A quarter with only `completed` courses is history, and reports as `info`. |
| V06 | Only posted terms. Two courses clash when, for some component of each, every section of one overlaps every section of the other (a definite clash). Warning. |
| V07 | One error for each unmet requirement of an unsatisfied program (see "Solver"). |
| V08 | A share limit that the solution exceeds: an error that names the shared courses. The program that declares the limit also gets a V07 error at its root, and is not satisfied. A limit applies to each matching program separately. `with` forms: `type:<type>`, `core`, `program:<glob>` or a bare id glob. `except` removes the units whose path, or any node id on that path, is listed. Violations of `policy.requires` / `policy.excludes` are also V08 errors. |
| V09 | `total_units` counts every item, placeholder and credit. `units_by_enrollment` counts only enrolled items and placeholders. The Core must be listed and satisfied. `language_node` must be satisfied. Residency: the `policy.residency` of a program. If it has none, `residency_min_fraction` for every program except the Core and study-abroad blocks, as a share of the courses that the solver assigns to the program. `max_quarters` counts the Autumn/Winter/Spring quarters with enrolled courses. **On a partial plan, these stay errors** (the spec lists V09 as Error). The messages give the distance ("has 1200 so far (3000 to go)"). `Report.progress` is always filled, including rows under the pseudo-program `college` (`college/total_units`, `college/units_by_enrollment`). The verifier skips null policy values and lists them in `assumptions`. |
| V10 | Warnings. Courses on or before `core_complete_by` must be able to satisfy the Core. A later Core course still counts if it is in or before plan year `civ_abroad_year`, and also either a `study_abroad_block` program of the plan uses it or it is in the term of a `study_abroad` goal. The same test applies to the `timing.complete_by` of a program. The `timing.apply_requires` courses must be done strictly before `timing.apply_by`. |
| V11 | One predicate for each goal type (`planner_core/goals.py`). A failed hard goal: error. A failed soft goal: warning, with a score in [0, 1]. Per-term goals with career scope look at every Autumn/Winter/Spring quarter that has courses. A `language` goal needs `courses` or `list`. `interest` counts courses that are not assigned to a `slot` as electives. `workload_hours` uses `ci_high` when the goal is `strict` or `options.strictness` is `strict`. Missing attribute values count 0, and are listed in `assumptions`. |
| V12 | A Pass/Fail course is never eligible for a unit under `no_pass_fail`. It is an error only where the plan relies on it: the course would fit a requirement that is still unmet, or the program is unmet and would be met if its Pass/Fail courses had letter grades. (This takes one extra exact solve of that program alone. It catches this case: the solver filled the requirement of the Pass/Fail course with a different course, and left a different requirement open.) |

**Rule trees.**
- A *unit* is a slot, a select, or one part of a bounded_parts node.
- `no_pass_fail`, `min_grade` (the strictest wins) and `allow_double_count` on a group or bounded_parts node apply to every unit below it.
- Within a program, a course fills one unit, unless the unit allows double counting.
- Set constraints apply to all courses used below the node that has them:
  - `same_sequence`: all in one sublist of the lists that the selectors name. A node whose selectors name no list with sublists cannot be satisfied.
  - `in_order`: two courses of one subject, in ascending number order and in strictly increasing terms.
  - `max_from`: cross-list groups, or the code as written with `as_enrolled`.
  - `distinct_subjects`: the subject of the code as written in the plan.
- A slot takes exactly one course. A select by count takes exactly `count`. A part takes at most its maximum.
- The parts of a bounded_parts node add up to exactly `total.courses` (or at least `total.units`).
- An `n_of` group activates at most n children. The other children take no courses.

**Solver.**
- In the model, share limits are soft.
- Objective, in priority order:
  1. Maximize the weighted number of satisfied nodes. A node weighs more than its full subtree.
  2. Break as few rules as possible (courses shared beyond a limit, residency).
  3. Use as few courses as possible.
- There are two solves:
  1. The first solve requires every root (exact). Every certificate comes from this solve.
  2. Only if the first solve is infeasible: the full objective, under a deterministic work limit.
- If the second solve stops before it proves optimality, the unmet nodes that it reports are still true. `assumptions` says that the list may not be the smallest.
- The solver is single-threaded. Thus equal inputs give equal reports.
- The progress shown for an unmet unit is a greedy pick of unused eligible courses. It is only for display.

**Checker.** `check_certificate` accepts when all of these are true:
- The plan hash and the rule hashes match.
- Every assigned course is in the plan, and matches the selector and grading rules of its unit.
- A course fills one unit for each program, unless double counting is allowed.
- The assignments satisfy every program root, including the set constraints.
- Every share limit holds.
- Every planned or in-progress course with a requisite has a witness that cites only facts of the plan and is sufficient.
- Loads and goal results compute again to the same values, and no hard goal fails.

The checker does not check V01, V02, V04-V06, V09 or V10 again. These are lookups in the report. Witness tokens: `CODE@TERM`, `credit:CODE`, `placement:VALUE`, `standing:VALUE`, `program:GLOB`, `consent:VALUE`.

**`POST /verify`.**
- For each `plan.programs` entry, it loads the `program_version` of the catalog year of the plan. A bound `version_id` must be that row.
- It loads only `published` versions, unless `show_unpublished_programs` is set.
- All other cases are a 422 in the validation-error shape of FastAPI (`loc` points at the program).
- It loads only the subset of the catalog that the plan can touch (`api/repo/rules.py`).
- It reads attribute values with `subject_type = course` and `subject_id` = course code.
- Cache key: `verify:{core_version}:{digest}:{plan_hash}`. The digest is a hash of the loaded rules, the catalog facts and the request options. TTL: one hour. The API logs Redis errors and ignores them.

## Plan generator (prompt 06)

`planner_core.generator.generate(plan, rules, catalog, options) -> GenerateResult` is pure and has no LLM.

**What it keeps and what it decides.**
- Completed, in-progress, credited and locked courses never move. Courses outside the quarters that the generator plans also never move.
- Unlocked planned courses inside those quarters *float*, together with a pool of catalog courses. The solver decides whether to place each one, and where.
- The pool holds:
  - The courses that can fill the requirements of the plan: the best few for each requirement, and full sequences for sequence lists.
  - The courses that a goal names, and the prerequisites of everything in the pool.
  - Forty free electives.
- Real courses replace the requirement placeholders (`slot_ref` items) in those quarters.
- The generator never plans Summer. With `today_term`, it places nothing before the current quarter.
- Scope "remaining" starts at `today_term`. Scope "selected" uses only `selected_terms`.

**Model.** The model has a variable `place[c, t]` for each pool course and quarter. It places a course at most one time (a repeatable course gets two enrolments). Constraints:
- Prerequisites must be met by earlier quarters (or by the same quarter when it is a Summer quarter). Co-requisites must be met by the same quarter or an earlier quarter.
  - Placement, standing and program atoms come from the plan.
  - Consent never blocks, but courses that need it have a lower preference.
- `p_offered` >= 0.3, unless the student accepts the course in `allow_rarely_offered`. Where a quarter has a posted schedule, a course must be in it.
- Each quarter that has courses is full time, within the College maximum. A 500-unit quarter is permitted only with `allow_overload`, and only where the plan already claims an overload reason that applies.
- Program satisfaction uses the V07 model again (`solver.ProgramModel`, which now lets the caller decide `in_order` for floating courses). Sharing limits, residency and graduation totals (units, units by enrollment, number of quarters) also hold.

**Goals.** `goalcompile.compile_goals` compiles the goals, as the table in SPEC "Goal predicates" tells:
- Hard bounds: `course_load`, `graduate_by`, `light_quarter`, and `workload_hours` / `difficulty_cap` when the goal is hard.
- Rewards: `challenge`, `interest`.
- Penalties: `protect_gpa`, and soft `workload_hours` / `difficulty_cap`.
- A pinned block: `study_abroad`.
- Precedence: `bxms` (the `apply_requires` of its program before `apply_by`), `premed`, `language`.

**Objective.** The objective is the sum of these terms:
- The preference of each placed course, minus a cost for each course. The cost is larger than any preference. Thus the generator adds no course that no rule, goal or full-time load needs.
- A bonus for each own course of the student that stays, especially in its own quarter.
- Goal rewards and penalties, and the load slider (lighter spreads courses out, heavier finishes sooner).
- A penalty on the peak weekly workload, and on Core courses after the Core deadline.

Default preferences (`preferences.py`) rank by interest match (tags, Core areas, title words), then by forum `recommend_rate`, then by lower course level. `options.preferences` (the agent of prompt 07) overrides them for the courses that it names.

**Variants.**
- There are a maximum of three variants. Each variant is different from every earlier variant in at least four placements.
- Each variant goes through `verify_checked`, which runs `verify` and then `check_certificate`.
- If a variant has errors or a rejected certificate, the generator drops it and logs an `ALERT`, because that would be a bug in the generator.
- Each variant comes back with:
  - Its verified plan.
  - The change operations from the current plan (`apply_ops` makes the plan again).
  - The report.
  - Its metrics. The UI reads `avg_hours` and `hardest_quarter_hours`.

**Time.** `time_limit_s` (default 4 s, the API clamps it to 5 s) is the solver budget for the full call:
1. The solver first looks for any plan, without an objective (15% of the budget).
2. On large instances, it uses a staged solve as the fallback (60%). It places what the programs and goals need, without the graduation totals. It keeps those placements, and adds only the electives that the totals still need.
3. Then it makes the plan better from that start point (10%).
4. The other variants share the last 15%.

The 20 synthetic profiles in `services/api/tests/test_generate_profiles.py` each finish in less than 5 s. Each profile must give either verified plans or an explanation that names its exact conflicts. A time-out message is a test failure.

**Limits.**
- The generator refuses a plan with more than 200 items, or with quarters more than 8 years from its entry quarter.
- Generation has a limit of 200 requests for each IP for each day. For saved plans, the limit is 100 for each account for each day.
- Before the solve, an exact capacity check compares the units still necessary to graduate with what the open quarters can hold under the unit and course limits. When the quarters cannot hold enough, the check names the limits that cause the difference.

**Impossible requests.**
- Each hard goal and limit is an assumption literal: each program, sharing, offerings, loads, courses for each quarter, graduation, the prerequisites of locked courses, and each hard goal.
- When the solve is infeasible, the solver returns a core of those literals. The generator makes it smaller, to a minimal set (with a budget).
- The result is in plain English:
  - For a `graduate_by` that is too early: "Graduating by Spring 2029 needs 5 more courses than your remaining quarters allow".
  - For a program that cannot be completed: the requirements that are still missing, and a hint when the blocker is a missing placement result.
  - In all other cases: the goals that cannot all hold together.

**Saving a plan.**
- `PATCH /plans/{id}` with a `state` saves the full plan, including the items.
- Items keep their ids (the update is in place). Thus change sets that target items by id stay valid across saves.
- `PATCH /plans/{id}/items` stays the way to make small edits, with the plan hash as the guard.

**Change sets in the API.**
- The API applies a change set only while the hash of the plan is still its `base_plan_hash`.
- If not, the API marks the change set `stale`, makes a new preview against the current plan, and returns 409.
- A request with an old `base_plan_hash` of its own gets a 409, and the change set does not change.
- `ChangeSetApply.terms` applies only the operations that touch the selected quarters.
- "Agents (prompt 07)" describes typed confirmations (`confirmation_text`).

**Frontend.** The Generate popup uses the generator that `VITE_GENERATOR_MODE` selects: `deterministic` (the default until prompt 07), or `agent`, which streams `/agents/generate`. In deterministic mode:
- A plan that is saved to the account, and has not changed since the save, uses `POST /plans/{id}/generate`. Apply goes through the change-set endpoint.
- All other plans use `POST /plans/generate`. The browser applies the operations itself.

## Agents (prompt 07)

**Gateway (`packages/llm_gateway`).**
- `LLM.structured(task, ...)` (the contract that prompt 08 uses) did not change.
- Agent harnesses use `run_agent(llm, AgentSpec)`. This is a Messages-API tool loop with:
  - A fixed tool list.
  - A `submit_*` tool that Pydantic validates. On a validation error, there is one repair turn with the error, then `AgentError("invalid_output")`.
  - A `Budget` of tool calls, tokens and seconds (`budget_*` failures). The `submit` tool does not count as a tool call.
- Provider errors count for each run. After `fallback_after_errors` (2), the run moves to OpenRouter. A 4xx other than 429 counts as both at the same time.
- Each model call becomes a `CallRecord` (task, model, prompt version, tokens, cost from `prices` in `llm_routing.yaml`, latency, ok). It has no user identifier.
- `AgentError` is an `LLMUnavailableError`. Thus one `except` covers every fallback.
- `FakeLLM.run_agent` replays scripted turns (`ToolCall`, lists of them, `FakeTurn`, text, exceptions) through the same loop.
- The API installs the real `Gateway` only with `LLM_LIVE=true` and a provider key.

**Requests.**
- Anthropic: no `thinking` parameter (adaptive), `output_config.effort` from the routing file, `tool_choice: auto`, `strict` tools, no sampling parameters, no prefill.
- The system block has `cache_control` (the cache covers tools + system). Top-level automatic caching covers the conversation.
- `refusal_fallback: true` uses the beta `fallbacks: "default"`.
- OpenRouter gets the same history in the OpenAI format (without the thinking blocks).

**Events.**
- `AgentEvent` has two new events: `infeasible` (`message`, `conflicts`) and `confirm` (`change_set`, `confirmation_text`).
- `variant` has the new field `citations`.
- `GenerateRequest` has the new field `today_term`.
- `ChatRequest` has two new fields, both for a plan that is not saved: `history` (the last 12 turns of the browser) and `latest_proposal` (the newest open card of the browser).

**`POST /agents/generate`.**
- The steps, in order:
  1. "Loading requirements".
  2. "Choosing electives" (LLM). On failure: `failed`, then "Using the default elective ranking" `done`.
  3. "Solving".
  4. "Verifying". `failed` when the generator dropped a variant.
  5. "Writing rationale" (LLM). `failed` means that there is no rationale.
  6. `infeasible`, or one `variant` for each plan.
  7. `done`, with the `agent_run` id.
- In the step "Choosing electives", the model gets the unmet requirements that have two or more candidates (a maximum of 12, with 40 candidates shown for each). Its picks must be candidates of that requirement.
- In the step "Writing rationale", the model must repeat the exact course set of each quarter. If not, the rationale of that variant is dropped. Texts of more than 25 words get the repair turn.
- With the `plan_id` of a saved plan of the caller, and a request plan with the same hash, the API stores the variants as proposed change sets. The plan of a different account is a 404.
- Limits: 10 for each account for each day. Logged out: 3 for each client address for each day. (Redis counters with a key that is a hash of the address and the day, 24-hour TTL.)

**`POST /agents/chat`.**
- The API first parses a typed confirmation, without a model (`api/agents/confirm.py` documents the grammar).
  - "apply it" names the latest open proposal: the newest `proposal` chat message of a saved plan, or the `latest_proposal` of the browser.
  - "I agree to ..." must be equal to the operations of that proposal, or be fully explicit (every course with every quarter that it touches). In the explicit case, the API drafts a new change set (`origin: user`).
  - In both cases, the plan must still have the hash of the proposal. The answer is a `confirm` event, and the browser applies it. For a saved plan, the browser uses `POST /plans/{id}/changesets/{cs}/apply` with `confirmation_text`. The server parses the text again, and checks that it names this change set.
- Other messages go through the scope gate.
  - `off_topic` and `suspicious` get fixed one-line replies without the main model.
  - A failed gate counts as `in_scope`.
- Then the advisor runs: `a2_advisor_chat`, or `a2_advisor_chat_escalation` when the gate asks for a whole-plan comparison. Its tools:
  - `get_plan`, `preview_ops`, `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `compare_courses`.
  - The draft tool `propose_change_set`: a maximum of 2 for each answer. The API stores them only after the answer passes validation.
  - `submit_answer`.
- Citations are `kind:id` pairs. If a tool in the run did not return a citation, the API drops it and logs it.
- Limits: 60 messages for each account for each day. Logged out: 30 for each client address.

**History.**
- A saved plan has one `agent_run` of kind `chat`.
- `chat_message.role` is `user`, `assistant` or `proposal` (content = change-set id).
- At the start of each chat request, the API deletes messages older than 30 days. It never reads them.
- A plan that is only in the browser stores nothing on the server.

**Prompts and evals.**
- `prompts/a1_preferences.md`, `a1_rationale.md`, `a2_chat.md` and `a2_scope.md` start with `id`, `version` and `task`.
- `llm_call.prompt_version` is `<id>@<version>`.
- Forum text goes to a model only inside `<untrusted_source id="post:N|summary:N">`. The text is HTML-escaped, so it cannot close the tag.
- `evals/` holds the sets (`evals/build_sets.py` builds them from the seed) and the runner.
- `make evals` refuses to run without `CONFIRM_SPEND=yes`.

**Frontend.** `VITE_GENERATOR_MODE` now has the default `agent`. The agent mocks for vitest and e2e are in `apps/web/src/mocks/agents.ts`.

## Planner agent (issues #17 and #18)

One agent writes the first plan and changes it in the chat. Its rules are `data/planner/plan-guideline.md` (rules `G01`...), its limits `data/planner/config.yaml`. Routes: `a1_planner_agent` (generation) and `a1_planner_chat`, both Opus 5.5; `a2_scope_classifier` still gates chat messages.

**`POST /agents/planner`.** Body `PlannerRequest`:
- `mode`: `generate` or `chat`. `plan`: the plan as the page has it. `plan_id`: a saved plan of the caller (another account's plan is a 404).
- Chat: `message`. Generate: optional `run_id` + `answer` to continue a run that paused for a question.
- A plan in the browser also sends `history` (last 12 turns), `pending` (open proposals), `profile_answers` (General Information answers it holds) and `working_notes`.

**Events** (`PlannerEvent`, one per `data:` line):

| type | fields | meaning |
|---|---|---|
| `step` | `name`, `status` (`started`, `done`, `failed`) | progress: "Reading your information", "Checking what can fit", "Writing your plan", "Checking the plan", "Fixing the plan (round n)", "Explaining each choice" |
| `question` | `run_id`, `question_id`, `field` (a General Information field, or null), `text`, `options[]`, `allow_other` | the run paused; the page shows option buttons and an "Other" box, then sends `run_id` + `answer` |
| `plan` | `run_id`, `verdict` (`valid`, `invalid`), `issues[]` (`PlanIssue`), `compromises[]`, `summary` | the whole proposed plan. `verdict` comes only from `verify_checked` + `check_certificate()` |
| `proposal` | `change_set_id` (saved plan) or null, `group_id`, `title`, `kind` (`major`, `core`, `elective`, `minor`, `replace`, `other`), `ops[]`, `why`, `citations[]`, `rules[]` (`{id, text}`), `preview` (`Verdict`), `base_plan_hash` (a browser plan sends it back in `pending`) | one course or sequence as unsaved blocks |
| `message` | `text`, `citations[]` | a chat answer |
| `confirm` | `change_set`, `confirmation_text` | a typed confirmation (as before) |
| `done` | `run_id`, `working_notes` and `profile_answers` (browser plans: the new working information, and this run's answers as their fields store them) | the end of the stream |
| `error` | `message`, `reason` (`expired`, `unavailable`, `invalid_output`, `budget`, `invalid_plan`) | the run stopped; `expired` = start again |

**Questions and resume.** Before planning, the agent asks for an empty General Information answer that planning needs (`intended_programs`, `interests`, `expected_graduation_term`), with the question and options from `data/profile/questions.yaml`, then at most 2 questions of its own. Before each question the server saves the run in `agent_run.state` and ends the stream. A resume does not count toward the rate limit. A state older than one day gives `error {reason: "expired"}`. A logged-in student's answer is stored as a `profile_proposal` (accepted on the dashboard); the run uses it at once.

**Citations.** Kinds `profile` (`profile:interests`, only a field the student answered; the chip links to `/me#field-<field>`) and `guideline` (`guideline:G07`, only a rule that exists) join `course`, `post`, `summary`, `attribute`, `program`. The server rebuilds every label.

**Proposals and re-base.** Each group is its own change set (`origin` `generate` or `chat`, with `run_id` and `meta`). Apply (`POST /plans/{id}/changesets/{cs}/apply`): for a change set with a `run_id`, a different plan hash no longer makes it stale by itself. If its ops still apply to the current plan, they are applied; if not, it becomes `stale` and the answer is 409 "This proposal no longer fits your plan." Change sets without a `run_id` and typed confirmations keep the strict hash check. Browser plans follow the same rule with `applyOps()`.

**Working information.** The chat tool `note_preference {text, kind: avoid|prefer|schedule|other, courses[]}` adds the line `- YYYY-MM-DD · kind · text [CODES]` to `student_profile.working_notes` (saved plan) or returns the new text in `done.working_notes` (browser plan). `avoid` lines with course codes are a list that the planner never proposes again.

**History.** A saved plan's planner chat is kept while the plan exists (`DELETE` clears it). A plan in the browser keeps its chat in `localStorage`.

**Limits.** Generation (a new `generate` request): 10 per account per day, 3 per client address logged out. Chat: 60 / 30.

## Forum -> course attributes (prompt 11)

**When it runs.**
- `api.attributes.job.run_nightly` runs every night at 03:30 as an Arq cron job (`worker.main.nightly_attributes`).
- To run it by hand, use `make attributes`.
- It writes one `attribute_value` row for each subject and key. Each night, the new rows replace the old rows.
- A subject is a course (`subject_id` = course code) or a course x instructor page (`subject_id` = the page id).
- The course page, the forum and the planner read those rows.

**The numbers** (`aggregate.py`). Each value is `(k*m + sum(w*r)) / (k + sum(w))`:
- The prior m:
  - The department average, when the department has at least 3 ratings (k = 5).
  - If not, the cold-start estimate of the course (k = 2, "weighted as 2 ratings").
  - If not, nothing (k = 0).
- Weights: a structured rating counts 1. A value taken from post text counts 0.5. Anything older than 4 years counts 0.5.
- The confidence interval is the value plus or minus 1.96 standard errors, clamped to the scale.
- The job publishes forum-derived values only when n >= 3 (method `blend`, or `forum` with no prior). Below that, the row holds the estimate (method `prior`, n 0), and the UI gives it the label "estimate".
- The job updates these attributes: workload hours, difficulty, intellectual intensity and recommend rate. Pace and grading strictness have no forum source yet.

**Agent A3** (`a3.py`, prompts `prompts/a3_*.md`). Code checks each answer before use:
- **Extraction (Haiku):** Each quote must be in the post. A workload number must be in its quote. Difficulty words map to easy 2, moderate 3, hard 4, very hard 5.
- **Summary (Sonnet):**
  - A maximum of 120 words.
  - Each `[n]` marker must point into the citation list. The summary can cite only posts that the model got.
  - Then the A4 classifier must return `ok`. When moderation is not available, nothing is published.
  - The job makes the summaries again after 3 new visible posts or after 30 days.
- **Cold start (Sonnet):** A rubric gives the workload and difficulty from the description and the level. The job stores the result as an estimate. Only courses that have a forum page get an estimate, a maximum of 200 each night.

The job gives post text to the model inside `<untrusted_source>`. These calls have no tools. Without a model, the job skips the A3 steps and aggregates only the structured ratings.

## Catalog ingestion (prompt 09)

**Where it lives.** `services/worker/worker/ingest/` (its `__init__.py` has the module map). It imports the API package for the database models, the seed loader and the prompt loader. The API never imports the worker.

**Crawler.** `Crawler` does these things:
- It fetches only the hosts that it gets.
- It reads robots.txt one time for each host. A 404 permits everything. A 401, 403, 5xx or a network error makes it skip the host.
- It waits at least 1 second between requests. A longer `Crawl-delay` wins.
- It sends `QuarterlyCatalogBot/0.1 (...; contact: <CATALOG_CONTACT_EMAIL>)`.
- It refuses to start without a contact address, and it never logs the address.
- Each response, including robots.txt, becomes a snapshot:
  - The bytes go into MinIO (S3 API, SigV4, key `catalog/<sha256[:2]>/<sha256>`).
  - A `source_snapshot` row records the url, time, sha256, key and content type.
- Snapshot ids in rule trees are `source_snapshot.id` as a string.

**Agents.** All agents go through `llm_gateway`, with tasks from `llm_routing.yaml` and prompts in `prompts/` (header `id`, `version`, `task`):

| Agent | Task | Prompt | Tools | Output |
| --- | --- | --- | --- | --- |
| E1 prerequisite | `e1_prereq_formalizer` | `e1_prereq` | none | `E1Answer` (DSL expression or `unparseable`) |
| E2 enumerator | `e2_program_enumerator` | `e2_enumerator` | `list_pages`, `read_snapshot` | `submit_programs`: `ProgramCandidate[]` |
| E3 run A | `e3_program_formalizer` | `e3_formalizer` | `read_snapshot`, `lookup_course`, `get_course_list`, `validate_rules` (5 calls), `run_golden` | `submit_rules`: YAML that passes (a)-(c) |
| E3 run B | `e3b_second_opinion` | `e3b_formalizer` (same sections, different order) | same | same |
| E4 judge | `e4_backtranslation_judge` | `e4_backtranslation` | none | `E4Answer` (English + differences by node path) |

- Page text goes to each agent inside `<untrusted_source id="snapshot:<id>">`.
- No agent has a write tool.
- Each run is an `extraction_run` row. Each model call is an `llm_call` row.
- `Metered` wraps the client with the spending cap (`INGEST_COST_CAP_USD`).

**Checks.**
- E1: The expression parses. Every course exists. Every course number is in the sentence. There is no self-reference. If a check fails, a `requisite` review item.
- E2: The candidates must agree with at least two independent lists that code builds:
  - The counts that the College states. The count uses distinct `family` names for each type, so a BA and a BS are one major.
  - The Programs of Study index. Every URL must be in both directions.
  - The A-Z index. Each candidate must be on it.
  - Any difference writes an `ingest_run` review item and stops the run.
- E3: validators:
  - (a) The schema, with a source on every node, part, cap and policy entry.
  - (b) The courses and lists exist.
  - (c) The quotes are verbatim, after the decode of entities and the collapse of whitespace.
  - (d) Run A and run B agree node by node.
  - (e) E4 found no difference.
  - (f) The golden plans in `data/golden/<program>/` behave as expected.
  - (g) A major needs 9-19 courses (the fewest courses that satisfy the tree).
  - (a)-(c) must pass before E3 can submit. (d)-(g) become flags in the review item.

**Node-level agreement** (`compare.node_agreement`).
- A node agrees when its kind, counts, courses, selectors and constraints match.
- The comparison ignores labels, ids, quotes, `needs_review` and weights. It also ignores the order of codes in a list.
- Children are paired by id, then by identical subtree, then by position.
- The policy counts as one extra node.
- Agreement = agreed / (reference nodes + extra candidate nodes).

**Review items written by the pipeline** (`review_item.diff.kind` = `target_type`):
- `program_version` (target id = the version id):
  - Fields: `rules`, `second_run_rules`, `previous`, `nodes[]` (path, kind, label, summary, quote, url, snapshot_id, flags), `checks[]` (id, name, ok, skipped, problems), `backtranslation`, `agreement_runs`, `changes_from_previous`, `decision_hint` (`review` or `carry_over`), `snapshots`, `cost_usd`.
  - The pipeline writes the version itself with status `review`.
  - The pipeline never touches an existing `published` version for the same program and year. In that case, the item has `program_version_id: null` and `blocked`.
- `course_batch` (target id `<year>:<subject>`): `courses[]`, `added`, `changed[]` (fields before/after), `removed`, `crosslist_groups`, `relations`, `requisites` (E1 results that passed), `unchanged`.
- `requisite` (`<year>:<code>`): `raw_text`, `proposed`, `proposed_text`, `errors`, `source`.
- `ingest_run` (`<year>:<step>`): `step`, `problems` (a blocked enumeration, a program that E3 could not formalize, pages not fetched, course blocks that did not parse, the spending cap).
- `catalog_change` (`<year>:<day>`): `changed[]` (url, before and after sha256) and `new_pages`, from the monthly check.

**Carry over.** The pipeline carries a tree over when both of these conditions are true:
- The new tree means exactly what the published tree of last year meant.
- The quotes of last year are still on the pages of this year.

In that case, the version holds the tree of last year (with the catalog year updated), and the item says "unchanged". A curator must still publish it.

**Review API** (only admins, `X-CSRF-Token` on every POST, `Cache-Control: private, no-store`):
- `GET /admin/review-items?status=open|accepted|rejected` returns `Page[ReviewItemOut]`. `ReviewItemOut` adds typed `title`, `program_version_id`, `program_version_status`, `decision_hint`, `nodes` and `checks`, which it reads from the diff.
- `POST /admin/review-items/{id}/decision` with `{decision: accept|edit|reject, edited?, note?}`. Only for open items (if not open, 409).
  - `program_version`: accept marks it ready. Edit takes `edited.rules` (validated as `ProgramRules`, every node with a source, the same id and year) and replaces the rules of the version. Reject sets the version to `draft`.
  - `requisite`: accept or edit (`edited.prereq`) upserts `requisite`. The course must exist.
  - `course_batch`: accept upserts the courses, cross-list groups, relations, offering patterns and prerequisites of the subject for the new year. Edit is refused (422).
  - Other types (including the types of the schedule pipeline) only record the decision. An edit is kept as `diff.edited_content`.
- `POST /admin/program-versions/{id}/publish`:
  - The version must be in `review`, with no open item about it, and not all of its items rejected.
  - It sets `published`, `verified_by` (the username of the admin) and `verified_at` (day).
  - This is the only way for a version to reach students.

**Jobs.**
- `worker.ingest.jobs.cron_jobs()` registers the annual run (1 August, 04:00) and the monthly check (the 15th, 04:00) only when `CATALOG_INGEST_ENABLED=true`. The job functions also check this flag.
- Without `LLM_LIVE=true`, the annual run still crawls and stages courses. It files one item that says that the agents were skipped.

## Schedule pipeline (prompt 10)

**Package.** `services/scraper/scraper`.
- It now depends on `quarterly-api`, and the worker depends on it.
- Nothing in it sends a request unless `SCHEDULE_SCRAPER_ENABLED=true` and `CLASS_SEARCH_URL` is set. (`scraper.settings.require_enabled` checks this before a browser starts.)
- Tests use only `services/scraper/fixtures/SYNTHETIC_*` and `FakeLLM`.

**Flow.**
1. `class_search.crawl` (Playwright, 1 page each second).
2. `snapshots.record_snapshot`: the bytes go to MinIO under `class-search/<sha[:2]>/<sha>.html`, with one `source_snapshot` row. The same URL with the same bytes uses its existing row.
3. `pipeline.run_schedule(db, store, term_id, snapshot_ids)`.
4. If the run fails, `repair.propose_repair`.

`watch.weekly_watch` does all four steps for the next two quarters. The worker cron `weekly_schedule_watch` (Mondays 04:00) calls it. When the flag is off, it returns `disabled: ...`.

**Parser.** `parse.parse_page(html, ParserConfig)` reads a page with selectors that are stored as data (`scraper.dom`: tag, `.class`, `#id`, `[attr=value]`, descendant, `>`, commas). It raises `ParseError` in these cases:
- The results marker is missing.
- There are no course blocks and no empty-page marker.
- The parser cannot read a cell.
- A page lists the same section two times.

Fields:
- Meetings are stored as `[{days: [Mon..Sun], start: "HH:MM", end: "HH:MM", location?}]`.
- `status` is `open`, `closed`, `waitlist` or `cancelled`. If a later run of the same term does not show a section, it sets `not_listed` on that section.
- `capacity` is the enrolment limit.

**A run** is one `extraction_run` row:
- `kind = schedule_parse`, `model = deterministic`, `prompt_version` = the parser version, `input_snapshot_ids`, and `status` `ok` or `failed`.
- Its `output` holds `counts_by_subject`, `counts_by_snapshot` (the "last good counts"), `review_item_ids`, `new_instructors` and `errors`.

A failed run (any page error, or zero sections) writes nothing else. An ok run does these things:
- It upserts `section` by term, course, section number and component.
- It creates an instructor for each name that is not similar to the name of an existing instructor.
- It calls `api.forum.pages.ensure_page` for every instructor of every section that is not cancelled (cross-listed codes share a page).
- It updates `offering_pattern` for the subjects that it covered.

**Review items.**
- `target_type` is the kind. `diff.kind` repeats it.
- There is one open item for each kind and target. A new run refreshes it.

| kind | target_id | raised when | accepting does |
| --- | --- | --- | --- |
| `schedule_unknown_code` | `<term>:<code>` | A code is not in the catalog. Its sections are not saved. | Nothing yet (prompt 09 adds the course). |
| `schedule_instructor_match` | `<term>:<normalised name>` | A name is near the name of an instructor (score >= 0.80), but not the same. | `apply.apply_instructor_match(db, id, instructor_id or None)`: adds an alias or a new person, then the sections and forum pages. |
| `schedule_count_alert` | `<term>:<subject>` | The section count is more than 30% different from the same quarter last year. | Nothing. (The sections were saved. It is a warning.) |
| `schedule_parser_repair` | `run:<failed run id>` | A run failed. `diff.proposed_config` is the verified proposal, or null. | `pipeline.active_config` uses the newest accepted proposal. |
| `schedule_dept_plan` | `<department>:<academic year>` | The pipeline read a department page. See `diff.accepted`, `unknown_codes`, `rejected`. | `apply.apply_department_plan_item(db, id)`: p = 0.95. |

The `apply_*` functions refuse items that are not `accepted`.

**Offering pattern.**
- `p = (k + 1) / 5`. k is the number of the last 3 years (this year included) that had a listed, non-cancelled section in that quarter.
- The pipeline matches courses by code across catalog years. It stores the pattern on the newest course row.
- The method tells where p came from:
  - `posted_schedule`: p = 1, from a posted schedule.
  - `department_plan`: p = 0.95, from an accepted department plan, with `evidence_terms` = the planned term. The pipeline skips it when the schedule of that same term is already posted.
  - `history`: the formula.

**Agents.**
- `repair.propose_repair` runs `scraper_repair`.
  - Its tools are read-only: `read_snapshot(snapshot_id, offset)` (HTML inside `<untrusted_source>`) and `try_config(config)`.
  - It ends with `submit_parser_config({config, explanation})`.
  - A proposal must give the same count as the last good run on each snapshot of that run. It must also parse every failed snapshot with at least one section. The submit check and code after the run both verify this.
- `dept_pages.extract_department_plan` calls `dept_offerings_extraction`, with no tools. The quote of each offering must be on the page. It must contain the code, every quarter that it names, and the instructor.

Prompts: `prompts/scraper_repair.md`, `prompts/dept_offerings.md`.

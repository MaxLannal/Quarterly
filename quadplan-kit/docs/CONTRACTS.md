# Contracts (prompt 01)

Frozen so prompts 02-05 can run in parallel. Change a contract once, regenerate (`make api-client`), and tell every parallel worker. Sources of truth:

- **planner_core models**: `packages/planner_core/planner_core/models.py` (JSON Schemas in `docs/schemas/`).
- **Database**: `services/api/api/db/models.py` + `services/api/api/migrations/versions/0001_initial_schema.py` (a test fails if they drift).
- **API**: the FastAPI routers in `services/api/api/routers/`; OpenAPI in `apps/web/src/api/openapi.json`, TypeScript types in `apps/web/src/api/schema.d.ts` (`make api-client`; `make check` fails if stale).
- **Seed and golden files**: `services/api/api/seed/models.py`.

## Endpoints

All stubs return `501 {"detail": "Not implemented yet (prompt NN)"}` after request validation (so a malformed body is still a 422). "Builds in" is the prompt expected to implement it.

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
| POST | `/plans/generate?mode=deterministic` | `GenerateLocal {plan, options: GenerateOptions}` | `GenerateOut` (change sets without ids; nothing saved) | No (rate-limited) | 06 |
| POST | `/plans/{plan_id}/generate?mode=deterministic` | `GenerateOptions` | `GenerateOut` (each variant stored as a proposed change set) | Yes | 06 |
| POST | `/verify` | `VerifyRequest {plan: PlanState, options}` | `Report` | No | 02 |
| POST | `/agents/generate` | `GenerateRequest` | SSE stream of `AgentEvent` | No (rate-limited) | 06/07 |
| POST | `/agents/chat` | `ChatRequest` | SSE stream of `AgentEvent` | No (rate-limited) | 07 |
| GET | `/agents/chat/history?plan_id` | | `ChatHistory` | Yes | 07 |
| GET | `/forum/pages?course&instructor`, `/forum/pages/{page_id}` | | `ForumPageOut` | Yes | 08 |
| GET / POST | `/forum/pages/{page_id}/posts?kind&sort&term` | `PostCreate` | `Page[PostOut]` / `PostOut` | Yes | 08 |
| GET / PATCH / DELETE | `/forum/posts/{post_id}` | `PostUpdate` | `PostDetail` / `PostOut` / 204 | Yes | 08 |
| POST | `/forum/posts/{post_id}/comments` | `CommentCreate` | `CommentOut` | Yes | 08 |
| POST | `/forum/votes` | `VoteIn` | `VoteOut` | Yes | 08 |
| POST | `/forum/reports` | `ForumReportIn` | `ForumReportOut` (202) | Yes | 08 |
| GET | `/forum/courses/{code}` | | `CourseForumOut` (every instructor's page, ratings pooled) | Yes | 08 (added) |
| GET | `/admin/moderation` | | `Page[ModerationItemOut]` | Admin | 08 (added) |
| POST | `/admin/moderation/{target_type}/{target_id}/decision` | `ModerationDecision` | `ModerationResult` | Admin | 08 (added) |
| POST | `/auth/email` | `EmailStart` | `EmailStarted {pending_id}` (202) | No | 04 |
| POST | `/auth/verify-code` | `VerifyCode` | `RegistrationTicket` | No | 04 |
| POST | `/auth/register` | `Register {ticket, username, password}` | `SessionOut` | No | 04 |
| POST | `/auth/login`, `/auth/logout`; GET `/auth/session` | `Login` | `SessionOut` / 204 | - | 04 |
| POST | `/auth/password-reset/start`, `/auth/password-reset/finish` | `PasswordResetStart`, `PasswordResetFinish` | 202 / 204 | No | 04 |
| GET | `/account/export` | | `AccountExport` | Yes | 04 |
| POST | `/account/password`, `/account/delete` | `PasswordChange`, `AccountDelete` | 204 | Yes | 04 |
| GET | `/admin/review-items?status` | | `Page[ReviewItemOut]` | Admin | 09 |
| POST | `/admin/review-items/{item_id}/decision` | `ReviewDecision` | `ReviewItemOut` | Admin | 09 |
| POST | `/admin/program-versions/{version_id}/publish` | | `ProgramVersionOut` | Admin | 09 |

The frontend calls these under `/api/...` (Vite dev proxy and nginx strip the prefix).

## Decisions that are not obvious

**Canonical DSL form with YAML shorthands.** Authors write the spec's YAML (`{course: X}`, `{all: [...]}`, `{n_of: 2, of: [...]}`, a bare `"CMSC 14100"`, `{id: intro, group: {...}}`). Models normalise to one canonical JSON (`Expr {op, n, children, atom}`, nodes with a `kind` discriminator) so `model_validate(model_dump())` is stable and hashes are reproducible. Unknown keys are errors (`extra="forbid"`) to catch typos in hand-written YAML. Keys that are Python keywords keep their spec spelling on the wire: `from`, `with`, `except`, `list`, `pass`.

**Node ids and paths.** A node's `id` is optional; missing ids become the 1-based position among siblings. A node's path is the program id plus child ids (`cmsc-bs/intro/1`, matching the spec's certificate example); the root's path is the program id. Parts of a `bounded_parts` node are addressed as `<node path>/<part id>`. `plan_item.slot_ref`, `Issue.node_id`, `Assignment.node` and `NodeProgress.node_id` all use these paths. Helpers: `planner_core.dsl.iter_nodes / iter_parts / node_paths`.

**Selector semantics.** A course matches when it is not excluded and every criterion that is set holds: `codes` (any), `subject`, `number_range` (inclusive, 5-digit number), `tags` (any), `list` (named list, sublists included), `union` (any sub-selector). A course's tag set is its `tags` plus `core:<t>` for each of its `core_tags`, so `tags: [core:arts]` matches a course with `core_tags: [arts]`. Matching and exclusion work on cross-list groups, so a cross-listed code matches wherever its partner does. Union is the only way to say "A or B" across criteria. One exception, opt-in: a `max_from` limit with `as_enrolled: true` counts a course only when the code written in the plan itself meets the selector's `subject`, `number_range` and `tags` (`codes`, `list` and `exclude` still work on the group), so "at most two from the 20000 level" does not count a cross-listed course taken under its 30000-level number.

**Sequences.** `same_sequence` needs to know which courses form a sequence. `course_list` gains `sublists`: a list such as `core-huma-sequences` has one sublist per sequence; `same_sequence` means every course used by the node comes from one sublist. The DB column is `course_list.sublists text[]` next to `course_ids bigint[]`.

**RuleSet vs Catalog.** `verify(plan, rules, catalog, options)` takes the *rules* (program versions, College policy, requisites) separately from *catalog facts* (courses, cross-lists, relations, course lists, terms, offering patterns, sections, attribute values), because rules are versioned and hashed into certificates while catalog facts are lookup tables. `check_certificate(plan, rules, catalog, certificate)` takes the catalog too: matching a course to a selector needs subject, number, tags and list membership.

**College policy as data.** `CollegePolicy` holds the College-wide numbers (4200/3800 units, 300-400 full-time, 500 overload and its reasons, Core timing, residency). Every non-null value must carry a source in `sources[field]`; a null value means "not encoded yet" and the check reports that as an assumption instead of guessing. Stored in an added `college_policy` table (one row per catalog year). Overload reasons can state the plan year, a qualifying course selector, or a minimum course size, so V05 can check them.

**Goals are a discriminated union** on `type` (all 12 goal types in the spec table), each with typed parameters; the DB keeps `type` + `params` JSONB. Term-scoped goals must set `term`; career goals must not. Goal deadlines accept relative terms (`Y3-WI`) or absolute ones; `planner_core.terms.resolve_term_ref` converts.

**Report extras.** Besides the spec's status, issues and certificate, `Report` carries `progress` (per-node have/need for the planner's requirement rail), `assumptions` (e.g. planned courses assumed to meet grade minimums) and `plan_hash` / `core_version` (the cache key). `VerifyOptions.checks` restricts which V-codes run; golden plans that test one program in isolation use it to skip loads (V05) and graduation totals (V09).

**Hashes.** `plan_hash` is the SHA-256 of the canonical JSON of a `PlanState` with item ids dropped and lists sorted, so reordering or renumbering items does not change it. `rules_hash` hashes a `ProgramRules`; certificate keys are `<program id>@<catalog year>`.

**Change sets.** Ops are `add`, `move`, `remove`, `lock` and `unlock`. Existing items are targeted by exactly one of `item_id`, `course` or `slot_ref`, plus a term to tell repeated courses apart. `planner_core.changes.apply_ops` is the single implementation: locked items cannot be moved or removed, and an ambiguous or missing target raises `ChangeOpError`. The server applies a change set only if the plan still hashes to `base_plan_hash`.

**Seed format.** `data/seed/<catalog_year>/` holds `terms.yaml`, `courses.yaml` and/or `courses/*.yaml` (`SeedCourse`: CourseLeaf block fields, plus `prereq` in the DSL, `prereq_text` verbatim, `crosslists`/`equivalents`/`mutually_exclusive`/`replaces`, `terms_offered`, a required `source`), `course_lists.yaml`, `college_policy.yaml` and `programs/*.yaml` (`ProgramSeed` = `ProgramRules` + name, type, degree, department, status, sources). `make seed` validates everything (every program node and part needs a `source`, every referenced course and list must exist; unknown courses in prerequisites are warnings) and then upserts idempotently. Every program-level share limit and every `max_from` cap (on nodes and parts) also needs its own `source`, and a non-empty `policy.requires` / `policy.excludes` needs `requires_source` / `excludes_source`. The fake fixture lives in `services/api/tests/fixtures/seed/2099-00/`.

**Offerings from "Terms Offered".** Until schedule data exists, a course's catalog "Terms Offered" line becomes `offering_pattern` rows with `method: catalog`: p = 0.95 for listed quarters (like a department's published plan) and 0.05 for unlisted Autumn/Winter/Spring. Courses without the line get no pattern (no V04 warning). This mapping is an open question.

**Golden plans.** `data/golden/<program>/*.yaml` (`GoldenPlan`): `expect: pass` means no error-level issues and a certificate that `check_certificate` accepts; `expect: fail` lists `expected_codes`, each of which must appear. The runner gives the verifier the College policy and the programs the plan lists (the Core only if listed). While `verify` is a stub, plans are reported as SKIP.

**Accounts (decision 5).** `account.email` (unique, lowercase) is the only column holding an email; a migration test enforces this. No blind-signature tables. User rows use day-level dates only (`*_day`), also enforced by a test.

**Program versions.** One `program_version` per program per catalog year (unique). Only `published` versions reach students; the seed loader writes the status in the YAML (default `review`).

## Forum (prompt 08)

Code: `services/api/api/forum/`. Tests: `services/api/tests/test_forum_api.py`, `test_forum_privacy.py`.

- **Pages.** A forum page is a `course_instructor` row (`page_id`). `api.forum.pages.ensure_page(db, course_id, instructor_id, term_id)` creates it on first sight and widens its term range; the schedule pipeline (prompt 10) must call it. One page per course *code* and instructor: a course row of another catalog year reuses the existing page. `GET /courses/{code}` now lists `instructors` (public names, P03-12).
- **Identity.** `author_ref`, `voter_ref` and `reporter_ref` are all `api.auth.hashing.author_ref(account_id, page_id)`. No forum row holds an account id. Pseudonyms are random two-word handles, one per (ref, page), unique on the page.
- **Visibility.** Readers see `visible` items; authors also see their own `held` / `removed` items with `mine: true` and a `moderation_note`. Others' hidden items answer 404 (reads, votes, comments, reports). A hidden comment with visible replies stays in the thread as a `[removed]` / `[awaiting moderation]` placeholder with the pseudonym `[hidden]`.
- **Contract additions (all additive).** `PostOut` / `CommentOut`: `body_html` (server-rendered and sanitized; the only HTML the client inserts), `mine`, `moderation_note`; `PostOut.edited_day`; `PostUpdate.term_taken`; `ForumPageOut.ratings` (`RatingSummary`); `InstructorCourse.ratings`; the three endpoints above.
- **Comments** are returned depth-first; siblings in Best order; `depth` = `nlevel(path) - 1` (top level 0). Paths are ltree labels of comment ids.
- **Sorting** (SQL, `api/forum/sorting.py`): Best = Wilson lower bound (z = 1.96), Top = net score, New = day then id, Controversial = (u + d) ^ (min/max) when both are positive, Hot = score * 0.5 ^ (age_days / 30). Ties: newer id first.
- **Moderation.** Posts, comments and edits are published at once after the scrub (emails, phone numbers); nothing checks them first (Richard, 2026-11-14, P08-1). Guideline breaks are taken down through reports and the admin queue. A4 (`a4_moderation`, `prompts/a4_moderation.md`, text inside `<untrusted_source>`, 3 s wall clock) now labels only the AI-written "What students say" summaries, which publish only on `ok`. Items an earlier version held or rejected keep their status and author note.
- **Queue and suspension.** Admins only. The queue lists items with an open report (and any held item from before). `approve` keeps the item and dismisses open reports; `remove` takes it down and upholds them. Suspensions are manual only (P08-3): `remove` with `suspend_days` (1-365) sets the author's `account.suspended_until` to today + that many days (never shortening an existing suspension); `approve` with `suspend_days` is a 422. The author is found by recomputing `author_ref` for every account, only when a suspension is asked for; the admin learns only `author_suspended`. A suspended account can log in and read but not post, comment or vote.
- **Cross-listed courses (P08-5, Richard 2026-11-14).** One forum page per cross-listed group and instructor: `pages.crosslisted_codes(code)` gives the code and every code it shares a `crosslist_group` with (any catalog year); `ensure_page`, `find_page`, `terms_taught`, `pages_of_code` (course view, course page instructors, the advisor's forum tools) and the nightly course values all use it, and `ForumPageOut.also_listed_as` names the other codes. A page is reused when it exists under any sibling code (lowest id first). Pages created separately for two sibling codes before this rule are not merged automatically; none exist today (the demo seed uses single codes).
- **Optional review questions (Q11, Richard 2026-11-14).** `review_rating.pace` and `review_rating.grading_strictness` (1-5, nullable; migration `0002`). `ReviewRatingIn` takes them as optional; `RatingSummary` and the rating distributions average only the reviews that answered. The nightly job publishes `pace` and `grading_strictness` attribute values from the reviews that answered (n counts those posts, the usual minimum of 3); the generator's "protect my GPA" goal reads `grading_strictness`.
- **Rate limits** (per account, Redis only): 10 posts / hour and 30 / day, 30 edits or deletes / hour, 60 comments / hour, 300 votes / hour, 20 reports / day; plus a loose per-IP limit on every forum write.
- **Storage note.** `review_rating.grade_bucket` is `varchar(16)`; "prefer not to say" is stored as `undisclosed` and mapped back on read. No migration was needed.
- **Demo data.** `make seed-forum-demo` (development only) adds FAKE instructors "Demo Instructor A".."E" (`demo-instructor-a`..) on CMSC 14100, CMSC 14200, MATH 15100, ECON 20000 and HUMA 11000, plus a few fake posts; `ARGS=--remove` deletes them. Never part of `data/seed`.

## Verifier semantics (prompt 02)

Entry points in `planner_core`: `verify(plan, rules, catalog, options) -> Report` (pure, deterministic), `check_certificate(plan, rules, catalog, certificate) -> bool` (the trusted checker; `certificate_problems` gives the reasons), and `verify_checked(...) -> (Report, problems)`, which runs both. Anything that shows "Valid" must go through `verify_checked` (`POST /verify` does). Each module's docstring states the rules it implements; this section is the summary.

**Status and certificate.** `Report.status` is `errors` if any issue is an error, else `warnings`, else `valid`; `info` issues never change it. A certificate is attached only when it can be complete: no reported errors, prerequisites and program requirements hold, every listed program has rules, and every hard goal holds. `options.checks` filters which issues are reported, not what the certificate attests: prerequisites (V03) and program satisfaction (V07, V08) are evaluated for the certificate even when left out, so a must-pass golden plan may skip V05 or V09 and still get a certificate, while a plan whose hidden V03 or V07 fails gets none. `verify_checked` then runs the checker. A rejected certificate is dropped, the status becomes `errors`, and a V07 error says so (the API logs an alert and does not cache the report). A report without errors and without a certificate (a restricted run hiding a failed V03/V07/V08) is downgraded by `verify_checked` to `warnings` with a note, because it proves nothing. `include_certificate: false` only hides the certificate.

**Which programs.** Only the programs in `plan.programs` are checked. A listed program without rules is a V01 error. `PlanProgram.options` (track, specialization) is not read: tracks are programs of their own.

**Courses.** A cross-list group is one course everywhere. `equivalent` and `replaces` relations make two courses interchangeable for prerequisites and for "done by" deadlines, but not for selectors. Enrolled statuses (`planned`, `in_progress`, `completed`) carry quarter load and count as "by enrollment" and "in residence"; `transfer` and `exam` items and `credits` do not. A credit with `maps_to` counts as that course, taken before every term. A placeholder (`slot_ref`) counts 100 units (or its `units`) toward loads and totals and fills nothing. A course that is not `repeatable` counts once toward program requirements however often it is listed (V02 reports the repeat). Each enrolment of a `repeatable` course is a course of its own for program requirements (a "two-quarter series" under one number is `count: 2` from that code); the n-th enrolment may be used in a unit only where the (n-1)-th is, and a certificate that lists the code n times in a unit means its first n enrolments.

| Code | Reading |
| --- | --- |
| V01 | Unknown course, unknown credit target, listed program without rules, placeholder that names no node of the plan's programs, or rules/catalog of another catalog year: error. |
| V02 | The same course (cross-list group) twice unless `repeatable`; two courses related as `mutually_exclusive`, `equivalent` or `replaces`; exam or placement credit for a course that is also taken ("credit forfeited"): error, as the spec lists V02. |
| V03 | Checked for `planned` and `in_progress` items only (completed, transfer and exam items are history). `course`: strictly earlier term; `concurrent`, and every course atom inside `coreq`: same or earlier; `placement`: in `plan.placements` or a placement credit; `standing`: class year in that term (plan year + `entry_year_level` - 1) at least the named one; `program`: glob on the plan's program ids; `consent`: warning, never blocks. With `any` / `n_of`, branches needing the fewest consents win. A recorded grade below `min_grade` fails; no grade yet is assumed to meet it (listed in `assumptions`). `restrictions` are errors like prerequisites. |
| V04 | `planned` items only. A term is "posted" when it has any section: a course with no (non-cancelled) section there is an error. Otherwise `p_offered` < 0.3 is a warning; a course with no offering pattern at all is not flagged; a course with patterns but none for that quarter counts as 0. |
| V05 | Autumn, Winter and Spring quarters **that have at least one course** must carry `full_time_min_units`..`full_time_max_units`. **Empty quarters and Summer are not flagged**, so a plan in progress is not an error only for being unfinished. Above the maximum and up to `overload_units`, a reason claimed in `plan.overload_reasons` whose conditions hold (class year, a course matching the selector, a course of at least `min_course_units`) gives a "needs petition" warning; anything else is an error whose hints name the reasons that would apply. A quarter whose courses are all `completed` is history and reports as `info`. |
| V06 | Posted terms only. Two courses clash when, for some component of each, every section of one overlaps every section of the other (a definite clash). Warning. |
| V07 | One error per unmet requirement of an unsatisfied program (see "Solver"). |
| V08 | A share limit the solution exceeds: error naming the shared courses; the program that declares the limit also gets a V07 error at its root and is not satisfied. A limit applies to each matching program separately. `with` forms: `type:<type>`, `core`, `program:<glob>` or a bare id glob. `except` leaves out units whose path, or any node id on it, is listed. `policy.requires` / `policy.excludes` violations are V08 errors too. |
| V09 | `total_units` counts every item, placeholder and credit; `units_by_enrollment` only enrolled items and placeholders. The Core must be listed and satisfied; `language_node` must be satisfied. Residency: `policy.residency` of a program, else `residency_min_fraction` for every program except the Core and study-abroad blocks, as a share of the courses the solver assigns to the program. `max_quarters` counts Autumn/Winter/Spring quarters with enrolled courses. **On a partial plan these stay errors** (the spec lists V09 as Error); the messages give the distance ("has 1200 so far (3000 to go)") and `Report.progress` is filled regardless, including rows under the pseudo-program `college` (`college/total_units`, `college/units_by_enrollment`). Null policy values are skipped and listed in `assumptions`. |
| V10 | Warnings. The Core is satisfiable by courses on or before `core_complete_by`; a later Core course still counts when it is in or before plan year `civ_abroad_year` and is used by a `study_abroad_block` program of the plan or sits in the term of a `study_abroad` goal. Same test for a program's `timing.complete_by`. `timing.apply_requires` courses must be done strictly before `timing.apply_by`. |
| V11 | One predicate per goal type (`planner_core/goals.py`). Hard goal failed: error. Soft goal failed: warning with a score in [0, 1]. Per-term goals with career scope look at every Autumn/Winter/Spring quarter that has courses. A `language` goal needs `courses` or `list`. `interest` counts courses not assigned to a `slot` as electives. `workload_hours` uses `ci_high` when the goal is `strict` or `options.strictness` is `strict`. Missing attribute values count 0 and are listed in `assumptions`. |
| V12 | A Pass/Fail course is never eligible for a unit under `no_pass_fail`. It is an error only where the plan relies on it: the course would fit a requirement that is still unmet, or the program is unmet and would be met if its Pass/Fail courses had letter grades (one extra exact solve of that program alone; this catches the case where the solver filled the course's own requirement with another course and left a different one open). |

**Rule trees.** A *unit* is a slot, a select, or one part of a bounded_parts node. `no_pass_fail`, `min_grade` (strictest wins) and `allow_double_count` on a group or bounded_parts node apply to every unit below it. Within a program a course fills one unit, unless the unit allows double counting. Set constraints apply to all courses used below the node that carries them: `same_sequence` (all in one sublist of the lists the selectors name; a node whose selectors name no list with sublists cannot be satisfied), `in_order` (two courses of one subject in ascending number order and strictly increasing terms), `max_from` (cross-list groups, or the code as written with `as_enrolled`), `distinct_subjects` (subject of the code as written in the plan). A slot takes exactly one course, a select by count exactly `count`, a part at most its maximum; the parts of a bounded_parts node sum to exactly `total.courses` (or at least `total.units`). An `n_of` group activates at most n children; the others take no courses.

**Solver.** Share limits are soft in the model. Objective: (1) maximize the weighted number of satisfied nodes, a node outweighing its whole subtree; (2) break as few rules as possible (courses shared beyond a limit, residency); (3) use as few courses as possible. Two solves: first with every root required (exact; every certificate comes from this one), and only if that is infeasible the full objective under a deterministic work limit. If the second solve stops before proving optimality, the unmet nodes it reports are still true, and `assumptions` says the list may not be the smallest. Single-threaded, so equal inputs give equal reports. Progress shown for an unmet unit is a greedy pick of unused eligible courses and is display-only.

**Checker.** `check_certificate` accepts when: the plan hash and the rule hashes match; every assigned course is in the plan, matches its unit's selector and grading rules; a course fills one unit per program unless double counting is allowed; every program root is satisfied by the assignments, set constraints included; every share limit holds; every planned or in-progress course with a requisite has a witness that cites only facts of the plan and suffices; loads and goal results recompute to the same values and no hard goal fails. It does not re-check V01, V02, V04-V06, V09 or V10, which are lookups in the report. Witness tokens: `CODE@TERM`, `credit:CODE`, `placement:VALUE`, `standing:VALUE`, `program:GLOB`, `consent:VALUE`.

**`POST /verify`.** Loads, for each `plan.programs` entry, the `program_version` of the plan's catalog year (a bound `version_id` must be that row), `published` only unless `show_unpublished_programs`; anything else is a 422 in FastAPI's validation-error shape (`loc` points at the program). The catalog is loaded as the subset the plan can touch (`api/repo/rules.py`). Attribute values are read with `subject_type = course` and `subject_id` = course code. Cache key `verify:{core_version}:{digest}:{plan_hash}`, where the digest hashes the loaded rules, catalog facts and request options; TTL one hour; Redis errors are logged and ignored.

## Plan generator (prompt 06)

`planner_core.generator.generate(plan, rules, catalog, options) -> GenerateResult` is pure and has no LLM.

**What it keeps and what it decides.** Completed, in-progress, credited and locked courses never move, and neither do courses outside the quarters being planned. Unlocked planned courses inside those quarters *float*, along with a pool of catalog courses: the solver decides whether each one is placed, and where. The pool holds:
- the courses that can fill the plan's requirements: the best few per requirement, and whole sequences for sequence lists;
- the courses a goal names, and the prerequisites of everything in the pool;
- forty free electives.

Requirement placeholders (`slot_ref` items) in those quarters are replaced by real courses. Summer is never planned, and with `today_term` nothing is placed before the current quarter. Scope "remaining" starts at `today_term`; "selected" uses only `selected_terms`.

**Model.** The model has a variable `place[c, t]` per pool course and quarter, and a course is placed at most once (a repeatable course gets two enrolments). Constraints:
- Prerequisites must be met by earlier quarters, and co-requisites by the same quarter or an earlier one. Placement, standing and program atoms are read from the plan; consent never blocks, but such courses are less preferred.
- `p_offered` >= 0.3 unless the student accepts the course in `allow_rarely_offered`. Where a quarter has a posted schedule, a course must appear in it.
- Every quarter that has courses is full time, within the College maximum. A 500-unit quarter is allowed only with `allow_overload`, and only where the plan already claims an overload reason that applies.
- Program satisfaction reuses the V07 model (`solver.ProgramModel`, which now lets the caller decide `in_order` for floating courses). Sharing limits, residency and graduation totals (units, units by enrollment, number of quarters) also hold.

**Goals.** Goals are compiled by `goalcompile.compile_goals`, following the table in SPEC "Goal predicates":
- hard bounds: `course_load`, `graduate_by`, `light_quarter`, and `workload_hours` / `difficulty_cap` when the goal is hard;
- rewards: `challenge`, `interest`;
- penalties: `protect_gpa`, and soft `workload_hours` / `difficulty_cap`;
- a pinned block: `study_abroad`;
- precedence: `bxms` (its program's `apply_requires` before `apply_by`), `premed`, `language`.

**Objective.** The objective adds up:
- the preference of each placed course, minus a cost per course that is larger than any preference, so nothing is added that no rule, goal or full-time load needs;
- a bonus for keeping the student's own courses, especially in their quarter;
- goal rewards and penalties, and the load slider (lighter spreads courses out; heavier finishes sooner);
- a penalty on the peak weekly workload and on Core courses after the Core deadline.

Default preferences (`preferences.py`) rank by interest match (tags, Core areas, title words), then forum `recommend_rate`, then lower course level. `options.preferences` (prompt 07's agent) overrides them for the courses it names.

**Variants.** There are up to three variants, each differing from every earlier one in at least four placements. Each variant goes through `verify_checked`, which runs `verify` and then `check_certificate`. A variant that has errors or a rejected certificate is dropped, and an `ALERT` is logged, because that would be a bug in the generator. Each variant comes back with its verified plan, the change operations from the current plan (`apply_ops` reproduces the plan), the report and its metrics (`avg_hours` and `hardest_quarter_hours` are what the UI reads).

**Time.** `time_limit_s` (default 4 s; the API clamps it to 5 s) is the solver budget for the whole call:
- The solver first looks for any plan, without an objective (15% of the budget).
- On large instances it falls back to a staged solve (60%): it places what the programs and goals need without the graduation totals, keeps those placements, and adds only the electives the totals still need.
- It then improves the plan from that starting point (10%).
- The remaining variants share the last 15%.

The 20 synthetic profiles in `services/api/tests/test_generate_profiles.py` each finish in under 5 s. Each profile must produce either verified plans or an explanation naming its exact conflicts; a time-out message is a test failure.

**Limits.**
- A plan with more than 200 items, or with quarters more than 8 years from its entry quarter, is refused.
- Generation is limited to 200 requests per IP per day, and to 100 per account per day for saved plans.
- Before solving, an exact capacity check compares the units still needed to graduate with what the open quarters can hold under the unit and course limits. When they fall short, it names the limits that make the difference.

**Impossible requests.** Every hard goal and limit is an assumption literal: each program, sharing, offerings, loads, courses per quarter, graduation, the prerequisites of locked courses, and each hard goal. When the solve is infeasible, the solver returns a core of those literals, and the generator shrinks it to a minimal set (budgeted). The result is said in plain English:
- for a too-early `graduate_by`: "Graduating by Spring 2029 needs 5 more courses than your remaining quarters allow";
- for a program that can't be completed: the requirements still missing, plus a hint when the blocker is a missing placement result;
- otherwise, the goals that can't all hold together.

**Saving a plan.** `PATCH /plans/{id}` with a `state` saves the whole plan, items included. Items keep their ids (they are updated in place), so change sets that target items by id stay valid across saves. `PATCH /plans/{id}/items` remains the way to make small edits guarded by the plan hash.

**Change sets in the API.** A change set is applied only while the plan still hashes to its `base_plan_hash`. Otherwise it is marked `stale`, re-previewed against the current plan, and the request gets a 409. A request whose own `base_plan_hash` is outdated gets a 409 without changing the change set. `ChangeSetApply.terms` applies only the operations that touch the selected quarters. Typed confirmations (`confirmation_text`) are described under "Agents (prompt 07)".

**Frontend.** The Generate popup uses the generator selected by `VITE_GENERATOR_MODE`: `deterministic` (the default until prompt 07), or `agent`, which streams `/agents/generate`. In deterministic mode:
- A plan saved to the account, and unchanged since it was saved, uses `POST /plans/{id}/generate`, and Apply goes through the change-set endpoint.
- Any other plan uses `POST /plans/generate`, and the browser applies the operations itself.

## Agents (prompt 07)

**Gateway (`packages/llm_gateway`).** `LLM.structured(task, ...)` (the contract prompt 08 uses) is unchanged; agent harnesses use `run_agent(llm, AgentSpec)`: a Messages-API tool loop with a fixed tool list, a `submit_*` tool validated with Pydantic (one repair turn with the error, then `AgentError("invalid_output")`), and a `Budget` of tool calls, tokens and seconds (`budget_*` failures). The `submit` tool does not count as a tool call. Provider errors count per run: after `fallback_after_errors` (2) the run moves to OpenRouter; a 4xx other than 429 counts as both at once. Every model call becomes a `CallRecord` (task, model, prompt version, tokens, cost from `prices` in `llm_routing.yaml`, latency, ok) with no user identifier. `AgentError` is an `LLMUnavailableError`, so one `except` covers every fallback. `FakeLLM.run_agent` replays scripted turns (`ToolCall`, lists of them, `FakeTurn`, text, exceptions) through the same loop. The API installs the real `Gateway` only with `LLM_LIVE=true` and a provider key.

**Requests.** Anthropic: no `thinking` parameter (adaptive), `output_config.effort` from the routing file, `tool_choice: auto`, `strict` tools, no sampling parameters, no prefill; the system block carries `cache_control` (caching tools + system) and top-level automatic caching covers the conversation. `refusal_fallback: true` uses the beta `fallbacks: "default"`. OpenRouter gets the same history in the OpenAI format (thinking blocks dropped).

**Events.** `AgentEvent` gained `infeasible` (`message`, `conflicts`) and `confirm` (`change_set`, `confirmation_text`); `variant` gained `citations`. `GenerateRequest` gained `today_term`; `ChatRequest` gained `history` (the browser's last 12 turns, for a plan not saved) and `latest_proposal` (the browser's newest open card, for a plan not saved).

**`POST /agents/generate`.** Steps, in order: "Loading requirements", "Choosing electives" (LLM; on failure `failed` then "Using the default elective ranking" `done`), "Solving", "Verifying" (`failed` when the generator dropped a variant), "Writing rationale" (LLM; `failed` means no rationale), then `infeasible` or one `variant` per plan, then `done` with the `agent_run` id. Step 3 offers the model the unmet requirements with two or more candidates (up to 12, 40 candidates shown each); its picks must be candidates of that requirement. Step 6 must echo each quarter's exact course set, else that variant's rationale is dropped; texts over 25 words get the repair turn. With `plan_id` of the caller's saved plan, and the request's plan hashing like it, variants are stored as proposed change sets; another account's plan is a 404. Limits: 10 per account per day, 3 per client address per day logged out (Redis counters keyed by a hash of the address and the day, 24-hour TTL).

**`POST /agents/chat`.** A typed confirmation is parsed first, without a model (`api/agents/confirm.py` documents the grammar). "apply it" names the latest open proposal (a saved plan's newest `proposal` chat message, or the browser's `latest_proposal`); "I agree to ..." must equal that proposal's operations or be fully explicit (every course with every quarter it touches), in which case a new change set (`origin: user`) is drafted. Either way the plan must still have the proposal's hash, and the answer is a `confirm` event: the browser applies it, through `POST /plans/{id}/changesets/{cs}/apply` with `confirmation_text` for a saved plan (the server parses the text again and checks it names this change set). Other messages go through the scope gate (`off_topic` and `suspicious` get fixed one-line replies without the main model; a failed gate counts as `in_scope`), then the advisor (`a2_advisor_chat`, or `a2_advisor_chat_escalation` when the gate asks for a whole-plan comparison) with `get_plan`, `preview_ops`, `search_courses`, `get_course`, `get_program`, `get_forum_summary`, `get_forum_posts`, `compare_courses`, the draft tool `propose_change_set` (at most 2 per answer, stored only after the answer validates) and `submit_answer`. Citations are `kind:id` pairs; any not returned by a tool in the run are dropped and logged. Limits: 60 messages per account per day, 30 per client address logged out.

**History.** A saved plan has one `agent_run` of kind `chat`; `chat_message.role` is `user`, `assistant` or `proposal` (content = change-set id). Messages older than 30 days are deleted at the start of every chat request and never read. A plan that lives in the browser stores nothing on the server.

**Prompts and evals.** `prompts/a1_preferences.md`, `a1_rationale.md`, `a2_chat.md`, `a2_scope.md` start with `id`, `version` and `task`; `llm_call.prompt_version` is `<id>@<version>`. Forum text reaches a model only inside `<untrusted_source id="post:N|summary:N">`, HTML-escaped so it cannot close the tag. `evals/` holds the sets (built from the seed by `evals/build_sets.py`) and the runner; `make evals` refuses without `CONFIRM_SPEND=yes`.

**Frontend.** `VITE_GENERATOR_MODE` now defaults to `agent`. The agent mocks for vitest and e2e live in `apps/web/src/mocks/agents.ts`.

## Forum -> course attributes (prompt 11)

**When it runs.** `api.attributes.job.run_nightly` runs every night at 03:30 as an Arq cron job (`worker.main.nightly_attributes`); run it by hand with `make attributes`. It writes one `attribute_value` row per subject and key, replaced each night. A subject is a course (`subject_id` = course code) or a course x instructor page (`subject_id` = the page id). The course page, the forum and the planner read those rows.

**The numbers** (`aggregate.py`). Each value is `(k*m + sum(w*r)) / (k + sum(w))`:
- The prior m is the department average when the department has at least 3 ratings (k = 5), else the course's cold-start estimate (k = 2, "weighted as 2 ratings"), else nothing (k = 0).
- Weights: a structured rating counts 1, a value pulled from post text 0.5, and anything older than 4 years 0.5.
- The confidence interval is the value plus or minus 1.96 standard errors, clamped to the scale.
- Forum-derived values are published only when n >= 3 (method `blend`, or `forum` with no prior). Below that, the row holds the estimate (method `prior`, n 0), and the UI labels it an estimate.
- Attributes updated: workload hours, difficulty, intellectual intensity and recommend rate. Pace and grading strictness have no forum source yet.

**Agent A3** (`a3.py`, prompts `prompts/a3_*.md`). Every answer is checked by code before it is used:
- **Extraction (Haiku):** every quote must appear in the post, and a workload number must appear in its quote. Difficulty words map to easy 2, moderate 3, hard 4, very hard 5.
- **Summary (Sonnet):** at most 120 words; every `[n]` marker must point into the citation list, and only posts the model was given may be cited. The A4 classifier must then return `ok`; when moderation is unavailable, nothing is published. Summaries are rebuilt after 3 new visible posts or after 30 days.
- **Cold start (Sonnet):** a rubric gives workload and difficulty from the description and level, stored as an estimate. Only courses that have a forum page get one, at most 200 a night.

Post text is passed to the model inside `<untrusted_source>`, and these calls hold no tools. Without a model, the job skips the A3 steps and aggregates the structured ratings only.

## Catalog ingestion (prompt 09)

**Where it lives.** `services/worker/worker/ingest/` (see its `__init__.py` for the module map). It imports the API package for the database models, the seed loader and the prompt loader; the API never imports the worker.

**Crawler.** `Crawler` fetches only the hosts it is given, reads robots.txt once per host (404 allows everything; 401, 403, 5xx or a network error skips the host), waits at least 1 second between requests (a longer `Crawl-delay` wins), and sends `QuarterlyCatalogBot/0.1 (...; contact: <CATALOG_CONTACT_EMAIL>)`. It refuses to start without a contact address and never logs it. Every response, robots.txt included, is a snapshot: bytes in MinIO (S3 API, SigV4, key `catalog/<sha256[:2]>/<sha256>`), a `source_snapshot` row with url, time, sha256, key and content type. Snapshot ids in rule trees are `source_snapshot.id` as a string.

**Agents.** All go through `llm_gateway` with tasks from `llm_routing.yaml` and prompts in `prompts/` (header `id`, `version`, `task`):

| Agent | Task | Prompt | Tools | Output |
| --- | --- | --- | --- | --- |
| E1 prerequisite | `e1_prereq_formalizer` | `e1_prereq` | none | `E1Answer` (DSL expression or `unparseable`) |
| E2 enumerator | `e2_program_enumerator` | `e2_enumerator` | `list_pages`, `read_snapshot` | `submit_programs`: `ProgramCandidate[]` |
| E3 run A | `e3_program_formalizer` | `e3_formalizer` | `read_snapshot`, `lookup_course`, `get_course_list`, `validate_rules` (5 calls), `run_golden` | `submit_rules`: YAML that passes (a)-(c) |
| E3 run B | `e3b_second_opinion` | `e3b_formalizer` (same sections, reordered) | same | same |
| E4 judge | `e4_backtranslation_judge` | `e4_backtranslation` | none | `E4Answer` (English + differences by node path) |

Page text reaches every agent inside `<untrusted_source id="snapshot:<id>">`. No agent holds a write tool. Every run is an `extraction_run` row and every model call an `llm_call` row. `Metered` wraps the client with the spending cap (`INGEST_COST_CAP_USD`).

**Checks.** E1: the expression parses, every course exists, every course number appears in the sentence, no self-reference; otherwise a `requisite` review item. E2: the candidates must match at least two independent lists built by code (the College's stated counts, counted as distinct `family` names per type, so a BA and BS are one major; the Programs of Study index, every URL both ways; the A-Z index, candidates must be on it). Any mismatch writes an `ingest_run` review item and stops the run. E3: validators (a) schema with a source on every node, part, cap and policy entry; (b) courses and lists exist; (c) quotes verbatim after decoding entities and collapsing whitespace; (d) run A and run B agree node by node; (e) E4 found no difference; (f) golden plans in `data/golden/<program>/` behave as expected; (g) a major needs 9-19 courses (the fewest courses that satisfy the tree). (a)-(c) must pass for E3 to submit; (d)-(g) become flags in the review item.

**Node-level agreement** (`compare.node_agreement`). A node agrees when its kind, counts, courses, selectors and constraints match; labels, ids, quotes, `needs_review` and weights are ignored, and so is the order of codes in a list. Children are paired by id, then by identical subtree, then by position. The policy counts as one extra node. Agreement = agreed / (reference nodes + extra candidate nodes).

**Review items written by the pipeline** (`review_item.diff.kind` = `target_type`):
- `program_version` (target id = the version id): `rules`, `second_run_rules`, `previous`, `nodes[]` (path, kind, label, summary, quote, url, snapshot_id, flags), `checks[]` (id, name, ok, skipped, problems), `backtranslation`, `agreement_runs`, `changes_from_previous`, `decision_hint` (`review` or `carry_over`), `snapshots`, `cost_usd`. The version itself is written with status `review`; an existing `published` version for the same program and year is never touched (the item then has `program_version_id: null` and `blocked`).
- `course_batch` (target id `<year>:<subject>`): `courses[]`, `added`, `changed[]` (fields before/after), `removed`, `crosslist_groups`, `relations`, `requisites` (E1 results that passed), `unchanged`.
- `requisite` (`<year>:<code>`): `raw_text`, `proposed`, `proposed_text`, `errors`, `source`.
- `ingest_run` (`<year>:<step>`): `step`, `problems` (a blocked enumeration, a program E3 could not formalize, pages not fetched, course blocks that did not parse, the spending cap).
- `catalog_change` (`<year>:<day>`): `changed[]` (url, before and after sha256) and `new_pages` from the monthly check.

**Carry over.** When the new tree means exactly what last year's published tree meant and last year's quotes are still on this year's pages, the version holds last year's tree (catalog year updated) and the item says "unchanged"; it is still a curator who publishes it.

**Review API** (admins only; `X-CSRF-Token` on every POST; `Cache-Control: private, no-store`):
- `GET /admin/review-items?status=open|accepted|rejected` returns `Page[ReviewItemOut]`. `ReviewItemOut` adds typed `title`, `program_version_id`, `program_version_status`, `decision_hint`, `nodes` and `checks` read from the diff.
- `POST /admin/review-items/{id}/decision` with `{decision: accept|edit|reject, edited?, note?}`. Only open items (409 otherwise).
  - `program_version`: accept marks it ready; edit takes `edited.rules` (validated as `ProgramRules`, every node sourced, same id and year) and replaces the version's rules; reject sets the version to `draft`.
  - `requisite`: accept or edit (`edited.prereq`) upserts `requisite`; the course must exist.
  - `course_batch`: accept upserts the subject's courses, cross-list groups, relations, offering patterns and prerequisites for the new year; edit is refused (422).
  - Other types (including the schedule pipeline's) only record the decision; an edit is kept as `diff.edited_content`.
- `POST /admin/program-versions/{id}/publish`: the version must be in `review`, with no open item about it and not every item rejected. It sets `published`, `verified_by` (the admin's username) and `verified_at` (day). This is the only way a version reaches students.

**Jobs.** `worker.ingest.jobs.cron_jobs()` registers the annual run (1 August, 04:00) and the monthly check (the 15th, 04:00) only when `CATALOG_INGEST_ENABLED=true`; the job functions also check it. Without `LLM_LIVE=true` the annual run still crawls and stages courses, and files one item saying the agents were skipped.

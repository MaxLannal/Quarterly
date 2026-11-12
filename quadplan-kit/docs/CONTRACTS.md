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
| GET | `/instructors`, `/instructors/{slug}` | | `Page[InstructorSummary]`, `InstructorDetail` | Yes | 08 |
| GET / POST | `/plans` | `PlanCreate` | `PlanSummary[]` / `PlanOut` | Yes | 04/06 |
| POST | `/plans/import` | `PlanImport` (logged-out plans) | `PlanSummary[]` | Yes | 04/06 |
| GET | `/plans/compare?a&b` | | `PlanComparison` | Yes | 06 |
| GET / PATCH / DELETE | `/plans/{plan_id}` | `PlanUpdate` | `PlanOut` / 204 | Yes | 04/06 |
| POST | `/plans/{plan_id}/duplicate` | | `PlanOut` | Yes | 04/06 |
| PATCH | `/plans/{plan_id}/items` | `ItemsPatch {base_plan_hash, ops[]}` | `PlanOut` | Yes | 04/06 |
| GET | `/plans/{plan_id}/changesets` | | `ChangeSet[]` | Yes | 06 |
| POST | `/plans/{plan_id}/changesets/{changeset_id}/apply` | `ChangeSetApply` (`terms` = apply selected quarters) | `PlanOut` | Yes | 06 |
| POST | `/plans/{plan_id}/changesets/{changeset_id}/discard` | | `ChangeSet` | Yes | 06 |
| POST | `/verify` | `VerifyRequest {plan: PlanState, options}` | `Report` | No | 02 |
| POST | `/agents/generate` | `GenerateRequest` | SSE stream of `AgentEvent` | No (rate-limited) | 06/07 |
| POST | `/agents/chat` | `ChatRequest` | SSE stream of `AgentEvent` | No (rate-limited) | 07 |
| GET | `/forum/pages?course&instructor`, `/forum/pages/{page_id}` | | `ForumPageOut` | Yes | 08 |
| GET / POST | `/forum/pages/{page_id}/posts?kind&sort&term` | `PostCreate` | `Page[PostOut]` / `PostOut` | Yes | 08 |
| GET / PATCH / DELETE | `/forum/posts/{post_id}` | `PostUpdate` | `PostDetail` / `PostOut` / 204 | Yes | 08 |
| POST | `/forum/posts/{post_id}/comments` | `CommentCreate` | `CommentOut` | Yes | 08 |
| POST | `/forum/votes` | `VoteIn` | `VoteOut` | Yes | 08 |
| POST | `/forum/reports` | `ForumReportIn` | `ForumReportOut` | Yes | 08 |
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

**Selector semantics.** A course matches when it is not excluded and every criterion that is set holds: `codes` (any), `subject`, `number_range` (inclusive, 5-digit number), `tags` (any), `list` (named list, sublists included), `union` (any sub-selector). A course's tag set is its `tags` plus `core:<t>` for each of its `core_tags`, so `tags: [core:arts]` matches a course with `core_tags: [arts]`. Matching and exclusion work on cross-list groups, so a cross-listed code matches wherever its partner does. Union is the only way to say "A or B" across criteria.

**Sequences.** `same_sequence` needs to know which courses form a sequence. `course_list` gains `sublists`: a list such as `core-huma-sequences` has one sublist per sequence; `same_sequence` means every course used by the node comes from one sublist. The DB column is `course_list.sublists text[]` next to `course_ids bigint[]`.

**RuleSet vs Catalog.** `verify(plan, rules, catalog, options)` takes the *rules* (program versions, College policy, requisites) separately from *catalog facts* (courses, cross-lists, relations, course lists, terms, offering patterns, sections, attribute values), because rules are versioned and hashed into certificates while catalog facts are lookup tables. `check_certificate(plan, rules, catalog, certificate)` takes the catalog too: matching a course to a selector needs subject, number, tags and list membership.

**College policy as data.** `CollegePolicy` holds the College-wide numbers (4200/3800 units, 300-400 full-time, 500 overload and its reasons, Core timing, residency). Every non-null value must carry a source in `sources[field]`; a null value means "not encoded yet" and the check reports that as an assumption instead of guessing. Stored in an added `college_policy` table (one row per catalog year). Overload reasons can state the plan year, a qualifying course selector, or a minimum course size, so V05 can check them.

**Goals are a discriminated union** on `type` (all 12 goal types in the spec table), each with typed parameters; the DB keeps `type` + `params` JSONB. Term-scoped goals must set `term`; career goals must not. Goal deadlines accept relative terms (`Y3-WI`) or absolute ones; `planner_core.terms.resolve_term_ref` converts.

**Report extras.** Besides the spec's status, issues and certificate, `Report` carries `progress` (per-node have/need for the planner's requirement rail), `assumptions` (e.g. planned courses assumed to meet grade minimums) and `plan_hash` / `core_version` (the cache key). `VerifyOptions.checks` restricts which V-codes run; golden plans that test one program in isolation use it to skip loads (V05) and graduation totals (V09).

**Hashes.** `plan_hash` is the SHA-256 of the canonical JSON of a `PlanState` with item ids dropped and lists sorted, so reordering or renumbering items does not change it. `rules_hash` hashes a `ProgramRules`; certificate keys are `<program id>@<catalog year>`.

**Change sets.** Ops are `add`, `move`, `remove`, `lock` and `unlock`. Existing items are targeted by exactly one of `item_id`, `course` or `slot_ref`, plus a term to tell repeated courses apart. `planner_core.changes.apply_ops` is the single implementation: locked items cannot be moved or removed, and an ambiguous or missing target raises `ChangeOpError`. The server applies a change set only if the plan still hashes to `base_plan_hash`.

**Seed format.** `data/seed/<catalog_year>/` holds `terms.yaml`, `courses.yaml` and/or `courses/*.yaml` (`SeedCourse`: CourseLeaf block fields, plus `prereq` in the DSL, `prereq_text` verbatim, `crosslists`/`equivalents`/`mutually_exclusive`/`replaces`, `terms_offered`, a required `source`), `course_lists.yaml`, `college_policy.yaml` and `programs/*.yaml` (`ProgramSeed` = `ProgramRules` + name, type, degree, department, status, sources). `make seed` validates everything (every program node and part needs a `source`, every referenced course and list must exist; unknown courses in prerequisites are warnings) and then upserts idempotently. The fake fixture lives in `services/api/tests/fixtures/seed/2099-00/`.

**Offerings from "Terms Offered".** Until schedule data exists, a course's catalog "Terms Offered" line becomes `offering_pattern` rows with `method: catalog`: p = 0.95 for listed quarters (like a department's published plan) and 0.05 for unlisted Autumn/Winter/Spring. Courses without the line get no pattern (no V04 warning). This mapping is an open question.

**Golden plans.** `data/golden/<program>/*.yaml` (`GoldenPlan`): `expect: pass` means no error-level issues and a certificate that `check_certificate` accepts; `expect: fail` lists `expected_codes`, each of which must appear. The runner gives the verifier the College policy and the programs the plan lists (the Core only if listed). While `verify` is a stub, plans are reported as SKIP.

**Accounts (decision 5).** `account.email` (unique, lowercase) is the only column holding an email; a migration test enforces this. No blind-signature tables. User rows use day-level dates only (`*_day`), also enforced by a test.

**Program versions.** One `program_version` per program per catalog year (unique). Only `published` versions reach students; the seed loader writes the status in the YAML (default `review`).

## Verifier semantics (prompt 02)

Entry points in `planner_core`: `verify(plan, rules, catalog, options) -> Report` (pure, deterministic), `check_certificate(plan, rules, catalog, certificate) -> bool` (the trusted checker; `certificate_problems` gives the reasons), and `verify_checked(...) -> (Report, problems)`, which runs both. Anything that shows "Valid" must go through `verify_checked` (`POST /verify` does). Each module's docstring states the rules it implements; this section is the summary.

**Status and certificate.** `Report.status` is `errors` if any issue is an error, else `warnings`, else `valid`; `info` issues never change it. A certificate is attached only when it can be complete: no reported errors, prerequisites and program requirements hold, every listed program has rules, and every hard goal holds. `options.checks` filters which issues are reported, not what the certificate attests: prerequisites (V03) and program satisfaction (V07, V08) are evaluated for the certificate even when left out, so a must-pass golden plan may skip V05 or V09 and still get a certificate, while a plan whose hidden V03 or V07 fails gets none. `verify_checked` then runs the checker. A rejected certificate is dropped, the status becomes `errors`, and a V07 error says so (the API logs an alert and does not cache the report). A report without errors and without a certificate (a restricted run hiding a failed V03/V07/V08) is downgraded by `verify_checked` to `warnings` with a note, because it proves nothing. `include_certificate: false` only hides the certificate.

**Which programs.** Only the programs in `plan.programs` are checked. A listed program without rules is a V01 error. `PlanProgram.options` (track, specialization) is not read: tracks are programs of their own.

**Courses.** A cross-list group is one course everywhere. `equivalent` and `replaces` relations make two courses interchangeable for prerequisites and for "done by" deadlines, but not for selectors. Enrolled statuses (`planned`, `in_progress`, `completed`) carry quarter load and count as "by enrollment" and "in residence"; `transfer` and `exam` items and `credits` do not. A credit with `maps_to` counts as that course, taken before every term. A placeholder (`slot_ref`) counts 100 units (or its `units`) toward loads and totals and fills nothing.

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
| V12 | A Pass/Fail course is never eligible for a unit under `no_pass_fail`. It is an error only where the plan relies on it: the course would fit a requirement that is still unmet. |

**Rule trees.** A *unit* is a slot, a select, or one part of a bounded_parts node. `no_pass_fail`, `min_grade` (strictest wins) and `allow_double_count` on a group or bounded_parts node apply to every unit below it. Within a program a course fills one unit, unless the unit allows double counting. Set constraints apply to all courses used below the node that carries them: `same_sequence` (all in one sublist of the lists the selectors name; a node whose selectors name no list with sublists cannot be satisfied), `in_order` (two courses of one subject in ascending number order and strictly increasing terms), `max_from`, `distinct_subjects` (subject of the code as written in the plan). A slot takes exactly one course, a select by count exactly `count`, a part at most its maximum; the parts of a bounded_parts node sum to exactly `total.courses` (or at least `total.units`). An `n_of` group activates at most n children; the others take no courses.

**Solver.** Share limits are soft in the model. Objective: (1) maximize the weighted number of satisfied nodes, a node outweighing its whole subtree; (2) break as few rules as possible (courses shared beyond a limit, residency); (3) use as few courses as possible. Two solves: first with every root required (exact; every certificate comes from this one), and only if that is infeasible the full objective under a deterministic work limit. If the second solve stops before proving optimality, the unmet nodes it reports are still true, and `assumptions` says the list may not be the smallest. Single-threaded, so equal inputs give equal reports. Progress shown for an unmet unit is a greedy pick of unused eligible courses and is display-only.

**Checker.** `check_certificate` accepts when: the plan hash and the rule hashes match; every assigned course is in the plan, matches its unit's selector and grading rules; a course fills one unit per program unless double counting is allowed; every program root is satisfied by the assignments, set constraints included; every share limit holds; every planned or in-progress course with a requisite has a witness that cites only facts of the plan and suffices; loads and goal results recompute to the same values and no hard goal fails. It does not re-check V01, V02, V04-V06, V09 or V10, which are lookups in the report. Witness tokens: `CODE@TERM`, `credit:CODE`, `placement:VALUE`, `standing:VALUE`, `program:GLOB`, `consent:VALUE`.

**`POST /verify`.** Loads, for each `plan.programs` entry, the `program_version` of the plan's catalog year (a bound `version_id` must be that row), `published` only unless `show_unpublished_programs`; anything else is a 422 in FastAPI's validation-error shape (`loc` points at the program). The catalog is loaded as the subset the plan can touch (`api/repo/rules.py`). Attribute values are read with `subject_type = course` and `subject_id` = course code. Cache key `verify:{core_version}:{digest}:{plan_hash}`, where the digest hashes the loaded rules, catalog facts and request options; TTL one hour; Redis errors are logged and ignored.

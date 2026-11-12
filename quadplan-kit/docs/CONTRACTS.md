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

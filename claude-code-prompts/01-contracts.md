# Prompt 01 · Contracts (schema, DSL models, API surface)

> Recommended: Opus 5.5, effort `xhigh`. Plan mode first. Everything later builds on this, so take your time.

---

Read `CLAUDE.md` and SPEC sections "Data model", "Requirements DSL", "Verification engine" (inputs/outputs, certificate, goal predicates) and "Sitemap and every page" (API notes).

Goal: freeze the contracts so prompts 02-05 can run in parallel without colliding.

Do:
1. **Database.** SQLAlchemy 2 models and one Alembic migration for every table in SPEC "Data model", plus `course_list (id, catalog_year, name, course_ids[], source_id)`. Enable `ltree` and `pg_trgm`. Index course code, term, `course_instructor`, `plan_hash`. Day-level date columns where the spec says so.
2. **planner_core models** (`packages/planner_core/models.py`, Pydantic v2): Atom, Expr, the four Node kinds, Selector, Constraints, Policy, Source; PlanState, PlanItem, Credit, Goal (every type in the goal table), RuleSet, Report, Issue (codes V01-V12), Certificate, ChangeSet ops (add, move, remove, lock, unlock). Export JSON Schemas to `docs/schemas/`.
3. **Seed format.** YAML files under `data/seed/<catalog_year>/` for terms, courses, course_lists, programs, college_policy. A loader (`make seed`) that validates through the Pydantic models and upserts. Prove it with a clearly fake fixture (`TEST 10000`-style courses, one fake program); real data comes in prompt 05.
4. **API surface.** Every endpoint the spec implies, as FastAPI stubs returning 501 with correct request/response schemas: catalog (courses, course, programs, program, instructors), plans (CRUD, PATCH items, list), POST /verify, change sets (apply, discard), agents (POST /agents/generate and /agents/chat as SSE), forum (pages, posts, comments, votes, reports), auth (email, verify-code, issue, register, login, logout, account export/delete), admin (review queue, publish). Add `make api-client` generating the TypeScript client with openapi-typescript into `apps/web/src/api/`.
5. **Docs.** `docs/CONTRACTS.md`: one table of endpoints and one paragraph per non-obvious schema decision.

Tests: migration up and down; Pydantic round-trip of the YAML examples in the spec; loader on the fake fixture.

Done when `make check` passes and the schemas and generated client are committed. Run the `spec-reviewer` subagent, fix findings, update `docs/PROGRESS.md`.

# Open questions

Questions for Richard. Each has a default so work can continue; nothing here is a guessed catalog fact.

## Decisions (docs/SPEC.md "Summary and decisions to confirm")

1. **Decision 5 (accounts) — resolved 2026-11-12.** Richard edited row 5 to "Email and password
   is stored on the backend" and confirmed it: accounts store the verified `@uchicago.edu` email and
   an argon2id password hash; no blind signatures. CLAUDE.md and SPEC "Accounts and anonymity" were
   updated to match. Forum anonymity (per-page pseudonyms, HMAC author refs) is unchanged.
2. **Decision 12 (name).** The UI uses "Quarterly" / "Quarterly Planner". The forum name is written
   "Quarterly Forumn"; the UI uses "Quarterly Forum" assuming a typo. Code identifiers keep the
   neutral names (`planner_core`, `api`, ...); the Compose project and DB are `quarterly`.

## Infrastructure

3. **OpenRouter model names** in `llm_routing.yaml` (`anthropic/claude-opus-5.5` style) are not
   verified against OpenRouter's catalog; confirm before prompt 07. `max_tokens` values there are
   starting defaults, not from the spec.

## Contracts (prompt 01)

4. **"Terms Offered" to `p_offered`.** Until schedule data exists, listed quarters get p = 0.95 and
   unlisted Autumn/Winter/Spring get p = 0.05 (`method: catalog`), so V04 warns when a course is
   placed outside its catalog quarters. Confirm this mapping or give another.
5. **One `program_version` per program per catalog year.** Editing a published version in place
   would change plans made under it; v1 relies on review items for such edits. Revisit before
   prompt 09.

## Prompt 03 mocks

All handlers live in `apps/web/src/mocks/handlers.ts` (typed from the generated schema; data in
`mocks/data.ts`, a toy verifier in `mocks/verify.ts`). They run only in vitest, in Playwright e2e
(`VITE_MOCK_API=1` build) and in dev with `VITE_MOCK_API=1`; the Docker build calls the real API.
Mock data is deliberately fake (catalog year `2099-00`, `TEST`/`FAKE` courses, "Fake Program").
Remove each handler once its endpoint is real and the e2e test can run against seed data.

| Endpoint(s) | Mocked because | Remove when |
| --- | --- | --- |
| `GET /catalog-years`, `/terms`, `/courses`, `/courses/{code}`, `/course-lists/{name}`, `/programs`, `/programs/{id}`, `/programs/{id}/eligible` | 501 until M1 integration | M1 integration |
| `POST /verify` (toy checks: V01 prereq order, V02 unknown course, V04 offering, V05 > 4 courses, V07 per node) | 501 until prompt 02 lands | prompt 02 merged |
| `POST /agents/generate` (SSE: 5 steps, N variants, done) | 501 until prompts 06/07 | 06/07 |
| `POST /agents/chat` (SSE: message + citations, a proposal when the text says "add") | 501 until prompt 07 | 07 |
| `/auth/*`, `/account/*` (any login works; code `123456`; session flag in sessionStorage) | 501 until prompt 04 | prompt 04 |
| `/plans`, `/plans/import`, `/plans/{id}`, `/plans/{id}/items`, `/plans/{id}/duplicate`, `/plans/compare`, `/plans/{id}/changesets/*` (in-memory) | 501 in M1 | prompts 04/06 |
| `/instructors`, `/instructors/{slug}`, `/forum/*` (one fake instructor, empty threads) | 501 until prompt 08 | 08 |
| `/admin/*` (empty queues) | 501 until prompt 09 | 09 |
| `/health`, `/version` | completeness | any time |

## Prompt 03 frontend questions

6. **Logged-out session status.** The UI treats any non-200 from `GET /auth/session` (401 or 501)
   as logged out. Confirm prompt 04 answers 401 when there is no session.
7. **Generate variant metrics keys.** `VariantEvent.metrics` is a free dict; the UI reads
   `avg_hours` and `hardest_quarter_hours`. Pin these names in prompt 06/07 or tell the frontend.
8. **"Mark completed" has no op.** Change ops are add/move/remove/lock/unlock, so the planner marks
   an item completed as unlock (if locked) + remove + add with `status: completed`, keeping the
   lock. A `set_status` op would be cleaner for `PATCH /plans/{id}/items`.
9. **Course details in bulk.** The grid fetches `GET /courses/{code}` once per planned course
   (cached). A batch endpoint (`GET /courses?codes=...` returning attributes) would cut ~40 requests.
10. **Citation links.** `Citation.id` for `attribute` and `post` kinds has no documented format, so
    those chips are not links (only `course` and `program` chips link). Post chips need the course
    code and instructor slug to reach `/courses/{code}/i/{instructor}/t/{id}`.
11. **Goal chip defaults (user preferences, not catalog facts).** "Challenge me" = `challenge`
    with `min_index: 10`; "Light quarter" = `light_quarter` with `max_courses: 3`; "Lighter first
    year" = light quarters for Y1 Autumn–Spring; "Graduate in four years" = `graduate_by` Y4 Spring;
    "At most one very hard course per quarter" = `difficulty_cap` `max_very_hard: 1`. Adjust freely.
12. **Home search of instructors.** SPEC says the home page searches courses and instructors, but
    `/instructors` needs login; the home search covers courses only for now.
13. **Shared read-only snapshot** (planner state "read-only when viewing a shared snapshot") has no
    route or endpoint yet; not built.

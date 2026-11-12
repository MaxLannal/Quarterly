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

## Prompt 04

Choices made so work could continue; each is the conservative option and easy to change.

6. **Email provider.** `EMAIL_BACKEND=console` (development: prints the code and pending id, never
   the address) or `smtp` (stdlib `smtplib`, STARTTLS with certificate verification, works with
   any transactional provider). No provider SDK was added. Which provider, and the `EMAIL_FROM`
   address? The API refuses to start with the console backend, development secrets
   or a non-Secure cookie unless `ENVIRONMENT` is explicitly `development` or `test`.
7. **Plus-addressing and aliases.** Only plain `local@uchicago.edu` is accepted: no subdomains
   (`@cs.uchicago.edu`, `@alumni.uchicago.edu`) and no `+tag`, so one mailbox cannot verify
   several accounts. If real student addresses need either, relax `normalize_uchicago_email`.
8. **Rate-limit numbers** (`api/auth/ratelimit.py` and the `ip_limit(...)` on each route): 5 codes
   per address per hour, 5 wrong codes per pending id, 10 failed logins per login name per 15
   minutes, 10 failed password confirmations per account per 15 minutes; per IP per day: 40
   email/reset starts, 40 registrations, 100 code checks, 300 logins. IP limits are loose because
   campus networks share addresses. Confirm or tune.
9. **Client IP behind the proxy. Resolved (M1 integration).** nginx sends `X-Forwarded-For` and
   the `api` service sets `TRUSTED_PROXY_HOPS: "1"`.
10. **"IP counter never written to disk." Resolved (M1 integration).** Redis runs with
    `--save "" --appendonly no`.
11. **Session lifetime** is 30 days, fixed (not extended on use). Reset ends all sessions; a
    password change ends all but the current one.
12. **Forum identity.** `api.auth.hashing.author_ref(account_id, page_id)` implements the SPEC's
    `HMAC(server_key, account_id ‖ page_id)`; account deletion recomputes it per forum page to
    find an account's rows, so prompt 08 must use the same function for `author_ref`,
    `voter_ref` and `reporter_ref`. With "delete my posts", a comment that someone else replied
    to is blanked ("[deleted]", no author) instead of removed, so the replies survive; vote rows
    are removed but tallied scores are not recomputed. Confirm.
13. **CSRF for later prompts.** Every POST/PATCH/DELETE sent with a session cookie needs
    `X-CSRF-Token` (from `SessionOut.csrf_token`), enforced app-wide. Exempt: the pre-session
    `/auth/*` steps and the stateless `POST /verify`. Frontend code can use the client in
    `apps/web/src/features/auth/api.ts`, which adds the header.
14. **Plans API.** CONTRACTS lists `/plans` CRUD and `/plans/import` as "04/06"; prompt 04 built
    only the read path for `GET /account/export` (`api/auth/account_data.py`, which assumes
    `goal.params` holds the goal's type-specific fields). The rest is left to prompt 06.
15. **Suspended accounts** (`account.status`, `suspended_until`) can still log in; the forum
    (prompt 08) should enforce suspension where it matters.


## Prompt 05

Seed data for catalog year 2026-27 (fetched 2026-11-12). Each item says what was encoded meanwhile
(the strictest expressible reading); the nodes are marked `needs_review` in the seed and listed with
their quotes in `data/seed/REVIEW.md`. Numbered P05-n so parallel prompts do not collide.

**DSL / verifier gaps**

- **P05-1. `same_sequence` accepts any subset of one sublist.** A three-course sublist would also
  accept each of its pairs, and one course of a calculus pair passes the Core math part. For the
  physical sciences Core only three-course combinations whose every pair is itself approved were
  kept; 250 three-course combinations the catalog allows (PHSC 11600-11700 + any PHSC Core course,
  Astro 12000s triples, PHSC 18000s + any approved pair) are left out. Also not encoded: "the student
  must take two calculus courses" when calculus is used for the math Core. Option: a "whole sublist
  or nothing" / minimum-per-sublist constraint in the DSL.
- **P05-2. Group-level constraints.** `econ-ba/empirical` has `in_order`, and the three Bx/MS roots
  have `max_from` ("at most two courses from the 20000-level offerings"), on `group` nodes. Please
  confirm the verifier applies group-level constraints to all courses used under the group.
  *(M1 integration: confirmed, it does. See M1-1 for how cross-listed courses count toward the cap.)*
- **P05-3. Rules the DSL cannot express (left out):** "enrollment limited to first-year students"
  (a maximum standing; CHEM 10100/10200); "beyond their first year" for study abroad; HIST
  13500-13700 needs two *consecutive* quarters; Econ empirical methods "in consecutive quarters";
  "no more than one per quarter" for Bx/MS Reading and Research; "exactly three courses per
  quarter" and "3900 of 4200 units and all general education before the first Bx/MS quarter";
  grade averages (Math approved courses "overall C average", encoded as C in each); GPA rules.
- **P05-4. Placement-conditional rules.** CS: placing out of CMSC 14300 (CS 3 exam) means one extra
  elective; the Discrete Mathematics Placement Exam allows Theory BC / BCC. Math: the MATH
  15910/16300 requirement is waived when the first course is MATH 20700. Not encoded (no "if
  placement then" node); the standard path is required.
- **P05-5. `requires: ["cmsc-b?"]`** (Bx/MS Options 1-2) and `excludes: ["cmsc-b?"]` (Option 3) use a
  shell glob (`?` = one character) for "CS BA or CS BS". Confirm glob semantics and that `requires`
  means any-of.

**Catalog wording**

- **P05-6. Core timing.** The catalog says the Core "should be completed by the end of the second
  year"; encoded as `core_complete_by: Y2-SP` (V10 is a warning). `civ_abroad_year: 3` comes from the
  College's Core requirements PDF, which carries no catalog year. Keep both?
- **P05-7. Overload reasons.** "a 200-unit language course" is encoded as any course of 200+ units
  (no language-course list is seeded). "Reading and Research or B.A. Thesis/Colloquium course" uses a
  list built from course *titles* (CMSC 29700, CMSC 29900, ECON 29700, DATA 29700, HUMA 29700, ...);
  departments may have other thesis/colloquium courses. Who owns this list?
- **P05-8. Language Competence.** Only the course route is encoded, with FREN 10300 and SPAN 10300 as
  the only seeded "third course of a first-year language sequence". Exam, placement, AP/IB,
  study-abroad and proficiency routes are not plan items. Model them as `credits` that satisfy
  `core/language`, and seed every language's third quarter?
- **P05-9. Writing Grey track.** HUMA 19100 is one course number taken in two quarters; it is marked
  `repeatable` (the catalog says "two-quarter series", not "repeatable"). *(M1 integration: the
  verifier now counts each enrolment of a repeatable course, see M1-2.)*
- **P05-10. Computer Science.** BA electives must "span at least five curriculum areas", and areas and
  PhD Core/Elective designations are published only on course-info.cs.uchicago.edu, not in the
  catalog. Encoded: BA electives = any 8 CMSC 20000-29999 (breadth not checked); specialization lists
  exactly as printed; CMSC 300-level courses not accepted as major electives. May course-info be
  used as a second source?
- **P05-11. Bx/MS.** (a) The page names no course for "two Reading and Research courses"; encoded as
  two more CMSC 30000-level courses. (b) PhD-program Core Systems courses and MPCS Core Systems / Core
  Programming courses are not in the catalog; only the major's Systems list is used (graduate
  cross-listed numbers match through cross-listing). (c) Admission (3.5 GPA, B+ average in two intro
  courses) is not encoded; `apply_by: Y3-WI` from the January/February admissions cycle, no
  `apply_requires` because the requirement is a choice of pairs. (d) Titles of CMSC 37115, MPCS 50103
  and MPCS 55001 are taken from the requirement labels (no course block found).
- **P05-12. Mathematics.** "(or equivalent)" / "(or higher)" after the chemistry and physics
  sequences not encoded (honors chemistry and PHYS 13100/14100 are not accepted for the math majors'
  general education). MATH 29700 ("as approved") and Paris courses left off the approved list. PSCD
  "department" read as subject code; "GEOS courses not cross-listed as PHSC" and "reserves the right
  to exclude courses which are new in 2026-27" not encoded. BS minor field read as three courses in
  addition to the four PSCD courses.
- **P05-13. Economics.** (a) The Fundamentals table lists MATH 20420 as an alternative to MATH 15250
  but the Summary of Requirements does not; MATH 20420 not accepted. (b) Mixing standard and honors
  core courses not accepted. (c) ECMA courses counted on the strict side of "at least two economics
  courses numbered higher than ECON 20210" (with outside electives and ECON 10200, at most 2 of 4).
  (d) Booth 3xxxx alternates of the pre-approved BUSN courses not encoded. (e) Only the standard
  track is seeded; the three specializations are not.
- **P05-14. Study abroad.** The Córdoba and Paris (Migration, Decolonization, and Diaspora) programs
  include a Spanish / French course with no course code on the program page; not encoded. Only these
  two civilization programs abroad are seeded, so `core-civ-sequences` accepts only them abroad.
- **P05-15. Cross-list copies.** 366 Equivalent Course codes have no block on the fetched pages; they
  are seeded as copies of the block that names them (same title, units, prerequisites, terms). OK, or
  fetch every subject page?
- **P05-16. Prerequisites.** 261 prerequisite sentences are not formalised (none on a course a slot
  names; mostly BIOS, SOSC, BUSN, ARTH, STAT and graduate CMSC electives); they keep `prereq_text`
  and `needs_review`. Sentences addressed only to master's/graduate students were dropped. Run agent
  E1 over these, or hand-encode?

**Infrastructure note (not a catalog question)**

- **P05-17. `make golden` was slow. Resolved (M1 integration).** `golden.py` now parses the seed
  once per catalog year.
- **P05-17b. Still open:** `golden.py` still runs `build_catalog` once per plan; building it once
  per catalog year would shorten `make golden` further.

## Prompt 02

Verifier readings that are choices, not catalog facts. Each is implemented as stated (see
`docs/CONTRACTS.md` "Verifier semantics") and can be changed in one place.

1. **V02 levels.** The spec lists V02 as Error, so "exam credit forfeited when the course is also
   taken" is an error (remove the credit or the course), and so is taking two courses related as
   `equivalent` or `replaces`. Should forfeiture be a warning that just stops counting the credit?
2. **`equivalent` vs cross-listing.** The catalog's "Equivalent Course(s)" line is the cross-list
   line and belongs in `crosslists`. The verifier lets `equivalent` / `replaces` partners satisfy
   prerequisites and deadlines, but selectors match on cross-list groups only (contract). Confirm.
3. **V05 on quarters in progress.** Empty quarters and Summer are not flagged; a quarter with one or
   two courses is an error (below full time); a quarter whose courses are all `completed` reports
   as info. Should a half-built future quarter be a warning instead of an error?
4. **Civilization abroad in third year (V10).** `CollegePolicy` only has `civ_abroad_year`. A late
   Core course is excused when it is used by a `study_abroad_block` program of the plan, or sits in
   the term of a `study_abroad` goal. Is that the right test, or should courses carry a tag?
5. **Share limits are per pair of programs** ("at most 0 with each major"), as in the spec formula.
   Some rules may mean "in total across all minors"; the DSL cannot say that yet.
6. **Residency.** "Half of each program in residence" is measured on the courses the solver assigns
   to the program; the Core and study-abroad blocks are exempt from the College-wide share unless
   the program states its own. Confirm against the Graduation Requirements page.
7. **`in_order` and `distinct_subjects`.** `in_order` compares courses of one subject by course
   number and needs strictly increasing terms; `distinct_subjects` uses the subject of the code as
   written in the plan (a cross-listed course counts under the code the student enrolled in).
8. **Attribute values.** `/verify` reads `attribute_value` rows with `subject_type = course` and
   `subject_id` = course code; prompts 08/11 must write them that way. Default thresholds when a
   goal sets none: "very hard" = difficulty 4.0 or more, "strict grading" = 4.0 or more (1-5 scale).
9. **Graduation totals count placeholders** (100 units each) so a plan with unfilled slots shows
   the units it intends; V07 still fails until they are filled. Confirm.
10. **Incomplete plans and the solver.** Whether the programs are satisfied is decided exactly. For
    an incomplete plan the list of missing requirements comes from a second solve with a
    deterministic work limit; on very hard instances it may not be the smallest list, and the
    report says so. The benchmark instance (60 courses, 201 nodes, 3 programs) is proven optimal.
11. **`VerifyOptions.strictness`.** `strict` currently only makes workload goals use the upper
    confidence bound. Should it also turn V04 / V10 warnings into errors?

## M1 integration

Decisions taken while making the nine failing golden plans pass. Each is implemented and tested;
please confirm or overturn.

- **M1-1. Level caps and cross-listed courses (`max_from.as_enrolled`).** The contract matches
  selectors on cross-list groups, so "at most two courses from the 20000-level offerings" also
  counted CMSC 33550 (cross-listed with CMSC 23500) and CMSC 33380 (with CMSC 23380). Under that
  reading Bx/MS Option 3 cannot be satisfied at all from the seeded lists: it needs three Core
  Systems courses and every course on the major's Systems list is a 20000-level number (the PhD and
  MPCS Core Systems lists are not in the catalog, P05-11b). The prompt-05 golden plans assumed the
  other reading: a course counts under the number the student enrolled in. Implemented as an
  opt-in flag on the limit (`as_enrolled: true`, set on the three Bx/MS roots only, still
  `needs_review`); every other `max_from` (e.g. the Economics ECMA / outside-elective caps) keeps the
  stricter group reading. To confirm with the department: does a cross-listed course taken under
  its 30000-level number escape the 20000-level cap? If not, Option 3 needs the PhD / MPCS Core
  Systems lists before any plan can pass.
- **M1-2. Repeatable courses count once per enrolment.** `core/writing/grey` is `count: 2` from the
  single code HUMA 19100, which no plan could satisfy while a course counted once. Each enrolment
  of a `repeatable` course is now a course of its own for program requirements (the n-th counts
  only in the unit where the (n-1)-th does). This also lets CMSC 29700 / CMSC 29900 taken twice
  count twice toward electives; the CS majors already cap each at one with `max_from`. Is "counts
  once per enrolment" right for every repeatable course, or should the DSL say how often?
- **M1-3. V12 when another course takes the Pass/Fail course's place.** `cmsc-bxms-2/fail-03`
  (Algorithms CMSC 37000 taken Pass/Fail, CMSC 27200 also in the plan) reported only V07 on Core
  Systems: the solver put CMSC 27200 in the Algorithms slot, which pushed the plan over the
  20000-level cap elsewhere. V12 now also fires when the program is unmet but would be met if its
  Pass/Fail courses had letter grades (checked for that program alone, share limits ignored).
- **M1-4. A share-limit must-fail for Bx/MS Option 1 needs a 30000-level number.** Discrete,
  Algorithms and ML taken as CMSC 27100 / 27200 / 25300 are three 20000-level courses, so the cap
  (V07) fails before the share limit (V08) can. `cmsc-bxms-1/fail-05` now takes ML as CMSC 35300
  (cross-listed with CMSC 25300, which the major needs), so exactly the share limit fails.

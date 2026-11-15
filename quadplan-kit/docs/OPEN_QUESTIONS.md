# Open questions and decisions

Each question below has Richard's answer underneath it (answered 2026-11-14), or the default that stands when no answer was given. Nothing here is a guessed catalog fact.

New questions in this file are written in plain language, each with a suggested answer or a few options (Richard's preference, 2026-11-14).

## Working rule for the demo phase (Richard, 2026-11-14)

> One main idea now as we start further building is that, at this stage we are working towards a working demo. The Catalog is very complicated and intricate and will require a significant amount of manpower to reasearch it out. For now, for every new question that is catalog rule related, you should make a suggestion to yourself, document the desicion as a question for later, and build the thing out first. We will defer solving these questions in the future when we are about to deploy this website.

> **General rule:** when the catalog is unclear, be strict (do not count the course) and show a warning explaining why, so the student can check with an advisor.

What this means in practice:
- **New catalog questions:** pick the strict reading and show a warning explaining it. Add the question to "Deferred until before deployment" below with the suggested default, then keep building.
- **`data/seed/REVIEW.md`:** the rule-by-rule hand check is deferred until before deployment, for the same reason. The seed is used as encoded for the demo.

Status words used below:
- **Decided:** answered; build it.
- **OK:** the current default is confirmed.
- **Default stands:** no answer was given; this is a technical item to revisit when the related prompt is built.
- **Later:** explicitly deferred.
- **Resolved:** already done in code.

## Answers to the questions from the steps 1-5 run (Richard, 2026-11-14)

**Decided**
- **P08-1. Posts when the automatic check is down.** No check before a post is published. Posts go up at once (emails and phone numbers are still removed). Keep a way to take a post down when it breaks the guidelines: reports and the admin moderation queue.
- **P08-3. Repeat suspensions.** Suspensions are always manual. Removing posts never suspends anyone automatically; an admin suspends by hand from the moderation queue.
- **P08-4. Which term a reviewer can pick.** Yes, keep it as built.
- **P08-5. Cross-listed courses.** Yes: one forum page per cross-listed group and instructor, shown under every code.
- **Q6. Transfer students.** Transfer students must take at least 1800 units at UChicago (the residency requirement). Transfer credits count toward the 3800 units "earned by enrollment".
  > Richard: "Transfer student need to meet the 1800 credit residency requirement, meaning that they have to minimally take 1800 credits at Uchicago. Transfer credits count towards the 3800 credit requirement"

  Encoded in `data/seed/2026-27/college_policy.yaml` (`residency_min_units`, `transfer_counts_by_enrollment`) with this quote as the source and both fields marked for review. **Before deployment:** find the catalog sentence for each and replace the source.
- **Q11. Pace and grading strictness.** Add the two optional 1-5 questions to the review form.
- **P08-2.** Accept; mention it on the privacy page.

**New question from building these answers (2026-11-14)**
- **P08-14. Suspended students, account deletion, and lifting a suspension.** A suspended student cannot delete their account until the suspension ends (now at most 90 days, the longest choice in the admin menu). There is also no button yet for an admin to end a suspension early.
  **Suggested:** keep the block (otherwise deleting and signing up again would dodge the suspension), keep 90 days as the longest, and add an "end suspension" action to the admin page later. Option: let suspended students delete their account at any time; their email is then free to sign up again.
  **Decided (Richard, 2026-11-14): go with the suggestion.** The block and the 90-day maximum stay as built. **Built (6c07395):** an "End suspension" action for admins. **Originally planned as later work:** an "end suspension" action for admins. Admins never learn who is suspended, so it would sit on the removal decision that started the suspension, in the moderation history.

**OK (go with the suggestion):** P08-6 to P08-13, Q7 to Q10, Q12, Q13, DF-1 to DF-13, P7-1 to P7-8, and the Safari note (use Chrome or Firefox locally). P7-1 and P7-2 wait until Richard lifts the hold on API calls. DF-8 (Rare UI parts) and P08-11 (instructors in the home search) are later work.

**Work these answers create (done 2026-11-14, see PROGRESS):** P08-1, P08-3, P08-5, Q6, Q11, P08-2 (privacy page line), P08-10 (back to the page after login), DF-6 (note the two pale colors in DESIGN.md), DF-7 (delete confirmation), DF-12 (About page text), DF-13 (phone jump buttons).

## Work these answers create (not started)

**Spec and docs**
- SPEC decision row 12: "Quarterly Forumn" → "Quarterly Forum" (2).
- SPEC Checks table: V02 is no longer an Error; it becomes a warning (P02-1).
- SPEC sitemap: instructor names become public; ratings and reviews stay behind login (P03-12).
- `docs/CONTRACTS.md`: quote the residency sentence from the Graduation Requirements page (P02-6).

**Frontend**
- Show "Likely offered in: {quarters}" on courses; remind the student when a course is placed in a quarter where it is likely not offered (4).
- Public instructor names in search and the instructor directory (P03-12).

**DSL and verifier (`planner_core`)**
- **Whole-sequence construct:** complete every step of a sequence, with any approved level per step (P05-1). Apply it to all sequences and to Bx/MS `apply_requires` (P05-11c).
- **New rule types:**
  - maximum and minimum standing
  - consecutive quarters
  - per-quarter limits
  - completed-before-program (P05-3)
  - "if placement then" (P05-4)
  - "spans 2 quarters" (P05-9)
  - per-course "counts at most N times" (M1-2)
- **Reminders:** grade and GPA rules become reminders only, not checks (P05-3, P05-11c). Remove the "C in each course" encoding of the Math average.
- **Warning levels:**
  - V02 becomes a warning: exam credit stops counting; only one of two equivalent courses counts (P02-1).
  - V05 future quarters with one or two courses become warnings (P02-3).
  - `civ_abroad_year` becomes a warning (P05-6).
- **Matching:**
  - A `replaces` (renumbered course) partner also satisfies requirement selectors (P02-2).
  - `in_order` compares step position (P02-7).
  - Transfer credits count as not in residence (P02-6).
- **New warnings:**
  - needs department approval (P05-12b)
  - catalog inconsistent, check with an Econ advisor (P05-13a)
  - ECMA decided the result (P05-13c)

**Seed data**
- **Physical sciences:** restore the ~250 combinations (P05-1).
- **Overload lists:** language courses by subject code; Reading and Research / thesis courses by title (P05-7).
- **Language Competence:** the third quarter of every first-year language sequence (P05-8).
- **Computer Science:** course-info.cs.uchicago.edu as a second source for curriculum areas and PhD designations, with the five-areas rule (P05-10).
- **Bx/MS:** graduate Reading and Research number, PhD and MPCS Core Systems lists, title checks (P05-11a, b, d).
- **Math:** equivalent-or-higher chemistry and physics list, MATH 29700 and the Paris courses, the GEOS rule (P05-12).
- **Economics:** standard/honors mixing, Booth alternates (P05-13b, d).
- **Study abroad:** placeholder language courses for Córdoba and Paris (P05-14).
- **Courses:** fetch every subject page and use the real course blocks (P05-15).
- **Prerequisites:** formalize the 261 sentences with agent E1 (prompt 09), then spot-check and hand-review graduate CMSC electives (P05-16). **On hold:** no API calls until Richard says so.

## Deferred until before deployment

**Later (by Richard)**
- OpenRouter model names (3).
- Sending email to real users; development uses the console backend (P04-6).
- Student-level placement and credit field in the planner (P05-4, P05-8).
- Econ specializations (P05-13e).
- Other civilization programs abroad (P05-14).
- Econ items (a)–(c), to confirm with the Econ department.
- The full hand check of `data/seed/REVIEW.md`.
- M1-1: department confirmation of the `as_enrolled` reading.

**New questions (Richard, 2026-11-14), with the suggested default to build meanwhile**

Q1. **Transfer students (P05-6).** Does the planner count "second year" from when the student started at UChicago, or by class standing? If by class standing, the Y2-SP Core warning would hit a transfer student at the end of their first year here.
   *Suggested default:* count from the student's start at UChicago (what `resolve_term_ref` does now), because the warning would otherwise fire for almost every transfer student. It is only a warning.

Q2. **HUMA 19100 (P05-9).** Must the two quarters be consecutive? If yes, also use the consecutive-quarters rule from P05-3.
   *Suggested default:* yes, require consecutive quarters (strict reading of "two-quarter series"; Summer does not break the sequence). Explain it in the warning.

Q3. **CS (P05-10).** Is it correct that 300-level CMSC courses do not count as major electives?
   *Suggested default:* keep them not counted (strict). When one is in a plan with a CS major, show a warning to check with the department.

Q4. **Study abroad (P05-14).** Does the Córdoba/Paris language course count toward Language Competence (the study-abroad route in P05-8)?
   *Suggested default:* do not count it automatically. Once the credit field exists (P05-8), the student can enter it as a Language Competence credit, with a warning to confirm with the College.

Q5. **Prerequisites (P05-16).** Should prerequisites written for master's students apply to Bx/MS students instead of being dropped?
   *Suggested default:* apply them to plans that include a Bx/MS program, as warnings explaining they come from the master's-level text.

---

**From prompt 06 (plan generator), with the default built meanwhile**

Q6. **Transfer students and "units earned at UChicago".** The seeded College rule says 3800 of the 4200 units must be earned by enrollment here. A transfer student with three years left can earn at most 3600 (nine full quarters), so the generator says no plan exists for them.
   *Suggested default:* keep the rule as written and show the explanation. Before deployment, find the College's rule for transfer students (it is probably different) and encode that.

Q7. **Cross-listed courses in generated plans.** When two course numbers are the same course (cross-listed), the generator picks one of them, usually the one a requirement names first. This matters for the Bx/MS "at most two 20000-level courses" rule (M1-1).
   *Suggested default:* keep it. Students can swap to the other number by hand, and the verifier checks either one.

---

**From prompt 11 (forum ratings into course numbers), with the default built meanwhile**

Q8. **How much the starting guess counts.** The spec gives a course's starting point two different weights: 5 reviews' worth in the Forum section, and 2 reviews' worth for the AI's first guess in the A3 section.
   *Suggested default (built):* 5 when the starting point is the department's average from real reviews, and 2 when it is the AI's guess. Real data then outweighs a guess quickly.

Q9. **Turning words into a difficulty number.** When a post says a course is "easy", "moderate", "hard" or "very hard", it counts as 2, 3, 4 or 5 on the 1-5 scale, at half the weight of a star rating.
   *Suggested default (built):* keep this mapping. Alternatively, use words only as supporting quotes and never as numbers.

Q10. **Which courses get an AI first guess.** Only courses that have a forum page get one, at most 200 a night, to keep the cost down.
   *Suggested default (built):* keep it. Alternatively, guess for every course in the catalog once (about 1,300 calls).

Q11. **Pace and grading strictness.** Reviews have no question for these, so they stay empty. That also means the "protect my GPA" goal has nothing to work with yet.
   *Suggested default:* add two optional 1-5 questions to the review form ("How fast did it move?", "How strictly was it graded?"), or leave them out of the demo.

Q12. **Numbers for a specific instructor in the planner.** The forum computes numbers per course and per course-and-instructor, but the planner only uses the per-course ones for now, because the planner does not yet know who teaches each section (that comes with the class schedule, prompt 10).
   *Suggested default (built):* per-course numbers until the schedule arrives, then switch to the instructor's numbers when the quarter's instructor is known.

Q13. **What counts as "3 ratings".** Forum numbers appear only once 3 different posts back them. A discussion post that mentions hours or difficulty counts once (the middle value of what it says), at half the weight of a review; a review's text is not read for numbers, because its star ratings already count.
   Several discussion posts by the same person on the same page also count once.
   *Suggested default (built):* keep this, so one person cannot move a course's numbers by repeating themselves.

---

## Decisions (docs/SPEC.md "Summary and decisions to confirm")

1. **Decision 5 (accounts).** Richard edited row 5 to "Email and password is stored on the backend" and confirmed it: accounts store the verified `@uchicago.edu` email and an argon2id password hash; there are no blind signatures. CLAUDE.md and SPEC "Accounts and anonymity" were updated to match. Forum anonymity (per-page pseudonyms, HMAC author refs) is unchanged.
   **Answer: Resolved (2026-11-12).**

2. **Decision 12 (name).** The UI uses "Quarterly" / "Quarterly Planner". The forum name is written "Quarterly Forumn"; the UI uses "Quarterly Forum", assuming a typo. Code identifiers keep the neutral names (`planner_core`, `api`, ...); the Compose project and database are `quarterly`.
   **Answer: Decided.** "Yes, please use 'Forum'." (To do: fix SPEC row 12.)

6. **Which AI model turns each program page into rules (E3)?** Richard (2026-11-14): Fable is overkill, because every rule is still checked by our own code, the golden plans and a human. The main run now uses **Opus 5.5**.
   The spec has a second, separate run whose answer is compared with the first; any disagreement goes to a person. Which model should that second run use?
   - **Sonnet 5.5 (suggested, and what is set now).** It is about half the price of Opus. Because it is a different model, it is less likely to make the same mistake as the first run.
   - **Opus 5.5 again, with the instructions reordered.** This costs the same as the first run, and the two runs may share blind spots.
   **Answer: Default (Sonnet 5.5) set in `llm_routing.yaml`; change it if you prefer the other option.**

## Infrastructure

3. **OpenRouter model names** in `llm_routing.yaml` (`anthropic/claude-opus-5.5` style) are not verified against OpenRouter's catalog; confirm before prompt 07. The `max_tokens` values there are starting defaults, not from the spec.
   **Answer: Later.**

## Contracts (prompt 01)

4. **"Terms Offered" to `p_offered`.** Until schedule data exists, listed quarters get p = 0.95 and unlisted Autumn/Winter/Spring get p = 0.05 (`method: catalog`), so V04 warns when a course is placed outside its catalog quarters. Confirm this mapping or give another.
   **Answer: OK, decided.** "The idea is that the probability should on the backend of the program. On the front-end the use should see 'Likely offered in: {quarters}'. We should remind the users when they've placed the course in a position that the course is likely not offered. We infer the availability of the courses by using available course offering information and past data."

5. **One `program_version` per program per catalog year.** Editing a published version in place would change plans made under it; v1 relies on review items for such edits. Revisit before prompt 09.
   **Answer: OK.**

## Prompt 03 mocks

All handlers live in `apps/web/src/mocks/handlers.ts` (typed from the generated schema; data in `mocks/data.ts`, a toy verifier in `mocks/verify.ts`). They run only in vitest, in Playwright e2e (`VITE_MOCK_API=1` build) and in dev with `VITE_MOCK_API=1`; the Docker build calls the real API. Mock data is deliberately fake (catalog year `2099-00`, `TEST`/`FAKE` courses, "Fake Program"). Remove each handler once its endpoint is real and the e2e test can run against seed data.

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

- **P03-6. Logged-out session status.** The UI treats any non-200 from `GET /auth/session` (401 or 501) as logged out. Confirm prompt 04 answers 401 when there is no session.
  **Answer: Default stands.**
- **P03-7. Generate variant metrics keys.** `VariantEvent.metrics` is a free dict; the UI reads `avg_hours` and `hardest_quarter_hours`. Pin these names in prompt 06/07 or tell the frontend.
  **Answer: Default stands** (pin in prompt 06/07).
- **P03-8. "Mark completed" has no op.** Change ops are add/move/remove/lock/unlock, so the planner marks an item completed as unlock (if locked) + remove + add with `status: completed`, keeping the lock. A `set_status` op would be cleaner for `PATCH /plans/{id}/items`.
  **Answer: Default stands.**
- **P03-9. Course details in bulk.** The grid fetches `GET /courses/{code}` once per planned course (cached). A batch endpoint (`GET /courses?codes=...` returning attributes) would cut ~40 requests.
  **Answer: Default stands.**
- **P03-10. Citation links.** `Citation.id` for `attribute` and `post` kinds has no documented format, so those chips are not links (only `course` and `program` chips link). Post chips need the course code and instructor slug to reach `/courses/{code}/i/{instructor}/t/{id}`.
  **Answer: Default stands** (define in prompt 07/08).
- **P03-11. Goal chip defaults (user preferences, not catalog facts).** "Challenge me" = `challenge` with `min_index: 10`; "Light quarter" = `light_quarter` with `max_courses: 3`; "Lighter first year" = light quarters for Y1 Autumn–Spring; "Graduate in four years" = `graduate_by` Y4 Spring; "At most one very hard course per quarter" = `difficulty_cap` `max_very_hard: 1`. Adjust freely.
  **Answer: OK.**
- **P03-12. Home search of instructors.** The SPEC says the home page searches courses and instructors, but `/instructors` needs login; the home search covers courses only for now.
  **Answer: Decided.** "Make instructor names public. Names appear in public search, but ratings and reviews stay behind login."
- **P03-13. Shared read-only snapshot** (planner state "read-only when viewing a shared snapshot") has no route or endpoint yet; not built.
  **Answer: OK** (not built yet).

## Prompt 04

Choices made so work could continue; each is the conservative option and easy to change.

- **P04-6. Email provider.** `EMAIL_BACKEND=console` (development: prints the code and pending id, never the address) or `smtp` (stdlib `smtplib`, STARTTLS with certificate verification, works with any transactional provider). No provider SDK was added. Which provider, and which `EMAIL_FROM` address? The API refuses to start with the console backend, development secrets or a non-Secure cookie unless `ENVIRONMENT` is explicitly `development` or `test`.
  **Answer: Later.** "For now we only make sure that the development enviroment work, sending email to real users later."
- **P04-7. Plus-addressing and aliases.** Only plain `local@uchicago.edu` is accepted: no subdomains (`@cs.uchicago.edu`, `@alumni.uchicago.edu`) and no `+tag`, so one mailbox cannot verify several accounts. If real student addresses need either, relax `normalize_uchicago_email`.
  **Answer: OK.**
- **P04-8. Rate-limit numbers** (`api/auth/ratelimit.py` and the `ip_limit(...)` on each route). Per address: 5 codes per hour, and 10 wrong codes per day across sign-up and reset. Per pending id: 5 wrong codes. Per login name: 10 failed logins per 15 minutes. Per account: 10 failed password confirmations per 15 minutes. Per IP per day: 40 email/reset starts, 40 registrations, 100 code checks, 300 logins. IP limits are loose because campus networks share addresses. Confirm or tune.
  **Answer: OK.**
- **P04-9. Client IP behind the proxy.** nginx sends `X-Forwarded-For` and the `api` service sets `TRUSTED_PROXY_HOPS: "1"`.
  **Answer: Resolved (M1 integration).**
- **P04-10. "IP counter never written to disk."** Redis runs with `--save "" --appendonly no`.
  **Answer: Resolved (M1 integration).**
- **P04-11. Session lifetime** is 30 days, fixed (not extended on use). A password reset ends all sessions; a password change ends all but the current one.
  **Answer: OK.**
- **P04-12. Forum identity.** `api.auth.hashing.author_ref(account_id, page_id)` implements the SPEC's `HMAC(server_key, account_id ‖ page_id)`; account deletion recomputes it per forum page to find an account's rows, so prompt 08 must use the same function for `author_ref`, `voter_ref` and `reporter_ref`. With "delete my posts", a comment that someone else replied to is blanked ("[deleted]", no author) instead of removed, so the replies survive; vote rows are removed but tallied scores are not recomputed. Confirm.
  **Answer: Default stands** (revisit in prompt 08).
- **P04-13. CSRF for later prompts.** Every POST/PATCH/DELETE sent with a session cookie needs `X-CSRF-Token` (from `SessionOut.csrf_token`), enforced app-wide. Exempt: the pre-session `/auth/*` steps and the stateless `POST /verify`. Frontend code can use the client in `apps/web/src/features/auth/api.ts`, which adds the header.
  **Answer: Default stands.**
- **P04-14. Plans API.** CONTRACTS lists `/plans` CRUD and `/plans/import` as "04/06"; prompt 04 built only the read path for `GET /account/export` (`api/auth/account_data.py`, which assumes `goal.params` holds the goal's type-specific fields). The rest is left to prompt 06.
  **Answer: Default stands** (prompt 06).
- **P04-15. Suspended accounts** (`account.status`, `suspended_until`) can still log in; the forum (prompt 08) should enforce suspension where it matters.
  **Answer: OK.**

## Prompt 05

Seed data for catalog year 2026-27 (fetched 2026-11-12). Each item says what was encoded meanwhile (the strictest expressible reading); the nodes are marked `needs_review` in the seed and listed with their quotes in `data/seed/REVIEW.md`. Numbered P05-n so parallel prompts do not collide.

**Richard's general rule for these items:** when the catalog is unclear, be strict (do not count the course) and show a warning explaining why, so the student can check with an advisor.

### DSL / verifier gaps

- **P05-1. `same_sequence` accepts any subset of one sublist.** A three-course sublist would also accept each of its pairs, and one course of a calculus pair passes the Core math part. For the physical sciences Core, only three-course combinations whose every pair is itself approved were kept; 250 three-course combinations the catalog allows (PHSC 11600-11700 + any PHSC Core course, Astro 12000s triples, PHSC 18000s + any approved pair) are left out. Also not encoded: "the student must take two calculus courses" when calculus is used for the math Core. Option: a "whole sublist or nothing" / minimum-per-sublist constraint in the DSL.
  **Answer: Decided.** "Take courses from one approved sequence" means the whole sequence must be taken: every step completed. Each step may be taken at a different level (e.g. the analysis sequence can be completed as MATH 20700 → MATH 20410 → MATH 20500). A partial sequence never passes (one course of a calculus pair, or two of a three-course sequence). Add a DSL construct for "complete every step; any approved level per step." Apply it to all sequences unless the catalog says otherwise. Restore the ~250 dropped physical sciences combinations under it. This also enforces "two calculus courses" for the math Core.
- **P05-2. Group-level constraints.** `econ-ba/empirical` has `in_order`, and the three Bx/MS roots have `max_from` ("at most two courses from the 20000-level offerings"), on `group` nodes. Please confirm the verifier applies group-level constraints to all courses used under the group.
  **Answer: Resolved.** The verifier applies group-level constraints (`in_order`, `max_from`) to all courses under the group, as confirmed in M1 integration. No change. See M1-1 for how cross-listed courses count toward the cap.
- **P05-3. Rules the DSL cannot express (left out):** "enrollment limited to first-year students" (a maximum standing; CHEM 10100/10200); "beyond their first year" for study abroad; HIST 13500-13700 needs two *consecutive* quarters; Econ empirical methods "in consecutive quarters"; "no more than one per quarter" for Bx/MS Reading and Research; "exactly three courses per quarter" and "3900 of 4200 units and all general education before the first Bx/MS quarter"; grade averages (Math approved courses "overall C average", encoded as C in each); GPA rules.
  **Answer: Decided.** Add DSL rule types for:
  - maximum standing (first-year-only courses: CHEM 10100/10200)
  - minimum standing (study abroad beyond the first year)
  - consecutive quarters (HIST 13500–13700; Econ empirical methods)
  - per-quarter limits (Bx/MS: at most one Reading and Research per quarter; exactly three courses per quarter)
  - completed-before-program (3900 of 4200 units and all general education before the first Bx/MS quarter)

  Grade and GPA rules become reminders only, not checks. Remove the "C in each course" encoding of the Math "overall C average."
- **P05-4. Placement-conditional rules.** CS: placing out of CMSC 14300 (CS 3 exam) means one extra elective; the Discrete Mathematics Placement Exam allows Theory BC / BCC. Math: the MATH 15910/16300 requirement is waived when the first course is MATH 20700. Not encoded (no "if placement then" node); the standard path is required.
  **Answer: Decided.** Add "if placement then" support. Eventually, placement results will be a student-entered field in the planner, stored once at the student level and available to every check (the field itself is deferred). Cases:
  - CS 3 exam placing out of CMSC 14300 → one extra elective
  - Discrete Mathematics Placement Exam → Theory BC / BCC options
  - Math: the MATH 15910/16300 requirement is waived when the student's first math course is MATH 20700, 20310 or 20300 (detectable from the plan; no placement input needed)
- **P05-5. `requires: ["cmsc-b?"]`** (Bx/MS Options 1-2) and `excludes: ["cmsc-b?"]` (Option 3) use a shell glob (`?` = one character) for "CS BA or CS BS". Confirm glob semantics and that `requires` means any-of.
  **Answer: OK.** Keep the glob. `?` matches exactly one character; `requires` means any-of (at least one match).

### Catalog wording

- **P05-6. Core timing.** The catalog says the Core "should be completed by the end of the second year"; encoded as `core_complete_by: Y2-SP` (V10 is a warning). `civ_abroad_year: 3` comes from the College's Core requirements PDF, which carries no catalog year. Keep both?
  **Answer: Decided.** Keep `core_complete_by: Y2-SP` as a warning. Keep `civ_abroad_year: 3`, but as a warning only, since the source PDF has no catalog year. (Follow-up: Q1, transfer students.)
- **P05-7. Overload reasons.** "a 200-unit language course" is encoded as any course of 200+ units (no language-course list is seeded). "Reading and Research or B.A. Thesis/Colloquium course" uses a list built from course *titles* (CMSC 29700, CMSC 29900, ECON 29700, DATA 29700, HUMA 29700, ...); departments may have other thesis/colloquium courses. Who owns this list?
  **Answer: Decided.** Build both lists automatically each catalog year and flag new entries for review:
  - language courses by subject code (replaces "any course of 200+ units")
  - Reading and Research / B.A. Thesis/Colloquium courses by title
- **P05-8. Language Competence.** Only the course route is encoded, with FREN 10300 and SPAN 10300 as the only seeded "third course of a first-year language sequence". Exam, placement, AP/IB, study-abroad and proficiency routes are not plan items. Model them as `credits` that satisfy `core/language`, and seed every language's third quarter?
  **Answer: Decided.** Model the exam, placement, AP/IB, study-abroad and proficiency routes as credits that satisfy `core/language`, entered in the same student-level field as placement results (P05-4; the field itself is deferred). Seed the third quarter of every first-year language sequence.
- **P05-9. Writing Grey track.** HUMA 19100 is one course number taken in two quarters; it is marked `repeatable` (the catalog says "two-quarter series", not "repeatable"). *(M1 integration: the verifier now counts each enrolment of a repeatable course, see M1-2.)*
  **Answer: Decided.** Replace `repeatable` with a specific "spans 2 quarters" marker: the course must be taken in exactly two quarters. (Follow-up: Q2, consecutive quarters.)
- **P05-10. Computer Science.** BA electives must "span at least five curriculum areas", and the areas and PhD Core/Elective designations are published only on course-info.cs.uchicago.edu, not in the catalog. Encoded: BA electives = any 8 CMSC 20000-29999 (breadth not checked); specialization lists exactly as printed; CMSC 300-level courses not accepted as major electives. May course-info be used as a second source?
  **Answer: Decided.** course-info.cs.uchicago.edu may be used as a second source. The catalog takes priority; course-info fills gaps (curriculum areas, PhD Core/Elective designations). Record the source of each fact. Use it to check the BA rule that electives "span at least five curriculum areas." (Follow-up: Q3, 300-level courses.)
- **P05-11. Bx/MS.** (a) The page names no course for "two Reading and Research courses"; encoded as two more CMSC 30000-level courses. (b) PhD-program Core Systems courses and MPCS Core Systems / Core Programming courses are not in the catalog; only the major's Systems list is used (graduate cross-listed numbers match through cross-listing). (c) Admission (3.5 GPA, B+ average in two intro courses) is not encoded; `apply_by: Y3-WI` from the January/February admissions cycle, no `apply_requires` because the requirement is a choice of pairs. (d) Titles of CMSC 37115, MPCS 50103 and MPCS 55001 are taken from the requirement labels (no course block found).
  **Answer: Decided.**
  - (a) Find the graduate Reading and Research course number on course-info. Keep "two more CMSC 30000-level courses" until then.
  - (b) Add the PhD Core Systems and MPCS Core Systems / Core Programming lists from course-info or the MPCS website.
  - (c) Admission GPA/grade rules (3.5 GPA, B+ average) become reminders. Keep `apply_by: Y3-WI`. Add `apply_requires` using the new P05-1 construct ("complete one of these pairs before applying").
  - (d) Keep the titles of CMSC 37115, MPCS 50103 and MPCS 55001 taken from the requirement labels; mark them `needs_review` and verify against course-info / the MPCS site.
- **P05-12. Mathematics.** "(or equivalent)" / "(or higher)" after the chemistry and physics sequences not encoded (honors chemistry and PHYS 13100/14100 are not accepted for the math majors' general education). MATH 29700 ("as approved") and Paris courses left off the approved list. PSCD "department" read as subject code; "GEOS courses not cross-listed as PHSC" and "reserves the right to exclude courses which are new in 2026-27" not encoded. BS minor field read as three courses in addition to the four PSCD courses.
  **Answer: Decided.**
  - (a) Encode "(or equivalent)" / "(or higher)" for the chemistry and physics sequences: accept honors chemistry and PHYS 13100/14100, via an explicit list of equivalent-or-higher sequences.
  - (b) Add MATH 29700 and the Paris courses to the approved list with a "needs department approval" warning.
  - (c) Confirmed: "PSCD department" = subject code belonging to a PSCD department; BS minor field = three courses in addition to the four PSCD courses.
  - (d) Encode the GEOS rule (read as: GEOS courses not cross-listed as PHSC do not count; confirm against the catalog wording). "Reserves the right to exclude courses new in 2026–27" becomes a reminder.
- **P05-13. Economics.** (a) The Fundamentals table lists MATH 20420 as an alternative to MATH 15250, but the Summary of Requirements does not; MATH 20420 not accepted. (b) Mixing standard and honors core courses not accepted. (c) ECMA courses counted on the strict side of "at least two economics courses numbered higher than ECON 20210" (with outside electives and ECON 10200, at most 2 of 4). (d) Booth 3xxxx alternates of the pre-approved BUSN courses not encoded. (e) Only the standard track is seeded; the three specializations are not.
  **Answer: Decided.**
  - (a) Do not accept MATH 20420; show a warning that the catalog is inconsistent and the student should check with an Econ advisor.
  - (b) Allow mixing standard and honors core courses (consistent with P05-1) unless the Econ catalog explicitly forbids it. Check the catalog.
  - (c) Keep ECMA on the strict side; show a warning when ECMA courses decide the result.
  - (d) Add Booth 3xxxx alternates where the catalog lists the numbers; otherwise leave out.
  - (e) Specializations: deferred.
- **P05-14. Study abroad.** The Córdoba and Paris (Migration, Decolonization, and Diaspora) programs include a Spanish / French course with no course code on the program page; not encoded. Only these two civilization programs abroad are seeded, so `core-civ-sequences` accepts only them abroad.
  **Answer: Decided.** Add placeholder courses for the Córdoba Spanish course and the Paris French course. Other civilization programs abroad are deferred. (Follow-up: Q4, Language Competence.)
- **P05-15. Cross-list copies.** 366 Equivalent Course codes have no block on the fetched pages; they are seeded as copies of the block that names them (same title, units, prerequisites, terms). OK, or fetch every subject page?
  **Answer: Decided.** Fetch every subject page. Use the real course block wherever it exists; keep the copy only for codes that still have no block.
- **P05-16. Prerequisites.** 261 prerequisite sentences are not formalized (none on a course a slot names; mostly BIOS, SOSC, BUSN, ARTH, STAT and graduate CMSC electives); they keep `prereq_text` and `needs_review`. Sentences addressed only to master's/graduate students were dropped. Run agent E1 over these, or hand-encode?
  **Answer: Decided.** Run agent E1 over the 261 unformalized sentences, then spot-check a sample by hand. Review every graduate CMSC elective by hand. (Note: E1 is built in prompt 09 and calls the Anthropic API. Follow-up: Q5, master's-level prerequisites.)

### Infrastructure note (not a catalog question)

- **P05-17. `make golden` was slow.** `golden.py` now parses the seed once per catalog year.
  **Answer: Resolved (M1 integration).**
- **P05-17b.** `golden.py` still runs `build_catalog` once per plan; building it once per catalog year would shorten `make golden` further.
  **Answer: Default stands.**

## Prompt 02

Verifier readings that are choices, not catalog facts. Each is implemented as stated (see `docs/CONTRACTS.md` "Verifier semantics") and can be changed in one place.

- **P02-1. V02 levels.** The spec lists V02 as Error, so "exam credit forfeited when the course is also taken" is an error (remove the credit or the course), and so is taking two courses related as `equivalent` or `replaces`. Should forfeiture be a warning that just stops counting the credit?
  **Answer: Decided.** Change both to warnings:
  - (a) Exam credit plus taking the same course: warning; stop counting the exam credit.
  - (b) Taking two courses related as `equivalent` or `replaces`: warning; count only one.

  Units, requirement and other checks still catch any real problem this causes. Update the spec (V02 is no longer an Error).
- **P02-2. `equivalent` vs cross-listing.** The catalog's "Equivalent Course(s)" line is the cross-list line and belongs in `crosslists`. The verifier lets `equivalent` / `replaces` partners satisfy prerequisites and deadlines, but selectors match on cross-list groups only (contract). Confirm.
  **Answer: Decided.** Confirmed: the catalog's "Equivalent Course(s)" line goes in `crosslists`; selectors match on cross-list groups; `equivalent` / `replaces` partners satisfy prerequisites and deadlines only. Exception: where `replaces` represents a renumbered course (old number → new number), it also satisfies requirement selectors, so students who took the old number are not wrongly flagged.
- **P02-3. V05 on quarters in progress.** Empty quarters and Summer are not flagged; a quarter with one or two courses is an error (below full time); a quarter whose courses are all `completed` reports as info. Should a half-built future quarter be a warning instead of an error?
  **Answer: Decided.** Future quarters with one or two courses: warning (not error). Completed quarters: info. Empty quarters and Summer: no flag.
- **P02-4. Civilization abroad in third year (V10).** `CollegePolicy` only has `civ_abroad_year`. A late Core course is excused when it is used by a `study_abroad_block` program of the plan, or sits in the term of a `study_abroad` goal. Is that the right test, or should courses carry a tag?
  **Answer: OK.** Keep the current test (excused when used by a `study_abroad_block` program of the plan, or in the term of a `study_abroad` goal). No course tag needed. Low risk, since this is a warning (P05-6).
- **P02-5. Share limits are per pair of programs** ("at most 0 with each major"), as in the spec formula. Some rules may mean "in total across all minors"; the DSL cannot say that yet.
  **Answer: Decided.** Keep per-pair share limits. Mark any rule whose wording says "in total" or "across" (e.g. across all minors) as `needs_review`. Add a "total across programs" option to the DSL when a real rule needs it.
- **P02-6. Residency.** "Half of each program in residence" is measured on the courses the solver assigns to the program; the Core and study-abroad blocks are exempt from the College-wide share unless the program states its own. Confirm against the Graduation Requirements page.
  **Answer: Decided.** Find and quote the exact sentence from the Graduation Requirements page in `docs/CONTRACTS.md` next to the implementation, and adjust if the wording differs. Make sure transfer credits count as not in residence.
- **P02-7. `in_order` and `distinct_subjects`.** `in_order` compares courses of one subject by course number and needs strictly increasing terms; `distinct_subjects` uses the subject of the code as written in the plan (a cross-listed course counts under the code the student enrolled in).
  **Answer: Decided.**
  - `in_order`: compare by step position in the sequence (step 1, 2, 3), not by course number, so mixed-level sequences (P05-1, e.g. MATH 20700 → MATH 20410 → MATH 20500) and mixed-subject sequences work. Fall back to course number only when a sequence has no steps. Keep strictly increasing terms.
  - `distinct_subjects`: confirmed, it uses the subject of the code as enrolled (consistent with M1-1).
- **P02-8. Attribute values.** `/verify` reads `attribute_value` rows with `subject_type = course` and `subject_id` = course code; prompts 08/11 must write them that way. Default thresholds when a goal sets none: "very hard" = difficulty 4.0 or more, "strict grading" = 4.0 or more (1-5 scale).
  **Answer: Default stands.**
- **P02-9. Graduation totals count placeholders** (100 units each) so a plan with unfilled slots shows the units it intends; V07 still fails until they are filled. Confirm.
  **Answer: Default stands.**
- **P02-10. Incomplete plans and the solver.** Whether the programs are satisfied is decided exactly. For an incomplete plan the list of missing requirements comes from a second solve with a deterministic work limit; on very hard instances it may not be the smallest list, and the report says so. The benchmark instance (60 courses, 201 nodes, 3 programs) is proven optimal.
  **Answer: Default stands.**
- **P02-11. `VerifyOptions.strictness`.** `strict` currently only makes workload goals use the upper confidence bound. Should it also turn V04 / V10 warnings into errors?
  **Answer: Default stands.**

## M1 integration

Decisions taken while making the nine failing golden plans pass. Each is implemented and tested.

- **M1-1. Level caps and cross-listed courses (`max_from.as_enrolled`).** The contract matches selectors on cross-list groups, so "at most two courses from the 20000-level offerings" also counted CMSC 33550 (cross-listed with CMSC 23500) and CMSC 33380 (with CMSC 23380). Under that reading Bx/MS Option 3 cannot be satisfied at all from the seeded lists: it needs three Core Systems courses, and every course on the major's Systems list is a 20000-level number (the PhD and MPCS Core Systems lists are not in the catalog, P05-11b). The prompt-05 golden plans assumed the other reading: a course counts under the number the student enrolled in. Implemented as an opt-in flag on the limit (`as_enrolled: true`, set on the three Bx/MS roots only, still `needs_review`); every other `max_from` (e.g. the Economics ECMA / outside-elective caps) keeps the stricter group reading. To confirm with the department: does a cross-listed course taken under its 30000-level number escape the 20000-level cap? If not, Option 3 needs the PhD / MPCS Core Systems lists before any plan can pass.
  **Answer: OK.** Keep `as_enrolled: true` on the three Bx/MS roots only; every other `max_from` keeps the stricter cross-list-group reading. Keep `needs_review` until the CS department confirms that a cross-listed course taken under its 30000-level number escapes the 20000-level cap (deferred). Adding the PhD / MPCS Core Systems lists (P05-11b) reduces Option 3's dependence on this reading.
- **M1-2. Repeatable courses count once per enrolment.** `core/writing/grey` is `count: 2` from the single code HUMA 19100, which no plan could satisfy while a course counted once. Each enrolment of a `repeatable` course is now a course of its own for program requirements (the n-th counts only in the unit where the (n-1)-th does). This also lets CMSC 29700 / CMSC 29900 taken twice count twice toward electives; the CS majors already cap each at one with `max_from`. Is "counts once per enrolment" right for every repeatable course, or should the DSL say how often?
  **Answer: OK, decided.** Each enrolment of a `repeatable` course counts as its own course by default. Add an optional per-course limit to the DSL ("counts at most N times") for when the catalog gives one; programs can still cap with `max_from`. HUMA 19100 no longer relies on this: it uses the "spans 2 quarters" marker (P05-9).
- **M1-3. V12 when another course takes the Pass/Fail course's place.** `cmsc-bxms-2/fail-03` (Algorithms CMSC 37000 taken Pass/Fail, CMSC 27200 also in the plan) reported only V07 on Core Systems: the solver put CMSC 27200 in the Algorithms slot, which pushed the plan over the 20000-level cap elsewhere. V12 now also fires when the program is unmet but would be met if its Pass/Fail courses had letter grades (checked for that program alone, share limits ignored).
  **Answer: OK.**
- **M1-4. A share-limit must-fail for Bx/MS Option 1 needs a 30000-level number.** Discrete, Algorithms and ML taken as CMSC 27100 / 27200 / 25300 are three 20000-level courses, so the cap (V07) fails before the share limit (V08) can. `cmsc-bxms-1/fail-05` now takes ML as CMSC 35300 (cross-listed with CMSC 25300, which the major needs), so exactly the share limit fails.
  **Answer: OK.** Note: this test depends on the M1-1 reading; if the department rejects `as_enrolled`, revise this test.

## Design foundation

Places where `docs/DESIGN.md` (the look) and `docs/SPEC.md` (what the pages do and say) pull in different directions, or where DESIGN.md says nothing. The app keeps the SPEC's behavior and follows DESIGN.md for the look; each item says what was built. How DESIGN.md maps to code is in `docs/DESIGN-IMPLEMENTATION.md`.

- **DF-1. Site name.** DESIGN.md's wordmark is "UChicago Course Forum"; the SPEC and the app call the site "Quarterly". Which name should the header show?
  **Suggested:** keep "Quarterly" (built that way, in the DESIGN.md wordmark style: the light serif). Option: switch to "UChicago Course Forum" everywhere, which also changes page titles and tests.
- **DF-2. Planner width.** DESIGN.md caps page content at 1200px wide. The planner has three side-by-side columns (requirements, the four-year grid, issues and advisor) that do not fit in 1200px without squeezing the grid.
  **Suggested:** let the planner alone use up to 1600px (built); every other page stays at 1200px or narrower. Option: keep 1200px and put the issues and advisor panel under the grid on every screen size.
- **DF-3. Course code in the course page title.** The SPEC's course page header starts with the code and title ("CMSC 14300 · Systems Programming I"). DESIGN.md says course codes are never set in the large serif type.
  **Suggested:** keep both in the one heading, but show the code as a small grey label above the title in the plain font (built). Screen readers still read "CMSC 14300 · Systems Programming I".
- **DF-4. The filled button in the top bar.** DESIGN.md's top bar ends with a filled maroon button, but it also says "one filled maroon button per page", and most pages already have one ("Start planning", "Add to plan", "Generate plan").
  **Suggested:** the top bar's "Log in" is an outlined button, not a filled one (built). Option: add a filled "Sign up" button to the top bar on every page.
- **DF-5. Several "Apply" buttons at once.** The Generate popup shows one result card per variant (up to three), and the advisor can show several proposal cards. Each card's "Apply" is a filled maroon button, so one view can show two or three.
  **Suggested:** keep it (built): each card is its own decision, and filling only one would suggest a favourite. Option: make every card's "Apply" outlined and keep filled buttons for page-level actions only.
- **DF-6. Colors for "warning" and "information" boxes.** DESIGN.md gives a pale background for errors and successes but not for warnings and information notes.
  **Suggested:** use the warning and information colors mixed at 8% into white, the same recipe DESIGN.md uses for the pale maroon (built; no new color values). If you agree, add these two to DESIGN.md.
- **DF-7. Deleting without a second step.** DESIGN.md says delete buttons ask "are you sure?" in place. Today "Delete" on My plans removes a plan straight away; that is the existing behavior, and this task did not change behavior.
  **Suggested:** add an in-place "Delete? Yes / Cancel" step to plan deletion now, and to forum posts when the forum is built. Option: leave plan deletion as one click, since a plan can be duplicated first.
- **DF-8. Rare UI components.** DESIGN.md suggests animated components from Rare UI (toasts, drawers, counters, the animated hero orb). None are installed yet: each one comes from an outside website and requires a visible credit link.
  **Suggested:** add them one at a time when the forum is built (toasts and the delete button first), each restyled to our colors, with the credit in the footer. Until then the hero orb is a still, soft color glow.
- **DF-9. Filters on phones.** DESIGN.md moves course filters into a bottom drawer on phones. The course search filters currently sit above the results on phones.
  **Suggested:** build the drawer together with the Rare UI drawer (DF-8); the stacked filters work in the meantime.
- **DF-10. Dark mode.** DESIGN.md does not define one and says to ask first.
  **Suggested:** no dark mode for the demo (built that way).
- **DF-11. A footer on every page.** DESIGN.md has a footer; the SPEC's page list does not mention one.
  **Suggested:** keep the footer (built), with links only to pages the SPEC already lists (planner, my plans, programs, course search, instructors, guidelines, privacy, about).
- **DF-12. What the About page says (design review, step 5).** The About page is still empty. It used to show a note meant for us ("Placeholder ... built in prompt 03"); it now says "Coming soon". The SPEC only says the page holds "disclaimers", and disclaimers are your call, not ours.
  **Suggested:** three short paragraphs: (1) Quarterly is a student project, not run by or endorsed by the University of Chicago; (2) the planner checks plans against the published catalog, but your adviser and the official degree audit have the final word; (3) forum posts are students' opinions, are moderated, and are anonymous to other students. Options: write it yourself, or drop the About page and put one line of this in the footer.
- **DF-13 (superseded 2026-11-14 by FEEDBACK "Planner GUI": the advisor now opens from the top as its own sheet, and the jump buttons were removed).** **The advisor on a phone (design review, step 5).** On a phone the planner shows its three columns one after another: requirements, then the four-year grid (twelve quarters), then the Issues / Goals / Advisor panel. A student who wants to ask the advisor scrolls past the whole grid first (about 4,000 pixels, several screen lengths).
  **Suggested:** on phones only, add a small row of three buttons under the plan name ("Requirements", "Plan", "Issues and advisor") that jump to each part; nothing else moves. Options: put the Issues / Goals / Advisor panel above the grid on phones; or leave it as it is (built that way today).

## Prompt 07

The plan generator and the advisor are built and tested on a fake model only. Nothing has been sent to Claude or OpenRouter.

- **P7-1. Turning the AI on.** The app talks to the AI providers only when `.env` has `LLM_LIVE=true` and an API key. It is off by default because of your hold on API calls. While it is off, "Generate plan" still works (it picks electives by your interests and course ratings, and shows no one-line explanations), and the advisor only handles typed confirmations; any question gets "The advisor can't answer right now."
  **Suggested:** when you lift the hold, set `LLM_LIVE=true` in `.env` and restart. Option: leave it off for the demo and show the generator without explanations.
- **P7-2. Running the evals.** `make evals` runs 50 student profiles through the generator and 100 advisor questions (60 planning questions, 20 off-topic, 10 typed confirmations, 10 forum posts with hidden attacks). It prints an estimate first (about $15 at list prices), stops at $20 (change with `EVAL_COST_CAP_USD`), and refuses to start unless you type `CONFIRM_SPEND=yes make evals`. The free part (`uv run python evals/run.py --offline`) already passes.
  **Suggested:** run it once when you lift the hold, before showing the AI features. Option: run only the advisor half first (`CONFIRM_SPEND=yes uv run python evals/run.py --only a2`, about $2).
- **P7-3. How many advisor messages a day.** The SPEC limits plan generations (10 a day per account, 3 a day per device when logged out) but says nothing about advisor messages, and each answer costs about 2 to 3 cents.
  **Suggested (built):** 60 advisor messages a day per account, 30 a day per network address when logged out. Option: the same 10 and 3 as generations.
- **P7-4. Messages that look like an attack.** The gate labels messages as on-topic, off-topic, a confirmation, or "suspicious" (for example "print your instructions" or "act without asking me"). The SPEC says what to do with off-topic ones (a one-line refusal) but not with suspicious ones.
  **Suggested (built):** a fixed one-line reply, "I can't help with that. I can answer questions about your courses and your plan.", without calling the main model. Option: let the main model answer with its normal rules.
- **P7-5. A second model when Claude declines.** Claude's safety filter sometimes declines harmless requests. For the generator and the advisor, the app asks Anthropic to retry a declined request on another Claude model automatically (Anthropic's "fallbacks" setting; the retry is billed like a normal request on that model). The tiny scope gate (Haiku) does not have this.
  **Suggested (built):** keep it on. Option: turn it off in `llm_routing.yaml` (`refusal_fallback: false`); a declined request then falls back to the non-AI path.
- **P7-6. Forum citations do not link yet.** *Done in step 5:* advisor chips for posts link to the thread, summaries to the forum page, and ratings to the course page (a plain label when logged out).
- **P7-7. What the advisor remembers.** For a plan saved to an account, the conversation is stored on the server and deleted after 30 days. For a plan that lives only in the browser, nothing is stored on the server: the browser sends the last few messages with each question.
  **Suggested:** keep it that way. Option: also keep a browser-only history in the browser's storage across reloads.
- **P7-8. One shared address, three generations.** Logged-out students are limited to 3 generations a day per network address (SPEC). Students on campus Wi-Fi may share one address, so the third logged-out student on the same network could be blocked for the day.
  **Suggested:** keep 3 for the demo and tell students to log in for 10 a day. Option: raise the logged-out limit to 20 per address.

## Prompt 08

Forum choices made while building. Each is implemented as described and can be changed in one place.

- **P08-1. Posts when the automatic check is down.** Real AI calls are on hold, so in production every post would wait for a moderator. For local development, `MODERATION_FALLBACK=publish` shows posts right away (after emails and phone numbers are removed); the server refuses to start with that setting outside development.
  **Suggested:** keep "wait for a moderator" as the production rule (what the SPEC says). Option: publish straight away and check later, which is faster for students but lets a bad post be seen for a while.
- **P08-2. A suspension leaves a small trace.** When an account is suspended, the database records the end date on the account. Someone with a stolen copy of the database could match that date to the moderator's removal on the same day and guess that this account wrote that removed post. It only affects removed posts of suspended accounts; ordinary posts stay unlinkable.
  **Suggested:** accept it and say so on the privacy page. Options: start suspensions on the next Monday, which blurs the match; or keep suspensions outside the database (lost if the server restarts).
- **P08-3. Repeat suspensions.** Every third post removed by a moderator suspends the account for 30 days (so the 3rd, 6th, 9th...). Posts the automatic check rejects do not count unless a moderator also removes them.
  **Suggested:** keep this, and let an admin ban an account by hand after the second suspension. Option: an automatic permanent ban at 6 removals.
- **P08-4. Which term a reviewer can pick.** A review must name a term in which the schedule shows that instructor teaching the course. Students who took it before our schedule data begins cannot review it yet.
  **Suggested:** keep it for the demo; once schedule data goes back further, the list grows by itself. Option: allow any term in the last four years, which lets older students review but cannot check they really took it then.
- **P08-5. Cross-listed courses.** A course listed under two codes (for example CMSC 25300 and STAT 27700) with the same instructor would get two separate forum pages, splitting its reviews.
  **Suggested:** one page per cross-listed group, shown under every code. This needs a small change when the schedule pipeline (prompt 10) creates pages.
- **P08-6. Who moderates.** Only admins can use the moderation queue; curators cannot.
  **Suggested:** admins only for now. Option: let curators moderate too.
- **P08-7. Deleting a post that has replies.** The post's text becomes "[deleted]" and its author is hidden, so the replies under it stay readable. A post with no replies is removed completely.
  **Suggested:** keep this.
- **P08-8. No images in posts.** A picture loaded from another website would tell that website the address of every student who reads the post, so images are not allowed; links are (they open only when clicked).
  **Suggested:** keep it. Option: allow images we host ourselves later.
- **P08-9. Rate limits.** Per account: 10 posts an hour and 30 a day, 60 comments an hour, 300 votes an hour, 20 reports a day, 30 edits or deletions an hour.
  **Suggested:** keep these for launch and adjust from real use.
- **P08-10. Back to the forum after logging in.** Forum pages ask readers to log in, but the login page then opens the planner rather than the page they came from (the login page belongs to prompt 04).
  **Suggested:** return to the page they came from. Small change to the login page.
- **P08-11. Instructor names in the home page search.** Names are now public on `/instructors`, which has its own search, but the home page search still covers courses only (the home page was outside this task).
  **Suggested:** add instructors to the home search in a later pass.
- **P08-12. Deleting an account right after a moderator removes a post.** Deleting an account and signing up again would also wipe its count of removed posts, which a rule-breaker could use to dodge a suspension. So an account cannot be deleted for 30 days after a moderator removes one of its posts (the student sees a message saying why). Removals an admin later reverses do not count.
  **Suggested:** keep the 30-day wait. Option: allow deletion at any time and accept that a determined rule-breaker can reset their count (their email can still be blocked by hand).
- **P08-13. Logged-out students and the AI helpers.** Forum posts are only for logged-in students, so the plan generator and the advisor chat cannot read forum posts or summaries for someone who is not logged in; they still use catalog facts and course ratings.
  **Suggested:** keep it, so the AI cannot be used to read the forum without an account.


## Prompt 09

The catalog pipeline is built and tested with fake pages and a fake model only. Nothing below blocks the demo; each item has the default that is built now.

- **P09-1. Programs that did not change since last year.** When this year's catalog says exactly what last year's did, the pipeline copies last year's published rules and marks them "Unchanged since last year". Should those go live by themselves?
  **Suggested (built):** no. A curator still clicks Accept and then Publish, which takes seconds per program. Option: publish unchanged programs automatically, which saves clicks but means a student could see a new year's rules that no person looked at.
- **P09-2. The "9 to 19 courses" check for majors.** The spec says a major needs between 9 and 19 courses. Our Mathematics BS needs 21 by that count, because the seed also lists the general-education math courses the major asks for.
  **Suggested (built):** treat it as a flag for the reviewer, never a reason to reject. Option: leave general-education parts out of the count.
- **P09-3. The contact address the crawler sends.** Every request to the catalog says who we are and gives an email address, so the University can reach us if the crawler causes trouble. Which address should it be?
  **Suggested:** a project address (not a personal one), set as `CATALOG_CONTACT_EMAIL` in `.env`. The crawler refuses to run until it is set, and the address is never written to the logs.
- **P09-4. When the yearly run happens.** It is set for 1 August at 4 a.m., with a check for changed pages on the 15th of every month. Both are off until `CATALOG_INGEST_ENABLED=true`.
  **Suggested:** keep these dates and switch it on once the new catalog is out. Option: leave it off and start each yearly run by hand.
- **P09-5. Courses that did not change.** New courses for the year arrive as one review item per subject (about 200), including subjects where nothing changed; those are labelled "no changes".
  **Suggested (built):** keep this for the first real year, so a person sees every subject once. Later, accept unchanged subjects automatically.
- **P09-6. Counting programs.** The run stops if our list of programs does not match the College's own counts ("68 majors and 57 minors") and the catalog's index. We count a BA and a BS in the same subject as one major, as the College seems to. If the College counts some joint degrees or tracks differently, the run will stop and a person must look.
  **Suggested (built):** keep the strict stop. Option: allow a small difference and only warn.
- **P09-7. How much a real run may spend.** The pilot (11 programs) is estimated at about $16 and stops at $25 (`INGEST_COST_CAP_USD`). A full yearly run over about 150 programs would cost roughly $200 at list prices.
  **Suggested:** approve the pilot first; set the cap to about $250 only for the first full yearly run.
- **P09-8. Who reviews.** Only admins can use the review page, like the moderation queue; accounts with the "curator" role cannot.
  **Suggested (built):** admins only for now. Option: let curators review catalog changes too.
- **P09-9. What the pilot compares.** The pilot runs the agents on the 11 programs we wrote by hand and checks the program list against our own list of those 11, not against the whole catalog index (the full index check runs in the yearly job).
  **Suggested:** keep it that way; the pilot is meant to measure how well the agents read rules, not to find every program.

## Prompt 10

Questions about the schedule pipeline (reading Class Search). The pipeline is built and tested, but only on pages we made up.

- **P10-1. Reading the real Class Search is blocked. We need a few real pages, and permission.** Nobody has seen a real Class Search results page while building this, and no request was sent to the site. The reader was built against invented pages (`services/scraper/fixtures/SYNTHETIC_*`, each with a big "SYNTHETIC" banner). It cannot read the real site until it has seen real pages. Scraping also stays off (`SCHEDULE_SCRAPER_ENABLED=false`) until the University says it is allowed.
  **Suggested answer:** two steps.
  1. **Permission.** Ask the Registrar (or whoever runs Class Search) one of two things. Is a slow automated read of the public guest Class Search allowed (one page a second, once a week)? Or can they send a data file instead? Write their answer here.
  2. **Save a few real pages from your own browser.** This is you browsing normally, not the scraper.
     - Open the public Class Search as a guest. Pick a term that is already posted (for example Autumn 2026) and search one subject, for example Computer Science (CMSC). If the results run over several pages, open page 2 as well.
     - Do the same for one small subject (for example a language). If you find a subject with no classes that term, save that too.
     - Save each results page with File > Save Page As... Choose "Webpage, HTML Only" (Chrome) or "Page Source" (Safari).
     - Name the files like `REAL_class_search_2026-AU_CMSC_p1.html` and `..._p2.html`. Put them in `quadplan-kit/services/scraper/fixtures/`.
     - Also save the search form before you search, as `REAL_class_search_form.html`. It shows what the term and subject menus are called.
     - Please use the guest view: pages saved while logged in to my.UChicago may show your name. If one does, tell us and we will remove it before saving the file in the project.
  With those pages, the reader's settings (`scraper.parse.DEFAULT_CONFIG`) and the form steps (`scraper.class_search.ClassSearchSite`) can be written for the real site in an hour or two.
- **P10-2. Where the weekly check runs.** The weekly check is a worker job, but the browser it needs (Chromium) is installed only in the scraper container. This does not matter while scraping is off.
  **Suggested:** when scraping is allowed, run the weekly check inside the scraper container (one line in `docker-compose.yml`). Option: also install Chromium in the worker container, which makes it much bigger.
- **P10-3. Which AI model reads department pages.** The SPEC does not name one. It is set to Sonnet 5.5 (`dept_offerings_extraction` in `llm_routing.yaml`), like the other mid-difficulty reading tasks. Every item it returns must quote the page word for word. Code checks each quote, then a curator reviews the list.
  **Suggested:** keep Sonnet 5.5. Option: Haiku 5.5, about 20 times cheaper. It could be tried once the hold on AI calls is lifted, and kept if its answers pass the checks as often.
- **P10-4. Similar instructor names are never merged automatically.** Two different people's names often differ by one letter ("Demo Instructor A" and "Demo Instructor B"). So a name matches an existing instructor only when it is the same words, or a known other spelling of their name. Order, capital letters, accents and punctuation are ignored. A name that is close but different goes to the review queue. A name unlike anyone's becomes a new instructor, with their own forum pages.
  **Suggested:** keep this. Option: let a very close name (one typo) merge on its own. That saves review work, but sometimes joins two different people's reviews.
- **P10-5. Courses on the schedule that are not in the catalog.** If a section's course code is not in the catalog (a new or topics course), the section is not saved. The code goes to the review queue.
  **Suggested:** keep this until the catalog pipeline (prompt 09) can add such courses after review.


## Prompt 12

- **P12-1 (met 2026-11-15 on the final stack: verify 49.6/s, p95 240 ms; forum reads 99.3/s, 0 failures; still re-run on the real server).** **Load-test targets on this laptop (logged per the "same fix fails twice" rule).** Target: checking a plan (`POST /verify`) at 50 a second with 95% answered within half a second, and forum page reads at 100 a second. On the Mac development machine through Docker Desktop:
  - Several runs met the plan-check target: 48.3 a second with p95 240 ms, and 50.3 a second.
  - Others missed it as the machine got busier: p95 400 ms to 2.4 s.
  - Forum reads ran at 100 a second with a median of 11-300 ms and p95 of 200-620 ms.
  - Measured directly, the server handles about 235 forum reads a second, and one read takes 7 ms. Much of the delay comes from Docker Desktop's port forwarding on a Mac with ~100 open connections (138 ms even for the health check) and from running the load generator on the same busy machine.
  - Improvements made: catalog data kept in memory (preloaded and refreshed in the background), forum page headers reused for 5 s, a bigger database pool.

  **Suggested:** run `make loadtest` on the real server before launch (`docs/DEPLOY.md`, and the launch checklist in `docs/PROGRESS.md`). If it misses there, raise `WEB_CONCURRENCY` with the server's CPU count (each worker uses up to 20 database connections; Postgres allows 200).

- **P12-2 (privacy; needs Richard).** **The admin "Suspensions" list can show that two removed posts have the same author.** The list has one row per suspended student, shown by the latest post that was removed with a suspension (never the student's name). If an admin suspends the same student twice, through two different posts, the first row disappears when the second appears. So the admin learns that those two posts were written by the same person, though not who it is (security re-review N7, 2026-11-15).
  - **(a) Accept it (suggested).** Admins already read both posts, and one row per student keeps "End suspension" clear.
  - **(b) One row per removal.** Ending a suspension would then clear all of that student's rows at once, which shows the same link at that moment; it only delays it.
  - **(c) No list.** Admins end a suspension only from the removed post itself, so nothing changes on screen when a second suspension is added.
- **P12-3 (privacy; needs Richard).** **Restoring a backup brings back accounts deleted after that backup.** Backups are kept 14 days. If the database is ever restored from one, accounts (with their emails) deleted since that backup come back. `/privacy` now says backups keep a deleted account for 14 days, and `docs/DEPLOY.md` says what to do after a restore.
  - **(a) Restore only to recover from losing the database, and tell students deleted in that window to delete again (suggested for launch).**
  - **(b) Keep a 14-day list of deleted account numbers (no emails) and delete them again automatically after a restore.** More work; closes the gap fully.

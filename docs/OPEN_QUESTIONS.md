# Open questions and decisions

> **Start here (updated 2026-11-24).** This file records every question that was asked, and its answer. The questions are grouped by the build step that raised them. Almost all of them have an answer. The code cites items by id (for example, P05-7). When you see an id, search for it here. These items are still open:
>
> - **Before launch** ("Deferred until before deployment" below):
>   - **DF-A1**: replace the watermarked demo photo behind the homepage chapel.
>   - **DF-S1**: 44 summer-only courses are not yet in the planner.
>   - The **"Later (by Richard)"** list: email to real users, placement field, Econ specializations, more study-abroad programs, Econ items, the full hand check of `data/seed/REVIEW.md`.
> - **Tests** (at the end of the file):
>   - **E2E-1**: the drawer drag test tries a missed drag again.
>   - **E2E-2**: the preference checks of journey C depend on the time limit of the solver.
> - **Campus companion** (2026-11-20, at the end of the file): **CC-1** to **CC-8**. These are decisions made during the build of the Ask chatbot, the dashboard, the feed and the Commons. Each has a suggested answer.
> - **Site structure and catalog** (GitHub issues #15 and #19, 2026-11-24, at the end of the file): the answers to the decisions of both issues. **S19-N1** (the list of new courses) has an answer: the list stays empty until Richard or Max add courses with a source quote, or until the next catalog year fills it.
> - **Forum page, issue #20** (2026-11-24, at the end of the file):
>   - **F20-1** has an answer: the AI answer under a forum question keeps its 60-word limit, and the team can test how it works in use.
>   - Still open: **F20-2** to **F20-4**. These are defaults taken during the build, each with a suggested answer.
> - **Integration run** (2026-11-24, at the end of the file): **INT-1** (Needs Richard): how long the plan generator can think in the app (4 s now, 20 s in the end-to-end tests).
> - **Student record and dashboard** (2026-11-24, at the end of the file): **SR-1** to **SR-6**. These are decisions made during the build of Issues #14 and #16. Each has a suggested answer.
> - **Merge of PR #21** (2026-11-24, at the end of the file): **M21-1** to **M21-3**. These questions came up during the merge of Max's PR #21 into the integration branch. Each has a suggested answer.
> - **"Work these answers create (not started)"** below is a list from 2026-11-14. Some of its items were built since then. Before you start an item, check `docs/PROGRESS.md` and the code.
>
> Put new questions at the end of the matching section, in plain language, with a suggested answer (see `CLAUDE.md`, "Working with the owner").

Each question below has Richard's answer under it (answered 2026-11-14), or the default that applies when there was no answer. Nothing here is a guessed catalog fact.

New questions in this file use plain language. Each has a suggested answer or a few options (Richard's preference, 2026-11-14).

## Working rule for the demo phase (Richard, 2026-11-14)

> One main idea now as we start further building is that, at this stage we are working towards a working demo. The Catalog is very complicated and intricate and will require a significant amount of manpower to reasearch it out. For now, for every new question that is catalog rule related, you should make a suggestion to yourself, document the desicion as a question for later, and build the thing out first. We will defer solving these questions in the future when we are about to deploy this website.

> **General rule:** when the catalog is unclear, be strict (do not count the course) and show a warning explaining why, so the student can check with an advisor.

What this means in practice:
- **New catalog questions:**
  1. Select the strict reading, and show a warning that explains it.
  2. Add the question to "Deferred until before deployment" below, with the suggested default.
  3. Continue the build.
- **`data/seed/REVIEW.md`:** for the same reason, the rule-by-rule hand check waits until before deployment. The demo uses the seed as it is encoded.

Status words used below:
- **Decided:** there is an answer. Build it.
- **OK:** the current default is confirmed.
- **Default stands:** there was no answer. This is a technical item. Look at it again when the related prompt is built.
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

  This is encoded in `data/seed/2026-27/college_policy.yaml` (`residency_min_units`, `transfer_counts_by_enrollment`). The source is this quote, and both fields have a mark for review. **Before deployment:** find the catalog sentence for each field, and replace the source.
- **Q11. Pace and grading strictness.** Add the two optional 1-5 questions to the review form.
- **P08-2.** Accept; mention it on the privacy page.

**New question from building these answers (2026-11-14)**
- **P08-14. Suspended students, account deletion, and lifting a suspension.**
  - A suspended student cannot delete their account until the suspension ends. The maximum is now 90 days, the longest choice in the admin menu.
  - There is also no button yet for an admin to end a suspension early.

  **Suggested:** Keep the block (if not, a student could delete the account and sign up again to avoid the suspension). Keep 90 days as the longest. Add an "end suspension" action to the admin page later. Option: let suspended students delete their account at any time. Their email is then free for a new sign-up.

  **Decided (Richard, 2026-11-14): go with the suggestion.** The block and the 90-day maximum stay as built. **Built (6c07395):** an "End suspension" action for admins. **Originally planned as later work:** an "end suspension" action for admins. Admins never learn who is suspended. Thus the action would be on the removal decision that started the suspension, in the moderation history.

**OK (go with the suggestion):** P08-6 to P08-13, Q7 to Q10, Q12, Q13, DF-1 to DF-13, P7-1 to P7-8, and the Safari note (use Chrome or Firefox locally).
- P7-1 and P7-2 wait until Richard lifts the hold on API calls.
- DF-8 (Rare UI parts) and P08-11 (instructors in the home search) are later work.

**Work these answers create (done 2026-11-14, see PROGRESS):** P08-1, P08-3, P08-5, Q6, Q11, P08-2 (privacy page line), P08-10 (back to the page after login), DF-6 (note the two pale colors in DESIGN.md), DF-7 (delete confirmation), DF-12 (About page text), DF-13 (phone jump buttons).

## Work these answers create (not started)

**Spec and docs**
- SPEC decision row 12: "Quarterly Forumn" → "Quarterly Forum" (2).
- SPEC Checks table: V02 is not an Error now. It becomes a warning (P02-1).
- SPEC sitemap: instructor names become public. Ratings and reviews stay behind login (P03-12).
- `docs/CONTRACTS.md`: quote the residency sentence from the Graduation Requirements page (P02-6).

**Frontend**
- Show "Likely offered in: {quarters}" on courses. Remind the student when a course is in a quarter where it is probably not offered (4).
- Public instructor names in search and in the instructor directory (P03-12).

**DSL and verifier (`planner_core`)**
- **Whole-sequence construct:** complete every step of a sequence, with any approved level for each step (P05-1). Apply it to all sequences and to Bx/MS `apply_requires` (P05-11c).
- **New rule types:**
  - maximum and minimum standing
  - consecutive quarters
  - per-quarter limits
  - completed-before-program (P05-3)
  - "if placement then" (P05-4)
  - "spans 2 quarters" (P05-9)
  - per-course "counts at most N times" (M1-2)
- **Reminders:** grade and GPA rules become only reminders, not checks (P05-3, P05-11c). Remove the "C in each course" encoding of the Math average.
- **Warning levels:**
  - V02 becomes a warning: exam credit stops counting. Only one of two equivalent courses counts (P02-1).
  - V05: future quarters with one or two courses become warnings (P02-3).
  - `civ_abroad_year` becomes a warning (P05-6).
- **Matching:**
  - A `replaces` (renumbered course) partner also satisfies requirement selectors (P02-2).
  - `in_order` compares the step position (P02-7).
  - Transfer credits count as not in residence (P02-6).
- **New warnings:**
  - needs department approval (P05-12b)
  - catalog inconsistent, check with an Econ advisor (P05-13a)
  - ECMA decided the result (P05-13c)

**Seed data**
- **Physical sciences:** restore the ~250 combinations (P05-1).
- **Overload lists:** language courses by subject code. Reading and Research / thesis courses by title (P05-7).
- **Language Competence:** the third quarter of every first-year language sequence (P05-8).
- **Computer Science:** course-info.cs.uchicago.edu as a second source for curriculum areas and PhD designations, with the five-areas rule (P05-10).
- **Bx/MS:** graduate Reading and Research number, PhD and MPCS Core Systems lists, title checks (P05-11a, b, d).
- **Math:** the equivalent-or-higher chemistry and physics list, MATH 29700 and the Paris courses, the GEOS rule (P05-12).
- **Economics:** standard/honors mixing, Booth alternates (P05-13b, d).
- **Study abroad:** placeholder language courses for Córdoba and Paris (P05-14).
- **Courses:** fetch every subject page, and use the real course blocks (P05-15).
- **Prerequisites:** formalize the 261 sentences with agent E1 (prompt 09). Then spot-check, and hand-review the graduate CMSC electives (P05-16). **On hold:** no API calls until Richard says so.

## Deferred until before deployment

- **DF-A1 (homepage chapel picture and weather, 2026-11-16).**
  - **The chapel drawing on the homepage comes from a watermarked stock photo** (the demo picture that you asked to use for now). It must not go live.
  - Suggested: send me your own photo of Rockefeller Chapel. `tools/ascii-scene/` has the steps to convert it (approximately 15 minutes of my time).
  - **Weather:** the free service of Open-Meteo is for non-commercial use and asks for credit (the caption credits it). If Quarterly earns money at some time (ads, paid plans), it needs the paid plan of Open-Meteo (approximately EUR 29 a month). As an alternative, the scene should change to fixed "clear" weather. Suggested: keep the free service while Quarterly is a free student project.
  - **Update 2026-11-19 (course-title chapel, not yet committed):** the homepage does not show weather now, so the Open-Meteo part does not apply now. (The `/weather` endpoint still exists, and we can remove it.) The photo must still be replaced:
    1. Convert it with `tools/ascii-scene/tools/convert.py`.
    2. Save the result as `tools/course-chapel/scene.rockefeller.json`.
    3. Run `python3 tools/course-chapel/build.py`.

- **DF-S1 (summer-only courses, 2026-11-16).** **44 Summer Session courses are not in the planner.**
  - The Summer Session course finder lists 152 courses that are open to College students (`data/seed/2026-27/summer_courses.yaml`).
  - The 108 courses that are in our course list are now offered in Summer in the planner.
  - The other 44 are not in our 2026-27 course list. Examples: PHIL 20100 Introduction to Logic, PHYS 13300 Waves, Optics & Heat, the Summer Intensive language courses, and some graduate courses such as MAPS 36035.
  - The summer site does not say how many units they have. Thus the file documents them, but a student cannot add them to a plan yet (strict reading: no invented units).
  - **Suggested default:** add each as a 100-unit course that cites its summer page (most College courses are 100 units). Before that, check whether the full College Catalog lists it. Do not add graduate (30000-level) and no-credit (NOCR) courses.
**Later (by Richard)**
- OpenRouter model names (3).
- Sending email to real users. Development uses the console backend (P04-6).
- Student-level placement and credit field in the planner (P05-4, P05-8).
- Econ specializations (P05-13e).
- Other civilization programs abroad (P05-14).
- Econ items (a)–(c), to confirm with the Econ department.
- The full hand check of `data/seed/REVIEW.md`.
- M1-1: department confirmation of the `as_enrolled` reading.

**New questions (Richard, 2026-11-14), with the suggested default to build meanwhile**

Q1. **Transfer students (P05-6).** Does the planner count "second year" from the start of the student at UChicago, or by class standing? If by class standing, the Y2-SP Core warning would show for a transfer student at the end of their first year here.
   *Suggested default:* count from the start of the student at UChicago (what `resolve_term_ref` does now). If not, the warning would show for almost every transfer student. It is only a warning.

Q2. **HUMA 19100 (P05-9).** Must the two quarters be consecutive? If yes, also use the consecutive-quarters rule from P05-3.
   *Suggested default:* yes, require consecutive quarters (the strict reading of "two-quarter series"). Summer does not break the sequence. The warning explains it.

Q3. **CS (P05-10).** Is it correct that 300-level CMSC courses do not count as major electives?
   *Suggested default:* do not count them (strict). When a plan with a CS major has one, show a warning to check with the department.

Q4. **Study abroad (P05-14).** Does the Córdoba/Paris language course count toward Language Competence (the study-abroad route in P05-8)?
   *Suggested default:* do not count it automatically. When the credit field exists (P05-8), the student can enter it as a Language Competence credit, with a warning to confirm with the College.

Q5. **Prerequisites (P05-16).** Should the prerequisites written for master's students apply to Bx/MS students, and not be dropped?
   *Suggested default:* apply them to plans that include a Bx/MS program, as warnings. The warnings explain that they come from the master's-level text.

---

**From prompt 06 (plan generator), with the default built meanwhile**

Q6. **Transfer students and "units earned at UChicago".**
   - The seeded College rule says that a student must earn 3800 of the 4200 units by enrollment here.
   - A transfer student with three years left can earn a maximum of 3600 (nine full quarters).
   - Thus the generator says that no plan exists for them.

   *Suggested default:* keep the rule as written, and show the explanation. Before deployment, find the rule of the College for transfer students (it is probably different), and encode it.

Q7. **Cross-listed courses in generated plans.** When two course numbers are the same course (cross-listed), the generator selects one of them. Usually it is the one that a requirement names first. This is important for the Bx/MS "at most two 20000-level courses" rule (M1-1).
   *Suggested default:* keep it. Students can change to the other number by hand, and the verifier checks either one.

---

**From prompt 11 (forum ratings into course numbers), with the default built meanwhile**

Q8. **How much the start guess counts.** The spec gives two different weights to the start point of a course:
   - In the Forum section: the value of 5 reviews.
   - In the A3 section, for the first guess of the AI: the value of 2 reviews.

   *Suggested default (built):* 5 when the start point is the department average from real reviews. 2 when it is the guess of the AI. Then real data quickly has more weight than a guess.

Q9. **Turning words into a difficulty number.** When a post says that a course is "easy", "moderate", "hard" or "very hard", it counts as 2, 3, 4 or 5 on the 1-5 scale. Its weight is half the weight of a star rating.
   *Suggested default (built):* keep this mapping. Alternative: use words only as supporting quotes, and never as numbers.

Q10. **Which courses get a first guess from the AI.** Only courses that have a forum page get one, a maximum of 200 each night, to keep the cost low.
   *Suggested default (built):* keep it. Alternative: make one guess for every course in the catalog (approximately 1,300 calls).

Q11. **Pace and grading strictness.** Reviews have no question for these, so they stay empty. Thus the "protect my GPA" goal also has nothing to work with yet.
   *Suggested default:* add two optional 1-5 questions to the review form ("How fast did it move?", "How strictly was it graded?"), or do not include them in the demo.

Q12. **Numbers for a specific instructor in the planner.**
   - The forum computes numbers for each course and for each course-and-instructor.
   - But for now, the planner uses only the per-course numbers. The planner does not yet know who teaches each section (that comes with the class schedule, prompt 10).

   *Suggested default (built):* per-course numbers until the schedule is available. Then change to the numbers of the instructor when the instructor of the quarter is known.

Q13. **What counts as "3 ratings".** Forum numbers show only when 3 different posts support them.
   - A discussion post that mentions hours or difficulty counts one time (the middle value of what it says), at half the weight of a review.
   - The text of a review is not read for numbers, because its star ratings already count.
   - Several discussion posts by the same person on the same page also count one time.

   *Suggested default (built):* keep this, so that one person cannot move the numbers of a course by repeating themselves.

---

## Decisions (docs/SPEC.md "Summary and decisions to confirm")

1. **Decision 5 (accounts).** Richard edited row 5 to "Email and password is stored on the backend" and confirmed it:
   - Accounts store the verified `@uchicago.edu` email and an argon2id password hash.
   - There are no blind signatures.
   - CLAUDE.md and SPEC "Accounts and anonymity" were updated to agree.
   - Forum anonymity (per-page pseudonyms, HMAC author refs) did not change.

   **Answer: Resolved (2026-11-12).**

2. **Decision 12 (name).**
   - The UI uses "Quarterly" / "Quarterly Planner".
   - The forum name is written "Quarterly Forumn". The UI uses "Quarterly Forum", because we assumed a typo.
   - Code identifiers keep the neutral names (`planner_core`, `api`, ...). The Compose project and the database are `quarterly`.

   **Answer: Decided.** "Yes, please use 'Forum'." (To do: fix SPEC row 12.)

6. **Which AI model turns each program page into rules (E3)?** Richard (2026-11-14): Fable is overkill, because our own code, the golden plans and a human still check every rule. The main run now uses **Opus 5.5**.
   The spec has a second, separate run. Its answer is compared with the first answer, and each difference goes to a person. Which model should that second run use?
   - **Sonnet 5.5 (suggested, and the current setting).** It costs approximately half the price of Opus. Because it is a different model, it is less likely to make the same mistake as the first run.
   - **Opus 5.5 again, with the instructions in a different order.** This costs the same as the first run, and the two runs can have the same blind spots.

   **Answer: Default (Sonnet 5.5) set in `llm_routing.yaml`; change it if you prefer the other option.**

## Infrastructure

3. **OpenRouter model names** in `llm_routing.yaml` (`anthropic/claude-opus-5.5` style) are not verified against the catalog of OpenRouter. Confirm them before prompt 07. The `max_tokens` values there are start defaults, not from the spec.
   **Answer: Later.**

## Contracts (prompt 01)

4. **"Terms Offered" to `p_offered`.** Until schedule data exists, listed quarters get p = 0.95, and unlisted Autumn/Winter/Spring get p = 0.05 (`method: catalog`). Thus V04 gives a warning when a course is outside its catalog quarters. Confirm this mapping, or give a different one.
   **Answer: OK, decided.** "The idea is that the probability should on the backend of the program. On the front-end the use should see 'Likely offered in: {quarters}'. We should remind the users when they've placed the course in a position that the course is likely not offered. We infer the availability of the courses by using available course offering information and past data."

5. **One `program_version` for each program for each catalog year.** An edit in place of a published version would change the plans made under it. For such edits, v1 uses review items. Look at this again before prompt 09.
   **Answer: OK.**

## Prompt 03 mocks

- All handlers are in `apps/web/src/mocks/handlers.ts`. They are typed from the generated schema. The data is in `mocks/data.ts`, and a toy verifier is in `mocks/verify.ts`.
- They run only in vitest, in Playwright e2e (`VITE_MOCK_API=1` build) and in dev with `VITE_MOCK_API=1`. The Docker build calls the real API.
- The mock data is fake on purpose (catalog year `2099-00`, `TEST`/`FAKE` courses, "Fake Program").
- Remove each handler when its endpoint is real and the e2e test can run against seed data.

| Endpoint(s) | Mocked because | Remove when |
| --- | --- | --- |
| `GET /catalog-years`, `/terms`, `/courses`, `/courses/{code}`, `/course-lists/{name}`, `/programs`, `/programs/{id}`, `/programs/{id}/eligible` | 501 until M1 integration | M1 integration |
| `POST /verify` (toy checks: V01 prereq order, V02 unknown course, V04 offering, V05 > 4 courses, V07 per node) | 501 until prompt 02 is available | prompt 02 merged |
| `POST /agents/generate` (SSE: 5 steps, N variants, done) | 501 until prompts 06/07 | 06/07 |
| `POST /agents/chat` (SSE: message + citations, a proposal when the text says "add") | 501 until prompt 07 | 07 |
| `/auth/*`, `/account/*` (any login works, code `123456`, session flag in sessionStorage) | 501 until prompt 04 | prompt 04 |
| `/plans`, `/plans/import`, `/plans/{id}`, `/plans/{id}/items`, `/plans/{id}/duplicate`, `/plans/compare`, `/plans/{id}/changesets/*` (in-memory) | 501 in M1 | prompts 04/06 |
| `/instructors`, `/instructors/{slug}`, `/forum/*` (one fake instructor, empty threads) | 501 until prompt 08 | 08 |
| `/admin/*` (empty queues) | 501 until prompt 09 | 09 |
| `/health`, `/version` | completeness | any time |

## Prompt 03 frontend questions

- **P03-6. Logged-out session status.** The UI treats any non-200 from `GET /auth/session` (401 or 501) as logged out. Confirm that prompt 04 answers 401 when there is no session.
  **Answer: Default stands.**
- **P03-7. Generate variant metrics keys.** `VariantEvent.metrics` is a free dict. The UI reads `avg_hours` and `hardest_quarter_hours`. Pin these names in prompt 06/07, or tell the frontend.
  **Answer: Default stands** (pin in prompt 06/07).
- **P03-8. "Mark completed" has no op.**
  - The change ops are add/move/remove/lock/unlock.
  - Thus the planner marks an item completed as unlock (if locked) + remove + add with `status: completed`, and keeps the lock.
  - A `set_status` op would be cleaner for `PATCH /plans/{id}/items`.

  **Answer: Default stands.**
- **P03-9. Course details in bulk.** The grid fetches `GET /courses/{code}` one time for each planned course (cached). A batch endpoint (`GET /courses?codes=...` that returns attributes) would remove ~40 requests.
  **Answer: Default stands.**
- **P03-10. Citation links.** `Citation.id` for the `attribute` and `post` kinds has no documented format. Thus those chips are not links (only `course` and `program` chips link). Post chips need the course code and the instructor slug to go to `/courses/{code}/i/{instructor}/t/{id}`.
  **Answer: Default stands** (define in prompt 07/08).
- **P03-11. Goal chip defaults (user preferences, not catalog facts).** You can change them freely.
  - "Challenge me" = `challenge` with `min_index: 10`.
  - "Light quarter" = `light_quarter` with `max_courses: 3`.
  - "Lighter first year" = light quarters for Y1 Autumn–Spring.
  - "Graduate in four years" = `graduate_by` Y4 Spring.
  - "At most one very hard course per quarter" = `difficulty_cap` `max_very_hard: 1`.

  **Answer: OK.**
- **P03-12. Home search of instructors.** The SPEC says that the home page searches courses and instructors. But `/instructors` needs login. Thus for now, the home search covers only courses.
  **Answer: Decided.** "Make instructor names public. Names appear in public search, but ratings and reviews stay behind login."
- **P03-13. Shared read-only snapshot** (planner state "read-only when viewing a shared snapshot") has no route or endpoint yet. It is not built.
  **Answer: OK** (not built yet).

## Prompt 04

These choices let the work continue. Each is the conservative option and is easy to change.

- **P04-6. Email provider.**
  - `EMAIL_BACKEND=console` (development: it prints the code and the pending id, never the address).
  - Or `smtp` (stdlib `smtplib`, STARTTLS with certificate verification). It works with any transactional provider. No provider SDK was added.
  - Which provider, and which `EMAIL_FROM` address?
  - The API does not start with the console backend, development secrets or a non-Secure cookie, unless `ENVIRONMENT` is explicitly `development` or `test`.

  **Answer: Later.** "For now we only make sure that the development enviroment work, sending email to real users later."
- **P04-7. Plus-addressing and aliases.** The app accepts only plain `local@uchicago.edu`. It accepts no subdomains (`@cs.uchicago.edu`, `@alumni.uchicago.edu`) and no `+tag`. Thus one mailbox cannot verify several accounts. If real student addresses need either, relax `normalize_uchicago_email`.
  **Answer: OK.**
- **P04-8. Rate-limit numbers** (`api/auth/ratelimit.py` and the `ip_limit(...)` on each route). Confirm or tune:
  - For each address: 5 codes for each hour, and 10 wrong codes for each day across sign-up and reset.
  - For each pending id: 5 wrong codes.
  - For each login name: 10 failed logins for each 15 minutes.
  - For each account: 10 failed password confirmations for each 15 minutes.
  - For each IP for each day: 40 email/reset starts, 40 registrations, 100 code checks, 300 logins. The IP limits are loose, because campus networks share addresses.

  **Answer: OK.**
- **P04-9. Client IP behind the proxy.** nginx sends `X-Forwarded-For`, and the `api` service sets `TRUSTED_PROXY_HOPS: "1"`.
  **Answer: Resolved (M1 integration).**
- **P04-10. "IP counter never written to disk."** Redis runs with `--save "" --appendonly no`.
  **Answer: Resolved (M1 integration).**
- **P04-11. Session lifetime** is 30 days, fixed (use does not make it longer). A password reset ends all sessions. A password change ends all sessions except the current one.
  **Answer: OK.**
- **P04-12. Forum identity.**
  - `api.auth.hashing.author_ref(account_id, page_id)` implements the `HMAC(server_key, account_id ‖ page_id)` of the SPEC.
  - Account deletion computes it again for each forum page, to find the rows of an account. Thus prompt 08 must use the same function for `author_ref`, `voter_ref` and `reporter_ref`.
  - With "delete my posts", a comment with replies from other people is blanked ("[deleted]", no author), not removed. Thus the replies stay.
  - Vote rows are removed, but the tallied scores are not computed again.
  - Confirm.

  **Answer: Default stands** (revisit in prompt 08).
- **P04-13. CSRF for later prompts.**
  - Each POST/PATCH/DELETE sent with a session cookie needs `X-CSRF-Token` (from `SessionOut.csrf_token`). The app enforces this everywhere.
  - Exempt: the pre-session `/auth/*` steps and the stateless `POST /verify`.
  - Frontend code can use the client in `apps/web/src/features/auth/api.ts`, which adds the header.

  **Answer: Default stands.**
- **P04-14. Plans API.** CONTRACTS lists `/plans` CRUD and `/plans/import` as "04/06". Prompt 04 built only the read path for `GET /account/export` (`api/auth/account_data.py`, which assumes that `goal.params` holds the type-specific fields of the goal). Prompt 06 does the rest.
  **Answer: Default stands** (prompt 06).
- **P04-15. Suspended accounts** (`account.status`, `suspended_until`) can still log in. The forum (prompt 08) should enforce the suspension where it is important.
  **Answer: OK.**

## Prompt 05

Seed data for catalog year 2026-27 (fetched 2026-11-12).

- Each item tells what was encoded meanwhile (the strictest reading that the DSL can express).
- The seed marks these nodes `needs_review`. `data/seed/REVIEW.md` lists them with their quotes.
- The numbers are P05-n, so that parallel prompts do not collide.

**Richard's general rule for these items:** when the catalog is unclear, be strict (do not count the course) and show a warning explaining why, so the student can check with an advisor.
### DSL / verifier gaps

- **P05-1. `same_sequence` accepts any subset of one sublist.**
  - A three-course sublist would also accept each of its pairs. One course of a calculus pair passes the Core math part.
  - For the physical sciences Core, we kept only three-course combinations in which every pair is also approved.
  - Thus 250 three-course combinations that the catalog permits are not included: PHSC 11600-11700 + any PHSC Core course, Astro 12000s triples, PHSC 18000s + any approved pair.
  - Also not encoded: "the student must take two calculus courses" when calculus is used for the math Core.
  - Option: a "whole sublist or nothing" / minimum-per-sublist constraint in the DSL.

  **Answer: Decided.** "Take courses from one approved sequence" means the whole sequence must be taken: every step completed. Each step may be taken at a different level (e.g. the analysis sequence can be completed as MATH 20700 → MATH 20410 → MATH 20500). A partial sequence never passes (one course of a calculus pair, or two of a three-course sequence). Add a DSL construct for "complete every step; any approved level per step." Apply it to all sequences unless the catalog says otherwise. Restore the ~250 dropped physical sciences combinations under it. This also enforces "two calculus courses" for the math Core.
- **P05-2. Group-level constraints.** `econ-ba/empirical` has `in_order` on a `group` node. The three Bx/MS roots have `max_from` ("at most two courses from the 20000-level offerings") on `group` nodes. Please confirm that the verifier applies group-level constraints to all courses used under the group.
  **Answer: Resolved.** The verifier applies group-level constraints (`in_order`, `max_from`) to all courses under the group, as confirmed in M1 integration. No change. See M1-1 for how cross-listed courses count toward the cap.
- **P05-3. Rules that the DSL cannot express (not included):**
  - "enrollment limited to first-year students" (a maximum standing, CHEM 10100/10200).
  - "beyond their first year" for study abroad.
  - HIST 13500-13700 needs two *consecutive* quarters.
  - Econ empirical methods "in consecutive quarters".
  - "no more than one per quarter" for Bx/MS Reading and Research.
  - "exactly three courses per quarter", and "3900 of 4200 units and all general education before the first Bx/MS quarter".
  - Grade averages (Math approved courses "overall C average", encoded as C in each).
  - GPA rules.

  **Answer: Decided.** Add DSL rule types for:
  - maximum standing (first-year-only courses: CHEM 10100/10200)
  - minimum standing (study abroad beyond the first year)
  - consecutive quarters (HIST 13500–13700; Econ empirical methods)
  - per-quarter limits (Bx/MS: at most one Reading and Research per quarter; exactly three courses per quarter)
  - completed-before-program (3900 of 4200 units and all general education before the first Bx/MS quarter)

  Grade and GPA rules become reminders only, not checks. Remove the "C in each course" encoding of the Math "overall C average."
- **P05-4. Placement-conditional rules.**
  - CS: if a student places out of CMSC 14300 (CS 3 exam), the student needs one extra elective. The Discrete Mathematics Placement Exam permits Theory BC / BCC.
  - Math: the MATH 15910/16300 requirement is waived when the first course is MATH 20700.
  - Not encoded (there is no "if placement then" node). The standard path is required.

  **Answer: Decided.** Add "if placement then" support. Eventually, placement results will be a student-entered field in the planner, stored once at the student level and available to every check (the field itself is deferred). Cases:
  - CS 3 exam placing out of CMSC 14300 → one extra elective
  - Discrete Mathematics Placement Exam → Theory BC / BCC options
  - Math: the MATH 15910/16300 requirement is waived when the student's first math course is MATH 20700, 20310 or 20300 (detectable from the plan; no placement input needed)
- **P05-5. `requires: ["cmsc-b?"]`** (Bx/MS Options 1-2) and `excludes: ["cmsc-b?"]` (Option 3) use a shell glob (`?` = one character) for "CS BA or CS BS". Confirm the glob semantics, and that `requires` means any-of.
  **Answer: OK.** Keep the glob. `?` matches exactly one character; `requires` means any-of (at least one match).

### Catalog wording

- **P05-6. Core timing.**
  - The catalog says that the Core "should be completed by the end of the second year". It is encoded as `core_complete_by: Y2-SP` (V10 is a warning).
  - `civ_abroad_year: 3` comes from the Core requirements PDF of the College, which has no catalog year.
  - Keep both?

  **Answer: Decided.** Keep `core_complete_by: Y2-SP` as a warning. Keep `civ_abroad_year: 3`, but as a warning only, since the source PDF has no catalog year. (Follow-up: Q1, transfer students.)
- **P05-7. Overload reasons.**
  - "a 200-unit language course" is encoded as any course of 200+ units (there is no seeded list of language courses).
  - "Reading and Research or B.A. Thesis/Colloquium course" uses a list made from course *titles* (CMSC 29700, CMSC 29900, ECON 29700, DATA 29700, HUMA 29700, ...). Departments can have other thesis/colloquium courses.
  - Who owns this list?

  **Answer: Decided.** Build both lists automatically each catalog year and flag new entries for review:
  - language courses by subject code (replaces "any course of 200+ units")
  - Reading and Research / B.A. Thesis/Colloquium courses by title
- **P05-8. Language Competence.**
  - Only the course route is encoded. FREN 10300 and SPAN 10300 are the only seeded "third course of a first-year language sequence".
  - The exam, placement, AP/IB, study-abroad and proficiency routes are not plan items.
  - Model them as `credits` that satisfy `core/language`, and seed the third quarter of every language?

  **Answer: Decided.** Model the exam, placement, AP/IB, study-abroad and proficiency routes as credits that satisfy `core/language`, entered in the same student-level field as placement results (P05-4; the field itself is deferred). Seed the third quarter of every first-year language sequence.
- **P05-9. Writing Grey track.** HUMA 19100 is one course number, taken in two quarters. It has the mark `repeatable` (the catalog says "two-quarter series", not "repeatable"). *(M1 integration: the verifier now counts each enrolment of a repeatable course, see M1-2.)*
  **Answer: Decided.** Replace `repeatable` with a specific "spans 2 quarters" marker: the course must be taken in exactly two quarters. (Follow-up: Q2, consecutive quarters.)
- **P05-10. Computer Science.**
  - BA electives must "span at least five curriculum areas".
  - Only course-info.cs.uchicago.edu publishes the areas and the PhD Core/Elective designations. The catalog does not.
  - Encoded: BA electives = any 8 CMSC 20000-29999 (breadth not checked). The specialization lists exactly as printed. CMSC 300-level courses are not accepted as major electives.
  - Can we use course-info as a second source?

  **Answer: Decided.** course-info.cs.uchicago.edu may be used as a second source. The catalog takes priority; course-info fills gaps (curriculum areas, PhD Core/Elective designations). Record the source of each fact. Use it to check the BA rule that electives "span at least five curriculum areas." (Follow-up: Q3, 300-level courses.)
- **P05-11. Bx/MS.**
  - (a) The page names no course for "two Reading and Research courses". It is encoded as two more CMSC 30000-level courses.
  - (b) The PhD-program Core Systems courses and the MPCS Core Systems / Core Programming courses are not in the catalog. Only the Systems list of the major is used. (Graduate cross-listed numbers match through cross-listing.)
  - (c) Admission (3.5 GPA, B+ average in two intro courses) is not encoded. `apply_by: Y3-WI` comes from the January/February admissions cycle. There is no `apply_requires`, because the requirement is a choice of pairs.
  - (d) The titles of CMSC 37115, MPCS 50103 and MPCS 55001 come from the requirement labels (we found no course block).

  **Answer: Decided.**
  - (a) Find the graduate Reading and Research course number on course-info. Keep "two more CMSC 30000-level courses" until then.
  - (b) Add the PhD Core Systems and MPCS Core Systems / Core Programming lists from course-info or the MPCS website.
  - (c) Admission GPA/grade rules (3.5 GPA, B+ average) become reminders. Keep `apply_by: Y3-WI`. Add `apply_requires` using the new P05-1 construct ("complete one of these pairs before applying").
  - (d) Keep the titles of CMSC 37115, MPCS 50103 and MPCS 55001 taken from the requirement labels; mark them `needs_review` and verify against course-info / the MPCS site.
- **P05-12. Mathematics.**
  - "(or equivalent)" / "(or higher)" after the chemistry and physics sequences is not encoded. (Honors chemistry and PHYS 13100/14100 are not accepted for the general education of the math majors.)
  - MATH 29700 ("as approved") and the Paris courses are not on the approved list.
  - PSCD "department" is read as subject code.
  - "GEOS courses not cross-listed as PHSC" and "reserves the right to exclude courses which are new in 2026-27" are not encoded.
  - The BS minor field is read as three courses in addition to the four PSCD courses.

  **Answer: Decided.**
  - (a) Encode "(or equivalent)" / "(or higher)" for the chemistry and physics sequences: accept honors chemistry and PHYS 13100/14100, via an explicit list of equivalent-or-higher sequences.
  - (b) Add MATH 29700 and the Paris courses to the approved list with a "needs department approval" warning.
  - (c) Confirmed: "PSCD department" = subject code belonging to a PSCD department; BS minor field = three courses in addition to the four PSCD courses.
  - (d) Encode the GEOS rule (read as: GEOS courses not cross-listed as PHSC do not count; confirm against the catalog wording). "Reserves the right to exclude courses new in 2026–27" becomes a reminder.
- **P05-13. Economics.**
  - (a) The Fundamentals table lists MATH 20420 as an alternative to MATH 15250, but the Summary of Requirements does not. MATH 20420 is not accepted.
  - (b) A mix of standard and honors core courses is not accepted.
  - (c) ECMA courses count on the strict side of "at least two economics courses numbered higher than ECON 20210" (with outside electives and ECON 10200, at most 2 of 4).
  - (d) The Booth 3xxxx alternates of the pre-approved BUSN courses are not encoded.
  - (e) Only the standard track is seeded. The three specializations are not.

  **Answer: Decided.**
  - (a) Do not accept MATH 20420; show a warning that the catalog is inconsistent and the student should check with an Econ advisor.
  - (b) Allow mixing standard and honors core courses (consistent with P05-1) unless the Econ catalog explicitly forbids it. Check the catalog.
  - (c) Keep ECMA on the strict side; show a warning when ECMA courses decide the result.
  - (d) Add Booth 3xxxx alternates where the catalog lists the numbers; otherwise leave out.
  - (e) Specializations: deferred.
- **P05-14. Study abroad.**
  - The Córdoba and Paris (Migration, Decolonization, and Diaspora) programs include a Spanish / French course with no course code on the program page. It is not encoded.
  - Only these two civilization programs abroad are seeded. Thus `core-civ-sequences` accepts only these two abroad.

  **Answer: Decided.** Add placeholder courses for the Córdoba Spanish course and the Paris French course. Other civilization programs abroad are deferred. (Follow-up: Q4, Language Competence.)
- **P05-15. Cross-list copies.** 366 Equivalent Course codes have no block on the fetched pages. They are seeded as copies of the block that names them (the same title, units, prerequisites, terms). OK, or fetch every subject page?
  **Answer: Decided.** Fetch every subject page. Use the real course block wherever it exists; keep the copy only for codes that still have no block.
- **P05-16. Prerequisites.**
  - 261 prerequisite sentences are not formalized. None is on a course that a slot names. Most are BIOS, SOSC, BUSN, ARTH, STAT and graduate CMSC electives.
  - They keep `prereq_text` and `needs_review`.
  - Sentences only for master's/graduate students were dropped.
  - Run agent E1 over them, or encode them by hand?

  **Answer: Decided.** Run agent E1 over the 261 unformalized sentences, then spot-check a sample by hand. Review every graduate CMSC elective by hand. (Note: E1 is built in prompt 09 and calls the Anthropic API. Follow-up: Q5, master's-level prerequisites.)

### Infrastructure note (not a catalog question)

- **P05-17. `make golden` was slow.** `golden.py` now parses the seed one time for each catalog year.
  **Answer: Resolved (M1 integration).**
- **P05-17b.** `golden.py` still runs `build_catalog` one time for each plan. If it built the catalog one time for each catalog year, `make golden` would be faster.
  **Answer: Default stands.**

## Prompt 02

These are verifier readings that are choices, not catalog facts. Each one is implemented as stated (see `docs/CONTRACTS.md` "Verifier semantics"). You can change each one in one place.

- **P02-1. V02 levels.**
  - The spec lists V02 as Error. Thus "exam credit forfeited when the course is also taken" is an error (remove the credit or the course).
  - Two courses related as `equivalent` or `replaces` are also an error.
  - Should forfeiture be a warning that only stops the count of the credit?

  **Answer: Decided.** Change both to warnings:
  - (a) Exam credit plus taking the same course: warning; stop counting the exam credit.
  - (b) Taking two courses related as `equivalent` or `replaces`: warning; count only one.

  Units, requirement and other checks still catch any real problem this causes. Update the spec (V02 is no longer an Error).
- **P02-2. `equivalent` vs cross-listing.**
  - The "Equivalent Course(s)" line of the catalog is the cross-list line. It goes in `crosslists`.
  - The verifier lets `equivalent` / `replaces` partners satisfy prerequisites and deadlines. But selectors match only on cross-list groups (contract).
  - Confirm.

  **Answer: Decided.** Confirmed: the catalog's "Equivalent Course(s)" line goes in `crosslists`; selectors match on cross-list groups; `equivalent` / `replaces` partners satisfy prerequisites and deadlines only. Exception: where `replaces` represents a renumbered course (old number → new number), it also satisfies requirement selectors, so students who took the old number are not wrongly flagged.
- **P02-3. V05 on quarters in progress.**
  - Empty quarters and Summer get no flag.
  - A quarter with one or two courses is an error (below full time).
  - A quarter with only `completed` courses reports as info.
  - Should a half-built future quarter be a warning, not an error?

  **Answer: Decided.** Future quarters with one or two courses: warning (not error). Completed quarters: info. Empty quarters and Summer: no flag.
- **P02-4. Civilization abroad in third year (V10).** `CollegePolicy` has only `civ_abroad_year`. A late Core course is excused when a `study_abroad_block` program of the plan uses it, or when it is in the term of a `study_abroad` goal. Is that the correct test, or should courses have a tag?
  **Answer: OK.** Keep the current test (excused when used by a `study_abroad_block` program of the plan, or in the term of a `study_abroad` goal). No course tag needed. Low risk, since this is a warning (P05-6).
- **P02-5. Share limits are per pair of programs** ("at most 0 with each major"), as in the formula of the spec. Some rules can mean "in total across all minors". The DSL cannot say that yet.
  **Answer: Decided.** Keep per-pair share limits. Mark any rule whose wording says "in total" or "across" (e.g. across all minors) as `needs_review`. Add a "total across programs" option to the DSL when a real rule needs it.
- **P02-6. Residency.**
  - "Half of each program in residence" is measured on the courses that the solver assigns to the program.
  - The Core and study-abroad blocks are exempt from the College-wide share, unless the program states its own share.
  - Confirm against the Graduation Requirements page.

  **Answer: Decided.** Find and quote the exact sentence from the Graduation Requirements page in `docs/CONTRACTS.md` next to the implementation, and adjust if the wording differs. Make sure transfer credits count as not in residence.
- **P02-7. `in_order` and `distinct_subjects`.**
  - `in_order` compares courses of one subject by course number, and needs strictly increasing terms.
  - `distinct_subjects` uses the subject of the code as written in the plan. (A cross-listed course counts under the code that the student enrolled in.)

  **Answer: Decided.**
  - `in_order`: compare by step position in the sequence (step 1, 2, 3), not by course number, so mixed-level sequences (P05-1, e.g. MATH 20700 → MATH 20410 → MATH 20500) and mixed-subject sequences work. Fall back to course number only when a sequence has no steps. Keep strictly increasing terms.
  - `distinct_subjects`: confirmed, it uses the subject of the code as enrolled (consistent with M1-1).
- **P02-8. Attribute values.**
  - `/verify` reads `attribute_value` rows with `subject_type = course` and `subject_id` = course code. Prompts 08/11 must write them that way.
  - Default thresholds when a goal sets none: "very hard" = difficulty 4.0 or more. "strict grading" = 4.0 or more (1-5 scale).

  **Answer: Default stands.**
- **P02-9. Graduation totals count placeholders** (100 units each). Thus a plan with unfilled slots shows the units that it intends. V07 still fails until the slots are filled. Confirm.
  **Answer: Default stands.**
- **P02-10. Incomplete plans and the solver.**
  - The verifier decides exactly whether the programs are satisfied.
  - For an incomplete plan, the list of missing requirements comes from a second solve with a deterministic work limit. On very hard instances, it may not be the smallest list, and the report says so.
  - The benchmark instance (60 courses, 201 nodes, 3 programs) is proven optimal.

  **Answer: Default stands.**
- **P02-11. `VerifyOptions.strictness`.** Currently, `strict` only makes workload goals use the upper confidence bound. Should it also change V04 / V10 warnings into errors?
  **Answer: Default stands.**

## M1 integration

These decisions were made to make the nine failing golden plans pass. Each one is implemented and tested.

- **M1-1. Level caps and cross-listed courses (`max_from.as_enrolled`).**
  - The contract matches selectors on cross-list groups. Thus "at most two courses from the 20000-level offerings" also counted CMSC 33550 (cross-listed with CMSC 23500) and CMSC 33380 (with CMSC 23380).
  - With that reading, no plan can satisfy Bx/MS Option 3 from the seeded lists. It needs three Core Systems courses, and every course on the Systems list of the major is a 20000-level number. (The PhD and MPCS Core Systems lists are not in the catalog, P05-11b.)
  - The golden plans of prompt 05 assumed the other reading: a course counts under the number that the student enrolled in.
  - Implemented as an opt-in flag on the limit (`as_enrolled: true`). It is set only on the three Bx/MS roots, and still has `needs_review`. Every other `max_from` (for example, the Economics ECMA / outside-elective caps) keeps the stricter group reading.
  - To confirm with the department: does a cross-listed course taken under its 30000-level number escape the 20000-level cap? If not, Option 3 needs the PhD / MPCS Core Systems lists before any plan can pass.

  **Answer: OK.** Keep `as_enrolled: true` on the three Bx/MS roots only; every other `max_from` keeps the stricter cross-list-group reading. Keep `needs_review` until the CS department confirms that a cross-listed course taken under its 30000-level number escapes the 20000-level cap (deferred). Adding the PhD / MPCS Core Systems lists (P05-11b) reduces Option 3's dependence on this reading.
- **M1-2. Repeatable courses count once per enrolment.**
  - `core/writing/grey` is `count: 2` from the single code HUMA 19100. No plan could satisfy it while a course counted one time.
  - Each enrolment of a `repeatable` course is now a separate course for program requirements. (The n-th counts only in the unit where the (n-1)-th counts.)
  - Thus CMSC 29700 / CMSC 29900 taken two times also count two times toward electives. The CS majors already cap each at one with `max_from`.
  - Is "counts one time for each enrolment" correct for every repeatable course, or should the DSL say how often?

  **Answer: OK, decided.** Each enrolment of a `repeatable` course counts as its own course by default. Add an optional per-course limit to the DSL ("counts at most N times") for when the catalog gives one; programs can still cap with `max_from`. HUMA 19100 no longer relies on this: it uses the "spans 2 quarters" marker (P05-9).
- **M1-3. V12 when another course takes the Pass/Fail course's place.**
  - `cmsc-bxms-2/fail-03` (Algorithms CMSC 37000 taken Pass/Fail, CMSC 27200 also in the plan) reported only V07 on Core Systems.
  - The solver put CMSC 27200 in the Algorithms slot. This pushed the plan over the 20000-level cap in a different place.
  - V12 now also fires when the program is unmet but would be met if its Pass/Fail courses had letter grades. (The check is for that program alone, and ignores share limits.)

  **Answer: OK.**
- **M1-4. A share-limit must-fail for Bx/MS Option 1 needs a 30000-level number.**
  - Discrete, Algorithms and ML taken as CMSC 27100 / 27200 / 25300 are three 20000-level courses. Thus the cap (V07) fails before the share limit (V08) can fail.
  - `cmsc-bxms-1/fail-05` now takes ML as CMSC 35300 (cross-listed with CMSC 25300, which the major needs). Thus exactly the share limit fails.

  **Answer: OK.** Note: this test depends on the M1-1 reading; if the department rejects `as_enrolled`, revise this test.

## Design foundation

This section lists the places where `docs/DESIGN.md` (the look) and `docs/SPEC.md` (what the pages do and say) do not agree, or where DESIGN.md says nothing.

- The app keeps the behavior of the SPEC and follows DESIGN.md for the look.
- Each item tells what was built.
- `docs/DESIGN-IMPLEMENTATION.md` tells how DESIGN.md maps to code.

- **DF-1. Site name.** The wordmark of DESIGN.md is "UChicago Course Forum". The SPEC and the app call the site "Quarterly". Which name should the header show?
  **Suggested:** keep "Quarterly" (built that way, in the DESIGN.md wordmark style: the light serif). Option: change to "UChicago Course Forum" everywhere. This also changes page titles and tests.
- **DF-2. Planner width.** DESIGN.md caps page content at 1200px wide. The planner has three columns side by side (requirements, the four-year grid, issues and advisor). They do not fit in 1200px without a squeezed grid.
  **Suggested:** let only the planner use up to 1600px (built). Every other page stays at 1200px or narrower. Option: keep 1200px, and put the issues and advisor panel under the grid on every screen size.
- **DF-3. Course code in the course page title.** The course page header of the SPEC starts with the code and title ("CMSC 14300 · Systems Programming I"). DESIGN.md says that course codes are never in the large serif type.
  **Suggested:** keep both in the one heading, but show the code as a small grey label above the title, in the plain font (built). Screen readers still read "CMSC 14300 · Systems Programming I".
- **DF-4. The filled button in the top bar.** The top bar of DESIGN.md ends with a filled maroon button. But DESIGN.md also says "one filled maroon button per page", and most pages already have one ("Start planning", "Add to plan", "Generate plan").
  **Suggested:** the "Log in" of the top bar is an outlined button, not a filled one (built). Option: add a filled "Sign up" button to the top bar on every page.
- **DF-5. Several "Apply" buttons at once.** The Generate popup shows one result card for each variant (a maximum of three). The advisor can show several proposal cards. The "Apply" of each card is a filled maroon button. Thus one view can show two or three.
  **Suggested:** keep it (built). Each card is its own decision, and if only one were filled, it would suggest a favourite. Option: make the "Apply" of every card outlined, and keep filled buttons only for page-level actions.
- **DF-6. Colors for "warning" and "information" boxes.** DESIGN.md gives a pale background for errors and successes, but not for warnings and information notes.
  **Suggested:** use the warning and information colors mixed at 8% into white. This is the same recipe that DESIGN.md uses for the pale maroon (built, no new color values). If you agree, add these two colors to DESIGN.md.
- **DF-7. Deleting without a second step.** DESIGN.md says that delete buttons ask "are you sure?" in place. Today, "Delete" on My plans removes a plan immediately. That is the existing behavior, and this task did not change behavior.
  **Suggested:** add an in-place "Delete? Yes / Cancel" step to plan deletion now, and to forum posts when the forum is built. Option: keep plan deletion as one click, because the student can duplicate a plan first.
- **DF-8. Rare UI components.** DESIGN.md suggests animated components from Rare UI (toasts, drawers, counters, the animated hero orb). None is installed yet. Each one comes from an outside website, and each requires a visible credit link.
  **Suggested:** add them one at a time when the forum is built (toasts and the delete button first). Restyle each to our colors, with the credit in the footer. Until then, the hero orb is a still, soft color glow.
- **DF-9. Filters on phones.** DESIGN.md moves course filters into a bottom drawer on phones. Currently, the course search filters are above the results on phones.
  **Suggested:** build the drawer together with the Rare UI drawer (DF-8). Until then, the stacked filters work.
- **DF-10. Dark mode.** DESIGN.md does not define one, and says to ask first.
  **Suggested:** no dark mode for the demo (built that way).
- **DF-11. A footer on every page.** DESIGN.md has a footer. The page list of the SPEC does not mention one.
  **Suggested:** keep the footer (built), with links only to pages that the SPEC already lists (planner, my plans, programs, course search, instructors, guidelines, privacy, about).
- **DF-12. What the About page says (design review, step 5).** The About page is still empty. It showed a note for us ("Placeholder ... built in prompt 03"). It now says "Coming soon". The SPEC says only that the page holds "disclaimers", and disclaimers are your decision, not ours.
  **Suggested:** three short paragraphs:
  1. Quarterly is a student project. The University of Chicago does not run it or endorse it.
  2. The planner checks plans against the published catalog, but your adviser and the official degree audit have the final word.
  3. Forum posts are the opinions of students. They are moderated, and they are anonymous to other students.

  Options: write it yourself, or remove the About page and put one line of this in the footer.
- **DF-13 (superseded 2026-11-14 by FEEDBACK "Planner GUI": the advisor now opens from the top as its own sheet, and the jump buttons were removed).** **The advisor on a phone (design review, step 5).** On a phone, the planner shows its three columns one after the other: requirements, then the four-year grid (twelve quarters), then the Issues / Goals / Advisor panel. A student who wants to ask the advisor must first scroll past the full grid (approximately 4,000 pixels, several screen lengths).
  **Suggested:** only on phones, add a small row of three buttons under the plan name ("Requirements", "Plan", "Issues and advisor"). Each button jumps to its part. Nothing else moves. Options: put the Issues / Goals / Advisor panel above the grid on phones. Or keep it as it is (built that way today).

## Prompt 07

The plan generator and the advisor are built and tested only on a fake model. Nothing went to Claude or OpenRouter.

- **P7-1. Turning the AI on.** The app talks to the AI providers only when `.env` has `LLM_LIVE=true` and an API key. It is off by default because of your hold on API calls. While it is off:
  - "Generate plan" still works. It selects electives by your interests and course ratings, and shows no one-line explanations.
  - The advisor handles only typed confirmations. Each question gets "The advisor can't answer right now."

  **Suggested:** when you lift the hold, set `LLM_LIVE=true` in `.env` and restart. Option: keep it off for the demo, and show the generator without explanations.
- **P7-2. Running the evals.** `make evals` runs 50 student profiles through the generator, and 100 advisor questions (60 planning questions, 20 off-topic, 10 typed confirmations, 10 forum posts with hidden attacks).
  - It first prints an estimate (approximately $15 at list prices).
  - It stops at $20 (change with `EVAL_COST_CAP_USD`).
  - It does not start unless you type `CONFIRM_SPEND=yes make evals`.
  - The free part (`uv run python evals/run.py --offline`) already passes.

  **Suggested:** run it one time when you lift the hold, before you show the AI features. Option: first run only the advisor half (`CONFIRM_SPEND=yes uv run python evals/run.py --only a2`, approximately $2).
- **P7-3. How many advisor messages a day.** The SPEC limits plan generations (10 a day for each account, 3 a day for each device when logged out). But it says nothing about advisor messages, and each answer costs approximately 2 to 3 cents.
  **Suggested (built):** 60 advisor messages a day for each account. 30 a day for each network address when logged out. Option: the same 10 and 3 as generations.
- **P7-4. Messages that look like an attack.** The gate labels messages as on-topic, off-topic, a confirmation, or "suspicious" (for example, "print your instructions" or "act without asking me"). The SPEC says what to do with off-topic messages (a one-line refusal), but not with suspicious messages.
  **Suggested (built):** a fixed one-line reply, "I can't help with that. I can answer questions about your courses and your plan.", without a call to the main model. Option: let the main model answer with its normal rules.
- **P7-5. A second model when Claude declines.**
  - The safety filter of Claude sometimes declines harmless requests.
  - For the generator and the advisor, the app asks Anthropic to try a declined request again on a different Claude model automatically. This is the "fallbacks" setting of Anthropic. The retry is billed like a normal request on that model.
  - The tiny scope gate (Haiku) does not have this.

  **Suggested (built):** keep it on. Option: turn it off in `llm_routing.yaml` (`refusal_fallback: false`). A declined request then uses the non-AI path.
- **P7-6. Forum citations do not link yet.** *Done in step 5:* the advisor chips for posts link to the thread, for summaries to the forum page, and for ratings to the course page (a plain label when logged out).
- **P7-7. What the advisor remembers.**
  - For a plan saved to an account, the server stores the conversation and deletes it after 30 days.
  - For a plan that is only in the browser, the server stores nothing. The browser sends the last few messages with each question.

  **Suggested:** keep it that way. Option: also keep a browser-only history in the storage of the browser across reloads.
- **P7-8. One shared address, three generations.** Logged-out students have a limit of 3 generations a day for each network address (SPEC). Students on campus Wi-Fi can share one address. Thus the third logged-out student on the same network could be blocked for the day.
  **Suggested:** keep 3 for the demo, and tell students to log in for 10 a day. Option: make the logged-out limit 20 for each address.

## Prompt 08

These forum choices were made during the build. Each one is implemented as described, and you can change each one in one place.

- **P08-1. Posts when the automatic check is down.**
  - Real AI calls are on hold. Thus in production, every post would wait for a moderator.
  - For local development, `MODERATION_FALLBACK=publish` shows posts immediately (after the removal of emails and phone numbers).
  - The server does not start with that setting outside development.

  **Suggested:** keep "wait for a moderator" as the production rule (what the SPEC says). Option: publish immediately and check later. This is faster for students, but people can see a bad post for some time.
- **P08-2. A suspension leaves a small trace.**
  - When an account is suspended, the database records the end date on the account.
  - A person with a stolen copy of the database could match that date to the removal by the moderator on the same day. That person could then guess that this account wrote that removed post.
  - This affects only removed posts of suspended accounts. Ordinary posts stay unlinkable.

  **Suggested:** accept it, and say so on the privacy page. Options: start suspensions on the next Monday, which makes the match less clear. Or keep suspensions outside the database (lost if the server restarts).
- **P08-3. Repeat suspensions.** Every third post that a moderator removes suspends the account for 30 days (thus the 3rd, 6th, 9th...). Posts that the automatic check rejects do not count, unless a moderator also removes them.
  **Suggested:** keep this, and let an admin ban an account by hand after the second suspension. Option: an automatic permanent ban at 6 removals.
- **P08-4. Which term a reviewer can pick.** A review must name a term in which the schedule shows that the instructor taught the course. Students who took it before our schedule data starts cannot review it yet.
  **Suggested:** keep it for the demo. When the schedule data goes back further, the list becomes longer automatically. Option: permit any term in the last four years. This lets older students review, but the app cannot check that they really took the course then.
- **P08-5. Cross-listed courses.** A course listed under two codes (for example, CMSC 25300 and STAT 27700) with the same instructor would get two separate forum pages. Its reviews would be split.
  **Suggested:** one page for each cross-listed group, shown under every code. This needs a small change when the schedule pipeline (prompt 10) creates pages.
- **P08-6. Who moderates.** Only admins can use the moderation queue. Curators cannot.
  **Suggested:** only admins for now. Option: let curators also moderate.
- **P08-7. Deleting a post that has replies.** The text of the post becomes "[deleted]", and its author is hidden. Thus the replies under it stay readable. A post with no replies is removed fully.
  **Suggested:** keep this.
- **P08-8. No images in posts.** A picture loaded from a different website would tell that website the address of every student who reads the post. Thus images are not permitted. Links are permitted (they open only on a click).
  **Suggested:** keep it. Option: permit images that we host ourselves, later.
- **P08-9. Rate limits.** For each account: 10 posts an hour and 30 a day, 60 comments an hour, 300 votes an hour, 20 reports a day, 30 edits or deletions an hour.
  **Suggested:** keep these for launch, and adjust them from real use.
- **P08-10. Back to the forum after logging in.** Forum pages ask readers to log in. But then the login page opens the planner, not the page that they came from. (The login page is part of prompt 04.)
  **Suggested:** go back to the page that they came from. This is a small change to the login page.
- **P08-11. Instructor names in the home page search.** The names are now public on `/instructors`, which has its own search. But the home page search still covers only courses (the home page was outside this task).
  **Suggested:** add instructors to the home search in a later pass.
- **P08-12. Deleting an account right after a moderator removes a post.**
  - If a person deleted an account and signed up again, the count of removed posts would also go away. A rule-breaker could use this to avoid a suspension.
  - Thus an account cannot be deleted for 30 days after a moderator removes one of its posts. The student sees a message that tells why.
  - Removals that an admin later reverses do not count.

  **Suggested:** keep the 30-day wait. Option: permit deletion at any time, and accept that a determined rule-breaker can reset their count. (An admin can still block their email by hand.)
- **P08-13. Logged-out students and the AI helpers.** Forum posts are only for logged-in students. Thus for a student who is not logged in, the plan generator and the advisor chat cannot read forum posts or summaries. They still use catalog facts and course ratings.
  **Suggested:** keep it, so that nobody can use the AI to read the forum without an account.


## Prompt 09

The catalog pipeline is built and tested only with fake pages and a fake model. Nothing below blocks the demo. Each item has the default that is built now.

- **P09-1. Programs that did not change since last year.** Sometimes the catalog of this year says exactly what the catalog of last year said. Then the pipeline copies the published rules of last year, and marks them "Unchanged since last year". Should those go live automatically?
  **Suggested (built):** no. A curator still clicks Accept and then Publish, which takes seconds for each program. Option: publish unchanged programs automatically. This saves clicks, but a student could then see the rules of a new year that no person looked at.
- **P09-2. The "9 to 19 courses" check for majors.** The spec says that a major needs between 9 and 19 courses. By that count, our Mathematics BS needs 21, because the seed also lists the general-education math courses that the major asks for.
  **Suggested (built):** use it as a flag for the reviewer, never as a reason to reject. Option: do not count the general-education parts.
- **P09-3. The contact address the crawler sends.** Each request to the catalog says who we are and gives an email address. Thus the University can contact us if the crawler causes trouble. Which address should it be?
  **Suggested:** a project address (not a personal one), set as `CATALOG_CONTACT_EMAIL` in `.env`. The crawler does not run until it is set. The address is never written to the logs.
- **P09-4. When the yearly run happens.** It is set for 1 August at 4 a.m. A check for changed pages runs on the 15th of every month. Both are off until `CATALOG_INGEST_ENABLED=true`.
  **Suggested:** keep these dates, and switch it on when the new catalog is available. Option: keep it off, and start each yearly run by hand.
- **P09-5. Courses that did not change.** New courses for the year come as one review item for each subject (approximately 200). This includes subjects where nothing changed. Those have the label "no changes".
  **Suggested (built):** keep this for the first real year, so that a person sees every subject one time. Later, accept unchanged subjects automatically.
- **P09-6. Counting programs.**
  - The run stops if our list of programs does not agree with the counts of the College ("68 majors and 57 minors") and with the index of the catalog.
  - We count a BA and a BS in the same subject as one major, as the College seems to.
  - If the College counts some joint degrees or tracks differently, the run stops, and a person must look.

  **Suggested (built):** keep the strict stop. Option: permit a small difference, and only give a warning.
- **P09-7. How much a real run may spend.** The estimate for the pilot (11 programs) is approximately $16, and it stops at $25 (`INGEST_COST_CAP_USD`). A full yearly run over approximately 150 programs would cost roughly $200 at list prices.
  **Suggested:** approve the pilot first. Set the cap to approximately $250 only for the first full yearly run.
- **P09-8. Who reviews.** Only admins can use the review page, the same as the moderation queue. Accounts with the "curator" role cannot.
  **Suggested (built):** only admins for now. Option: let curators also review catalog changes.
- **P09-9. What the pilot compares.** The pilot runs the agents on the 11 programs that we wrote by hand. It checks the program list against our own list of those 11, not against the full catalog index. (The full index check runs in the yearly job.)
  **Suggested:** keep it that way. The pilot measures how well the agents read rules. It does not have to find every program.

## Prompt 10

These are questions about the schedule pipeline (reading Class Search). The pipeline is built and tested, but only on pages that we invented.

- **P10-1. Reading the real Class Search is blocked. We need a few real pages, and permission.**
  - Nobody saw a real Class Search results page during the build, and no request went to the site.
  - The reader was built against invented pages (`services/scraper/fixtures/SYNTHETIC_*`, each with a big "SYNTHETIC" banner). It cannot read the real site until it sees real pages.
  - Scraping also stays off (`SCHEDULE_SCRAPER_ENABLED=false`) until the University says that it is permitted.

  **Suggested answer:** two steps.
  1. **Permission.** Ask the Registrar (or the office that runs Class Search) one of two things. Is a slow automated read of the public guest Class Search permitted (one page a second, one time a week)? Or can they send a data file? Write their answer here.
  2. **Save a few real pages from your own browser.** This is you browsing normally, not the scraper.
     - Open the public Class Search as a guest. Select a term that is already posted (for example, Autumn 2026), and search one subject, for example Computer Science (CMSC). If the results have several pages, also open page 2.
     - Do the same for one small subject (for example, a language). If you find a subject with no classes in that term, also save that.
     - Save each results page with File > Save Page As... Select "Webpage, HTML Only" (Chrome) or "Page Source" (Safari).
     - Give the files names like `REAL_class_search_2026-AU_CMSC_p1.html` and `..._p2.html`. Put them in `services/scraper/fixtures/`.
     - Before you search, also save the search form as `REAL_class_search_form.html`. It shows the names of the term and subject menus.
     - Please use the guest view. Pages saved while you are logged in to my.UChicago can show your name. If one does, tell us, and we will remove the name before we save the file in the project.

  With those pages, we can write the settings of the reader (`scraper.parse.DEFAULT_CONFIG`) and the form steps (`scraper.class_search.ClassSearchSite`) for the real site in one or two hours.
- **P10-2. Where the weekly check runs.** The weekly check is a worker job. But the browser that it needs (Chromium) is installed only in the scraper container. This is not important while scraping is off.
  **Suggested:** when scraping is permitted, run the weekly check inside the scraper container (one line in `docker-compose.yml`). Option: also install Chromium in the worker container, which makes it much bigger.
- **P10-3. Which AI model reads department pages.** The SPEC does not name one.
  - It is set to Sonnet 5.5 (`dept_offerings_extraction` in `llm_routing.yaml`), the same as the other medium-difficulty reading tasks.
  - Each item that it returns must quote the page word for word.
  - Code checks each quote. Then a curator reviews the list.

  **Suggested:** keep Sonnet 5.5. Option: Haiku 5.5, approximately 20 times cheaper. We could try it when the hold on AI calls is lifted, and keep it if its answers pass the checks as often.
- **P10-4. Similar instructor names are never merged automatically.**
  - The names of two different people often differ by one letter ("Demo Instructor A" and "Demo Instructor B").
  - Thus a name matches an existing instructor only when it has the same words, or is a known other spelling of their name. The match ignores order, capital letters, accents and punctuation.
  - A name that is near but different goes to the review queue.
  - A name that is not like the name of any instructor becomes a new instructor, with their own forum pages.

  **Suggested:** keep this. Option: let a very near name (one typo) merge automatically. That saves review work, but sometimes joins the reviews of two different people.
- **P10-5. Courses on the schedule that are not in the catalog.** If the course code of a section is not in the catalog (a new or topics course), the section is not saved. The code goes to the review queue.
  **Suggested:** keep this until the catalog pipeline (prompt 09) can add such courses after review.


## Prompt 12

- **P12-1 (met 2026-11-15 on the final stack: verify 49.6/s, p95 240 ms. Forum reads 99.3/s, 0 failures. Still run it again on the real server).** **Load-test targets on this laptop (logged as the "same fix fails twice" rule tells).**
  - Target: plan checks (`POST /verify`) at 50 a second, with 95% answered within half a second. Forum page reads at 100 a second.
  - Results on the Mac development machine, through Docker Desktop:
    - Several runs met the plan-check target: 48.3 a second with p95 240 ms, and 50.3 a second.
    - Other runs missed it as the machine became busier: p95 400 ms to 2.4 s.
    - Forum reads ran at 100 a second, with a median of 11-300 ms and a p95 of 200-620 ms.
    - In a direct measurement, the server handles approximately 235 forum reads a second, and one read takes 7 ms.
    - Much of the delay comes from two causes. The first is the port forwarding of Docker Desktop on a Mac with ~100 open connections (138 ms even for the health check). The second is the load generator, which runs on the same busy machine.
  - Improvements made: catalog data kept in memory (preloaded and refreshed in the background), forum page headers used again for 5 s, a bigger database pool.

  **Suggested:** run `make loadtest` on the real server before launch (`docs/DEPLOY.md`, and the launch checklist in `docs/PROGRESS.md`). If it misses there, make `WEB_CONCURRENCY` larger, to agree with the CPU count of the server. (Each worker uses a maximum of 20 database connections. Postgres permits 200.)

- **P12-2 (privacy, needs Richard).** **The admin "Suspensions" list can show that two removed posts have the same author.**
  - The list has one row for each suspended student. The row shows the latest post that was removed with a suspension (never the name of the student).
  - If an admin suspends the same student two times, through two different posts, the first row disappears when the second row shows. Thus the admin learns that the same person wrote those two posts, but not who it is (security re-review N7, 2026-11-15).
  - The same thing happens if an admin presses "End suspension" on one removed post and then tries it on a different post. The second answer shows whether both had the same author.

  Options:
  - **(a) Accept it (suggested).** Admins already read both posts, and one row for each student keeps "End suspension" clear.
  - **(b) One row for each removal.** Then the end of a suspension would clear all the rows of that student at the same time. This shows the same link at that moment. It only delays it.
  - **(c) No list.** Admins end a suspension only from the removed post itself. Thus nothing changes on screen when a second suspension is added.

**Richard's answer: Yes, option (a) is fine**

Resolved in b09f3f1: option (a), no change. The Suspensions list keeps one row for each suspended student, as that commit built it.

- **P12-3 (privacy, needs Richard).** **A restore from a backup brings back accounts that were deleted after that backup.**
  - Backups stay for 14 days.
  - If the database is restored from one, the accounts (with their emails) deleted since that backup come back.
  - `/privacy` now says that backups keep a deleted account for 14 days. `docs/DEPLOY.md` says what to do after a restore.

  Options:
  - **(a) Restore only to recover from the loss of the database, and tell students who deleted their account in that period to delete it again (suggested for launch).**
  - **(b) Keep a 14-day list of deleted account numbers (no emails), and delete those accounts again automatically after a restore.** More work. It closes the gap fully.

**Richard's answer: (a) is fine, since this is not very likely**

Resolved in 57c6723: option (a), no change. `docs/DEPLOY.md` says to restore only after a loss of the database, and to ask students who deleted their account in that period to delete it again. `/privacy` states the 14 days.

## Prompt 13 (live agent tests)

- **P13-1 (money, needs Richard).** **Which model should write the elective choices and the rationale of the plan generator?** In the live test (`docs/LIVE-TEST-REPORT.md` section 5), every plan from both models passed the checker. Sonnet 5.5 cost approximately $0.07 for each generation. Opus 5.5 cost approximately $0.19 and was 1.5–4.7x slower.
  - **(a) Sonnet 5.5 (suggested).** Approximately one third of the cost. The checker guarantees the plan, whatever model ranks the electives. Change `a1_plan_generator` in `llm_routing.yaml` to the `a1_plan_generator_sonnet` settings.
  - **(b) Keep Opus 5.5.** First, run the three Opus profiles again with the new output limits (approximately $0.60), because in this run its elective choices were cut off.

**Richard's answer: Yes, (a), Sonnet is fine**

Done 2026-11-16: `a1_plan_generator` now uses the Sonnet 5.5 settings (`llm_routing.yaml`, SPEC routing table, SPEC-CHANGES).

Resolved in 4049a63: option (a). The plan generator runs on Sonnet 5.5.

## End-to-end tests

- **E2E-1 (flaky test, logged after the same fix failed two times, 2026-11-16).**
  - The F4 test drags a course from the requirements drawer onto a quarter with a real mouse drag. Under heavy machine load (Docker builds during `make e2e`), the drop sometimes misses.
  - A measurement of the target after the drag starts did not fully fix it. Thus the test now tries the drag a maximum of three times, and still requires the course to land.
  - Suggested: if it continues to fail randomly, drive the drag with the keyboard sensor of dnd-kit, not the mouse.
  - On 2026-11-24, the goal-chip drag of the onboarding test failed in the same way, on both overnight branches. At that time, the two worktrees ran their tests (load average 30 to 100). It passed alone. Retries were not sufficient.
  - It now tries two pointer drags, and then drags with the keyboard sensor of dnd-kit (Space, arrows until the chip is on the quarter, Space), as suggested above. It has a 60 s test limit. (At the integration merge, this replaced the three pointer attempts of the issue #15/#19 branch.)
- **E2E-2 (flaky journey, 2026-11-16).**
  - Under heavy machine load, journey C sometimes fails. The plan generator stops at its time limit, so a busy machine can return a different valid plan.
  - Two times, the test then failed on a preference, not on a rule. One time it was the courses that the verifier credits to the civilization requirement of the Core. One time it was "the major's courses sit mostly in years 2-3". Both runs passed on retry.
  - Suggested: keep the hard checks (the Paris block, a maximum of 3 courses a quarter in year 4, a verified plan), and change the preference checks into warnings. Or give the e2e generator more time.
  - 2026-11-24, integration run:
    - Since the full catalog import, journeys A, B and C failed on the 4 s limit. The generator found one variant or none, and the infeasibility proof of journey B ran out of time.
    - The end-to-end stack now gives the solver 20 s (`GENERATE_SOLVER_SECONDS` in `docker-compose.e2e.yml`). The app keeps 4 s. See INT-1.
    - With 20 s, the preference "the major's courses sit mostly in years 2-3" failed 2 of 2 runs (7 courses in years 2-3, 8 in year 4). Thus journey C now records it as a gap and does not fail (7b11231), as suggested above. The hard checks stay. Richard can still ask for the strict check.
    - Over the day, it failed 3 of 4 runs with 20 s.

## Campus companion (2026-11-20, docs/BEST-OF-UCHICAGO-PLAN.md)

This was built in one overnight pass from Max's request. Each item is a decision that let the work continue. Nothing here is a catalog fact.

- **CC-1 Can the Commons be read without logging in?**
  - To read the course x instructor forum, a login is necessary.
  - Anyone can read the Commons (`/forum`, course questions), so a shared link works. To write, a login is necessary.
  - Because the Commons is public, the bot that answers there never reads the login-only forum reviews. Its answers keep only links to this site or to uchicago.edu.

  Suggested: keep it public, because these are questions about courses, not reviews of instructors. Option: require a login to read, the same as the forum (shared links would then ask visitors to log in).
- **CC-2 The campus guide must be hand-checked.** (Since issue #15, 2026-11-24: the Ask chatbot is gone. The Commons bot still cites the guide.)
  - `data/campus/guide.yaml` has 35 entries: the Core, the quarter system, libraries, advising, study abroad...
  - It was written from general knowledge, not from quoted sources. Every entry links to an official page.
  - The chatbot cites it, with an AI label.

  Suggested: before launch, check each entry against its page, and add a verbatim quote, the same as the catalog seed.
- **CC-3 The feed's book shelf.** (Resolved by issue #19, 2026-11-24: the shelf went away with the Feed, and `data/feed/books.yaml` is deleted.) `data/feed/books.yaml` (142 well-known books with authors and years) shows as "From the Quarterly shelf: reading for the curious, not a syllabus". Suggested: keep it, and spot-check it before launch. Option: show only books that course descriptions name (far fewer).
- **CC-4 AI answers that are stored.** (Since issue #15, 2026-11-24: the route drafter is gone.)
  - The harness saves the answer of the Commons bot as a reply with the mark "Quarterly AI" (the same as the AI summaries of the forum).
  - The interviewer and the route drafter only propose. The click of the student saves.

  Suggested: accept this reading of "agents never write to the database". (The agent has no write tool. The code stores its labelled output.) Option: show the answer of the bot only to the asker, until someone votes it helpful.
- **CC-5 Paid AI calls.** (Since issue #15, 2026-11-24: `a5_campus_ask`, `a7_routes` and `a10_updates_digest` are removed. Three of the six remain.)
  - The six new tasks (`a5_campus_ask` to `a10_updates_digest` in `llm_routing.yaml`) run only with `LLM_LIVE=true`.
  - Each has a daily limit for each account and for each address. Above the limit, the deterministic version answers.
  - During the build, we made approximately 40 live calls (on the key in `.env`).

  Suggested: keep the limits as they are for the demo. Review them before any public launch.
- **CC-6 What the dashboard stores.** (Since issue #15, 2026-11-24: no routes, and no Ask or companion conversations. The browser still clears old copies at logout.)
  - The account stores the profile (interests, career plans, humanities goal...) and the last 24 turns of the guide.
  - `/account/export` exports them. The deletion of the account deletes them.
  - The email is never copied into them (a test checks this).
  - Ask and companion conversations stay in the browser. The browser clears them at logout.

  Suggested: OK as built. Option: keep no interview turns on the server (then the guide would not remember earlier conversations).
- **CC-7 Commons reports.** Resolved (2026-11-20): `/admin/moderation` now has a "Commons reports" section (`GET /admin/commons-reports`, `POST /admin/commons-reports/{type}/{id}/decision`).
  - Remove shows the item as "[removed]". The replies under it stay.
  - Keep leaves it visible.
  - In both cases, its reports close, and a `moderation_action` is recorded.

  Still open: should Commons removals count toward suspensions, the same as forum removals? (Suggested: not for now.)
- **CC-8 Demo questions.** `make seed-commons-demo` adds 14 questions (not experiences or reviews) on real courses. Refs that match no account ask them. They are only for development. Suggested: remove them before launch (`make seed-commons-demo ARGS=--remove`).

## Site structure and catalog (GitHub issues #15 and #19, 2026-11-24)

Richard answered the open decisions of each issue in a comment on the issue. Each answer is recorded here. `docs/PROGRESS.md` logs the work.

- **S15-D1 Does the Companion stay?** **Decided (Richard, issue #15, 2026-11-24): remove it** ("agree with suggestion. Remove the orb."). Built: the companion, the Ask page and the question bar of the homepage are gone. `/ask` opens the planner.
- **S19-0 Can `course_instructor.first_term` show new courses?** As the issue asks, we checked this before D2: **no.**
  - `first_term` is part of one course × instructor forum page, not of a course.
  - It is set only when a forum page is created from a review or post (`api/forum/pages.py` `ensure_page`), or from schedule data. The schedule scraper is off.
  - The seed creates no such rows.
  - Thus it would show when someone first reviewed a course with an instructor, not when the course first ran.
- **S19-D1 Which Feed parts move into the Catalog page?** **Decided (Richard, issue #19, 2026-11-24): the suggestion** ("Agree with suggestions for now, see how the build turns out.").
  - Built: the course spotlights and the student quotes are browse rows of `/courses`.
  - Removed: the floating words, the ticker, the focus chips, the book shelf and the AI headline (task `a8_feed_notes`).
  - Removed with the Feed page: its word clouds, open questions, program cards, For you / Explore / Following tabs, and the "Save" and "Less like this" buttons of the spotlight cards (they only sorted the Feed).
- **S19-D2 Which courses are "newly released"?** **Decided (Richard, issue #19, 2026-11-24): the suggestion.**
  - A person writes `data/catalog/new_courses.yaml`.
  - Each course in it has a `source` with the page and a verbatim `quote`.
  - When the database holds a second catalog year, the list also shows the courses that are not in the earlier year.
- **S19-N1 The list of new courses is empty (Needs Richard).** No page in the seed says that a 2026-27 course is new. Thus the agent listed none (it never invents catalog facts). Until a course is listed, the "Newly released courses" row does not show. Options:
  - **(Suggested) You or Max add courses** to `data/catalog/new_courses.yaml`, from a department or College page that says that the course is new, with that sentence as the quote. The row shows them immediately.
  - Wait for the 2027-28 catalog. When it is loaded next to 2026-27, the row automatically fills with the courses that 2026-27 did not have.
  - Show the row anyway, with a short "No new courses listed yet" line.
  Richard's Answer: leave it empty for now. Max and I will manually add new courses. If not, we wait for the new catalog. No actions needed.
  Resolved in c3ef474: no code change. The list stays empty, and the row stays hidden, until Richard or Max add a course with a source quote, or until the next catalog year fills it. `data/catalog/new_courses.yaml` records this.

## Forum page, issue #20 (2026-11-24)

Richard's answers on the issue: D1 is option A (a short AI answer under each forum question), written as "Quarterly", not "Phil the Phoenix"; D2 as suggested (reviews and Commons keep their own tables and show in one list). The items below came up during the build.

- **F20-1 How long may the AI's answer under a question be? Needs Richard.**
  - Option A needs a word limit, and the issue comments set none. Thus the limit is **60 words** for now.
  - The prompt asks for it. A longer answer goes back to the AI one time, to make it shorter.
  - The site clips anything longer when it stores or shows it. (Older, longer answers also show clipped.)
  - 60 words is approximately three short sentences, or one sentence and two bullets.

  **Suggested:** keep 60. Options: **40** (one or two sentences. The AI gives a pointer, and students give the detail). **100** (space for a short list of courses with prerequisites. The list on `/forum` becomes longer to scroll).
  Richard's answer: 60 is fine for now. We can test how 60 works out.
  Resolved in c3ef474: the limit stays 60 words. SPEC (A9) and `api/commons/words.py` record it as confirmed, to look at again after testing.
- **F20-2 What "this quarter" and "this year" mean in the rankings.** Built: the reviews posted in the last 91 days ("Last 3 months") and in the last 365 days ("Last 12 months"), counted back from today. Thus there are always recent reviews to rank.
  **Suggested:** keep. Option: count the academic quarter or year in which students *took* the course ("Autumn 2026"). This agrees with how students think of a course. But early in a quarter, almost nothing is ranked, because reviews come after the course ends.
- **F20-3 The starting point of each score.** The Bayesian average of the SPEC needs a start average m. (Each course starts at m, as if it had 5 reviews.) Built: one m for everything, the average rating of all reviews in the period. Thus courses from different departments compare fairly in one ranking.
  **Suggested:** keep. Option: the own average of each department, as the SPEC uses for course attributes. Then a course would be compared with its department, which makes a single cross-department ranking less fair.
- **F20-4 Writing a review from `/forum`.** "New post" opens the question form (as the issue asks). Students still write reviews on the instructor page of a course (the "Course reviews by instructor" link of the forum), because a review needs its course, instructor and term.
  **Suggested:** later, let "New post" offer "Ask a question" or "Review a course". (The second option asks for the course and the instructor, then opens the review form of that page.) Option: keep as built.

## Integration run (2026-11-24)

- **INT-1 How long may "Generate" think in the app? Needs Richard.**
  - Since Max loaded the full catalog (11,301 courses, PR #9), "Generate" on this laptop often returns one plan, not two or three.
  - Sometimes it says "No plan was found within the time limit", where it previously listed the rules that conflict (journey B).
  - The app gives the solver 4 seconds. The end-to-end tests now give it 20 seconds. Thus they test the journeys, not the speed of this laptop.

  Options:
  - **(Suggested) Measure on the real server first.** It can be faster than this busy laptop. Run journeys A and B there with `GENERATE_SOLVER_SECONDS` unset (4 s), then decide.
  - **Raise the limit of the app to 8 seconds.** Set `GENERATE_SOLVER_SECONDS=8` in the `.env` of the server. Students wait up to approximately 4 seconds longer, and get two or three plans more often.
  - **Keep 4 seconds.** Plans come faster, but a student sometimes gets one option, or no explanation of a conflict.

## Student record and dashboard (Issues #14 and #16, 2026-11-24)

Max answered the open decisions on the issues:

- #14: no GPA, no freeform fields, working notes for each student.
- #16: the suggested answers. The portrait and "What's new" are removed.

These are the decisions made during the build. Each waits for the OK of Max or Richard.

- **SR-1. Credits at registration for first-year students.**
  - As #16 D1 tells, the registration form asks for credits and taken courses only when "I transferred, or I am not in my first year" is checked.
  - Many first-year students have AP credits. They add them later in the Academic background of the dashboard, which shows those questions to every student.

  *Suggested:* show the credits box to every student at registration (taken courses stay transfer-only). *Options:* (a) keep as built. (b) Credits for everyone.
- **SR-2. A new plan does not overwrite the student record.**
  - Credits and taken courses are now part of the student, not of a plan.
  - A plan can be created by an import of a plan made before login, or by a copy. If the record already has credits or taken courses, the record wins, and the plan shows the credits and courses of the record.
  - An empty record takes the credits and courses of the new plan.

  *Suggested:* keep.
- **SR-3. What stays in a plan.** Only completed and in-progress courses move to the record. Plan items with the mark "transfer" or "exam" (in a quarter of the grid) stay in their plan, the same as planned courses. *Suggested:* keep for the demo. Look at it again with Issue #17.
- **SR-4. A Summer start.** The entry term can be a Summer quarter. (The planner already lets a transfer student start with the summer before autumn, FEEDBACK 2026-11-14.) But Issue #14 lists only Autumn, Winter and Spring. *Suggested:* keep.
- **SR-5. "For you" in the feed.** The feed used the freeform interests to rank courses. Without them, it uses only the research areas and the intended programs. Thus a student who wants no research gets a less personal feed. *Suggested:* keep. Issue #19 (the combination of the feed and the catalog) can decide what personalises the catalog.
- **SR-6. Setting up a first plan.**
  - `/onboarding` is gone. Thus the planner shows "Set up your plan from your information" to a logged-in student whose plan is empty.
  - It builds the plan from the record (first quarter, programs and the Core, credits, taken courses), and opens the generator, as the last step of the wizard did.
  - Taken courses dated before the first quarter of the plan are not put on the plan.
  - A logged-out student can still drag courses onto a local plan. The planner offers "Sign up to set up your plan".

  *Suggested:* keep until the planner agent (Issues #17, #18) does this work.

## Merge of PR #21 (2026-11-24)

The merge of Max's PR #21 into `integration/2026-11-24` raised these questions. Nothing here blocks the demo.

- **M21-1. Should the dashboard guide send grades to the AI?**
  - Each time a student talks with the guide, the server sends the full `student.md` to the AI provider. That includes the taken courses with their grades.
  - The questions of the guide (goals, scheduling, preferences) do not use grades.
  - The privacy page now says that grades are sent.

  **Suggested:** do not include the grades in the copy of `student.md` for the guide. The export keeps them. Options:
  - **Leave grades out (suggested).** Less personal data goes to the provider. The guide asks the same questions.
  - **Keep as built.** The guide can mention a course and its grade. It does not do this now.

Richard's answer: I agree, leave the grades out of the copy.
Resolved in 7fbc438: the copy of `student.md` for the guide has no grades and no Pass/Fail. The export keeps them. The privacy page says so.

- **M21-2. `GET /me/updates` has no reader.** Issue #15 (step 13) kept the endpoint for the "What's new" card, and issue #16 (D5) removed that card. The server still computes the list, and the web app never asks for it.
  **Suggested:** keep it until the dashboard has a place for alerts, so that nobody must build it again. Option: remove it, its mock and its tests now, to have less code to maintain.

Richard's answer: Delete it for now.
Resolved in 7fbc438: `GET /me/updates` and `POST /me/updates/seen` are deleted, with their mock and tests. The column `student_profile.updates_seen` stays unused. A migration can delete it later.

- **M21-3. The guide can skip a question that the student did not accept.** The review of PR #21 found this, and it is still true.
  - On the next visit, the browser sends the stored turns.
  - The server then counts a proposed but unaccepted answer as covered.
  - The guide asks that question again only after the turn leaves its 16-turn history.
  - The dashboard shows "Not answered", so no saved data is wrong.

  **Suggested:** a small fix in the next dashboard PR. A question counts as covered only when the student accepted or skipped it. `memoryPatch` in `features/dashboard/logic.ts` already tracks this. Option: keep it as it is for the demo.

Richard's answer: Yes, we can implement a small fix in the next dashboard PR.
Not done yet: planned for the next dashboard PR.

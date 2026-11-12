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

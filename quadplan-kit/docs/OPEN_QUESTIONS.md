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
  `repeatable` (the catalog says "two-quarter series", not "repeatable").
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

- **P05-17. `make golden` takes about 5 minutes** with this seed because `api/golden.py` calls
  `loaded.setdefault(year, load_bundle(...))`, which re-parses the whole seed for every plan
  (`setdefault` evaluates its argument). Suggest `if year not in loaded: ...` and building the
  catalog once per year.

# Prompt 05 · Hand-verified seed data and golden plans

> Recommended: Opus 5.5, effort `high`, using the `data-curator` subagent. Parallel with 02-04. Richard reviews the output before prompt 06.

---

Use the data-curator subagent. Context: `CLAUDE.md`, SPEC "Requirements DSL", "Data ingestion" (program checklist) and the seed format from prompt 01.

Scope (catalog year 2026-27; if the 2026-27 page is not published, use the latest year and say so):
- College policy: units, full-time load, overload reasons, 4200/3800 units, residency, Core timing. Sources: the College pages in SPEC "Sources".
- The Core (all parts) and Language Competence.
- Computer Science BA and BS; CS Bx/MS (each option the catalog lists); Mathematics BA and BS; Economics.
- Two one-quarter civilization study-abroad programs, from the Study Abroad site.
- Every course those rules reference, from the catalog course blocks (code, title, units, description, prerequisite sentence, equivalents, notes), plus named course lists.

Rules:
1. Fetch the real pages. Every rule node has `source: {url, quote}` with the quote copied verbatim. Never infer what the page does not say.
2. Ambiguous wording: encode the strictest reading, set `needs_review: true`, and add a question to `docs/OPEN_QUESTIONS.md`.
3. Prerequisites: encode with the DSL; keep the original sentence in `raw_text`.
4. Golden plans in `data/golden/`: at least 5 must-pass and 5 must-fail per program; each must-fail names its expected issue codes.
5. Write `data/seed/REVIEW.md`: one table per program listing node id, rule in plain English, quote, URL and needs_review. This is what Richard will check by hand.

Done when `make seed && make golden` pass (golden may fail only where prompt 02 is not merged yet; say which). Run `spec-reviewer`, update `docs/PROGRESS.md`, and stop for Richard's review.

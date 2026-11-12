# Prompt 11 · Forum -> course attributes (nightly)

> Recommended: Opus 5.5, effort `medium`.

---

Context: `CLAUDE.md`, SPEC "Forum" (Forum -> course attributes) and A3 in "Agent harnesses".

Build a nightly worker job:
1. **Numeric aggregation (code):** Bayesian average per attribute and subject (course; course x instructor) with prior mean m (department average or cold-start estimate) and prior weight k = 5; structured ratings w = 1, text-extracted values w = 0.5, ratings older than 4 years w = 0.5; confidence interval; publish forum-derived values only when n >= 3.
2. **Text extraction (Haiku):** workload mentions, difficulty cues, exam style, prerequisite advice, each with a quote span; numbers accepted only if the quote contains them.
3. **Summaries (Sonnet):** "What students say", <= 120 words, [n] citations to post ids, rebuilt after 3 new posts or 30 days; passes A4 moderation; citations validated.
4. **Cold start (Sonnet):** rubric-based estimates from description and level, labelled "estimate", weight 2.
5. Write `attribute_value` rows with evidence; the planner and course page read the newest.

Tests: the formula against hand-computed cases; n < 3 shows the estimate; summary with an invalid citation is rejected; moderation failure blocks publishing.

Done when `make check` passes. Run `spec-reviewer`, update `docs/PROGRESS.md`.

# Prompt 10 · Quarterly schedule pipeline (feature-flagged)

> Recommended: Sonnet 5.5 (or Opus 5.5, `medium`).

---

IMPORTANT: Do not send any request to the live Class Search until Richard confirms in writing that the University permits it. Keep `SCHEDULE_SCRAPER_ENABLED=false` by default and develop against saved HTML fixtures in `services/scraper/fixtures/` (ask Richard to save a few result pages from his browser).

Context: `CLAUDE.md`, SPEC "Data ingestion" (quarterly schedule pipeline, predicting future offerings).

Build:
1. Playwright scraper for the public Class Search (guest access): iterate subjects for a term, snapshot every results page to MinIO.
2. Deterministic parser -> `section` rows (term, course, section, component, instructors, meetings, capacity, status).
3. Checks: unknown course codes flagged; instructor fuzzy matching with an uncertainty threshold -> review; per-department section counts within +/-30% of the same quarter last year, else alert.
4. Update `course_instructor` (creating forum pages) and `offering_pattern` with p = (k+1)/(3+2), 0.95 for department plans, 1 for posted schedules.
5. Department offering pages extractor (start with the CS course-info pages) via E-style LLM extraction with quotes.
6. Self-repair: on parse failure, a Sonnet agent proposes new selectors from the snapshot and old parser; the new parser must reproduce the last good counts on stored snapshots; output is a review item, never an automatic change.

Tests run only on fixtures. Done when `make check` passes. Run `spec-reviewer`, update `docs/PROGRESS.md`.

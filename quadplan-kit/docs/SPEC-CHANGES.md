# SPEC changes

Each line records a change to `docs/SPEC.md` that came from Richard's feedback (`docs/FEEDBACK.md`) or decisions (`docs/OPEN_QUESTIONS.md`). Newest last.

| Date | Source | SPEC section | Change |
| --- | --- | --- | --- |
| 2026-11-14 | FEEDBACK "Generate Plan Failure" | A1 plan generator, steps 1 and 5 | Unknown credits or completed courses already in the plan stop generation with a "Fix these first" message; when every variant fails verification the student is told what the check found. |
| 2026-11-14 | FEEDBACK "Locations of Summer Quarter" | Planner, the grid; term arithmetic | An academic year runs Summer, Autumn, Winter, Spring: the summer before autumn belongs to it (was: summer after spring). No summer after the last spring. |
| 2026-11-14 | FEEDBACK "Number of Years" | Planner, the grid; `plan` table | Plans end at `graduation_term` (default: Spring of the last year from the entry level, so three years for a second-year transfer); add a year, remove the last year, graduate early in Autumn or Winter. Replaces "Y1–Y4, optional Y5". |
| 2026-11-14 | FEEDBACK "Planner GUI" | Planner layout | Requirements, Issues and Goals move to a right-hand drawer; requirements are a vertical tree (bold code, small name); errors are subtle behind a "Check plan" button; the Advisor opens from the top, labelled generative AI, as a chat. Replaces the left rail and the three-tab right rail. |
| 2026-11-14 | FEEDBACK "Text" and "GUI Polishing" | All pages | Non-instructional filler text removed; subtle motion added (off under reduced motion). |
| 2026-11-14 | OPEN_QUESTIONS P08-1 | A4 moderation; Moderation and community rules; model routing | Students' posts are not checked before publishing; reports and the admin queue take them down; A4 checks only AI summaries. |
| 2026-11-14 | OPEN_QUESTIONS P08-3, P08-14; FEEDBACK "End suspension" | Moderation and community rules | Suspensions are manual (7/30/90 days, chosen when removing); admins can end one early; deletion waits while suspended or 30 days after an upheld removal. Replaces "three upheld removals suspend for 30 days". |
| 2026-11-14 | OPEN_QUESTIONS Q11 | Review ratings | Optional pace and grading-strictness questions (1–5). |
| 2026-11-14 | OPEN_QUESTIONS P08-5 | Data model, `course_instructor` | One forum page per cross-listed group and instructor, shown under every code. |
| 2026-11-14 | OPEN_QUESTIONS Q6 | Checks, V09 | Transfer credit counts toward the 3800 units by enrollment; at least 1800 units must be taken at the College. |

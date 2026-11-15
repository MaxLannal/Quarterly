# SPEC changes

Each line records a change to `docs/SPEC.md` that came from Richard's feedback (`docs/FEEDBACK.md`) or decisions (`docs/OPEN_QUESTIONS.md`). Newest last.

| Date | Source | SPEC section | Change |
| --- | --- | --- | --- |
| 2026-11-14 | FEEDBACK "Generate Plan Failure" | A1 plan generator, steps 1 and 5 | Unknown credits or completed courses already in the plan stop generation with a "Fix these first" message; when every variant fails verification the student is told what the check found. |
| 2026-11-14 | FEEDBACK "Locations of Summer Quarter" | Planner, the grid; term arithmetic | An academic year runs Summer, Autumn, Winter, Spring: the summer before autumn belongs to it (was: summer after spring). No summer after the last spring. |
| 2026-11-14 | FEEDBACK "Number of Years" | Planner, the grid; `plan` table | Plans end at `graduation_term` (default: Spring of the last year from the entry level, so three years for a second-year transfer); add a year, remove the last year, graduate early in Autumn or Winter. Replaces "Y1–Y4, optional Y5". |
| 2026-11-14 | FEEDBACK "Planner GUI" | Planner layout | Requirements, Issues and Goals move to a right-hand drawer; requirements are a vertical tree (bold code, small name); errors are subtle behind a "Check plan" button; the Advisor opens from the top, labelled generative AI, as a chat. Replaces the left rail and the three-tab right rail. |
| 2026-11-14 | FEEDBACK "Text" and "GUI Polishing" | All pages | Non-instructional filler text removed; subtle motion added (off under reduced motion). |

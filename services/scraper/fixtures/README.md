# SYNTHETIC fixtures: invented, not real pages

**Every file in this folder is invented.** None of them was saved from the real University of
Chicago Class Search or from a real department website. Nobody has looked at a real Class
Search page while building this pipeline, and no request has ever been sent to one.

- `SYNTHETIC_class_search_*.html` are made-up "results pages" in a layout invented for the tests.
  The real Class Search layout is unknown, so the parser's selectors (`scraper.parse.DEFAULT_CONFIG`)
  match these files only.
- `SYNTHETIC_cs_course_info_2027-28.html` is a made-up department "course plan" page.
- Course codes are either real codes from `data/seed` (for example CMSC 14100) or obviously fake
  ones (CMSC 99901, CMSC 99902, subject ZZZZ). Titles of real codes are copied from `data/seed`.
- Instructor names are fake ("Demo Instructor A" ... "F", "Demo Instrctor C" with a deliberate
  typo, "Instructor, Demo D" in last-name-first form). Rooms ("Demo Hall 101"), times, enrolment
  numbers and the quarters in the department plan are made up.
- `..._layout_v2.html` repeats `..._CMSC_p1.html` in a changed layout, to test the self-repair agent.

Nothing here is a catalog fact or a schedule fact. Do not copy any of it into `data/seed`.

When real pages are available (see `docs/OPEN_QUESTIONS.md`, "Prompt 10"), save them next to
these as `REAL_class_search_<term>_<subject>_p<n>.html` and write the real parser selectors.

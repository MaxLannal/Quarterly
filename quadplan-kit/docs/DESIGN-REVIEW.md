# Design review (D11), 2026-11-16

Richard's FEEDBACK "Minor design changes": *"Do a full runthrough with \impeccable to improve all UI and UX workflow components. Critique every part of the website and make improvements."* (D11, after D1-D10.)

## Method

- **Critique** (`/impeccable critique`), dual-agent as the skill requires: three isolated design reviewers (Assessment A: home, top bar and footer, onboarding / the planner with the generate popup, advisor chat and credits editor / course search, course page, forum, program pages, sign-up, login and account) and one isolated evidence agent (Assessment B: the Impeccable detector over `apps/web/src`, axe WCAG 2.2 AA at 1440 and 390 px on every page, overflow, target sizes, console errors). They did not see each other's output.
- **Audit** (`/impeccable audit`): the evidence agent's measurements plus static checks, scored on the five audit dimensions.
- Screenshots: before `docs/screenshots/before/`, after `docs/screenshots/after/` (every page, 1440 and 390 px, mock data).
- Scope rules (Richard's goal): presentation, layout, copy and motion only; DESIGN.md stays the source of truth; 4.5:1 text contrast, 44px targets, visible focus, keyboard access, reduced motion; no new third-party requests.

## Priorities and status

- **P0** blocks a task. **P1** significant difficulty or a WCAG AA failure. **P2** annoyance with a workaround. **P3** polish.
- Every P0 and P1 is **Fixed** or **Needs Richard**. P2 and P3 are Fixed or **Deferred** with a reason.

## Audit (all areas), from Assessment B

**Detector:** `impeccable detect --json apps/web/src` exit 0, no findings. **axe** (wcag2a, 2aa, 21a, 21aa, 22aa) on 19 page states x 2 widths (home, onboarding, planner, drawer, Generate popup before and after results, advisor with an answer, My plans, course search empty and searched, course page, forum page, thread, instructors, programs, a program page, sign-up, login, account): **no violations of any impact**. No horizontal overflow at 390 or 1440. No uncaught page errors.

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 4 | No axe violations (incl. WCAG 2.2 AA); focus replacements everywhere; reduced motion handled. |
| 2 | Performance | 3 | Transform/opacity animations; one width transition (A-2). Bundle and chapel runtime not measured. |
| 3 | Theming | 3 | Full token set; one rgba literal (A-3). No dark mode, by DESIGN.md's decision. |
| 4 | Responsive | 4 | No overflow; 44px drag handles with `touch-none`. Touch gestures not exercised. |
| 5 | Implementation integrity | 4 | Detector clean; shared tokens and components used consistently. |
| | **Total** | **18/20** | Excellent (minor polish) |

False positives checked: 20x20 radio and checkbox inputs sit inside 44px `ChoiceRow` labels; program list links stretch over their whole card; "View prerequisite" and "View offerings" are inline text links (WCAG inline exception).

| ID | P | Area | Finding | Status |
|---|---|---|---|---|
| A-1 | P3 | course page | Instructor name link is 22px tall (passes WCAG on spacing, under the project's 44px rule). `CourseOverview.tsx` | **Fixed** cc5ed78: the instructor links are 44px targets. |
| A-2 | P3 | course search | The Courses/Programs pill animates `width`, a layout property. `CatalogToggle.tsx` | **Fixed** 4297386: equal-width sides; the pill only translates. |
| A-3 | P3 | course search | A hard-coded `rgba` shadow on the switch's pill instead of a token. `CatalogToggle.tsx` | **Fixed** 4297386: the pill uses the `shadow-hover` token. |
| A-4 | P3 | top bar and footer | A 401 console message on every logged-out page load (the session check). | **Deferred**: the message is the API answering the logged-out session check with 401; changing that is API behaviour, outside this presentation-only pass. Suggested later: answer 200 with no session. |
| A-5 | P3 | top bar and footer | 44px footer and switch targets on touch screens are not covered by a test. | **Fixed** 26d2d9d: an e2e test on an emulated touch screen checks 44px footer links and switch targets. |

## Critique, by area

Scores are the design reviewers' Nielsen heuristic totals (n/a heuristics excluded from the maximum). Fix commits are filled in as each area is done.

### Home (19/28)
| ID | P | Finding | Status |
|---|---|---|---|
| H-1 | P2 | Two course searches on the home page (top bar and hero); at 390 the hero's full-width Search pill pushes "Start planning" down. | **Fixed** 267de87: the top bar hides its search on home and course search. |
| H-2 | P2 | The hero search is named "Search courses and instructors" but searches courses only. | **Fixed** 267de87: "Search courses", with an example code in the placeholder. |
| H-3 | P2 | Five controls in the action row; "Open my plan" opens an empty planner for a first-time visitor. | **Fixed** 267de87: "Open my plan" shows only when a plan exists on the device. |
| H-4 | P2 | On a phone the chapel is a small strip below the fold. | **Fixed** 267de87: the chapel runs edge to edge below 640px; tighter hero padding. |
| H-5 | P3 | The hero section has no accessible name; two `role="search"` landmarks. | **Fixed** 267de87: the hero section is named; one search landmark on home. |

### Top bar and footer (24/36)
| ID | P | Finding | Status |
|---|---|---|---|
| C-1 | P2 | Top bar (Plan / Catalog / Forum) and footer (Plan / Read / Quarterly) organise the site differently; the footer never says "Forum". | **Fixed** 267de87: footer columns Plan, Catalog, Forum, Quarterly. |
| C-2 | P2 | "Not official advising" appears only in the planner, though PRODUCT.md says every page says it. | **Fixed** 267de87: the footer adds "It is not official advising." on every page. |
| C-3 | P2 | Eyebrow labels above page titles repeat the title ("QUARTERLY / About", "PLANS / My plans", "PROGRAMS", "START PLANNING"). The craft floor bans them. | **Fixed** 81f1840: removed from onboarding, My plans, Compare, About, Privacy, Programs; the instructor and program pages moved theirs under the title. Kept where the label is content (course code, sign-up step, curator console). |
| C-4 | P3 | The top-bar search icon button covers the input's left padding; the search form has no name. | **Fixed** 267de87: `pl-11` and a "Site search" name. |

### Onboarding (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| O-1 | P2 | Step pills look like buttons but are not clickable. | **Fixed** db58c1d: the current step on a wash pill, done steps checked, the rest plain text. |
| O-2 | P2 | The step is named three or four times (eyebrow, h1, pills, h2 "Step 1 of 5: Entry term"). | **Fixed** 81f1840, db58c1d: the label is gone and a one-line description replaces it; the step heading keeps its number. |
| O-3 | P2 | The first field is "Catalog year" (jargon for a first-year); no word on how long setup takes or where the plan is kept. | **Fixed** db58c1d: first quarter first, catalog year with a plain-words hint, "Five short steps. You can change everything later." |
| O-4 | P2 | "Generate a starting plan" (on by default) does not say the plan is written by AI. | **Fixed** db58c1d: "Written by AI, then checked by the verifier. You choose what to keep." |
| O-5 | P3 | Goals step: developer wording ("drag a chip"), a cramped 3-column timeline at 390, `aria-label` on a plain div. | **Fixed** db58c1d: plain-words legend, one column below 480px, a named group. |

### Planner page and grid (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PL-1 | **P1** | No plan verdict on the page: only an error count inside "Check plan", which disappears at 0; a valid plan never says "Valid". | **Fixed** 9eeebf7: "Valid" / "N warnings" / "N errors" beside the plan name, opening the plan check. |
| PL-2 | **P1** | Plan-check items lose their content: requirement messages are cut at the first colon, so the list says "Fake Program." three times. | **Fixed** 9eeebf7, b228808: both message forms keep "needs ..."; unit tests. |
| PL-3 | P2 | Empty quarters repeat "0 units 0 h/wk Difficulty 0"; "Drop a course here" only describes dragging. | **Fixed** 9eeebf7: "No courses yet"; no row of zeros (goals still show). |
| PL-4 | P2 | Seven equal toolbar pills; three rows at 390; "Check plan" opens a tab called "Issues". | **Fixed** caf0684 (part): the drawer tab is "Check plan" like its button; on a phone the panel buttons are one sideways row, so the toolbar is two rows. **Deferred**: merging the four panel buttons into one control changes the toolbar Richard shaped in FEEDBACK F4. |
| PL-5 | P2 | Plan-check items use a 3px coloured left strip for severity, which can be read as the requirement colours (and the craft floor bans it). | **Fixed** 9eeebf7: no coloured strip on plan-check items. |
| PL-6 | P3 | "Difficulty 4.5" is explained only in a tooltip; many entrance animations at once. | **Deferred**: explaining "Difficulty" needs a glossary pattern the app does not have yet; the entrance animations are DESIGN.md's settle/rise and stop under reduced motion. |

### Generate plan popup (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| GE-1 | **P1** | Every variant has a maroon "Apply" (2-3 primaries in one view), and an invalid variant's Apply looks as safe as a valid one's. | **Fixed** a518be9: Apply is an outline button on every option; an option with errors says so in the error colour above its actions. |
| GE-2 | **P1** | Apply replaces quarters silently: nothing says which quarters change, and nothing confirms it afterwards. | **Fixed** a518be9, b228808: "Changes 3 quarters: ..." above the actions; the planner confirms "Applied the generated plan" afterwards. |
| GE-3 | P2 | The figures that differ between variants are a muted caption; the reasons take the weight. | **Fixed** a518be9: the figures are body text. |
| GE-4 | P2 | Four actions per variant; "View diff" is developer jargon. | **Fixed** a518be9, 05cc270: "See changes"; "Choose quarters to apply" moved inside it; three actions per option. |

### Advisor chat (29/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AD-1 | **P1** | "After this change: 4 errors" has nothing to compare with, so the student cannot tell whether the change helps. | **Fixed** 42d5647: "Now: 4 errors → After this change: 4 errors (no change)". |
| AD-2 | P2 | The sheet covers the plan it is discussing. | **Deferred**: a desktop side panel would change the advisor layout settled in FEEDBACK F4; Richard's call. |
| AD-3 | P2 | Citation chips are dense ("workload 13 h/wk · n=34"), underlined inside pills. | **Fixed** 4297386: "(34 ratings)" instead of "n=34"; linked chips are maroon, not underlined. |
| AD-4 | P3 | The disabled Send button is faded maroon instead of the disabled colour. | **Fixed** 42d5647: a disabled primary is a grey plate with legible muted text. |

### Credits editor (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CR-1 | P2 | Credit rows show raw data: "placement: …", "(needs mapping)". | **Fixed** e1ad1a2: "AP exam", "Placement", "Transfer credit", "not matched to a course yet". |
| CR-2 | P2 | Remove is instant and silent; DESIGN.md says destructive actions confirm in place. | **Fixed** e1ad1a2: Remove asks "Remove? Yes, remove / Keep" in place, in the error colour. |
| CR-3 | P2 | The add form has no heading; two identical forms show while editing. | **Fixed** e1ad1a2: "Add a credit" heading; the add form hides while a credit is edited. |
| CR-4 | P2 | The course picker's list can be clipped by the drawer's scroll area. | **Fixed** 9eeebf7, cc5ed78: the list sits in the page flow and closes after a click lands. |

### My plans and Compare plans (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| MP-1 | P2 | Each row leads with a bordered input instead of the plan's name; rows do not line up. | **Fixed** b62cb07: the name reads as the plan's title; its field shows on hover and focus. "N courses", the date in words. |
| MP-2 | P2 | "PLANS" eyebrow above both headings (see C-3). | **Fixed** 81f1840 (see C-3). |
| MP-3 | P2 | Compare shows "None / None / None" for identical plans and labels them "A" and "B". | **Fixed** ac84836: "Same courses in the same quarters."; columns named after the plans. |

### Course search (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CS-1 | P2 | The top-bar search and the page's search do the same job on one screen (see H-1). | **Fixed** 267de87 (see H-1). |
| CS-2 | P2 | "More filters" has no disclosure marker. | **Fixed** 6330b28: a chevron that turns when open. |
| CS-3 | P2 | Department and Core area are free-text fields; a wrong guess quietly returns nothing. | **Deferred**: offering choices needs the list of valid department and Core values, which the page does not load; the placeholders give the format. |
| CS-4 | P2 | Zero results is a dead end: "0 COURSES", an empty list, disabled paging. | **Fixed** 3ca0cff: "No courses match" with "Clear the search"; paging only with more than one page. |
| CS-5 | P3 | The placeholder is cut off at 390. | **Fixed** 3ca0cff, b228808: "Code or title". |

### Course page (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CP-1 | **P1** | Two different difficulty and workload numbers on one page (student ratings vs the planner's estimate) with nothing saying which is which. | **Fixed** cc5ed78: a caption says the block is the planner's estimate and the overview has the students' ratings; one format ("/ 5", "h/wk"). |
| CP-2 | P2 | Three warning-toned "Estimate" badges with no explanation. | **Fixed** cc5ed78: a neutral "Estimate" badge, explained in the caption. |
| CP-3 | P2 | The forum is hard to find: instructor names are the only links to it. | **Fixed** cc5ed78: "Choose an instructor to read their reviews and discussion." |
| CP-4 | P2 | "Unlikely (0%)"; the basis column repeats one source four times and wraps at 390. | **Fixed** cc5ed78, b228808: "Not expected"; a shared basis is stated once under the table. |
| CP-5 | P3 | Nested cards in the attributes block. | **Fixed** cc5ed78: hairline rows. |

### Forum page, thread and instructors (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| FO-1 | **P1** | The Forum's front door (`/instructors`) is a name search; most students arrive with a course, not an instructor's name. Its description leads with a restriction. | **Fixed** 6330b28, db55ef4: titled "Forum", says what it is, "Know the course? ..." with "Find a course"; the login note only for logged-out visitors. |
| FO-2 | P2 | Rating tiles and histograms push the first review about 1,450px down at 390. | **Fixed** 6330b28: "Rating breakdown" folds away. |
| FO-3 | P2 | Histogram bars are sized by count/max, so 1 of 2 ratings draws a full bar. | **Fixed** 6330b28: bars are shares of all ratings. |
| FO-4 | P2 | An untitled review's heading repeats the author ("Review by Fake Heron" under "Fake Heron"). | **Deferred**: the fallback heading is also the link to the review's thread and the review's accessible name; a better wording needs Richard's view on how reviews are named. |
| FO-5 | P3 | The thread header says the count twice and names a sort order that cannot change. | **Fixed** 05cc270: "Comments (10)", "Best first." |

### Program pages (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PR-1 | **P1** | Every course code on a program page is plain text; to see a course you copy its code into search. | **Fixed** 6330b28: every course code in requirements and the sample path links to its course. |
| PR-2 | P2 | Programs and Courses are composed differently; "PROGRAMS" eyebrow repeats the switch. | **Fixed** 81f1840: no label; the switch lines up with the header. |
| PR-3 | P2 | "In review" / "Needs review" are internal words. | **Fixed** ac84836: "Not yet hand-checked", sentence case. |
| PR-4 | P3 | Copy slips: plural type label on one program, ISO date, "Add to my plan" vs "Add to plan". | **Fixed** 81f1840, 05cc270: singular type, "July 1, 2099", "Add to plan". |

### Sign-up, login and account (34/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AU-1 | P2 | The first sign-up step is dense (heading, label, hint and a 4-line privacy paragraph before the button). | **Fixed** 05cc270: one line before the button; placeholder "cnetid@uchicago.edu". |
| AU-2 | P3 | "Forgot password?" and "Create an account" use different link styles. | **Fixed** ac84836. |
| AU-3 | P3 | The top bar's "Log in" pill shows on the login and sign-up pages. | **Fixed** ac84836. |

## Polish, harden and adapt

- **`/impeccable polish`, every area:** after the fixes, every page was shot again at 1440 and 390 and read side by side. It found and fixed (b228808, db55ef4): PL-2's second message form; the drawer's four tabs and close button not fitting 390 px; "Apply changes 3 quarters" wording; a shared offerings basis repeated per row; a course search placeholder cut off on a phone; a Forum-page hint that wrapped into ": its page lists"; an ISO date on the account page. The pass also caught that D9's form order put the course picker's list over "Add credit" (fixed in 9eeebf7, cc5ed78).
- **`/impeccable harden`, planner and forum** (caf0684): compact fields, the graduation list and the top-bar search are 16px on touch screens (iOS Safari zooms into smaller fields); long unbroken words in forum titles wrap like post bodies already did; empty quarters, an unavailable verifier ("Not checked yet"), no search results and identical plans all have their own state.
- **`/impeccable adapt`, planner and forum** (caf0684, 6330b28): on a phone the planner's panel buttons are one sideways-scrolling row, so the toolbar is two rows instead of three; the drawer tabs fit 390 px; the forum's rating breakdown folds away, so reviews start near the top.

## Summary

| | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|
| Found | 0 | 8 | 38 | 16 | 62 |
| Fixed | 0 | 8 | 35, plus PL-4 in part | 14 | 57 + 1 in part |
| Deferred (with a reason) | 0 | 0 | 3 (AD-2, CS-3, FO-4), plus the rest of PL-4 | 2 (A-4, PL-6) | 5 + 1 in part |
| Needs Richard | 0 | 0 | 0 | 0 | 0 |

Every P0 and P1 is fixed. Axe after the fixes: see docs/PROGRESS.md (design pass).

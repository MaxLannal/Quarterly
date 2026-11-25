# Design review (D11), 2026-11-16

Richard's FEEDBACK "Minor design changes": *"Do a full runthrough with \impeccable to improve all UI and UX workflow components. Critique every part of the website and make improvements."* (D11, after D1-D10.)

## Method

- **Critique** (`/impeccable critique`): two kinds of agents, as the skill requires. The agents did not see the output of the other agents.
  - Three isolated design reviewers (Assessment A). Their areas: home, top bar and footer, onboarding / the planner with the generate popup, advisor chat and credits editor / course search, course page, forum, program pages, sign-up, login and account.
  - One isolated evidence agent (Assessment B). Its checks: the Impeccable detector over `apps/web/src`, axe WCAG 2.2 AA at 1440 and 390 px on every page, overflow, target sizes, console errors.
- **Audit** (`/impeccable audit`): the measurements of the evidence agent and static checks. The audit gives a score on each of the five audit dimensions.
- Screenshots: before in `docs/screenshots/before/`, after in `docs/screenshots/after/`. They show every page at 1440 and 390 px, with mock data.
- Scope rules (Richard's goal):
  - Change only presentation, layout, copy and motion.
  - DESIGN.md stays the source of truth.
  - Keep 4.5:1 text contrast, 44px targets, visible focus, keyboard access and reduced motion.
  - Add no new third-party requests.

## Priorities and status

- **P0**: blocks a task. **P1**: a significant difficulty, or a WCAG AA failure. **P2**: an annoyance with a workaround. **P3**: polish.
- Each P0 and P1 is **Fixed** or **Needs Richard**. Each P2 and P3 is Fixed, or **Deferred** with a reason.

## Audit (all areas), from Assessment B

**Detector:** `impeccable detect --json apps/web/src` gave exit 0, with no findings.

**axe** (wcag2a, 2aa, 21a, 21aa, 22aa) ran on 19 page states x 2 widths: home, onboarding, planner, drawer, Generate popup before and after results, advisor with an answer, My plans, course search empty and searched, course page, forum page, thread, instructors, programs, a program page, sign-up, login, account. Result: **no violations of any impact**.

There is no horizontal overflow at 390 or 1440. There are no uncaught page errors.

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 4 | No axe violations (incl. WCAG 2.2 AA). Focus replacements everywhere. Reduced motion is handled. |
| 2 | Performance | 3 | Transform/opacity animations. One width transition (A-2). Bundle and chapel runtime not measured. |
| 3 | Theming | 3 | Full token set. One rgba literal (A-3). No dark mode, by the decision of DESIGN.md. |
| 4 | Responsive | 4 | No overflow. 44px drag handles with `touch-none`. Touch gestures not tested. |
| 5 | Implementation integrity | 4 | Detector clean. Shared tokens and components used consistently. |
| | **Total** | **18/20** | Excellent (minor polish) |

These false positives were checked:

- The 20x20 radio and checkbox inputs are inside 44px `ChoiceRow` labels.
- Program list links stretch over their full card.
- "View prerequisite" and "View offerings" are inline text links (WCAG inline exception).

| ID | P | Area | Finding | Status |
|---|---|---|---|---|
| A-1 | P3 | course page | The instructor name link is 22px tall. This passes WCAG on spacing, but is less than the 44px rule of the project. `CourseOverview.tsx` | **Fixed** cc5ed78: the instructor links are 44px targets. |
| A-2 | P3 | course search | The Courses/Programs pill animates `width`, a layout property. `CatalogToggle.tsx` | **Fixed** 4297386: the sides have equal width. The pill only translates. |
| A-3 | P3 | course search | The pill of the switch has a hard-coded `rgba` shadow, not a token. `CatalogToggle.tsx` | **Fixed** 4297386: the pill uses the `shadow-hover` token. |
| A-4 | P3 | top bar and footer | A 401 console message on each logged-out page load (the session check). | **Deferred**: the message is the API answer (401) to the logged-out session check. A change to it is a change to API behaviour, which is outside this presentation-only pass. Suggestion for later: answer 200 with no session. |
| A-5 | P3 | top bar and footer | No test covers the 44px footer and switch targets on touch screens. | **Fixed** 26d2d9d: an e2e test on an emulated touch screen checks the 44px footer links and switch targets. |

## Critique, by area

The scores are the Nielsen heuristic totals of the design reviewers. The maximum does not include n/a heuristics. Each fix commit was added when its area was done.

### Home (19/28)
| ID | P | Finding | Status |
|---|---|---|---|
| H-1 | P2 | Two course searches on the home page (top bar and hero). At 390, the full-width Search pill of the hero pushes "Start planning" down. | **Fixed** 267de87: the top bar hides its search on home and course search. |
| H-2 | P2 | The name of the hero search is "Search courses and instructors", but it searches only courses. | **Fixed** 267de87: "Search courses", with an example code in the placeholder. |
| H-3 | P2 | Five controls in the action row. "Open my plan" opens an empty planner for a first-time visitor. | **Fixed** 267de87: "Open my plan" shows only when a plan exists on the device. |
| H-4 | P2 | On a phone, the chapel is a small strip below the fold. | **Fixed** 267de87: below 640px, the chapel goes from edge to edge. The hero padding is tighter. |
| H-5 | P3 | The hero section has no accessible name. There are two `role="search"` landmarks. | **Fixed** 267de87: the hero section has a name. Home has one search landmark. |

### Top bar and footer (24/36)
| ID | P | Finding | Status |
|---|---|---|---|
| C-1 | P2 | The top bar (Plan / Catalog / Forum) and the footer (Plan / Read / Quarterly) organise the site differently. The footer never says "Forum". | **Fixed** 267de87: footer columns Plan, Catalog, Forum, Quarterly. |
| C-2 | P2 | "Not official advising" shows only in the planner, but PRODUCT.md says that every page says it. | **Fixed** 267de87: the footer adds "It is not official advising." on every page. |
| C-3 | P2 | Eyebrow labels above page titles repeat the title ("QUARTERLY / About", "PLANS / My plans", "PROGRAMS", "START PLANNING"). The craft floor bans them. | **Fixed** 81f1840: removed from onboarding, My plans, Compare, About, Privacy, Programs. The instructor and program pages moved their labels under the title. The labels stay where the label is content (course code, sign-up step, curator console). |
| C-4 | P3 | The search icon button of the top bar covers the left padding of the input. The search form has no name. | **Fixed** 267de87: `pl-11` and the name "Site search". |

### Onboarding (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| O-1 | P2 | Step pills look like buttons, but a click does nothing. | **Fixed** db58c1d: the current step is on a wash pill. Done steps have a check mark. The other steps are plain text. |
| O-2 | P2 | The page gives the name of the step three or four times (eyebrow, h1, pills, h2 "Step 1 of 5: Entry term"). | **Fixed** 81f1840, db58c1d: the label is gone, and a one-line description replaces it. The step heading keeps its number. |
| O-3 | P2 | The first field is "Catalog year" (jargon for a first-year). The page does not say how long setup takes or where it keeps the plan. | **Fixed** db58c1d: the first quarter comes first. Catalog year has a hint in plain words. New line: "Five short steps. You can change everything later." |
| O-4 | P2 | "Generate a starting plan" (on by default) does not say that an AI writes the plan. | **Fixed** db58c1d: "Written by AI, then checked by the verifier. You choose what to keep." |
| O-5 | P3 | Goals step: developer words ("drag a chip"), a cramped 3-column timeline at 390, and `aria-label` on a plain div. | **Fixed** db58c1d: a legend in plain words, one column below 480px, and a named group. |

### Planner page and grid (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PL-1 | **P1** | The page shows no plan verdict. It shows only an error count inside "Check plan", and this count disappears at 0. A valid plan never says "Valid". | **Fixed** 9eeebf7: "Valid" / "N warnings" / "N errors" is beside the plan name, and opens the plan check. |
| PL-2 | **P1** | Plan-check items lose their content. The code cuts requirement messages at the first colon, so the list says "Fake Program." three times. | **Fixed** 9eeebf7, b228808: both message forms keep "needs ...". Unit tests. |
| PL-3 | P2 | Empty quarters repeat "0 units 0 h/wk Difficulty 0". "Drop a course here" tells only about dragging. | **Fixed** 9eeebf7: "No courses yet". No row of zeros (goals still show). |
| PL-4 | P2 | Seven equal toolbar pills. Three rows at 390. "Check plan" opens a tab with the name "Issues". | **Fixed** caf0684 (part): the drawer tab is "Check plan", the same as its button. On a phone, the panel buttons are one sideways row, so the toolbar is two rows. **Deferred**: a merge of the four panel buttons into one control changes the toolbar that Richard shaped in FEEDBACK F4. |
| PL-5 | P2 | Plan-check items use a 3px coloured left strip for severity. A student can read it as the requirement colours (and the craft floor bans it). | **Fixed** 9eeebf7: no coloured strip on plan-check items. |
| PL-6 | P3 | Only a tooltip explains "Difficulty 4.5". Many entrance animations at the same time. | **Deferred**: an explanation of "Difficulty" needs a glossary pattern, and the app does not have one yet. The entrance animations are the settle/rise of DESIGN.md, and they stop with reduced motion. |

### Generate plan popup (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| GE-1 | **P1** | Each variant has a maroon "Apply" (2-3 primaries in one view). The Apply of an invalid variant looks as safe as the Apply of a valid one. | **Fixed** a518be9: Apply is an outline button on every option. An option with errors says so in the error colour above its actions. |
| GE-2 | **P1** | Apply replaces quarters silently. Nothing says which quarters change, and nothing confirms the change after it. | **Fixed** a518be9, b228808: "Changes 3 quarters: ..." is above the actions. After the change, the planner shows "Applied the generated plan". |
| GE-3 | P2 | The figures that are different between variants are a muted caption. The reasons have the visual weight. | **Fixed** a518be9: the figures are body text. |
| GE-4 | P2 | Four actions for each variant. "View diff" is developer jargon. | **Fixed** a518be9, 05cc270: "See changes". "Choose quarters to apply" moved inside it. Three actions for each option. |

### Advisor chat (29/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AD-1 | **P1** | "After this change: 4 errors" has nothing to compare with. Thus the student cannot tell if the change helps. | **Fixed** 42d5647: "Now: 4 errors → After this change: 4 errors (no change)". |
| AD-2 | P2 | The sheet covers the plan that it discusses. | **Deferred**: a desktop side panel would change the advisor layout that FEEDBACK F4 settled. This is Richard's decision. |
| AD-3 | P2 | Citation chips are dense ("workload 13 h/wk · n=34"), with underlines inside pills. | **Fixed** 4297386: "(34 ratings)" instead of "n=34". Linked chips are maroon, without underlines. |
| AD-4 | P3 | The disabled Send button is faded maroon, not the disabled colour. | **Fixed** 42d5647: a disabled primary is a grey plate with legible muted text. |

### Credits editor (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CR-1 | P2 | Credit rows show raw data: "placement: …", "(needs mapping)". | **Fixed** e1ad1a2: "AP exam", "Placement", "Transfer credit", "not matched to a course yet". |
| CR-2 | P2 | Remove is instant and silent. DESIGN.md says that destructive actions ask for confirmation in place. | **Fixed** e1ad1a2: Remove asks "Remove? Yes, remove / Keep" in place, in the error colour. |
| CR-3 | P2 | The add form has no heading. During an edit, two identical forms show. | **Fixed** e1ad1a2: an "Add a credit" heading. The add form hides while the student edits a credit. |
| CR-4 | P2 | The scroll area of the drawer can clip the list of the course picker. | **Fixed** 9eeebf7, cc5ed78: the list is in the page flow, and it closes after a click. |

### My plans and Compare plans (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| MP-1 | P2 | Each row starts with a bordered input, not with the name of the plan. The rows do not align. | **Fixed** b62cb07: the name reads as the title of the plan. Its field shows on hover and focus. "N courses", and the date in words. |
| MP-2 | P2 | "PLANS" eyebrow above both headings (see C-3). | **Fixed** 81f1840 (see C-3). |
| MP-3 | P2 | For identical plans, Compare shows "None / None / None" and gives them the labels "A" and "B". | **Fixed** ac84836: "Same courses in the same quarters.". The columns have the names of the plans. |

### Course search (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CS-1 | P2 | The search of the top bar and the search of the page do the same job on one screen (see H-1). | **Fixed** 267de87 (see H-1). |
| CS-2 | P2 | "More filters" has no disclosure marker. | **Fixed** 6330b28: a chevron that turns when open. |
| CS-3 | P2 | Department and Core area are free-text fields. A wrong guess quietly returns nothing. | **Deferred**: choices need the list of valid department and Core values, and the page does not load it. The placeholders give the format. |
| CS-4 | P2 | Zero results is a dead end: "0 COURSES", an empty list, disabled paging. | **Fixed** 3ca0cff: "No courses match" with "Clear the search". Paging shows only with more than one page. |
| CS-5 | P3 | At 390, the placeholder is cut off. | **Fixed** 3ca0cff, b228808: "Code or title". |

### Course page (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CP-1 | **P1** | Two different difficulty and workload numbers on one page (student ratings, and the estimate of the planner). Nothing tells which is which. | **Fixed** cc5ed78: a caption says that the block is the estimate of the planner, and that the overview has the ratings of the students. One format ("/ 5", "h/wk"). |
| CP-2 | P2 | Three "Estimate" badges in the warning tone, with no explanation. | **Fixed** cc5ed78: a neutral "Estimate" badge. The caption explains it. |
| CP-3 | P2 | The forum is hard to find. The instructor names are the only links to it. | **Fixed** cc5ed78: "Choose an instructor to read their reviews and discussion." |
| CP-4 | P2 | "Unlikely (0%)". The basis column repeats one source four times and wraps at 390. | **Fixed** cc5ed78, b228808: "Not expected". A shared basis shows one time, under the table. |
| CP-5 | P3 | Nested cards in the attributes block. | **Fixed** cc5ed78: hairline rows. |

### Forum page, thread and instructors (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| FO-1 | **P1** | The front door of the Forum (`/instructors`) is a name search. Most students come with a course, not with the name of an instructor. Its description starts with a restriction. | **Fixed** 6330b28, db55ef4: the title is "Forum". The page says what it is, with "Know the course? ..." and "Find a course". The login note shows only to logged-out visitors. |
| FO-2 | P2 | At 390, rating tiles and histograms push the first review approximately 1,450px down. | **Fixed** 6330b28: "Rating breakdown" folds away. |
| FO-3 | P2 | The size of histogram bars is count/max, so 1 of 2 ratings draws a full bar. | **Fixed** 6330b28: bars are shares of all ratings. |
| FO-4 | P2 | The heading of an untitled review repeats the author ("Review by Fake Heron" under "Fake Heron"). | **Deferred**: the fallback heading is also the link to the thread of the review, and the accessible name of the review. A better wording needs Richard's view on how to name reviews. |
| FO-5 | P3 | The thread header says the count two times and names a sort order that cannot change. | **Fixed** 05cc270: "Comments (10)", "Best first." |

### Program pages (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PR-1 | **P1** | Each course code on a program page is plain text. To see a course, the student must copy its code into search. | **Fixed** 6330b28: each course code in requirements and in the sample path links to its course. |
| PR-2 | P2 | Programs and Courses have different compositions. The "PROGRAMS" eyebrow repeats the switch. | **Fixed** 81f1840: no label. The switch aligns with the header. |
| PR-3 | P2 | "In review" / "Needs review" are internal words. | **Fixed** ac84836: "Not yet hand-checked", in sentence case. |
| PR-4 | P3 | Copy errors: a plural type label on one program, an ISO date, "Add to my plan" vs "Add to plan". | **Fixed** 81f1840, 05cc270: singular type, "July 1, 2099", "Add to plan". |

### Sign-up, login and account (34/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AU-1 | P2 | The first sign-up step is dense: heading, label, hint and a 4-line privacy paragraph before the button. | **Fixed** 05cc270: one line before the button. Placeholder "cnetid@uchicago.edu". |
| AU-2 | P3 | "Forgot password?" and "Create an account" use different link styles. | **Fixed** ac84836. |
| AU-3 | P3 | The "Log in" pill of the top bar shows on the login and sign-up pages. | **Fixed** ac84836. |

## Polish, harden and adapt

- **`/impeccable polish`, every area:** After the fixes, we made new screenshots of every page at 1440 and 390, and compared them side by side. The pass found and fixed these problems (b228808, db55ef4):
  - The second message form of PL-2.
  - The four tabs and the close button of the drawer did not fit 390 px.
  - The wording "Apply changes 3 quarters".
  - A shared offerings basis repeated on each row.
  - A course search placeholder that was cut off on a phone.
  - A hint on the Forum page that wrapped into ": its page lists".
  - An ISO date on the account page.
  - The form order of D9 put the list of the course picker over "Add credit" (fixed in 9eeebf7, cc5ed78).
- **`/impeccable harden`, planner and forum** (caf0684):
  - Compact fields, the graduation list and the top-bar search are 16px on touch screens. (iOS Safari zooms into smaller fields.)
  - Long unbroken words in forum titles wrap, the same as post bodies already did.
  - These cases each have their own state: empty quarters, an unavailable verifier ("Not checked yet"), no search results, and identical plans.
- **`/impeccable adapt`, planner and forum** (caf0684, 6330b28):
  - On a phone, the panel buttons of the planner are one row that scrolls sideways. Thus the toolbar is two rows, not three.
  - The drawer tabs fit 390 px.
  - The rating breakdown of the forum folds away, so reviews start near the top.

## Summary

| | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|
| Found | 0 | 8 | 38 | 16 | 62 |
| Fixed | 0 | 8 | 35, plus PL-4 in part | 14 | 57 + 1 in part |
| Deferred (with a reason) | 0 | 0 | 3 (AD-2, CS-3, FO-4), plus the rest of PL-4 | 2 (A-4, PL-6) | 5 + 1 in part |
| Needs Richard | 0 | 0 | 0 | 0 | 0 |

All P0 and P1 findings are fixed. For the axe results after the fixes, see docs/PROGRESS.md (design pass).

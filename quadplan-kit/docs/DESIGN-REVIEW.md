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
| A-1 | P3 | course page | Instructor name link is 22px tall (passes WCAG on spacing, under the project's 44px rule). `CourseOverview.tsx` | pending |
| A-2 | P3 | course search | The Courses/Programs pill animates `width`, a layout property. `CatalogToggle.tsx` | pending |
| A-3 | P3 | course search | A hard-coded `rgba` shadow on the switch's pill instead of a token. `CatalogToggle.tsx` | pending |
| A-4 | P3 | top bar and footer | A 401 console message on every logged-out page load (the session check). | pending |
| A-5 | P3 | top bar and footer | 44px footer and switch targets on touch screens are not covered by a test. | pending |

## Critique, by area

Scores are the design reviewers' Nielsen heuristic totals (n/a heuristics excluded from the maximum). Fix commits are filled in as each area is done.

### Home (19/28)
| ID | P | Finding | Status |
|---|---|---|---|
| H-1 | P2 | Two course searches on the home page (top bar and hero); at 390 the hero's full-width Search pill pushes "Start planning" down. | pending |
| H-2 | P2 | The hero search is named "Search courses and instructors" but searches courses only. | pending |
| H-3 | P2 | Five controls in the action row; "Open my plan" opens an empty planner for a first-time visitor. | pending |
| H-4 | P2 | On a phone the chapel is a small strip below the fold. | pending |
| H-5 | P3 | The hero section has no accessible name; two `role="search"` landmarks. | pending |

### Top bar and footer (24/36)
| ID | P | Finding | Status |
|---|---|---|---|
| C-1 | P2 | Top bar (Plan / Catalog / Forum) and footer (Plan / Read / Quarterly) organise the site differently; the footer never says "Forum". | pending |
| C-2 | P2 | "Not official advising" appears only in the planner, though PRODUCT.md says every page says it. | pending |
| C-3 | P2 | Eyebrow labels above page titles repeat the title ("QUARTERLY / About", "PLANS / My plans", "PROGRAMS", "START PLANNING"). The craft floor bans them. | pending |
| C-4 | P3 | The top-bar search icon button covers the input's left padding; the search form has no name. | pending |

### Onboarding (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| O-1 | P2 | Step pills look like buttons but are not clickable. | pending |
| O-2 | P2 | The step is named three or four times (eyebrow, h1, pills, h2 "Step 1 of 5: Entry term"). | pending |
| O-3 | P2 | The first field is "Catalog year" (jargon for a first-year); no word on how long setup takes or where the plan is kept. | pending |
| O-4 | P2 | "Generate a starting plan" (on by default) does not say the plan is written by AI. | pending |
| O-5 | P3 | Goals step: developer wording ("drag a chip"), a cramped 3-column timeline at 390, `aria-label` on a plain div. | pending |

### Planner page and grid (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PL-1 | **P1** | No plan verdict on the page: only an error count inside "Check plan", which disappears at 0; a valid plan never says "Valid". | pending |
| PL-2 | **P1** | Plan-check items lose their content: requirement messages are cut at the first colon, so the list says "Fake Program." three times. | pending |
| PL-3 | P2 | Empty quarters repeat "0 units 0 h/wk Difficulty 0"; "Drop a course here" only describes dragging. | pending |
| PL-4 | P2 | Seven equal toolbar pills; three rows at 390; "Check plan" opens a tab called "Issues". | pending |
| PL-5 | P2 | Plan-check items use a 3px coloured left strip for severity, which can be read as the requirement colours (and the craft floor bans it). | pending |
| PL-6 | P3 | "Difficulty 4.5" is explained only in a tooltip; many entrance animations at once. | pending |

### Generate plan popup (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| GE-1 | **P1** | Every variant has a maroon "Apply" (2-3 primaries in one view), and an invalid variant's Apply looks as safe as a valid one's. | pending |
| GE-2 | **P1** | Apply replaces quarters silently: nothing says which quarters change, and nothing confirms it afterwards. | pending |
| GE-3 | P2 | The figures that differ between variants are a muted caption; the reasons take the weight. | pending |
| GE-4 | P2 | Four actions per variant; "View diff" is developer jargon. | pending |

### Advisor chat (29/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AD-1 | **P1** | "After this change: 4 errors" has nothing to compare with, so the student cannot tell whether the change helps. | pending |
| AD-2 | P2 | The sheet covers the plan it is discussing. | pending |
| AD-3 | P2 | Citation chips are dense ("workload 13 h/wk · n=34"), underlined inside pills. | pending |
| AD-4 | P3 | The disabled Send button is faded maroon instead of the disabled colour. | pending |

### Credits editor (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CR-1 | P2 | Credit rows show raw data: "placement: …", "(needs mapping)". | pending |
| CR-2 | P2 | Remove is instant and silent; DESIGN.md says destructive actions confirm in place. | pending |
| CR-3 | P2 | The add form has no heading; two identical forms show while editing. | pending |
| CR-4 | P2 | The course picker's list can be clipped by the drawer's scroll area. | pending |

### My plans and Compare plans (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| MP-1 | P2 | Each row leads with a bordered input instead of the plan's name; rows do not line up. | pending |
| MP-2 | P2 | "PLANS" eyebrow above both headings (see C-3). | pending |
| MP-3 | P2 | Compare shows "None / None / None" for identical plans and labels them "A" and "B". | pending |

### Course search (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CS-1 | P2 | The top-bar search and the page's search do the same job on one screen (see H-1). | pending |
| CS-2 | P2 | "More filters" has no disclosure marker. | pending |
| CS-3 | P2 | Department and Core area are free-text fields; a wrong guess quietly returns nothing. | pending |
| CS-4 | P2 | Zero results is a dead end: "0 COURSES", an empty list, disabled paging. | pending |
| CS-5 | P3 | The placeholder is cut off at 390. | pending |

### Course page (26/40)
| ID | P | Finding | Status |
|---|---|---|---|
| CP-1 | **P1** | Two different difficulty and workload numbers on one page (student ratings vs the planner's estimate) with nothing saying which is which. | pending |
| CP-2 | P2 | Three warning-toned "Estimate" badges with no explanation. | pending |
| CP-3 | P2 | The forum is hard to find: instructor names are the only links to it. | pending |
| CP-4 | P2 | "Unlikely (0%)"; the basis column repeats one source four times and wraps at 390. | pending |
| CP-5 | P3 | Nested cards in the attributes block. | pending |

### Forum page, thread and instructors (27/40)
| ID | P | Finding | Status |
|---|---|---|---|
| FO-1 | **P1** | The Forum's front door (`/instructors`) is a name search; most students arrive with a course, not an instructor's name. Its description leads with a restriction. | pending |
| FO-2 | P2 | Rating tiles and histograms push the first review about 1,450px down at 390. | pending |
| FO-3 | P2 | Histogram bars are sized by count/max, so 1 of 2 ratings draws a full bar. | pending |
| FO-4 | P2 | An untitled review's heading repeats the author ("Review by Fake Heron" under "Fake Heron"). | pending |
| FO-5 | P3 | The thread header says the count twice and names a sort order that cannot change. | pending |

### Program pages (25/40)
| ID | P | Finding | Status |
|---|---|---|---|
| PR-1 | **P1** | Every course code on a program page is plain text; to see a course you copy its code into search. | pending |
| PR-2 | P2 | Programs and Courses are composed differently; "PROGRAMS" eyebrow repeats the switch. | pending |
| PR-3 | P2 | "In review" / "Needs review" are internal words. | pending |
| PR-4 | P3 | Copy slips: plural type label on one program, ISO date, "Add to my plan" vs "Add to plan". | pending |

### Sign-up, login and account (34/40)
| ID | P | Finding | Status |
|---|---|---|---|
| AU-1 | P2 | The first sign-up step is dense (heading, label, hint and a 4-line privacy paragraph before the button). | pending |
| AU-2 | P3 | "Forgot password?" and "Create an account" use different link styles. | pending |
| AU-3 | P3 | The top bar's "Log in" pill shows on the login and sign-up pages. | pending |

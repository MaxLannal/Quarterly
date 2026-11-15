# Design implementation

How each part of `docs/DESIGN.md` maps to code in `apps/web`. DESIGN.md decides the look; `docs/SPEC.md` decides behavior and content. Conflicts between them, and design-review questions, are DF-1 to DF-13 in `docs/OPEN_QUESTIONS.md` ("Design foundation").

## Tokens: `apps/web/src/index.css`

All DESIGN.md tokens live in one `@theme` block, so Tailwind utilities use token names. Tailwind's own palette, radii, shadows and type sizes are cleared (`--color-*: initial` and so on), so a class can only name a DESIGN.md token, and components contain no hex values.

| DESIGN.md | CSS variable | Tailwind names |
| --- | --- | --- |
| `colors.*` (all 43, incl. orbs, semantic, data-1..6) | `--color-<name>`; semantic ones drop the `semantic-` prefix, as in DESIGN.md "Implementation tokens" (`--color-error`) | `bg-canvas`, `text-ink`, `text-muted`, `border-hairline`, `bg-primary-wash`, `text-error`, `bg-success-wash`, `border-l-data-3`, ... |
| (not in DESIGN.md) warning and info washes | `--color-warning-wash`, `--color-info-wash` = the token mixed 8% into white (DF-6) | `bg-warning-wash`, `bg-info-wash` |
| `typography.*` (14 styles) | `--text-<name>` with `--line-height`, `--letter-spacing` and `--font-weight` sub-values | `text-display-mega` ... `text-display-sm`, `text-title-md`, `text-title-sm`, `text-body-md`, `text-body-strong`, `text-body-sm`, `text-caption`, `text-caption-uppercase` (add `uppercase`), `text-button`, `text-nav-link` |
| font families | `--font-display` (Newsreader), `--font-sans` (Inter) | `font-display`, `font-sans` (the default) |
| `rounded.*` | `--radius-xs` ... `--radius-pill` | `rounded-xs` ... `rounded-xxl`, `rounded-pill`, `rounded-full` |
| `spacing.*` | Tailwind's 4px step is DESIGN.md's base unit: `1`=xxs 4, `2`=xs 8, `3`=sm 12, `4`=base 16, `5`=md 20, `6`=lg 24, `8`=xl 32, `12`=xxl 48, `24`=section 96; also `--space-<name>` on `:root` for plain CSS | `p-4`, `gap-6`, `py-section` |
| Elevation | `--shadow-hover`, `--shadow-overlay` | `shadow-hover`, `shadow-overlay` |
| Layout | `--container-content` 1200, `--container-reading` 720, `--container-form` 448, `--container-tool` 1600 (planner only, DF-2) | `max-w-content`, `max-w-reading`, `max-w-form`, `max-w-tool` |
| Focus | `:focus-visible` = 2px maroon outline, 2px offset, on every element (base layer) | `focus-visible:outline-offset-*` to adjust |
| Orbs | `.orb` class: radial gradient of one orb color at 40% fading out, blurred 70px | `<Orb color="lake" />` |
| Motion | 150ms default transitions; `--animate-*` keyframes (see "FEEDBACK UI" below); `prefers-reduced-motion` turns every animation off and makes transitions instant | `animate-fade-in`, `animate-dialog-in`, `animate-drawer-in/out`, `animate-sheet-in/out`, `animate-rise`, `animate-settle`, `animate-typing` |

`src/lib/utils.ts` teaches `tailwind-merge` the token names, so `cn("text-caption", "text-ink")` keeps both (a size and a color).

## Fonts and assets: self-hosted

`@fontsource-variable/inter` and `@fontsource/newsreader` (weight 300) are npm dependencies imported in `src/main.tsx`; Vite bundles the font files into `/assets`. Icons are inline SVG in `src/components/ui/icons.tsx`. There are no images. The app makes no request outside its own origin; `e2e/design.spec.ts` loads 13 pages and fails on any other origin, and checks that both fonts load from `/assets`.

## Components

`src/components/ui/` (shadcn/ui style, restyled):

- `button.tsx`: `Button` with variants `primary` (alias `default`), `outline`, `ghost` (tertiary text), `destructive`, `link`; sizes `md` (40px pill), `sm` (32px pill), `icon` (40px circle). Every size is a 44px box: the pill is drawn inside a transparent border (`bg-clip-padding`), so the look matches DESIGN.md while the target stays 44px. Outline lines are inset shadows inside that border.
- `input.tsx`: `Input`, `Select`, `Textarea`, `Label`, `Field`, `FieldHint`, `FieldError` (icon + message), `ChoiceRow`; `controlClass` is DESIGN.md `text-input` (44px, 8px radius, `border-input` line, 2px maroon line on focus).
- `misc.tsx`: `Badge` (badge-pill; semantic tones always carry an icon), `Notice` (tinted box with icon), `NotAvailable`, `Spinner`, `ErrorText`, `Dots` (single series in maroon), `CourseCode` (caption-uppercase, never serif).
- `card.tsx`: `Card` variants `default` (course-card), `compact`, `post` (post-card), `orb` (orb-card), `featured` (maroon featured-card), `well` (grouped controls); `interactive` adds the hover shadow. Also `Orb`, `Avatar`, `Stat`.
- `dialog.tsx`, `menu.tsx`, `tabs.tsx` (moved from the planner): overlay shadow, maroon focus and selection, current tab = ink text over a 2px maroon underline.
- `icons.tsx`: local SVG icons.

`src/components/layout/`:

- `TopNav.tsx`: top-nav (64px, canvas, text wordmark, links with a pale maroon pill for the current page, search, account). Below 768px the links fold behind a "Menu" button; search stays visible.
- `Footer.tsx`: footer (canvas, body-sm, link columns).
- `page.tsx`: `PageContainer` (widths content / reading / form / tool), `PageHeader` (eyebrow, light-serif h1, meta, description, actions), `Section`, `Eyebrow`, `EmptyState`, `LoadingState` (skeleton plates), `inlineLinkClass` / `standaloneLinkClass` (link-inline).

Every page and feature uses these: home (hero-band with one orb), onboarding, planner (grid, course cards with data-color requirement stripes, toolbar, right-hand drawer with the requirement tree, goals and plan check, Generate popup, AI advisor sheet), course search and course page, program explorer and program page, my plans, compare, sign-up, login, account, privacy, and the placeholder pages.

## Accessibility kept

- Contrast: all text pairs come from DESIGN.md's AA table; `muted` is the smallest text color (4.6:1 on the pale maroon selection). `gray-dark` is used for icons and list markers only.
- 44px targets: every button, tab and menu item; `e2e/design.spec.ts` measures them on four pages and checks the primary pill is drawn 40px inside a 44px box.
- Visible focus on every interactive element; "Move to…" stays the keyboard alternative to drag and drop.
- axe: planner, home and course page (WCAG 2.1 A/AA tags), plus the auth pages' existing checks; since step 5 also the planner's Generate and Advisor states, the forum page and the thread at 1440 and 390px (see the step 5 section below).

## Deviations from DESIGN.md, and why

- Wordmark reads "Quarterly", not "UChicago Course Forum" (DF-1).
- The planner may be 1600px wide (DF-2).
- The top bar's sign-in is an outlined pill, not a filled one, to keep one filled button per page (DF-4).
- Warning and info washes are derived with `color-mix`, not new hex values (DF-6).
- No Rare UI components, so no credit link yet; the hero orb is still (DF-8). No mobile filter drawer (DF-9). No dark mode (DF-10).
- Inter is loaded as the variable font, so its CSS family name is "Inter Variable" (with "Inter" as a fallback name).
- The planner's dense cards use `caption` (14px) for course details; DESIGN.md has no smaller body size and none is invented.
- The footer's side padding is the page gutter (16/24/32px), not DESIGN.md's 48px, so its left edge lines up with the top bar and the page above it (step 5).

## Design review at 1440 and 390 (step 5)

Every page was opened at 1440×900 (desktop) and 390×844 (phone) against the MSW mocks and checked against DESIGN.md: spacing rhythm, type scale, color tokens, cards and borders, button variants, focus, empty/loading/error states, horizontal overflow, the phone header and tap targets. The pictures are in `docs/screenshots/<page>-1440.png` and `<page>-390.png` (`SCREENSHOTS=1 make screenshots`, spec `apps/web/e2e/screenshots.spec.ts`; full page at device scale 1, animations off, the mouse parked so no hover state shows; dialogs are shot at viewport size because they are fixed to it).

No page scrolls sideways at 390px, and axe found no WCAG 2.1 A/AA violations on any page at either width. What was found and fixed:

| Page | Found | Fixed |
| --- | --- | --- |
| Every page (top nav) | Only `/plan`, `/courses`, `/programs` and `/instructors` lit a nav item; My plans, compare, onboarding, forum pages, threads and guidelines lit none, or lit "Courses" for a forum thread. | Each nav item now owns its section: Plan = `/plan`, `/plans*`, `/onboarding`; Courses = `/courses*` except forum pages; Forum = `/instructors*`, `/guidelines`, forum pages and threads (`aria-current="page"` + the maroon-wash pill). Unit-tested in `routes.test.tsx`. |
| Every page (footer) | The footer content sat 16px right of the top bar and page content at desktop (48px padding against a 32px gutter); on the planner it was 1200px wide under a 1600px top bar. | Footer uses the page gutter and the same width rule as the top bar (tool width on `/plan`). |
| Home | The hero orb (640px) overflowed the hero band and was cut with a visible straight edge at its bottom. | Orb 560px, lifted 24px, so its fade ends inside the band. |
| Planner `/plan` | Course cards in a quarter column (about 195px wide at 1440) squeezed the title, program tag and issue messages between the drag handle and the "…" menu: issues wrapped one word per line. | Card is now a header row (drag handle · code and units · actions menu, each a 44px target) over a full-width body (title, tag, workload and difficulty, issues). |
| Planner, Advisor tab | Post and summary citation chips were plain grey pills; the chips sat 6px inside the message text edge. | Chips link to the thread (`post`), the forum page (`summary`) and the course page (`attribute`); see below. Chip rows are pulled out by the chip's transparent border so pills line up with the text. |
| Generate dialog | Radio and checkbox rows were hand-built (8px gap, no shared style). | All rows use `ChoiceRow` (same as onboarding and the program picker now). Same chip alignment fix as the Advisor. |
| My plans `/plans` | Each plan card wrapped its name, meta and four buttons as one flex row, so on a phone the buttons broke onto lines in a different order on each card. | Two rows: name field with its meta line, then the actions; side by side from 768px. |
| Course search `/courses` | On a phone the seven filters stacked one per row (a full screen of form before any result). | Short filters sit two to a row on phones; "Code or title" and the buttons keep the full width. The bottom drawer stays DF-9. |
| Course page `/courses/:code` | Logged in, the instructor list still said "reviews need login". Instructor and "Counts toward" links were 21px-tall targets. | The note shows only when logged out. Dense links get a 44px target without moving the layout (`tallTargetClass`: 12px padding cancelled by a negative margin). |
| Forum page | Section heads ("Ratings", "What students say") were Inter 18px while every other page's section heads are the light serif. Meta links (instructor, "Course page") and review titles were 21–26px targets. | Section heads use the standard `Section` size (Newsreader 300, `display-sm`). Meta links and post titles use `tallTargetClass`. |
| Forum composer and Report dialog | "Would you recommend it?" and the report reasons were hand-built radio rows. | Both use `ChoiceRow`. |
| Account, login, sign-up | The empty live regions for errors and notices took a slot in the form's flex column, so an extra 20–40px gap sat above buttons and at the top of the login card. | Empty live regions are `empty:absolute`: still in the page, so later messages are announced, but out of the flow. |
| Moderation queue | The "Community guidelines" meta link was a 21px target. | `tallTargetClass`. |
| About and the curator console placeholder | The page told students "Placeholder for `/about`. Built in prompt 03." | A plain "Coming soon. This page is not written yet." with a link home. The About text itself is DF-12. |
| Onboarding, program picker | Hand-built radio and checkbox rows. | `ChoiceRow`. |
| Thread, programs, program, instructors, instructor, guidelines, privacy, sign-up, 404 | Checked at both widths; nothing to fix. | — |

**Advisor citation chips.** A citation names only a kind and an id (`post:3`, `summary:1`, `attribute:CMSC 14300:workload_hours`). Course, program and attribute chips build their URL from the id. A `post` chip asks `GET /forum/posts/{id}` for its `page_id`, then `GET /forum/pages/{page_id}` for the course code and instructor slug, and links to `/courses/:code/i/:instructor/t/:id`; a `summary` chip asks only for the page. Forum reads need a login, so for a logged-out student (or a removed post, or a failed request) the chip stays a plain pill: same shape, no underline, nothing to click. Unit-tested in `AdvisorPanel.test.tsx`; the mock advisor now cites one post and one summary.

**How DESIGN.md was applied in this pass.**
- Tokens: no new color, font size, radius or shadow; every fix uses existing utilities. The only new shared class is `tallTargetClass` (`components/layout/page.tsx`), built from the 4px spacing scale.
- Type scale: page sections use `Section` (Newsreader 300 `display-sm`); dense UI stays Inter `caption`/`body-sm`; course codes stay tabular Inter.
- Components: `ChoiceRow` replaces every simple hand-built checkbox or radio row (the account page's bordered "delete my posts" options keep their own card layout); `Section`, `Button` variants and `Card` are unchanged.
- Phone width: the top bar keeps search on its own row and folds links behind "Menu" (`nav-menu-390.png`); grids go to one column; forms keep 44px controls; dense links get 44px targets. The planner on a phone stacks requirements, the grid, then the Issues/Goals/Advisor panel (DF-13).

**Evidence.** `e2e/design.spec.ts` runs axe (WCAG 2.1 A/AA) at 1440 and 390 on the planner with courses, the Generate dialog (options and results), the Advisor with an answer and resolved forum citation links, the forum page (with the review form open), and the thread (with the report dialog open), and fails on any serious or critical violation. `e2e/shell.spec.ts` checks 17 pages for sideways scrolling at phone width.

## FEEDBACK UI (2026-11-14)

Richard's FEEDBACK items F2 to F6 (`docs/FEEDBACK.md`). They override DESIGN.md and the SPEC where they conflict.

**Layout (F4).** The planner is now a header, a toolbar and the grid; the old three-column layout (requirement rail, grid, Issues/Goals/Advisor tabs) and the phone "Jump to" links are gone.
- Header: plan name with the line "Not official advising. Confirm with your adviser and My Planner." under it; catalog year and program pills.
- Toolbar: Requirements, Goals, Check plan (outline pills that open the drawer at that tab; the open one gets the maroon-wash selected state and `aria-expanded`), AI advisor, then Save and the one primary pill, Generate plan.
- Drawer (`features/planner/PlanDrawer.tsx`): tabs Requirements, Goals and Issues. At 1024px and up it is a sticky 380px column (400px from 1280px) beside the grid, with the overlay shadow; it is not modal, so the grid stays usable and courses drag from the tree onto the grid. Below 1024px it covers the screen as a modal dialog (focus trapped, Escape and "Close panel" close it, focus returns to the toolbar). It stays mounted while closed, so open tree nodes and goal fields survive.
- Requirement tree (`RequirementTree.tsx`): program heading, then its rule nodes as disclosure buttons (label, the rule in caption text, progress as a small "2 of 3" with a check when met), then courses: grip handle, the course code in bold (Inter 600) over the name in caption, a check if it is on the plan, and Add. Group nodes start open; course lists load when a node opens. Nesting is drawn with a hairline left border.
- Errors stay subtle: no banner or red counts on the page. "Check plan" carries a small error-wash count pill (screen readers hear "Check plan (3 errors)"); the drawer's Issues tab shows the verifier badge and the list. Course cards no longer turn their border red; issue lines keep a colored icon with body-colored text.
- AI advisor (`AdvisorSheet` in `features/advisor/AdvisorPanel.tsx`, `components/ui/sheet.tsx`): a modal sheet that slides down from the top, max 768px wide and 88vh tall on desktop, full screen on a phone. Header: spark avatar, "AI advisor", a neutral "Generative AI" badge and "Answers are written by an AI and can be wrong. Not official advising." Messages read as a chat: the student's bubbles on the right in maroon wash, the AI's on the left in white cards beside a spark avatar, proposal cards in the AI column, a three-dot typing indicator while the answer streams, and a composer pinned to the bottom (Enter sends, Shift+Enter is a new line; focus starts there). Everything else is unchanged: SSE streaming, citation chips with links, Apply, typed confirmations, history for saved plans, logged-out behavior. The sheet stays mounted when closed, so the conversation survives.
- Drag and drop: a `DragOverlay` follows the pointer (the source card stays as a 40% placeholder); drops go to the quarter under the pointer (`pointerWithin`, falling back to overlap for keyboard drags). "Move to…" and "Add" stay the keyboard path.

**Years (F2, F3).** `features/planner/terms.ts` mirrors `planner_core.terms`: an academic year runs SU, AU, WI, SP. Each year in the grid is headed by its class year relative to entry ("Second year" for a second-year transfer) and the academic year ("2100–01"); Summer comes first and stays hidden until "Show Summer". The grid ends at the plan's graduation quarter (`graduation_term`, defaulting to the Spring of the last year left), set with "Graduating in" (Autumn, Winter or Spring, up to a year past the current last year), "Add a year" and "Remove last year" (refused, with a short message, while that year has courses). Items outside are listed under "Other terms". Local plans saved with the old `years: 5` open with Spring of year 5.

**Motion (F6).** CSS keyframes in `index.css` and a 30-line helper (`lib/motion.ts`: `usePresence` keeps an element up for its exit animation, `useMediaQuery`); no animation library.

| Moment | Animation | Duration, easing |
| --- | --- | --- |
| Button press | pill scales to 97% | 150ms |
| Dialog open | backdrop fades; panel fades, rises 8px and scales from 98% | 200ms ease-out |
| Drawer open / close | slides 24px from the right with a fade | 250ms ease-out in, 200ms ease-in out |
| AI advisor open / close | slides 24px down from the top with a fade; backdrop fades | 250ms in, 200ms out |
| Course card placed | settles from 97% to 101% to 100% | 250ms ease-out |
| New list items (chat messages, issues, goals, tree courses, variants) | rise 6px and fade in; issues stagger 30ms | 200ms ease-out |
| Quarter under a dragged card | maroon-wash fill, maroon line and hover shadow | 200ms |
| AI typing | three dots pulse in turn | 1.2s loop |

Rules: entrances ease out, exits ease in and are shorter; nothing moves more than 24px; every keyframe ends at `transform: none`, so no containing block is left behind for the fixed drag overlay; reading surfaces (messages, post text) do not move once shown. With `prefers-reduced-motion: reduce` no animation runs at all (`animation: none`), transitions are instant, and closing skips the exit delay (`e2e/feedback-ui.spec.ts`, "with reduced motion, nothing animates").

**Text (F5).** Removed: the Generate dialog's "A form, not a prompt: every choice maps to a typed setting."; the quarter picker's "Choose a quarter."; the advisor's "Planning questions will work once the chat service is built."; the course search description; the program explorer description; the first sentence of the instructors description; the forum's empty-state encouragement under "No reviews yet" and "No discussion yet"; the footer tagline (now the not-affiliated line). Shortened: the forum's "No summary yet" body, "Other terms" note, and the home hero's "Plan four years of courses" (years are no longer fixed at four). Legal, privacy, error and instruction text is unchanged.

**Evidence.** `e2e/feedback-ui.spec.ts` (one test group per item), `e2e/planner.spec.ts`, axe in `e2e/design.spec.ts` with the drawer and the advisor open at 1440 and 390. Screenshots: `docs/screenshots/plan-*.png`, new `plan-drawer-*`, `plan-check-*`, `plan-years-*`; `plan-advisor-*` now shows the sheet.

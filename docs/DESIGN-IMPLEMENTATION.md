# Design implementation

This file tells how each part of `docs/DESIGN.md` maps to code in `apps/web`.

- DESIGN.md decides the look.
- `docs/SPEC.md` decides behavior and content.
- The conflicts between them, and the design-review questions, are DF-1 to DF-13 in `docs/OPEN_QUESTIONS.md` ("Design foundation").

## Tokens: `apps/web/src/index.css`

All DESIGN.md tokens are in one `@theme` block. Thus Tailwind utilities use token names.

The file clears the palette, radii, shadows and type sizes of Tailwind (`--color-*: initial` and the other resets). Thus a class can only name a DESIGN.md token, and components contain no hex values.

| DESIGN.md | CSS variable | Tailwind names |
| --- | --- | --- |
| `colors.*` (all 43, incl. orbs, semantic, data-1..6) | `--color-<name>`. Semantic names drop the `semantic-` prefix, as in DESIGN.md "Implementation tokens" (`--color-error`). | `bg-canvas`, `text-ink`, `text-muted`, `border-hairline`, `bg-primary-wash`, `text-error`, `bg-success-wash`, `border-l-data-3`, ... |
| (not in DESIGN.md) warning and info washes | `--color-warning-wash`, `--color-info-wash` = the token mixed 8% into white (DF-6) | `bg-warning-wash`, `bg-info-wash` |
| `typography.*` (14 styles) | `--text-<name>` with `--line-height`, `--letter-spacing` and `--font-weight` sub-values | `text-display-mega` ... `text-display-sm`, `text-title-md`, `text-title-sm`, `text-body-md`, `text-body-strong`, `text-body-sm`, `text-caption`, `text-caption-uppercase` (add `uppercase`), `text-button`, `text-nav-link` |
| font families | `--font-display` (Newsreader), `--font-sans` (Inter) | `font-display`, `font-sans` (the default) |
| `rounded.*` | `--radius-xs` ... `--radius-pill` | `rounded-xs` ... `rounded-xxl`, `rounded-pill`, `rounded-full` |
| `spacing.*` | The 4px step of Tailwind is the base unit of DESIGN.md: `1`=xxs 4, `2`=xs 8, `3`=sm 12, `4`=base 16, `5`=md 20, `6`=lg 24, `8`=xl 32, `12`=xxl 48, `24`=section 96. Also `--space-<name>` on `:root` for plain CSS. | `p-4`, `gap-6`, `py-section` |
| Elevation | `--shadow-hover`, `--shadow-overlay` | `shadow-hover`, `shadow-overlay` |
| Layout | `--container-content` 1200, `--container-reading` 720, `--container-form` 448, `--container-tool` 1600 (planner only, DF-2) | `max-w-content`, `max-w-reading`, `max-w-form`, `max-w-tool` |
| Focus | `:focus-visible` = 2px maroon outline, 2px offset, on every element (base layer) | `focus-visible:outline-offset-*` to adjust |
| Orbs | `.orb` class: a radial gradient of one orb color at 40% that fades out, with a 70px blur | `<Orb color="lake" />` |
| Motion | 150ms default transitions. `--animate-*` keyframes (see "FEEDBACK UI" below). `prefers-reduced-motion` stops every animation and makes transitions instant. | `animate-fade-in`, `animate-dialog-in`, `animate-drawer-in/out`, `animate-sheet-in/out`, `animate-rise`, `animate-settle`, `animate-typing` |

`src/lib/utils.ts` gives the token names to `tailwind-merge`. Thus `cn("text-caption", "text-ink")` keeps both classes (a size and a color).

## Fonts and assets: self-hosted

- `@fontsource-variable/inter` and `@fontsource/newsreader` (weight 300) are npm dependencies. `src/main.tsx` imports them.
- Vite bundles the font files into `/assets`.
- Icons are inline SVG in `src/components/ui/icons.tsx`.
- There are no images.
- The app makes no request outside its own origin. `e2e/design.spec.ts` loads 13 pages and fails on a request to a different origin. It also checks that both fonts load from `/assets`.

## Components

`src/components/ui/` (shadcn/ui style, with new styles):

- `button.tsx`: `Button`.
  - Variants: `primary` (alias `default`), `outline`, `ghost` (tertiary text), `destructive`, `link`.
  - Sizes: `md` (40px pill), `sm` (32px pill), `icon` (40px circle).
  - Each size is a 44px box. The pill is drawn inside a transparent border (`bg-clip-padding`). Thus the look agrees with DESIGN.md, and the target stays 44px.
  - Outline lines are inset shadows inside that border.
- `input.tsx`: `Input`, `Select`, `Textarea`, `Label`, `Field`, `FieldHint`, `FieldError` (icon + message), `ChoiceRow`. `controlClass` is the DESIGN.md `text-input` (44px, 8px radius, `border-input` line, 2px maroon line on focus).
- `misc.tsx`: `Badge` (badge-pill, semantic tones always have an icon), `Notice` (tinted box with icon), `NotAvailable`, `Spinner`, `ErrorText`, `Dots` (single series in maroon), `CourseCode` (caption-uppercase, never serif).
- `card.tsx`: `Card` variants `default` (course-card), `compact`, `post` (post-card), `orb` (orb-card), `featured` (maroon featured-card), `well` (grouped controls). `interactive` adds the hover shadow. The file also has `Orb`, `Avatar`, `Stat`.
- `dialog.tsx`, `menu.tsx`, `tabs.tsx` (moved from the planner): overlay shadow, maroon focus and selection. The current tab has ink text over a 2px maroon underline.
- `icons.tsx`: local SVG icons.

`src/components/layout/`:

- `TopNav.tsx`: the top-nav. It is 64px, on canvas, with a text wordmark, links with a pale maroon pill for the current page, search and account. Below 768px, the links fold behind a "Menu" button. Search stays visible.
- `Footer.tsx`: the footer (canvas, body-sm, link columns).
- `page.tsx`: `PageContainer` (widths content / reading / form / tool), `PageHeader` (eyebrow, light-serif h1, meta, description, actions), `Section`, `Eyebrow`, `EmptyState`, `LoadingState` (skeleton plates), `inlineLinkClass` / `standaloneLinkClass` (link-inline).

All pages and features use these components:

- Home (hero-band with one orb).
- Onboarding.
- Planner: grid, course cards with data-color requirement stripes, toolbar, drawer on the right with the requirement tree, goals and plan check, Generate popup, AI advisor sheet.
- Course search and course page.
- Program explorer and program page.
- My plans, compare, sign-up, login, account, privacy, and the placeholder pages.

## Accessibility kept

- Contrast: all text pairs come from the AA table of DESIGN.md. `muted` is the smallest text color (4.6:1 on the pale maroon selection). The code uses `gray-dark` only for icons and list markers.
- 44px targets: every button, tab and menu item. `e2e/design.spec.ts` measures them on four pages. It also checks that the primary pill is drawn 40px inside a 44px box.
- Visible focus on every interactive element. "Move to…" stays the keyboard alternative to drag and drop.
- axe: planner, home and course page (WCAG 2.1 A/AA tags), and the existing checks of the auth pages. Since step 5, axe also checks the Generate and Advisor states of the planner, the forum page and the thread, at 1440 and 390px (see the step 5 section below).

## Deviations from DESIGN.md, and why

- The wordmark is "Quarterly", not "UChicago Course Forum" (DF-1).
- The planner can be 1600px wide (DF-2).
- The sign-in of the top bar is an outlined pill, not a filled pill. Thus each page has only one filled button (DF-4).
- The warning and info washes come from `color-mix`, not from new hex values (DF-6).
- There are no Rare UI components, so there is no credit link yet. The hero orb does not move (DF-8).
- There is no mobile filter drawer (DF-9).
- There is no dark mode (DF-10).
- Inter loads as the variable font. Thus its CSS family name is "Inter Variable" (with "Inter" as a fallback name).
- The dense cards of the planner use `caption` (14px) for course details. DESIGN.md has no smaller body size, and we did not invent one.
- The side padding of the footer is the page gutter (16/24/32px), not the 48px of DESIGN.md. Thus its left edge aligns with the top bar and the page above it (step 5).

## Design review at 1440 and 390 (step 5)

We opened every page at 1440×900 (desktop) and 390×844 (phone) with the MSW mocks. We compared each page with DESIGN.md on these items: spacing rhythm, type scale, color tokens, cards and borders, button variants, focus, empty/loading/error states, horizontal overflow, the phone header and tap targets.

The pictures are in `docs/screenshots/<page>-1440.png` and `<page>-390.png`:

- Command: `SCREENSHOTS=1 make screenshots`. Spec: `apps/web/e2e/screenshots.spec.ts`.
- Each picture is a full page at device scale 1, with animations off. The mouse is parked, so no hover state shows.
- Dialogs are shot at viewport size, because they are fixed to the viewport.

No page scrolls sideways at 390px. axe found no WCAG 2.1 A/AA violations on any page at either width. The table shows what we found and fixed:

| Page | Found | Fixed |
| --- | --- | --- |
| Every page (top nav) | Only `/plan`, `/courses`, `/programs` and `/instructors` lit a nav item. My plans, compare, onboarding, forum pages, threads and guidelines lit no item, or lit "Courses" for a forum thread. | Each nav item now owns its section: Plan = `/plan`, `/plans*`, `/onboarding`. Courses = `/courses*` except forum pages. Forum = `/instructors*`, `/guidelines`, forum pages and threads (`aria-current="page"` + the maroon-wash pill). Unit tests in `routes.test.tsx`. |
| Every page (footer) | At desktop, the footer content was 16px to the right of the top bar and the page content (48px padding against a 32px gutter). On the planner, the footer was 1200px wide under a 1600px top bar. | The footer uses the page gutter and the same width rule as the top bar (tool width on `/plan`). |
| Home | The hero orb (640px) overflowed the hero band. The band cut it with a visible straight edge at its bottom. | The orb is 560px and 24px higher, so its fade ends inside the band. |
| Planner `/plan` | In a quarter column (approximately 195px wide at 1440), course cards squeezed the title, program tag and issue messages between the drag handle and the "…" menu. Issues wrapped one word per line. | The card is now a header row (drag handle · code and units · actions menu, each a 44px target) over a full-width body (title, tag, workload and difficulty, issues). |
| Planner, Advisor tab | Post and summary citation chips were plain grey pills. The chips were 6px inside the edge of the message text. | Chips link to the thread (`post`), the forum page (`summary`) and the course page (`attribute`). See below. The transparent border of the chip moves chip rows out, so the pills align with the text. |
| Generate dialog | The radio and checkbox rows were hand-built (8px gap, no shared style). | All rows use `ChoiceRow` (now the same as onboarding and the program picker). The same chip alignment fix as the Advisor. |
| My plans `/plans` | Each plan card wrapped its name, meta and four buttons as one flex row. Thus on a phone, the buttons broke onto lines in a different order on each card. | Two rows: the name field with its meta line, then the actions. From 768px, the rows are side by side. |
| Course search `/courses` | On a phone, the seven filters stacked one in each row (a full screen of form before any result). | On phones, short filters are two in a row. "Code or title" and the buttons keep the full width. The bottom drawer stays DF-9. |
| Course page `/courses/:code` | When logged in, the instructor list still said "reviews need login". Instructor and "Counts toward" links were 21px-tall targets. | The note shows only when logged out. Dense links get a 44px target, and the layout does not move (`tallTargetClass`: 12px padding with a negative margin that cancels it). |
| Forum page | Section heads ("Ratings", "What students say") were Inter 18px. The section heads of all other pages are the light serif. Meta links (instructor, "Course page") and review titles were 21–26px targets. | Section heads use the standard `Section` size (Newsreader 300, `display-sm`). Meta links and post titles use `tallTargetClass`. |
| Forum composer and Report dialog | "Would you recommend it?" and the report reasons were hand-built radio rows. | Both use `ChoiceRow`. |
| Account, login, sign-up | The empty live regions for errors and notices took a slot in the flex column of the form. Thus an extra 20–40px gap was above buttons and at the top of the login card. | Empty live regions are `empty:absolute`. They stay in the page, so screen readers announce later messages, but they are out of the flow. |
| Moderation queue | The "Community guidelines" meta link was a 21px target. | `tallTargetClass`. |
| About and the curator console placeholder | The page told students "Placeholder for `/about`. Built in prompt 03." | A plain "Coming soon. This page is not written yet." with a link home. The About text itself is DF-12. |
| Onboarding, program picker | Hand-built radio and checkbox rows. | `ChoiceRow`. |
| Thread, programs, program, instructors, instructor, guidelines, privacy, sign-up, 404 | Checked at both widths. Nothing to fix. | — |

**Advisor citation chips.**

- A citation gives only a kind and an id (`post:3`, `summary:1`, `attribute:CMSC 14300:workload_hours`).
- Course, program and attribute chips make their URL from the id.
- A `post` chip asks `GET /forum/posts/{id}` for its `page_id`. Then it asks `GET /forum/pages/{page_id}` for the course code and the instructor slug. It links to `/courses/:code/i/:instructor/t/:id`.
- A `summary` chip asks only for the page.
- Forum reads need a login. Thus for a logged-out student, a removed post or a failed request, the chip stays a plain pill. It has the same shape, no underline, and nothing to click.
- Unit tests are in `AdvisorPanel.test.tsx`. The mock advisor now cites one post and one summary.

**How we applied DESIGN.md in this pass.**
- Tokens: no new color, font size, radius or shadow. Every fix uses existing utilities. The only new shared class is `tallTargetClass` (`components/layout/page.tsx`), made from the 4px spacing scale.
- Type scale: page sections use `Section` (Newsreader 300 `display-sm`). Dense UI stays Inter `caption`/`body-sm`. Course codes stay tabular Inter.
- Components: `ChoiceRow` replaces every simple hand-built checkbox or radio row. (The bordered "delete my posts" options of the account page keep their own card layout.) `Section`, the `Button` variants and `Card` did not change.
- Phone width:
  - The top bar keeps search on its own row and folds links behind "Menu" (`nav-menu-390.png`).
  - Grids change to one column.
  - Forms keep 44px controls.
  - Dense links get 44px targets.
  - On a phone, the planner shows the requirements, then the grid, then the Issues/Goals/Advisor panel, in one column (DF-13).

**Evidence.**
- `e2e/design.spec.ts` runs axe (WCAG 2.1 A/AA) at 1440 and 390 on these states, and fails on any serious or critical violation:
  - The planner with courses.
  - The Generate dialog (options and results).
  - The Advisor with an answer and resolved forum citation links.
  - The forum page (with the review form open).
  - The thread (with the report dialog open).
- `e2e/shell.spec.ts` checks 17 pages for sideways scrolling at phone width.

## FEEDBACK UI (2026-11-14)

This section covers Richard's FEEDBACK items F2 to F6 (`docs/FEEDBACK.md`). Where they conflict with DESIGN.md and the SPEC, the FEEDBACK items win.

**Layout (F4).** The planner is now a header, a toolbar and the grid. The old three-column layout (requirement rail, grid, Issues/Goals/Advisor tabs) and the phone "Jump to" links are gone.
- Header: the plan name, with the line "Not official advising. Confirm with your adviser and My Planner." under it. Then the catalog year and the program pills.
- Toolbar, in this order:
  1. Requirements, Goals, Check plan. These are outline pills that open the drawer at that tab. The open pill gets the maroon-wash selected state and `aria-expanded`.
  2. AI advisor.
  3. Save.
  4. Generate plan, the one primary pill.
- Drawer (`features/planner/PlanDrawer.tsx`): tabs Requirements, Goals and Issues.
  - At 1024px and wider, it is a sticky 380px column (400px from 1280px) beside the grid, with the overlay shadow. It is not modal. Thus the grid stays usable, and the student can drag courses from the tree onto the grid.
  - Below 1024px, it covers the screen as a modal dialog. Focus is trapped. Escape and "Close panel" close it. Focus goes back to the toolbar.
  - It stays mounted while it is closed. Thus open tree nodes and goal fields keep their state.
- Requirement tree (`RequirementTree.tsx`):
  - The program heading comes first.
  - Then its rule nodes, as disclosure buttons: label, the rule in caption text, and progress as a small "2 of 3" with a check when met.
  - Then the courses: grip handle, the course code in bold (Inter 600) over the name in caption, a check if the course is on the plan, and Add.
  - Group nodes start open. Course lists load when a node opens.
  - A hairline left border shows the nesting.
- Errors stay subtle. There is no banner and there are no red counts on the page.
  - "Check plan" has a small error-wash count pill. Screen readers hear "Check plan (3 errors)".
  - The Issues tab of the drawer shows the verifier badge and the list.
  - Course cards do not turn their border red now. Issue lines keep a colored icon with body-colored text.
- AI advisor (`AdvisorSheet` in `features/advisor/AdvisorPanel.tsx`, `components/ui/sheet.tsx`):
  - It is a modal sheet that slides down from the top. On desktop, it is a maximum of 768px wide and 88vh tall. On a phone, it is full screen.
  - Header: spark avatar, "AI advisor", a neutral "Generative AI" badge and "Answers are written by an AI and can be wrong. Not official advising."
  - The messages look like a chat. The bubbles of the student are on the right, in maroon wash. The bubbles of the AI are on the left, in white cards beside a spark avatar. Proposal cards are in the AI column.
  - While the answer streams, a three-dot typing indicator shows.
  - The composer is pinned to the bottom. Enter sends. Shift+Enter makes a new line. Focus starts there.
  - All other behavior did not change: SSE streaming, citation chips with links, Apply, typed confirmations, history for saved plans, logged-out behavior.
  - The sheet stays mounted when it is closed. Thus the conversation stays.
- Drag and drop:
  - A `DragOverlay` follows the pointer. The source card stays as a 40% placeholder.
  - A drop goes to the quarter under the pointer (`pointerWithin`). For keyboard drags, the fallback is overlap.
  - "Move to…" and "Add" stay the keyboard path.

**Years (F2, F3).**
- `features/planner/terms.ts` mirrors `planner_core.terms`: an academic year has the order SU, AU, WI, SP.
- Each year in the grid has a heading with two parts:
  - Its class year relative to entry ("Second year" for a second-year transfer).
  - The academic year ("2100–01").
- Summer comes first. It stays hidden until the student clicks "Show Summer".
- The grid ends at the graduation quarter of the plan (`graduation_term`). Its default is the Spring of the last year left. These controls set it:
  - "Graduating in" (Autumn, Winter or Spring, up to one year after the current last year).
  - "Add a year".
  - "Remove last year". While that year has courses, the planner refuses and shows a short message.
- The planner lists items outside the grid under "Other terms".
- Local plans saved with the old `years: 5` open with Spring of year 5.

**Motion (F6).** The motion uses CSS keyframes in `index.css` and a 30-line helper, `lib/motion.ts`. The helper has `usePresence` (it keeps an element visible for its exit animation) and `useMediaQuery`. There is no animation library.

| Moment | Animation | Duration, easing |
| --- | --- | --- |
| Button press | The pill scales to 97%. | 150ms |
| Dialog open | The backdrop fades. The panel fades, rises 8px and scales from 98%. | 200ms ease-out |
| Drawer open / close | Slides 24px from the right with a fade. | 250ms ease-out in, 200ms ease-in out |
| AI advisor open / close | Slides 24px down from the top with a fade. The backdrop fades. | 250ms in, 200ms out |
| Course card placed | Settles from 97% to 101% to 100%. | 250ms ease-out |
| New list items (chat messages, issues, goals, tree courses, variants) | Rise 6px and fade in. Issues stagger by 30ms. | 200ms ease-out |
| Quarter under a dragged card | Maroon-wash fill, maroon line and hover shadow. | 200ms |
| AI typing | Three dots pulse in turn. | 1.2s loop |

Motion rules:

- Entrances ease out. Exits ease in and are shorter.
- Nothing moves more than 24px.
- Each keyframe ends at `transform: none`. Thus no containing block stays behind for the fixed drag overlay.
- Reading surfaces (messages, post text) do not move after they show.
- With `prefers-reduced-motion: reduce`, no animation runs (`animation: none`). Transitions are instant. A close does not wait for the exit delay (`e2e/feedback-ui.spec.ts`, "with reduced motion, nothing animates").

**Text (F5).**

We removed these texts:

- The Generate dialog: "A form, not a prompt: every choice maps to a typed setting."
- The quarter picker: "Choose a quarter."
- The advisor: "Planning questions will work once the chat service is built."
- The course search description.
- The program explorer description.
- The first sentence of the instructors description.
- The encouragement of the forum in the empty states under "No reviews yet" and "No discussion yet".
- The footer tagline (now the not-affiliated line).

We shortened these texts:

- The "No summary yet" body of the forum.
- The "Other terms" note.
- "Plan four years of courses" in the home hero (the number of years is not fixed at four now).

Legal, privacy, error and instruction text did not change.

**Evidence.**
- `e2e/feedback-ui.spec.ts` (one test group for each item) and `e2e/planner.spec.ts`.
- axe in `e2e/design.spec.ts`, with the drawer and the advisor open, at 1440 and 390.
- Screenshots: `docs/screenshots/plan-*.png`, and the new `plan-drawer-*`, `plan-check-*`, `plan-years-*`. `plan-advisor-*` now shows the sheet.

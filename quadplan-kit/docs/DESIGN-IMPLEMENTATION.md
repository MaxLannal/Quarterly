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
| Motion | 150ms default transitions; `prefers-reduced-motion` turns transitions and animations off | |

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

Every page and feature uses these: home (hero-band with one orb), onboarding, planner (grid, course cards with data-color requirement stripes, requirement rail, right-rail tabs, verifier badge, Generate popup, advisor), course search and course page, program explorer and program page, my plans, compare, sign-up, login, account, privacy, and the placeholder pages.

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

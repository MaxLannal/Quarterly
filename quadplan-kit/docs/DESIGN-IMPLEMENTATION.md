# Design implementation

How each part of `docs/DESIGN.md` maps to code in `apps/web`. DESIGN.md decides the look; `docs/SPEC.md` decides behavior and content. Conflicts between them are questions DF-1 to DF-11 in `docs/OPEN_QUESTIONS.md` ("Design foundation").

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
- axe: planner, home and course page (WCAG 2.1 A/AA tags), plus the auth pages' existing checks.

## Deviations from DESIGN.md, and why

- Wordmark reads "Quarterly", not "UChicago Course Forum" (DF-1).
- The planner may be 1600px wide (DF-2).
- The top bar's sign-in is an outlined pill, not a filled one, to keep one filled button per page (DF-4).
- Warning and info washes are derived with `color-mix`, not new hex values (DF-6).
- No Rare UI components, so no credit link yet; the hero orb is still (DF-8). No mobile filter drawer (DF-9). No dark mode (DF-10).
- Inter is loaded as the variable font, so its CSS family name is "Inter Variable" (with "Inter" as a fallback name).
- The planner's dense cards use `caption` (14px) for course details; DESIGN.md has no smaller body size and none is invented.

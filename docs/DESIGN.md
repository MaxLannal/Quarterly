---
version: alpha
name: uchicago-course-forum
description: Design system for the UChicago Course Forum. Structure, typography, spacing, shape, elevation and component geometry come from the ElevenLabs DESIGN.md (quiet, editorial, print-magazine feel). Every color comes from the University of Chicago Identity Guidelines (Feb 2020) — Maroon as the single accent, the university grays as neutrals, and the warm, nature-based secondary hues for atmosphere and data only. Interaction ideas come from Rare UI (rareui.com), restyled to these tokens.

colors:
  # Brand & action (UChicago primary palette)
  primary: "#800000"            # UChicago Maroon, PMS 202 — the ONLY action color
  primary-hover: "#6C0000"      # derived: maroon, 16% darker
  primary-active: "#5A0000"     # derived: maroon, 30% darker
  primary-wash: "#F5EBEB"       # derived: maroon at 8% on white — selected/active backgrounds
  on-primary: "#FFFFFF"

  # Text (UChicago black + Dark Gray family)
  ink: "#111111"                # UChicago black (guide gives no value; softened from #000)
  body-strong: "#262626"        # derived from black — emphasis
  body: "#4D4D4D"               # derived: Dark Gray #767676 shaded toward black — running text
  muted: "#6B6B6B"              # derived: Dark Gray shaded — meta text; passes AA on every surface
  muted-soft: "#ADADAD"         # derived: Dark Gray tint — disabled text only

  # Surfaces (white + UChicago Light Gray family)
  canvas: "#F7F7F5"             # derived: Light Gray #D6D6CE at 20% on white — page floor
  canvas-soft: "#FBFBFA"        # derived: Light Gray at 10% — alternating bands
  surface-card: "#FFFFFF"
  surface-strong: "#F1F1EE"     # derived: Light Gray at 35% — badges, avatar plates
  surface-dark: "#111111"       # ink — rare dark band
  surface-dark-elevated: "#1F1F1F"
  surface-inverse: "#800000"    # maroon inversion — at most one featured element per page
  on-dark: "#FFFFFF"
  on-dark-soft: "#ADADAD"
  on-inverse-soft: "#F0E0E0"    # derived: maroon at 12% on white — secondary text on maroon

  # Lines
  hairline: "#E8E8E4"           # derived: Light Gray at 55%
  hairline-soft: "#F1F1EE"
  hairline-strong: "#D6D6CE"    # UChicago Light Gray, Cool Gray 3
  border-input: "#8A8A8A"       # derived: Dark Gray family — 3.45:1 on white (meets non-text 3:1)
  gray-dark: "#767676"          # UChicago Dark Gray, Warm Gray 11 — icons, dividers, never small text on canvas

  # Atmospheric orbs (UChicago secondary palette — used ONLY as soft radial blooms)
  orb-lake: "#5B8FA8"           # PMS 549
  orb-goldenrod: "#FFB547"      # PMS 7405
  orb-ivy: "#ADB17D"            # PMS 5845
  orb-terracotta: "#D49464"     # PMS 7412
  orb-rose: "#B1746F"           # PMS 7523

  # Semantic (UChicago secondary palette)
  semantic-error: "#8F3931"     # Red, PMS 174
  semantic-error-wash: "#F6EFEF"
  semantic-success: "#616530"   # PMS 574
  semantic-success-wash: "#F2F3EE"
  semantic-warning: "#9A5324"   # PMS 1675 — warning text
  semantic-warning-icon: "#C68220"  # Yellow, PMS 153 — icons only (3.2:1)
  semantic-warning-wash: "#F7F1ED"  # derived: warning at 8% on white (added 2026-11-14, DF-6)
  semantic-info: "#155F83"      # Blue, PMS 633
  semantic-info-wash: "#ECF2F5"     # derived: info at 8% on white (added 2026-11-14, DF-6)

  # Data visualization (UChicago secondary palette, in this order)
  data-1: "#155F83"             # Blue
  data-2: "#FFA319"             # Yellow
  data-3: "#8A9045"             # Light Green
  data-4: "#C16622"             # Orange
  data-5: "#725663"             # PMS 5205
  data-6: "#58593F"             # Dark Green

typography:
  display-mega:
    fontFamily: "'Newsreader', 'Times New Roman', serif"
    fontSize: 64px
    fontWeight: 300
    lineHeight: 1.05
    letterSpacing: -1.92px
  display-xl:
    fontFamily: "'Newsreader', serif"
    fontSize: 48px
    fontWeight: 300
    lineHeight: 1.08
    letterSpacing: -0.96px
  display-lg:
    fontFamily: "'Newsreader', serif"
    fontSize: 36px
    fontWeight: 300
    lineHeight: 1.17
    letterSpacing: -0.36px
  display-md:
    fontFamily: "'Newsreader', serif"
    fontSize: 32px
    fontWeight: 300
    lineHeight: 1.13
    letterSpacing: -0.32px
  display-sm:
    fontFamily: "'Newsreader', serif"
    fontSize: 24px
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: 0
  title-md:
    fontFamily: "'Inter', sans-serif"
    fontSize: 20px
    fontWeight: 500
    lineHeight: 1.35
    letterSpacing: 0
  title-sm:
    fontFamily: "'Inter', sans-serif"
    fontSize: 18px
    fontWeight: 500
    lineHeight: 1.44
    letterSpacing: 0.18px
  body-md:
    fontFamily: "'Inter', sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0.16px
  body-strong:
    fontFamily: "'Inter', sans-serif"
    fontSize: 16px
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: 0.16px
  body-sm:
    fontFamily: "'Inter', sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.47
    letterSpacing: 0.15px
  caption:
    fontFamily: "'Inter', sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  caption-uppercase:
    fontFamily: "'Inter', sans-serif"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.96px
    textTransform: uppercase
  button:
    fontFamily: "'Inter', sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
  nav-link:
    fontFamily: "'Inter', sans-serif"
    fontSize: 15px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  # Tightened 2026-11-16 (FEEDBACK "A more compact interface": round less on corners);
  # buttons and chips keep the pill.
  none: 0px
  xs: 4px
  sm: 4px
  md: 6px
  lg: 8px
  xl: 10px
  xxl: 14px
  pill: 9999px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  base: 16px
  md: 20px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 96px

components:
  top-nav:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.nav-link}"
    height: 64px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 10px 20px
    height: 40px
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.pill}"
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.pill}"
  button-outline:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 9px 19px
    height: 40px
  button-tertiary-text:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.button}"
  button-destructive:
    backgroundColor: transparent
    textColor: "{colors.semantic-error}"
    typography: "{typography.button}"
    rounded: "{rounded.pill}"
    padding: 9px 19px
    height: 40px
  link-inline:
    backgroundColor: transparent
    textColor: "{colors.primary}"
    typography: "{typography.body-md}"
  hero-band:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.display-mega}"
    padding: 96px
  orb-card:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xxl}"
    padding: 32px
  course-card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.title-md}"
    rounded: "{rounded.xl}"
    padding: 24px
  post-card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.body}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xl}"
    padding: 32px
  thread-row:
    backgroundColor: transparent
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    padding: 12px 0
  thread-row-selected:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
  avatar:
    backgroundColor: "{colors.surface-strong}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    size: 32px
  featured-card:
    backgroundColor: "{colors.surface-inverse}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.xl}"
    padding: 32px
  text-input:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: 12px 16px
    height: 44px
  badge-pill:
    backgroundColor: "{colors.surface-strong}"
    textColor: "{colors.ink}"
    typography: "{typography.caption-uppercase}"
    rounded: "{rounded.pill}"
    padding: 4px 10px
  cta-band:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.display-lg}"
    padding: 96px
  footer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    padding: 64px 48px
  footer-link:
    backgroundColor: transparent
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
---

## Overview

The UChicago Course Forum should read like a **quiet, editorial print magazine** that happens to be a course forum. This file merges three sources, each with a fixed job:

| Source | Governs | Does NOT govern |
|---|---|---|
| ElevenLabs DESIGN.md | Typography, spacing, layout, radii, elevation, component geometry, overall restraint | Any color value |
| UChicago Identity Guidelines (2020) | Every color: accent, neutrals, atmosphere, semantic, data | Fonts (do **not** switch to Gotham/Garamond from that guide) |
| Rare UI (rareui.com) | Interaction ideas and animated components | Colors, fonts, radii — restyle every component to the tokens here |

When the sources pull in different directions, the priority is: **accessibility → this file → Rare UI defaults.**

**Key characteristics**
- Off-white canvas (`{colors.canvas}`), near-black ink, white cards with 1px hairlines.
- **Maroon is the single accent** and takes the role ElevenLabs gives its ink pill: primary CTAs, inline links, the active nav/selection state, focus rings. Used scarcely, so it carries weight.
- Display type is a **light serif at weight 300** — never bold. Body is Inter 400/500 with slightly loose tracking.
- Pill geometry for every button and badge; 16px radius for cards; 96px between page sections.
- Color "voltage" comes from soft atmospheric orbs in UChicago's warm, nature-based secondary hues (lake blue, goldenrod, ivy, terracotta, rose), never from saturated fills.

## Colors

All values trace back to the UChicago Identity Guidelines. Values marked **derived** in the YAML are tints or shades mixed from a guideline color (the guide groups its palette as Core Hues, Shades, and Tints); nothing comes from outside the palette.

### Brand & action
- **Maroon** (`{colors.primary}` — #800000, PMS 202): the university's signature color. Primary buttons, inline links, active nav indicator, focus ring, selected state. One primary button per view.
- **Maroon hover / active** (`{colors.primary-hover}` #6C0000, `{colors.primary-active}` #5A0000).
- **Maroon wash** (`{colors.primary-wash}` #F5EBEB): background for the selected thread row, active sidebar item, current tab.

### Neutrals
- **Ink** (`{colors.ink}` #111111): headings, primary text. The guide lists black without a value; this is softened slightly.
- **Body** (`{colors.body}` #4D4D4D): running text in posts and reviews.
- **Muted** (`{colors.muted}` #6B6B6B): timestamps, counts, course codes, metadata.
- **Dark Gray** (`{colors.gray-dark}` #767676, Warm Gray 11): icons and dividers. It fails AA for small text on the canvas (4.23:1), so do not use it for text — use `{colors.muted}`.
- **Light Gray** (`{colors.hairline-strong}` #D6D6CE, Cool Gray 3) and its tints form the canvas, hairlines and badge plates.

### Atmospheric orbs
`orb-lake`, `orb-goldenrod`, `orb-ivy`, `orb-terracotta`, `orb-rose` replace ElevenLabs' pastel orbs. They are mid-tones, so render them as **soft radial gradients at 35–45% opacity at the center, fading to transparent**, blurred 60–80px. That yields the same pastel, atmospheric feel. Never use them as button fills, text colors or card backgrounds. One orb color per section.

### Semantic
| Role | Text/icon | Wash background |
|---|---|---|
| Error | `{colors.semantic-error}` #8F3931 | `{colors.semantic-error-wash}` |
| Success | `{colors.semantic-success}` #616530 | `{colors.semantic-success-wash}` |
| Warning | `{colors.semantic-warning}` #9A5324 (icon #C68220) | `{colors.semantic-warning-wash}` |
| Info | `{colors.semantic-info}` #155F83 | `{colors.semantic-info-wash}` |

Error red and maroon are close (1.46:1 between them). Always pair errors with an icon and a message; never fill a button with the error color.

### Data visualization
For ratings, workload and grade distributions: single series = maroon; multiple categories = `data-1` … `data-6` in order; sequential scales = `{colors.primary-wash}` → `{colors.primary}`.

### Contrast (WCAG AA verified)
| Foreground | on card #FFF | on canvas | on surface-strong |
|---|---|---|---|
| ink | 18.9 | 17.6 | 16.7 |
| body | 8.5 | 7.9 | 7.5 |
| muted | 5.3 | 5.0 | 4.7 |
| maroon | 11.0 | 10.2 | 9.7 |
| white on maroon | 11.0 | — | — |

### Color don'ts
- Don't use the guide's violator colors (cyan #47B5FF, magenta #FF3399).
- Don't introduce any hex not in this file. If something new is needed, derive a tint/shade from an existing token and add it here.
- Don't use more than one saturated element per view besides the primary button.

## Typography

### Font families
- **Display: Newsreader, weight 300.** ElevenLabs uses Waldenburg Light, which is licensed. Newsreader (free, Google Fonts / `@fontsource/newsreader`) has a true 300 weight and the same contemporary editorial feel. (EB Garamond, the substitute the ElevenLabs file suggests, has no 300 weight.)
- **Body/UI: Inter** (`@fontsource-variable/inter`), the same family ElevenLabs uses.
- Do not use the UChicago guide's fonts (Gotham, Adobe Garamond, Fette Fraktur). Typography follows ElevenLabs by design.

### Hierarchy
| Token | Size | Weight | Line height | Tracking | Forum use |
|---|---|---|---|---|---|
| `display-mega` | 64px | 300 | 1.05 | -1.92px | Home hero |
| `display-xl` | 48px | 300 | 1.08 | -0.96px | Course page title |
| `display-lg` | 36px | 300 | 1.17 | -0.36px | Section heads |
| `display-md` | 32px | 300 | 1.13 | -0.32px | Sub-section heads |
| `display-sm` | 24px | 300 | 1.2 | 0 | Card group titles, thread title on its own page |
| `title-md` | 20px | 500 | 1.35 | 0 | Course card title |
| `title-sm` | 18px | 500 | 1.44 | 0.18px | Thread titles in lists |
| `body-md` | 16px | 400 | 1.5 | 0.16px | Post and review text |
| `body-strong` | 16px | 500 | 1.5 | 0.16px | Emphasis, usernames |
| `body-sm` | 15px | 400 | 1.47 | 0.15px | Footer, secondary text |
| `caption` | 14px | 400 | 1.5 | 0 | Timestamps, reply counts |
| `caption-uppercase` | 12px | 600 | 1.4 | 0.96px | Section labels, badges (e.g. CMSC, QUARTER) |
| `button` | 15px | 500 | 1.0 | 0 | Buttons |
| `nav-link` | 15px | 500 | 1.4 | 0 | Top nav |

### Principles
- **Display stays at weight 300.** Never bold a display headline.
- Negative tracking on display sizes; slightly positive tracking (+0.15–0.18px) on Inter body.
- Body never drops below 400.
- Course codes (e.g. "CMSC 14300") use `caption-uppercase` or tabular Inter; never the serif.

## Layout

### Spacing
Base unit 4px. Tokens: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 96. Section padding 96px.

### Grid & container
- Max content width ~1200px on a 12-column grid.
- **Reading column for posts and reviews: max 720px** (~70 characters), so long discussions stay comfortable to read.
- Card grids: 3-up for course browsing, 2-up for splits; 16–24px gaps.
- Footer: up to 5 columns at desktop.

### Whitespace
Generous, editorial pacing between bands (96px); tight inside them (16–24px between cards). Lists of threads are dense and hairline-divided; pages around them are airy.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | `{colors.canvas}` | Page bands, footer |
| Card | `{colors.surface-card}` + 1px `{colors.hairline}` | Course cards, post cards |
| Hover | `0 4px 16px rgba(0, 0, 0, 0.04)` | Hovered cards — the only shadow tier |
| Overlay | `0 8px 32px rgba(0, 0, 0, 0.08)` | Menus, drawers, toasts (added; ElevenLabs has none) |
| Orb | Radial gradient of one `orb-*` token | Atmosphere only, never a surface |

## Shapes

| Token | Value | Use |
|---|---|---|
| `xs` | 4px | Inline tags |
| `sm` | 6px | Compact rows, selected thread row |
| `md` | 8px | Inputs |
| `lg` | 12px | Compact cards, menus |
| `xl` | 16px | Course cards, post cards |
| `xxl` | 24px | Orb cards |
| `pill` | 9999px | All buttons, badges, chips |
| `full` | 9999px | Avatars |

## Components

### Navigation
**`top-nav`**: canvas background, 64px tall. Text wordmark left, primary links center/left (e.g. Courses / Departments / Discussions), search + sign-in + primary pill right. The active link gets a 2px maroon underline or a `primary-wash` pill, not a color change alone.

### Buttons
- **`button-primary`**: maroon pill, white text, 40px tall, 10×20px padding. Hover `primary-hover`, press `primary-active`. One per view (e.g. "Write a review", "Post").
- **`button-outline`**: transparent pill, 1px `{colors.hairline-strong}` border, ink text.
- **`button-tertiary-text`**: ink text, no chrome.
- **`button-destructive`**: outline pill with error-colored text; confirm in place (see Rare UI Delete Button), no modal.
- **Focus (all interactive elements)**: 2px `{colors.primary}` ring, 2px offset.

### Hero & atmosphere
- **`hero-band`**: canvas background, `display-mega` headline, `body-md` subhead, search input and/or one primary pill, one orb blooming behind the headline.
- **`orb-card`**: canvas-soft, 24px radius, 32px padding, one orb color per card.

### Content
- **`course-card`**: white, 16px radius, 24px padding, 1px hairline. Course code (`caption-uppercase`, muted) → title (`title-md`) → one line of meta (`caption`, muted). Hover = single soft drop.
- **`post-card`**: white, 16px radius, 32px padding. Avatar + name (`body-strong`) + timestamp (`caption`, muted) header; body in `body-md`/`{colors.body}` within the 720px reading column.
- **`thread-row`**: transparent row, 12px vertical padding, 1px hairline divider. 32px avatar left, title (`title-sm`) + meta stack, reply count right. Selected = `thread-row-selected`.
- **`avatar`**: 32px circle on `surface-strong` with initials; padded row gives a 48px tap zone.
- **`featured-card`**: the maroon inversion (like ElevenLabs' dark featured pricing tier). White text, `on-inverse-soft` for secondary text. At most one per page.
- **`link-inline`**: maroon text, underlined, in post bodies.

### Forms & tags
- **`text-input`**: white, 8px radius, 44px tall, 12×16px padding, 1px `{colors.border-input}` border; on focus the border becomes 2px maroon. Errors: error-colored border + icon + message below.
- **`badge-pill`**: `surface-strong` plate, `caption-uppercase`, pill. Department and quarter tags use this neutral badge, not colored chips.

### CTA & footer
- **`cta-band`**: canvas, centered `display-lg` line, one primary pill, optional orb. 96px padding.
- **`footer`**: canvas, `body-sm` in `{colors.body}`, link columns, 64×48px padding. Includes the Rare UI credit if any Rare UI component ships (see below).

## Motion

ElevenLabs leaves motion undocumented; these rules fill the gap.
- Durations: 150ms (hover/press), 200–250ms (menus, drawers), 400ms max (page-level reveals).
- Easing: ease-out for entrances; gentle springs (Motion `type: "spring", bounce ≤ 0.2`) for indicators and counters.
- **One signature animated moment per screen.** Reading surfaces (post bodies, review text) stay still.
- Respect `prefers-reduced-motion`: replace springs/drifts with instant or opacity-only transitions; orbs stop drifting.

## Rare UI components

Rare UI components are single-file React components built with Tailwind CSS and Motion, installed with the shadcn CLI, e.g. `npx shadcn@latest add swamimalode07/rare-ui/<name>`. If the project is not React + Tailwind, treat them as interaction references and rebuild the behavior natively.

**Rules**
1. After installing, **restyle every component to the tokens in this file**: replace its colors, fonts, radii and shadows. No Rare UI default color should survive.
2. Keep each component's copyright notice in the source file.
3. **License:** shipping any Rare UI component requires a visible link to https://rareui.com (footer, about page or README). Components may not be resold or redistributed on their own.
4. Motion rules above still apply, including reduced motion.

**Where they fit in the forum**
| Forum need | Rare UI component | Notes |
|---|---|---|
| Hero atmosphere | `fluid-orb` | Use as the hero orb with an `orb-*` color; hero only (WebGL). |
| Long course pages (overview, reviews, discussion) | `rail-toc` or `scroll-progress` | Pick one per page type. |
| Department / filter sidebar | `hook-sidebar` or `bounce-sidebar` | Active indicator in maroon. |
| Vote / like / view counts | `animated-counter` | Inter, tabular numbers. |
| Reacting to posts | `emoji-reaction` | Uses Apple emoji artwork via `react-apple-emojis`; swap for native emoji if that's a concern. |
| Reply notifications | `notification-bell` | Badge in maroon. |
| Post success / errors | `toast` | Overlay shadow tier; semantic colors. |
| Deleting own post | `delete-button` | In-place confirm; error-colored text. |
| Code in CS course posts | `code-block` | Pass `#800000` as its accent. |
| Mobile filters / composer | `family-drawer` | Bottom sheet on mobile only. |
| Email-code sign-in (if used) | `otp-input` | — |
| Forum FAQ / About | `faq` | Message-thread style fits a forum. |

Skip purely decorative pieces (`gravity-letters`, `matrix-orb`, `grid-reveal`, `folder-component`) unless there's a clear reason.

## Brand & logo

- Do **not** use the official University shield, wordmark, phoenix or Gothic "UChicago" mark unless the project has university approval. The guidelines restrict how those marks are used.
- Use a **text wordmark**: "UChicago Course Forum" in Newsreader 300 (or Inter 500 at small sizes), ink or maroon.

## Do's and Don'ts

### Do
- Use maroon for exactly one primary action per view, plus links, focus and selection.
- Use Newsreader 300 for every display headline; Inter 400/500 for everything else.
- Keep cards white on the off-white canvas with 1px hairlines; use one shadow tier on hover.
- Use pills for every button and badge, and 16px radii for cards.
- Keep post and review text in a 720px reading column.
- Reference tokens (`{colors.*}`, CSS variables), never inline hex.

### Don't
- Don't add a second accent color or use secondary hues as fills for buttons, cards or text.
- Don't bold display headlines.
- Don't use `{colors.gray-dark}` (#767676) for small text on the canvas.
- Don't use sharp corners on buttons.
- Don't stack multiple animated components in the same view.
- Don't import UChicago's fonts or official marks.

## Responsive Behavior

| Name | Width | Key changes |
|---|---|---|
| Mobile | < 640px | Hero h1 64→32px; course cards 1-up; nav → hamburger; orbs shrink; filters move to a bottom drawer. |
| Tablet | 640–1024px | Hero h1 48px; cards 2-up; sidebar collapses. |
| Desktop | 1024–1280px | Hero h1 64px; cards 3-up; sidebar visible. |
| Wide | > 1280px | Content caps at 1200px. |

- Top nav switches to hamburger below 768px.
- Primary pill stays 40px tall; padded rows give ≥48px tap targets.
- Orbs reduce in size at each breakpoint but never disappear.

## Implementation tokens

```css
:root {
  /* color */
  --color-primary: #800000;
  --color-primary-hover: #6C0000;
  --color-primary-active: #5A0000;
  --color-primary-wash: #F5EBEB;
  --color-on-primary: #FFFFFF;
  --color-ink: #111111;
  --color-body-strong: #262626;
  --color-body: #4D4D4D;
  --color-muted: #6B6B6B;
  --color-muted-soft: #ADADAD;
  --color-canvas: #F7F7F5;
  --color-canvas-soft: #FBFBFA;
  --color-surface-card: #FFFFFF;
  --color-surface-strong: #F1F1EE;
  --color-surface-dark: #111111;
  --color-surface-dark-elevated: #1F1F1F;
  --color-surface-inverse: #800000;
  --color-on-inverse-soft: #F0E0E0;
  --color-hairline: #E8E8E4;
  --color-hairline-soft: #F1F1EE;
  --color-hairline-strong: #D6D6CE;
  --color-border-input: #8A8A8A;
  --color-gray-dark: #767676;
  --color-orb-lake: #5B8FA8;
  --color-orb-goldenrod: #FFB547;
  --color-orb-ivy: #ADB17D;
  --color-orb-terracotta: #D49464;
  --color-orb-rose: #B1746F;
  --color-error: #8F3931;
  --color-error-wash: #F6EFEF;
  --color-success: #616530;
  --color-success-wash: #F2F3EE;
  --color-warning: #9A5324;
  --color-warning-icon: #C68220;
  --color-info: #155F83;
  --color-data-1: #155F83;
  --color-data-2: #FFA319;
  --color-data-3: #8A9045;
  --color-data-4: #C16622;
  --color-data-5: #725663;
  --color-data-6: #58593F;

  /* type */
  --font-display: "Newsreader", "Times New Roman", serif;
  --font-sans: "Inter", system-ui, sans-serif;

  /* radius */
  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-xxl: 24px;
  --radius-pill: 9999px;

  /* elevation */
  --shadow-hover: 0 4px 16px rgba(0, 0, 0, 0.04);
  --shadow-overlay: 0 8px 32px rgba(0, 0, 0, 0.08);

  /* layout */
  --container-max: 1200px;
  --reading-max: 720px;
  --section-pad: 96px;
}
```

If the project uses Tailwind v4, mirror these in an `@theme` block so utilities like `bg-primary` and `rounded-xl` resolve to these values.

## Known gaps

- Dark mode is not defined. Don't invent one; ask first.
- ElevenLabs' letter-spacing was tuned for Waldenburg. If Newsreader looks cramped at 64px, loosen display tracking by up to 0.5px; change nothing else.
- Form validation beyond focus/error, empty states and loading skeletons are not specified. Build them from existing tokens (hairlines, muted text, surface-strong plates).
## Changes approved in FEEDBACK (2026-11-16, design pass)

Richard's FEEDBACK "Minor design changes" overrides the rules above in these places only:

- **Wordmark weight.** The home page's "Quarterly" headline is 96px Newsreader **400** (`text-display-hero`, 64px on a phone), and the top bar's and footer's wordmark is Newsreader **500**. Every other display heading stays at 300.
- **Hero orb.** The home hero's orb is `orb-maroon` (#A44A4A, derived: maroon at 70% on the canvas), so the page's one atmospheric colour matches the accent. Other orbs keep the secondary hues.
- **Catalog switch.** Courses/Programs is a small segmented control: `surface-strong` track, the current side on a white pill with maroon text; the pill slides 200ms ease-out between sides (still under reduced motion).
- **Top-bar search.** A filled `surface-strong` field without an outline until it is hovered or focused; the icon and placeholder identify it.
- **Footer links.** 32px rows with a mouse; 44px targets on touch screens.

## Maroon and night (Max, 2026-11-20; branch `feature/best-of-uchicago`)

Requested with a reference login card ("Have words bigger and background colors maroon and black
combined. Take inspiration from this and apply to every page and every detail"). Not yet confirmed by
Richard: where it conflicts with the sections above, this section describes what is built now.

- **The night.** Every page sits on a fixed maroon-and-black background (`body`, `index.css`): deep
  maroon `#5c0a1d` to near black `#12040a`, with crimson light. The top bar and the footer live on it
  in white (`on-night`, `on-night-soft`, `on-night-muted`); the wordmark stays Newsreader, white.
- **The sheet.** Page content is one white sheet with large rounded corners (`rounded-sheet`, 44px;
  28px on phones) and a deep shadow, like the reference's card. Notices that belong to a page sit
  inside it.
- **Bigger words.** Body 17px, small 16px, captions 15px, buttons and nav 16px. Headlines are bold
  Inter (650-800, tight tracking, like "Welcome home"); their `<em>` words are Newsreader italic in
  maroon ("within your reach.", "Ask *anything*"). Voices and quotes (the guide, student quotes, the
  ticker, book covers) keep the serif.
- **Pills.** Buttons are 46px pills in a 52px box, semibold; `light` and `night` variants for the
  dark background. Inputs and selects are 52px pills (26px radius) with a soft maroon halo on focus;
  email fields carry an envelope, password fields an eye that shows or hides the characters.
- **Radii.** Cards 18-24px, panels 32px, art panels 36px (`rounded-art`).
- **Art panels.** `GradientArt` (generated SVG: crimson and coral folds of light over maroon and
  black, slowly drifting, still under reduced motion) is the reference's right panel. Page headers
  (`TypeHero`) are split like the reference card: title and controls on the left, an art panel on the
  right (on top on phones) with the page's TypeScape figure of real course titles glowing on it
  (`theme="night"`). Sign-in and sign-up are the reference itself: a maroon arch emblem, a big bold
  title, pill fields, an "or" rule, and the art panel.
- **The homepage** keeps the chapel drawn with course titles, on the white sheet; its title is bold
  Inter with the Newsreader accent line.
- **Wider pages** (Max, 2026-11-20, "widen everything horizontally in every page"): content 1560px
  (was 1200), reading 960 (720), forms 560 (448), the planner 1920 (1600); the Ask conversation
  1040px.
- **The menu bar** is a frosted white glass bar the width of the page sheet, floating on the maroon
  frame and sticky at the top: ink serif wordmark, 18px links, the current page a soft rose wash (not
  solid red), a quiet filled search pill. On a phone the account shows as its avatar only, so the bar
  keeps to two rows. (A dark "glass and flowing red" theme was tried and withdrawn the same day.)
- **Day and night on the homepage** (Max, 2026-11-20): a Day / Night switch at the top right of the
  hero (remembered on the device). Everything is painted in the chapel's course titles by the shader,
  with no separate layers and no enlarged type: two slim street lamps (about two letters wide)
  flank the chapel by day and night (iron letters, a gold lantern by day); at night the sky's titles
  turn a dim navy with a few twinkling gold star letters and a moon of gold letters, small snowflakes
  drift down as bright letters, the stone is a deep moonlit blue, the lawn and paths are under snow,
  and the lanterns glow orange, warming the snow and the letters near them. Texture comes from the
  letters' own colour and transparency: drifting night clouds (darker, denser banks; thin clear
  patches where the stars show; lavender edges near the moon), a darker zenith, moonlit and shadowed
  carving on the side facing the moon, weathered patches in the stone, mottled trees, and snow
  drifts. Reduced motion: a still night (no falling snow, no twinkle, the clouds stay put).


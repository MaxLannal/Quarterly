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

The UChicago Course Forum should read like a **quiet, editorial print magazine** that is also a course forum. This file merges three sources. Each source has a fixed job:

| Source | Governs | Does NOT govern |
|---|---|---|
| ElevenLabs DESIGN.md | Typography, spacing, layout, radii, elevation, component geometry, overall restraint | Any color value |
| UChicago Identity Guidelines (2020) | Every color: accent, neutrals, atmosphere, semantic, data | Fonts (do **not** change to Gotham/Garamond from that guide) |
| Rare UI (rareui.com) | Interaction ideas and animated components | Colors, fonts, radii. Restyle every component to the tokens here. |

When the sources do not agree, use this priority: **accessibility → this file → Rare UI defaults.**

**Key characteristics**
- An off-white canvas (`{colors.canvas}`), near-black ink, and white cards with 1px hairlines.
- **Maroon is the single accent.** It has the role that ElevenLabs gives its ink pill: primary CTAs, inline links, the active nav/selection state, focus rings. Use it rarely, so that it has weight.
- Display type is a **light serif at weight 300**. It is never bold. Body is Inter 400/500 with slightly loose tracking.
- Every button and badge has the pill geometry. Cards have a 16px radius. Page sections have 96px between them.
- Color "voltage" comes from soft atmospheric orbs in the warm, nature-based secondary hues of UChicago (lake blue, goldenrod, ivy, terracotta, rose). It never comes from saturated fills.

## Colors

All values come from the UChicago Identity Guidelines. In the YAML, values with the mark **derived** are tints or shades mixed from a guideline color. (The guide groups its palette as Core Hues, Shades, and Tints.) No value comes from outside the palette.

### Brand & action
- **Maroon** (`{colors.primary}` — #800000, PMS 202): the signature color of the university. Use it for primary buttons, inline links, the active nav indicator, the focus ring and the selected state. Use one primary button in each view.
- **Maroon hover / active** (`{colors.primary-hover}` #6C0000, `{colors.primary-active}` #5A0000).
- **Maroon wash** (`{colors.primary-wash}` #F5EBEB): the background for the selected thread row, the active sidebar item and the current tab.

### Neutrals
- **Ink** (`{colors.ink}` #111111): headings, primary text. The guide lists black without a value. This value is slightly softer.
- **Body** (`{colors.body}` #4D4D4D): running text in posts and reviews.
- **Muted** (`{colors.muted}` #6B6B6B): timestamps, counts, course codes, metadata.
- **Dark Gray** (`{colors.gray-dark}` #767676, Warm Gray 11): icons and dividers. It fails AA for small text on the canvas (4.23:1). Thus do not use it for text. Use `{colors.muted}`.
- **Light Gray** (`{colors.hairline-strong}` #D6D6CE, Cool Gray 3) and its tints make the canvas, the hairlines and the badge plates.

### Atmospheric orbs
`orb-lake`, `orb-goldenrod`, `orb-ivy`, `orb-terracotta` and `orb-rose` replace the pastel orbs of ElevenLabs. They are mid-tones. Thus render them as follows:

- Use **soft radial gradients at 35–45% opacity at the center, which fade to transparent**.
- Blur them by 60–80px.

The result has the same pastel, atmospheric feel. Never use them as button fills, text colors or card backgrounds. Use one orb color in each section.

### Semantic
| Role | Text/icon | Wash background |
|---|---|---|
| Error | `{colors.semantic-error}` #8F3931 | `{colors.semantic-error-wash}` |
| Success | `{colors.semantic-success}` #616530 | `{colors.semantic-success-wash}` |
| Warning | `{colors.semantic-warning}` #9A5324 (icon #C68220) | `{colors.semantic-warning-wash}` |
| Info | `{colors.semantic-info}` #155F83 | `{colors.semantic-info-wash}` |

Error red and maroon are near each other (1.46:1 between them). Always show an error with an icon and a message. Never fill a button with the error color.

### Data visualization
For ratings, workload and grade distributions:

- Single series: maroon.
- Multiple categories: `data-1` … `data-6`, in this order.
- Sequential scales: `{colors.primary-wash}` → `{colors.primary}`.

### Contrast (WCAG AA verified)
| Foreground | on card #FFF | on canvas | on surface-strong |
|---|---|---|---|
| ink | 18.9 | 17.6 | 16.7 |
| body | 8.5 | 7.9 | 7.5 |
| muted | 5.3 | 5.0 | 4.7 |
| maroon | 11.0 | 10.2 | 9.7 |
| white on maroon | 11.0 | — | — |

### Color don'ts
- Do not use the violator colors of the guide (cyan #47B5FF, magenta #FF3399).
- Do not add a hex value that is not in this file. If you need a new color, derive a tint/shade from an existing token and add it here.
- Do not use more than one saturated element in a view, in addition to the primary button.

## Typography

### Font families
- **Display: Newsreader, weight 300.** ElevenLabs uses Waldenburg Light, which has a license. Newsreader (free, Google Fonts / `@fontsource/newsreader`) has a true 300 weight and the same contemporary editorial feel. (EB Garamond, the substitute that the ElevenLabs file suggests, has no 300 weight.)
- **Body/UI: Inter** (`@fontsource-variable/inter`). ElevenLabs uses the same family.
- Do not use the fonts of the UChicago guide (Gotham, Adobe Garamond, Fette Fraktur). Typography follows ElevenLabs by design.

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
- **Display stays at weight 300.** Never make a display headline bold.
- Use negative tracking on display sizes. Use slightly positive tracking (+0.15–0.18px) on Inter body.
- Body is never below 400.
- Course codes (for example, "CMSC 14300") use `caption-uppercase` or tabular Inter. They never use the serif.

## Layout

### Spacing
The base unit is 4px. Tokens: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 96. Section padding is 96px.

### Grid & container
- The maximum content width is approximately 1200px, on a 12-column grid.
- **Reading column for posts and reviews: maximum 720px** (approximately 70 characters). Thus long discussions stay comfortable to read.
- Card grids: 3-up for course browsing, 2-up for splits. Gaps are 16–24px.
- Footer: a maximum of 5 columns at desktop.

### Whitespace
- Between bands, the pacing is generous and editorial (96px).
- Inside bands, the pacing is tight (16–24px between cards).
- Lists of threads are dense, with hairline dividers. The pages around them have much space.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | `{colors.canvas}` | Page bands, footer |
| Card | `{colors.surface-card}` + 1px `{colors.hairline}` | Course cards, post cards |
| Hover | `0 4px 16px rgba(0, 0, 0, 0.04)` | Hovered cards. This is the only shadow tier. |
| Overlay | `0 8px 32px rgba(0, 0, 0, 0.08)` | Menus, drawers, toasts (added. ElevenLabs has no overlay tier.) |
| Orb | Radial gradient of one `orb-*` token | Only for atmosphere, never a surface |

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
**`top-nav`**: canvas background, 64px tall.

- Left: the text wordmark.
- Center/left: the primary links (for example, Courses / Departments / Discussions).
- Right: search, sign-in and the primary pill.
- The active link gets a 2px maroon underline or a `primary-wash` pill. A color change alone is not sufficient.

### Buttons
- **`button-primary`**: maroon pill, white text, 40px tall, 10×20px padding. Hover `primary-hover`, press `primary-active`. Use one in each view (for example, "Write a review", "Post").
- **`button-outline`**: transparent pill, 1px `{colors.hairline-strong}` border, ink text.
- **`button-tertiary-text`**: ink text, no chrome.
- **`button-destructive`**: outline pill with error-colored text. It asks for confirmation in place (see the Rare UI Delete Button), not in a modal.
- **Focus (all interactive elements)**: 2px `{colors.primary}` ring, 2px offset.

### Hero & atmosphere
- **`hero-band`**: canvas background, `display-mega` headline, `body-md` subhead, a search input and/or one primary pill, and one orb that blooms behind the headline.
- **`orb-card`**: canvas-soft, 24px radius, 32px padding, one orb color for each card.

### Content
- **`course-card`**: white, 16px radius, 24px padding, 1px hairline.
  - Order: course code (`caption-uppercase`, muted) → title (`title-md`) → one line of meta (`caption`, muted).
  - Hover = one soft drop shadow.
- **`post-card`**: white, 16px radius, 32px padding.
  - Header: avatar + name (`body-strong`) + timestamp (`caption`, muted).
  - Body: `body-md`/`{colors.body}`, within the 720px reading column.
- **`thread-row`**: transparent row, 12px vertical padding, 1px hairline divider.
  - Left: 32px avatar. Then the title (`title-sm`) over the meta. Right: the reply count.
  - Selected = `thread-row-selected`.
- **`avatar`**: a 32px circle on `surface-strong` with initials. The padded row gives a 48px tap zone.
- **`featured-card`**: the maroon inversion (the same as the dark featured pricing tier of ElevenLabs). White text, with `on-inverse-soft` for secondary text. A maximum of one on each page.
- **`link-inline`**: maroon text with an underline, in post bodies.

### Forms & tags
- **`text-input`**: white, 8px radius, 44px tall, 12×16px padding, 1px `{colors.border-input}` border.
  - On focus, the border becomes 2px maroon.
  - Errors: an error-colored border, an icon, and a message below.
- **`badge-pill`**: `surface-strong` plate, `caption-uppercase`, pill. Department and quarter tags use this neutral badge, not colored chips.

### CTA & footer
- **`cta-band`**: canvas, a centered `display-lg` line, one primary pill, an optional orb. 96px padding.
- **`footer`**: canvas, `body-sm` in `{colors.body}`, link columns, 64×48px padding. If a Rare UI component ships, the footer includes the Rare UI credit (see below).

## Motion

ElevenLabs does not document motion. These rules fill the gap.
- Durations: 150ms (hover/press), 200–250ms (menus, drawers), a maximum of 400ms (page-level reveals).
- Easing: ease-out for entrances. Gentle springs (Motion `type: "spring", bounce ≤ 0.2`) for indicators and counters.
- **One signature animated moment on each screen.** Reading surfaces (post bodies, review text) do not move.
- Obey `prefers-reduced-motion`:
  - Replace springs/drifts with instant or opacity-only transitions.
  - Orbs stop their drift.

## Rare UI components

Rare UI components are single-file React components, made with Tailwind CSS and Motion. The shadcn CLI installs them, for example `npx shadcn@latest add swamimalode07/rare-ui/<name>`. If the project is not React + Tailwind, use them as interaction references, and build the behavior again natively.

**Rules**
1. After the installation, **restyle every component to the tokens in this file**. Replace its colors, fonts, radii and shadows. No Rare UI default color should stay.
2. Keep the copyright notice of each component in the source file.
3. **License:** If you ship a Rare UI component, you must show a visible link to https://rareui.com (footer, about page or README). You must not resell or redistribute the components on their own.
4. The motion rules above also apply, including reduced motion.

**Where they fit in the forum**
| Forum need | Rare UI component | Notes |
|---|---|---|
| Hero atmosphere | `fluid-orb` | Use it as the hero orb, with an `orb-*` color. Hero only (WebGL). |
| Long course pages (overview, reviews, discussion) | `rail-toc` or `scroll-progress` | Select one for each page type. |
| Department / filter sidebar | `hook-sidebar` or `bounce-sidebar` | Active indicator in maroon. |
| Vote / like / view counts | `animated-counter` | Inter, tabular numbers. |
| Reactions to posts | `emoji-reaction` | It uses Apple emoji artwork through `react-apple-emojis`. If that is a concern, use native emoji. |
| Reply notifications | `notification-bell` | Badge in maroon. |
| Post success / errors | `toast` | Overlay shadow tier. Semantic colors. |
| Delete of own post | `delete-button` | Confirmation in place. Error-colored text. |
| Code in CS course posts | `code-block` | Give it `#800000` as its accent. |
| Mobile filters / composer | `family-drawer` | Bottom sheet, on mobile only. |
| Email-code sign-in (if used) | `otp-input` | — |
| Forum FAQ / About | `faq` | The message-thread style fits a forum. |

Do not use the purely decorative components (`gravity-letters`, `matrix-orb`, `grid-reveal`, `folder-component`) without a clear reason.

## Brand & logo

- Do **not** use the official University shield, wordmark, phoenix or Gothic "UChicago" mark, unless the project has university approval. The guidelines restrict the use of those marks.
- Use a **text wordmark**: "UChicago Course Forum" in Newsreader 300 (or Inter 500 at small sizes), in ink or maroon.

## Do's and Don'ts

### Do
- Use maroon for exactly one primary action in each view, and for links, focus and selection.
- Use Newsreader 300 for every display headline. Use Inter 400/500 for all other text.
- Keep cards white on the off-white canvas, with 1px hairlines. Use one shadow tier on hover.
- Use pills for every button and badge. Use 16px radii for cards.
- Keep post and review text in a 720px reading column.
- Refer to tokens (`{colors.*}`, CSS variables). Never use inline hex.

### Don't
- Do not add a second accent color. Do not use secondary hues as fills for buttons, cards or text.
- Do not make display headlines bold.
- Do not use `{colors.gray-dark}` (#767676) for small text on the canvas.
- Do not use sharp corners on buttons.
- Do not put more than one animated component in the same view.
- Do not import the fonts or official marks of UChicago.

## Responsive Behavior

| Name | Width | Key changes |
|---|---|---|
| Mobile | < 640px | Hero h1 64→32px. Course cards 1-up. Nav → hamburger. Orbs become smaller. Filters move to a bottom drawer. |
| Tablet | 640–1024px | Hero h1 48px. Cards 2-up. The sidebar collapses. |
| Desktop | 1024–1280px | Hero h1 64px. Cards 3-up. The sidebar is visible. |
| Wide | > 1280px | The maximum content width is 1200px. |

- Below 768px, the top nav changes to a hamburger.
- The primary pill stays 40px tall. Padded rows give tap targets of 48px or more.
- At each breakpoint, the orbs become smaller, but they never disappear.

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

If the project uses Tailwind v4, copy these values into an `@theme` block. Then utilities such as `bg-primary` and `rounded-xl` resolve to these values.

## Known gaps

- Dark mode has no definition. Do not invent one. Ask first.
- The letter-spacing of ElevenLabs was tuned for Waldenburg. If Newsreader looks cramped at 64px, make the display tracking looser by a maximum of 0.5px. Change nothing else.
- This file does not specify form validation beyond focus/error, empty states or loading skeletons. Build them from existing tokens (hairlines, muted text, surface-strong plates).

## Changes approved in FEEDBACK (2026-11-16, design pass)

Richard's FEEDBACK "Minor design changes" overrides the rules above only in these places:

- **Wordmark weight.** The "Quarterly" headline of the home page is 96px Newsreader **400** (`text-display-hero`, 64px on a phone). The wordmark in the top bar and in the footer is Newsreader **500**. All other display headings stay at 300.
- **Hero orb.** The orb of the home hero is `orb-maroon` (#A44A4A, derived: maroon at 70% on the canvas). Thus the one atmospheric colour of the page agrees with the accent. Other orbs keep the secondary hues.
- **Catalog switch.** Courses/Programs is a small segmented control:
  - A `surface-strong` track.
  - The current side is on a white pill with maroon text.
  - The pill slides 200ms ease-out between sides. With reduced motion, the pill stays still.
- **Top-bar search.** A filled `surface-strong` field. It has no outline until the user hovers over it or focuses it. The icon and the placeholder identify it.
- **Footer links.** 32px rows with a mouse. 44px targets on touch screens.

## Maroon and night (Max, 2026-11-20; branch `feature/best-of-uchicago`)

Max requested this with a reference login card ("Have words bigger and background colors maroon and black
combined. Take inspiration from this and apply to every page and every detail"). Richard has not confirmed it yet. Where it conflicts with the sections above, this section describes what is built now.

- **The night.** Every page is on a fixed maroon-and-black background (`body`, `index.css`): deep maroon `#5c0a1d` to near black `#12040a`, with crimson light. The top bar and the footer are on it, in white (`on-night`, `on-night-soft`, `on-night-muted`). The wordmark stays Newsreader, in white.
- **The sheet.** The page content is one white sheet with large rounded corners (`rounded-sheet`, 44px, 28px on phones) and a deep shadow, the same as the card of the reference. Notices that are part of a page are inside the sheet.
- **Bigger words.**
  - Body 17px, small 16px, captions 15px, buttons and nav 16px.
  - Headlines are bold Inter (650-800, tight tracking, the same as "Welcome home").
  - The `<em>` words of headlines are Newsreader italic in maroon ("within your reach.", "Ask *anything*").
  - Voices and quotes (the guide, student quotes, the ticker, book covers) keep the serif.
- **Pills.**
  - Buttons are 46px pills in a 52px box, semibold. There are `light` and `night` variants for the dark background.
  - Inputs and selects are 52px pills (26px radius), with a soft maroon halo on focus.
  - Email fields have an envelope. Password fields have an eye that shows or hides the characters.
- **Radii.** Cards 18-24px, panels 32px, art panels 36px (`rounded-art`).
- **Art panels.**
  - `GradientArt` is the right panel of the reference. It is generated SVG: crimson and coral folds of light over maroon and black, with a slow drift. With reduced motion, it stays still.
  - Page headers (`TypeHero`) have two parts, the same as the reference card. The title and the controls are on the left. An art panel is on the right (on top on phones). On the panel, the TypeScape figure of the page glows, made of real course titles (`theme="night"`).
  - Sign-in and sign-up are the reference itself: a maroon arch emblem, a big bold title, pill fields, an "or" rule, and the art panel.
- **The homepage** keeps the chapel drawn with course titles, on the white sheet. Its title is bold Inter, with the Newsreader accent line.
- **Wider pages** (Max, 2026-11-20, "widen everything horizontally in every page"):
  - Content 1560px (before: 1200).
  - Reading 960 (before: 720).
  - Forms 560 (before: 448).
  - The planner 1920 (before: 1600).
  - The Ask conversation 1040px. (Issue #15 removed the Ask page on 2026-11-24.)
- **The menu bar** is a frosted white glass bar, as wide as the page sheet. It floats on the maroon frame and is sticky at the top.
  - It has an ink serif wordmark, 18px links, a soft rose wash for the current page (not solid red), and a quiet filled search pill.
  - On a phone, the account shows only as its avatar. Thus the bar stays at two rows.
  - (We tried a dark "glass and flowing red" theme and withdrew it on the same day.)
- **Day and night on the homepage** (Max, 2026-11-20):
  - A Day / Night switch is at the top right of the hero. The device remembers the choice.
  - The shader paints everything in the course titles of the chapel. There are no separate layers and no enlarged type.
  - By day and by night, two slim street lamps (approximately two letters wide) are on the two sides of the chapel. They have iron letters, and by day a gold lantern.
  - At night:
    - The titles of the sky become a dim navy, with a few twinkling gold star letters and a moon of gold letters.
    - Small snowflakes fall as bright letters.
    - The stone is a deep moonlit blue. The lawn and the paths are under snow.
    - The lanterns glow orange. They make the snow and the letters near them warmer.
  - The texture comes from the colour and transparency of the letters:
    - Night clouds that drift: darker, denser banks, thin clear patches where the stars show, and lavender edges near the moon.
    - A darker zenith.
    - Moonlit and shadowed carving on the side that faces the moon.
    - Weathered patches in the stone, mottled trees, and snow drifts.
  - With reduced motion: a still night. No snow falls, nothing twinkles, and the clouds do not move.
  - The day scene has the same kind of texture, but gentler:
    - Soft grey cloud banks drift across the sky, with thin clear patches and a deeper zenith.
    - Weathered patches and grain in the maroon stone (darker low down, lighter at the spires).
    - Mottled trees and lawn, and transparency that changes with them.

- **The dashboard (`/me`)** is a tight grid of panels, as wide as the page sheet. It has 12 columns with 12px gaps (6 on tablets, one column on phones). It has no orbit animations. (Max removed the orrery header and the orbiting interests on 2026-11-20.)
  - Top left: the student (name and class year, email, the portrait with its themes, class year and programs, "Talk with your guide" and "Draft my routes", the completeness ring).
  - Top right: the guide.
  - Below: interests, research areas and what's new. Then the humanities compass, career and horizons. Then workload and an "at a glance" panel. Then the routes, two side by side, each with a layout for its own width.
  - Issue #15 (2026-11-24) removed "Draft my routes", the "at a glance" panel and the routes. Workload now goes across the row.
- **The menu bar has four tabs** (issue #15, 2026-11-24): Dashboard, Planner, Catalog, Forum. The homepage is not a tab (the wordmark links to it). No page has the floating companion orb.
- **The Catalog page** (`/courses`, issue #19, 2026-11-24) keeps the centred search and its filters.
  - Before a search, browse rows are below the search:
    - "Newly released courses" (when the app knows of new courses).
    - "Course spotlights": the illustrated cards of the Feed, without the flying words, the book shelf, the AI note and the Save / Less buttons.
    - "What students say": the quote cards of the Feed.
  - Each row is a heading over cards that scroll sideways and snap, inside the page width.
  - For a logged-in student, each card and result has a rating line (overall, difficulty, number of reviews). A logged-out visitor sees one "Log in to see student ratings" line under the search.
  - The Feed page and its floating words, ticker, focus chips and AI headline are gone.

## Sign-up step 4 and the credits editor (Richard, 2026-11-25, 2838c6a)

- Step 4 ("About you") has a 36rem column. The other auth pages keep 30rem.
- A credit is one line: kind, name and course (cut with "…", the full line in a tooltip), then the units, then two 44px icon buttons (edit, remove). In a list narrower than 24rem, only screen readers get the kind.
- The add form of a credit is one box. Kind and Description are on the first row. Course, Units and "Add credit" are on the second row. In a narrow drawer, Course has its own row. In a panel wider than 42rem, all fields are on one row.
- The button beside a compact field is 44px tall, the same as the field.
- The transfer questions in step 4 have no box of their own. Their fields line up with the fields above.
- The kind labels are "AP exam", "Placement" and "Transfer".


## Dark glass (Max, 2026-11-27; branch `claude/quarterly-ui-redesign-c953e9`)

Max asked for this with three reference pictures: floating glass tool panels over a dark picture, glass folders on a swirl of dark red light, and a dark glass sign-in card with a ring of white light behind it. His words: "Reconstruct everything on Quarterly on this UI style", "Have the Harper Library at the homepage in this UI as well. Have each quarter in the planner a folder like as shown, and classes as files in it. Be magical, smooth, dark, red, glassy. Mature designs", and "white light goes together intersection with maroon dark red light, flowing in the background". Richard has not seen it yet. Where it conflicts with the sections above (including "Maroon and night"), this section describes what is built.

- **The night and its light** (`components/brand/Aurora.tsx`). Every page is on near-black (`night` #060203).
  - Behind it, a ring of white light crosses a ring of crimson light. A wide ring of maroon haze and two slow red blooms sit under both.
  - A bright arc travels slowly round each ring (110-220 s a turn). Where white crosses red, the two add up to a rose-white glow.
  - Film grain stops banding; a vignette keeps the edges black.
  - Only transforms animate, so the browser moves cached layers and does not repaint. With reduced motion, the light holds still.
  - The light is dimmer behind pages covered by a pane. It is at full strength on the homepage and on sign-in and sign-up.
- **The pane.** Each page is one pane of smoked glass (`.page-sheet`, about 86% opaque) with a lit hairline edge, 44px corners and a deep shadow.
  - The light shows faintly through the pane and fully around it.
  - The pane has no backdrop blur: blurring a whole page over a moving background would cost every frame.
  - The homepage has no pane (`data-bare`).
  - A page rises out of the glass when it opens (`.page-enter`, 520 ms).
- **Colour** (tokens in `index.css`; the names did not change, the values did):
  - Text is warm white: `ink` #f7f0f0, `body` #cdc1c3, `muted` #ab9c9f. Each is 4.5:1 or better on the pane and on its glass tints.
  - Red is the light itself: `primary` #ff5c70 (6.6:1 on the pane) for links, the current place, focus rings, bars and dots. As a fill, it carries dark text (`on-primary`).
  - Surfaces on the pane are tints of white (`surface-card` 4.5%, `surface-strong` 8.5%, `canvas-soft` 3%). Surfaces that float over content use `surface-raised` (#1a0f12) or the `.glass-raised` class.
  - `canvas` (#0c0608) is solid, for covers.
  - Lines are white at low alpha (`hairline` 9%, `hairline-strong` 17%), so they catch the light like the edge of a pane.
  - Semantic colours and the data colours are lifted so they read on dark. Their washes are tints of the same light.
  - Scrims use `scrim` (never `ink`, which is now white). The pair `bg-ink` + `text-on-dark` would now be white on white: use `bg-ink text-canvas`.
- **Type.**
  - Headlines use Instrument Serif at 400 (`font-display`; the `text-display-*` sizes are about 20% larger than the old bold Inter, because the serif's x-height is lower). Their `<em>` words are its italic, lit red.
  - `font-synthesis` is off, so a bold class never fakes a bold serif.
  - Body and controls stay Inter. Voices and quotes keep Newsreader (`font-serif`).
  - Small labels (eyebrows, course codes, footer column titles, dates) are JetBrains Mono capitals, widely spaced (`.mono-label`, `Eyebrow`, `CourseCode`), like "PLANNER // AUTUMN 2026".
  - All fonts are bundled from npm, so nothing is fetched from another origin.
- **Controls.**
  - The main button is a white pill with dark text and a red glow beneath it. The glow brightens on hover.
  - `outline` is a clear glass pill with a lit edge. `glow` is red glass, for a second strong action.
  - Inputs are dark glass pills with an inset shadow. On focus, the edge turns red with a red halo.
  - Cards are glass tiles with a lit top edge. Cards that are links lift 2px and light up.
  - Any `[data-spotlight]` surface carries a soft red light that follows the pointer (one listener in `AppShell`). It is decorative only.
- **Floating glass.** The menu bar is a slab of smoked glass (`.nav-glass`). The current tab is a lit glass pill with a point of red light. Menus, dialogs, drawers and the top sheet use `.glass-raised` over a blurred `scrim`.
- **The wordmark** is "Quarterly" in the display serif, with one point of red light after it.
- **Folders and files** (`components/ui/folder.tsx`).
  - A glass folder has a back panel with a tab on its top-left. The tab slopes down into the body.
  - The files stand inside it. A frosted front pocket runs across the bottom, and its top edge steps down from left to right. The files tuck 8px behind the pocket, so nothing they say is covered.
  - Tones: `smoke`, `ember` (red light) and `garnet`. A drop target lights its edge red and glows (`active`).
  - A file (`.glass-file`) is a sheet of light glass with a folded top-right corner. It is painted by pseudo-elements, so the element keeps a normal box for focus rings and dragging.
  - The planner draws each quarter as a folder and each class as a file in it.
- **Motion.** The ease is `cubic-bezier(0.16, 1, 0.3, 1)`: long and soft. Hover and press take 150-300 ms, entrances 400-520 ms. Reduced motion stops all of it.

# Brief for Claude Code: add the animated ASCII chapel to the homepage

## Goal

Add the `<ascii-scene>` component (this folder) to a section of the homepage. It shows an animated, colored ASCII drawing of Rockefeller Chapel whose sky, light and weather follow the real time and weather in Hyde Park. It must **sit directly on the site's beige/off-white canvas** and look like part of the page's design, not like an embedded widget: no box, no border, no card, no shadow. The edges dissolve into the page.

Read `README.md` in this folder for the full attribute and CSS-variable reference.

## 1. Learn the site before touching anything

1. Identify the framework and build setup (plain HTML, Jekyll/Hugo, Next.js, Astro, Vite + React, …) and where static assets are served from (`public/`, `static/`, `assets/`, site root).
2. Find the design tokens: the exact page background color behind the homepage section (resolve CSS variables and Tailwind classes to the real hex value), body text color, muted/secondary text color, accent color, fonts (serif/sans/mono), content max-width, spacing scale, button/link styles, and whether the site has a dark mode and how it's toggled.
3. Look at the homepage layout and decide where the scene goes. A good default is a full content-width section under or beside the intro, with at least ~720px of width on desktop.

## 2. Install the files

- Copy `ascii-scene.js` and `scene.rockefeller.json` to the static folder, e.g. `public/ascii-scene/`.
- Keep `tools/`, `demo.html` and these docs in the repo, e.g. at `tools/ascii-scene/` or `docs/ascii-scene/`, but **out of the deployed bundle**.
- With TypeScript + JSX, add `ascii-scene.d.ts` to the project and make sure tsconfig includes it.

## 3. Load the component

Plain HTML / Jekyll / Hugo:

```html
<script type="module" src="/ascii-scene/ascii-scene.js"></script>
<ascii-scene src="/ascii-scene/scene.rockefeller.json"></ascii-scene>
```

Next.js (App Router), as a client component that loads the module only in the browser:

```tsx
"use client";
import { useEffect } from "react";

export default function ChapelScene() {
  useEffect(() => {
    // ascii-scene.js copied into the source tree, e.g. src/lib/ascii-scene.js
    import("@/lib/ascii-scene.js");
  }, []);
  return <ascii-scene src="/ascii-scene/scene.rockefeller.json" fade="0.14" />;
}
```

Astro:

```astro
<ascii-scene src="/ascii-scene/scene.rockefeller.json"></ascii-scene>
<script>import "../lib/ascii-scene.js";</script>
```

Vite/React: the same pattern as Next.js. In React, pass boolean attributes as strings (`controls=""`).

The module is about 55 KB. If the section is below the fold, import it lazily, either when the section nears the viewport or in an idle callback. It must not become the LCP element or delay it.

## 4. Blend it into the design (the important part)

Set the CSS variables on `ascii-scene` or on its section, using the site's own tokens:

```css
.home-scene ascii-scene {
  --ascii-paper: var(--color-bg);      /* EXACT background color behind it */
  --ascii-ink: var(--color-text);      /* main text color */
  --ascii-ink-mix: 0.12;               /* 0.05 more colorful … 0.25 more editorial/monochrome */
  --ascii-saturation: 0.9;             /* lower for muted/earthy palettes */
  font: 12px/1 var(--font-mono, var(--font-sans));  /* used by the optional controls */
  color: var(--color-text-muted);      /* controls inherit this */
}
```

Rules:

- **No container styling.** No background, border, radius or shadow on the scene or its wrapper. The page background must be a solid color behind it. If the section has a texture or gradient, set `--ascii-paper` to its average color and raise `fade` to 0.18–0.25.
- **Edges:** `fade` between `0.10` and `0.20`. Make it bigger when the scene is narrower than the column around it, so it reads as a vignette rather than a rectangle.
- **Width and rhythm:** align the scene with the site's content grid. Use the same max-width and horizontal padding as neighboring sections, and the site's vertical spacing above and below it. Don't put it inside a fixed-height `overflow:hidden` box. It sets its own height (about 2:3 of its width).
- **Palette harmony:** compare the rendered scene with nearby elements. If its sandstone, green and blue feel louder than the rest of the page, lower `--ascii-saturation` (0.7–0.9) or raise `--ascii-ink-mix` (0.15–0.25). If the site has a strong accent color, don't recolor the scene with it. Echo it in the caption or controls instead.
- **Controls:** decide with the page's tone in mind:
  - Minimal/editorial site: leave `controls` off and add a small caption in the site's caption style, e.g. "Rockefeller Chapel · live from Hyde Park".
  - Playful/portfolio site: turn `controls` on and style it to match the site's buttons or links via `ascii-scene::part(button)`, `::part(status)` and `::part(controls)` (font, size, radius, colors, hover).
- **Dark mode:** if the site has one, switch `theme="dark"` and `--ascii-paper` to the dark background whenever the site's theme changes (class toggle or `prefers-color-scheme`).
- **Detail:** the default `density="medium"` is right for most layouts. Use `density="high"` only when the scene is at least ~1100px wide.

## 5. Platform details

- If the site sends a Content-Security-Policy header, allow `connect-src https://api.open-meteo.com` (live weather) and `font-src data:` (the embedded font). Otherwise set `weather` to a fixed value.
- Keep `weather="auto"` only if you also add a small "Weather data by Open-Meteo.com" credit link somewhere sensible, like the footer or the caption. Check Open-Meteo's current terms.
- The component already handles reduced motion, off-screen pausing, resize and the high-DPI cap. Don't reimplement these.
- Don't edit `scene.rockefeller.json` by hand. Don't swap the font: the characters were chosen for DejaVu Sans Mono's exact shapes, which the component embeds. Change the look with attributes and CSS variables. Edit `ascii-scene.js` only for a real bug, and note what you changed.

## 6. Verify with screenshots

Run the site locally and screenshot the homepage section at **1440px, 1024px and 390px** widths, in these states (set the attributes temporarily, or use `el.setTime()` / `el.setWeather()` from the console):

- `time="noon" weather="clear"`, `time="golden" weather="clear"`, `time="night" weather="clear"`
- `time="noon" weather="rain"`, `time="night" weather="snow"`, `time="morning" weather="fog"`

Check:

- [ ] No visible rectangle edge. The scene dissolves into the page color with no seam or color mismatch.
- [ ] Its colors feel like the same palette as the surrounding typography and accents.
- [ ] Spacing and alignment match the neighboring sections, and there's no layout shift while it loads.
- [ ] On a phone the chapel stays centered and legible, and the page doesn't scroll horizontally.
- [ ] No console errors. The page stays responsive (no long tasks over 50ms from the scene).
- [ ] With reduced motion enabled, the scene is still and the rest of the page works.
- [ ] Dark mode, if any, switches the scene correctly.

## 7. Important: replace the placeholder photo before launch

`scene.rockefeller.json` was converted from a **watermarked stock photo** for prototyping. Don't deploy it to production. Use the site owner's own photo of the chapel instead:

1. Put the photo in `tools/`.
2. Copy `rockefeller.regions.json` to `mine.regions.json` and re-measure, in the new photo's pixels: `building_box` [x0, y0, x1, y1]; `building_solid_above_y` (above this line everything inside the box is building, below it green pixels count as trees); `ground_y`; `path_min_x`; `lawn_y`; `stained_glass` and `warm_windows` rectangles (windows that glow at night); `lamps` points; `focus_x` (0–1, the subject's horizontal center).
3. Run `python3 segment.py photo.jpg mine.regions.json` and inspect `seg.png`. Blue = sky, tan = building, dark green = trees, light green = lawn, gray = path. Adjust the regions until it's right.
4. Run `python3 convert.py photo.jpg mine.regions.json ../scene.mine.json preview.png` and look at `preview.png`.
5. Point `src` at the new JSON and repeat the screenshot checks.

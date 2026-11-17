# ascii-scene: Rockefeller Chapel in animated ASCII

An animated, colored ASCII-art drawing of Rockefeller Chapel (University of Chicago). The sky, sunlight, windows and street lamps follow the **real sun position in Hyde Park**. The weather (clear, cloudy, rain, storm, snow, fog) can follow **live conditions** or be set by hand. It is designed to sit on a beige/off-white page and dissolve into it at the edges.

- One dependency-free web component: `<ascii-scene>` (~55 KB including an embedded font)
- One data file: `scene.rockefeller.json` (~175 KB, the pre-converted drawing at 3 resolutions)
- Works in plain HTML, React/Next.js, Astro, Vue, Svelte, Hugo/Jekyll

> **Before publishing:** the drawing was made from a watermarked **stock photo** (Dreamstime), for prototyping only. Replace it with your own photo (see "Use your own photo" below) before this goes on a public site.

## Files

| File | What it is |
|---|---|
| `ascii-scene.js` | The web component (ES module). Drop it in your static/public folder. |
| `scene.rockefeller.json` | The drawing: characters, colors and scene classes per cell, 3 resolutions. |
| `ascii-scene.d.ts` | Optional TypeScript/JSX types. |
| `demo.html` | Standalone demo on a beige page with the controls shown. |
| `tools/` | Python converter to regenerate the scene from a new photo (not deployed). |
| `CLAUDE_CODE_INSTRUCTIONS.md` | Brief for a coding agent to integrate this into the site and blend it with the design. |

## Quick start (plain HTML)

```html
<script type="module" src="/ascii-scene/ascii-scene.js"></script>

<ascii-scene src="/ascii-scene/scene.rockefeller.json"
             style="--ascii-paper:#F4EFE6; --ascii-ink:#2B2A33"></ascii-scene>
```

To preview locally, serve the folder, because browsers block `fetch` from `file://`:

```bash
python3 -m http.server 8000   # then open http://localhost:8000/demo.html
```

## Attributes

| Attribute | Values | Default |
|---|---|---|
| `src` | URL of the scene JSON | — |
| `theme` | `paper` (ink on a light page) · `dark` (light on a dark page) | `paper` |
| `time` | `auto` (real clock) · `cycle` (fast day loop) · `dawn` `morning` `noon` `golden` `dusk` `night` · `HH:MM` | `auto` |
| `weather` | `auto` (live via Open-Meteo) · `clear` `cloudy` `rain` `storm` `snow` `fog` | `auto` |
| `controls` | boolean: shows a small time/weather switcher under the scene | off |
| `density` | `low` · `medium` · `high` (smaller characters, more detail) | `medium` |
| `fade` | `0`–`0.4`: how far the edges dissolve into the page | `0.12` |
| `lat`, `lon` | location for sun and weather | Hyde Park |
| `timezone` | IANA zone for clock times | `America/Chicago` |
| `cycle-seconds` | length of one simulated day in `cycle` mode | `40` |
| `label` | accessible description | provided |

Named times are computed from that day's actual sunrise and sunset in Chicago. For example, `golden` is about 30 minutes before sunset.

## Matching your design (CSS custom properties)

Set these on the element or any ancestor:

| Property | Purpose | Default |
|---|---|---|
| `--ascii-paper` | The exact page color behind the scene. Edges fade into it. | `#F4EFE6` |
| `--ascii-ink` | A color every ink is pulled toward, e.g. your body text color | `#2B2A33` |
| `--ascii-ink-mix` | `0`–`1`: how strongly inks are pulled toward `--ascii-ink` (higher = more muted and editorial) | `0.12` |
| `--ascii-saturation` | `0`–`2`: color intensity | `1` |
| `--ascii-contrast` | `0.5`–`1.5`: ink strength on paper | `1` |

Style hooks: `ascii-scene::part(controls)`, `::part(button)`, `::part(status)`, `::part(canvas)`. The controls inherit `font` and `color` from the element.

JS: `el.setTime("dusk")`, `el.setWeather("snow")`, `el.addEventListener("ascii-scene:change", e => e.detail)`.

## Behavior built in

- Picks one of three resolutions to fit the width. On narrow screens it crops around the chapel instead of shrinking the characters until they're unreadable.
- Pauses when off-screen or when the tab is hidden. Shows a still frame, updated each minute, when the user prefers reduced motion.
- Reserves a 3:2 box before the data loads to avoid layout shift.
- Live weather: a client-side request to `api.open-meteo.com`, refreshed every 15 minutes. If the request fails (offline, or blocked by a Content Security Policy), it falls back to clear skies.

## Use your own photo

Take a photo with a clean sky behind the building. Blue sky works best, since the sky is detected by color and replaced with the animated one. Then:

```bash
cd tools
pip install -r requirements.txt          # numpy, opencv-python-headless, scipy, Pillow
cp rockefeller.regions.json mine.regions.json   # edit the pixel coordinates for your photo
python3 segment.py my-photo.jpg mine.regions.json            # writes seg.png: check the colored overlay
python3 convert.py my-photo.jpg mine.regions.json ../scene.mine.json preview.png
```

`*.regions.json` holds the hand-measured parts that are specific to one photo, in source-photo pixels: the building's bounding box, the ground line, which windows glow at night (`stained_glass`, `warm_windows`), street lamp positions, and `focus_x`, the horizontal center to keep on phones. Requires the DejaVu Sans Mono font. It's on most Linux systems; set `ASCII_FONT=/path/to/DejaVuSansMono.ttf` otherwise. It's the same font the component embeds, so the characters were chosen for its exact shapes.

## Credits and licenses

- Font: DejaVu Sans Mono (Bitstream Vera / DejaVu license, free to embed), subset to ASCII.
- Weather: [Open-Meteo](https://open-meteo.com). Their free API asks for attribution and is for non-commercial use, so check their current terms. Add a small "Weather data by Open-Meteo.com" link if you keep `weather="auto"`.
- Sun position: NOAA-style approximation, accurate to about half a degree.

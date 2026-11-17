/* Quarterly changes (2026-11-16, Richard's FEEDBACK "ASCII Scene"), marked "Quarterly:" below:
 *  - `weather-src` attribute: fetch the weather from the site's own server (privacy: the
 *    visitor's browser never contacts a third party) instead of api.open-meteo.com.
 *  - Interaction: sweeping the pointer across the trees makes them sway like a gust; a click
 *    sends a shooting star down the night sky, or a few birds up by day. Off under reduced
 *    motion.
 */
/*!
 * <ascii-scene> — animated, colored ASCII landscape that follows the real time of day and weather.
 * Zero dependencies. Works in plain HTML, React, Next.js, Astro, Vue, Svelte.
 *
 *   <script type="module" src="/ascii-scene/ascii-scene.js"></script>
 *   <ascii-scene src="/ascii-scene/scene.rockefeller.json"></ascii-scene>
 *
 * Attributes (all optional):
 *   src            URL of the scene JSON produced by tools/convert.py
 *   theme          "paper" (ink on a light page, default) | "dark" (light on a dark page)
 *   time           "auto" (real clock, default) | "cycle" | "dawn" | "morning" | "noon" | "golden" | "dusk" | "night" | "HH:MM"
 *   weather        "auto" (live from Open-Meteo, default) | "clear" | "cloudy" | "rain" | "storm" | "snow" | "fog"
 *   controls       show a small time/weather switcher under the scene (boolean attribute)
 *   density        "low" | "medium" (default) | "high" — how small characters may get
 *   fade           0–0.4, how far the scene dissolves into the page at its edges (default 0.12)
 *   lat, lon       location for the sun position and live weather (default: Hyde Park, Chicago)
 *   timezone       IANA time zone for clock times (default "America/Chicago")
 *   cycle-seconds  length of one simulated day in "cycle" mode (default 40)
 *   label          accessible description
 *
 * CSS custom properties (set on the element or any ancestor):
 *   --ascii-paper       the page color the scene sits on (default #F4EFE6)
 *   --ascii-ink         a color all inks are pulled toward, to match the site palette (default #2B2A33)
 *   --ascii-ink-mix     0–1, how strongly inks are pulled toward --ascii-ink (default 0.12)
 *   --ascii-saturation  0–2, color saturation multiplier (default 1)
 *   --ascii-contrast    0.5–1.5, ink strength on paper (default 1)
 *
 * JS API:  el.setTime("dusk"); el.setWeather("snow"); el.addEventListener("ascii-scene:change", e => e.detail)
 * Styling hooks: ::part(canvas) ::part(controls) ::part(button) ::part(status)
 */

const FONT_DATA = "data:font/woff;base64,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";
const FONT_NAME = "AsciiSceneMono";
const SKY = 0, BLD = 1, VEG = 2, GRS = 3, PTH = 4;
const HORIZON = 0.64;           // fraction of height where the visible horizon (tree line) sits
const BLD_BASE = 0.75;          // fraction of height where the building meets the ground
const SKY_RAMP = " `.-',:;~=+%";
const COLOR_CACHE = new Array(1 << 18);
const DENSITY = { low: 9, medium: 6.6, high: 4.5 };
const TIME_PRESETS = ["auto", "cycle", "dawn", "morning", "noon", "golden", "dusk", "night"];
const WEATHERS = ["auto", "clear", "cloudy", "rain", "storm", "snow", "fog"];
const WEATHER = {
  clear:  { cloud: 0.10, key: 1.00, amb: 1.00, desat: 0.00, gray: 0.00 },
  cloudy: { cloud: 0.62, key: 0.42, amb: 1.08, desat: 0.30, gray: 0.35 },
  rain:   { cloud: 0.86, key: 0.18, amb: 0.88, desat: 0.45, gray: 0.60, wet: 1, rain: 0.07 },
  storm:  { cloud: 0.96, key: 0.10, amb: 0.72, desat: 0.50, gray: 0.72, wet: 1, rain: 0.11, bolt: 1 },
  snow:   { cloud: 0.74, key: 0.30, amb: 1.12, desat: 0.35, gray: 0.45, snow: 1, flakes: 0.045 },
  fog:    { cloud: 0.45, key: 0.28, amb: 1.02, desat: 0.50, gray: 0.55, fog: 0.62 },
};
const STAINED = [[255, 196, 92], [236, 92, 80], [92, 140, 255], [255, 158, 64], [168, 112, 236], [255, 214, 120]];

// ---------- small math helpers ----------
const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
const lerp = (a, b, k) => a + (b - a) * k;
const mix = (a, b, k) => [lerp(a[0], b[0], k), lerp(a[1], b[1], k), lerp(a[2], b[2], k)];
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const lum = (c) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];
function hash(x, y) { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi), b = hash(xi + 1, yi), c = hash(xi, yi + 1), d = hash(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
const fbm = (x, y) => vnoise(x, y) * 0.6 + vnoise(x * 2.1, y * 2.1) * 0.3 + vnoise(x * 4.3, y * 4.3) * 0.1;
function parseColor(str, fallback) {
  const s = (str || "").trim();
  let m = s.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (m) {
    let h = m[1]; if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)].map((v) => v / 255);
  }
  m = s.match(/^rgba?\(([^)]+)\)$/i);
  if (m) { const p = m[1].split(/[ ,/]+/).filter(Boolean).slice(0, 3).map(parseFloat); if (p.length === 3) return p.map((v) => v / 255); }
  return fallback;
}

// Paper theme: turn an emitted color into a printable ink of the same hue —
// keep hue, push saturation up, and pull lightness into a range that reads on a light page.
function inkOf(r, g, b, contrast) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
  let h = 0, s = 0;
  if (d > 1e-5) {
    s = d / (1 - Math.abs(2 * l - 1));
    h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h /= 6; if (h < 0) h += 1;
  }
  const L = clamp((0.16 + l * 0.44) / contrast, 0.08, 0.62);
  const Sx = clamp(s * 1.2 + 0.1);
  const q = L < 0.5 ? L * (1 + Sx) : L + Sx - L * Sx, p = 2 * L - q;
  const f = (t) => { t = (t + 1) % 1; return t < 1 / 6 ? p + (q - p) * 6 * t : t < 0.5 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p; };
  return [f(h + 1 / 3), f(h), f(h - 1 / 3)];
}

// ---------- sun position (NOAA-style approximation, accurate to ~0.5°) ----------
function solar(date, lat, lon) {
  const rad = Math.PI / 180, n = date.getTime() / 86400000 + 2440587.5 - 2451545;
  const L = (280.46 + 0.9856474 * n) % 360, g = (357.528 + 0.9856003 * n) % 360;
  const lam = L + 1.915 * Math.sin(g * rad) + 0.02 * Math.sin(2 * g * rad), eps = 23.439 - 4e-7 * n;
  const ra = Math.atan2(Math.cos(eps * rad) * Math.sin(lam * rad), Math.cos(lam * rad));
  const dec = Math.asin(Math.sin(eps * rad) * Math.sin(lam * rad));
  const gmst = (((18.697374558 + 24.06570982441908 * n) % 24) + 24) % 24;
  const ha = (gmst * 15 + lon) * rad - ra;
  const el = Math.asin(Math.sin(lat * rad) * Math.sin(dec) + Math.cos(lat * rad) * Math.cos(dec) * Math.cos(ha));
  const az = Math.atan2(-Math.sin(ha), Math.tan(dec) * Math.cos(lat * rad) - Math.sin(lat * rad) * Math.cos(ha));
  return { el: el / rad, az: ((az / rad) + 360) % 360 };
}

// ---------- time zone helpers ----------
function tzParts(date, tz) {
  const p = {};
  new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })
    .formatToParts(date).forEach((x) => { p[x.type] = x.value; });
  return p;
}
function tzOffsetMs(date, tz) {
  const p = tzParts(date, tz);
  return Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour % 24, +p.minute, +p.second) - Math.floor(date.getTime() / 1000) * 1000;
}
function wallTime(base, tz, h, m) {   // Date for clock time h:m on base's calendar day in tz
  const p = tzParts(base, tz);
  const guess = Date.UTC(+p.year, +p.month - 1, +p.day, h, m);
  return new Date(guess - tzOffsetMs(new Date(guess), tz));
}

// Sky colors by sun elevation (degrees): [elevation, zenith, horizon]
const SKY_KEYS = [
  [-90, [12, 14, 58], [34, 30, 96]],
  [-12, [16, 18, 72], [48, 40, 118]],
  [-6, [44, 36, 120], [150, 80, 160]],
  [-2, [48, 50, 130], [238, 118, 112]],
  [2, [70, 98, 184], [255, 158, 92]],
  [8, [62, 128, 214], [255, 206, 160]],
  [20, [52, 128, 220], [176, 214, 246]],
  [90, [44, 118, 214], [168, 210, 246]],
];
function skyAt(el) {
  for (let i = 0; i < SKY_KEYS.length - 1; i++) {
    const a = SKY_KEYS[i], b = SKY_KEYS[i + 1];
    if (el >= a[0] && el <= b[0]) {
      const k = (el - a[0]) / (b[0] - a[0]);
      return { top: mix(a[1], b[1], k).map((v) => v / 255), hor: mix(a[2], b[2], k).map((v) => v / 255) };
    }
  }
  const z = SKY_KEYS[SKY_KEYS.length - 1];
  return { top: z[1].map((v) => v / 255), hor: z[2].map((v) => v / 255) };
}

function decodeLevel(L) {
  const n = L.cols * L.rows;
  const bin = atob(L.rgb), rgb = new Float32Array(n * 3);
  for (let i = 0; i < n * 3; i++) rgb[i] = bin.charCodeAt(i) / 255;
  const cls = new Uint8Array(n), glow = new Uint8Array(n), cap = new Uint8Array(n);
  for (let i = 0; i < n; i++) { cls[i] = L.cls.charCodeAt(i) - 48; glow[i] = L.glow.charCodeAt(i) - 48; }
  for (let y = 0; y < L.rows; y++) for (let x = 0; x < L.cols; x++) {
    const i = y * L.cols + x;
    if (cls[i] === SKY) continue;
    const up = y > 0 ? cls[i - L.cols] : SKY;
    cap[i] = up !== cls[i] && (up === SKY || cls[i] === VEG || cls[i] === GRS) ? 1 : 0;
  }
  return { cols: L.cols, rows: L.rows, light: L.chars, dark: L.charsDark || L.chars, rgb, cls, glow, cap };
}

const CSS = `
:host{display:block;position:relative;width:100%;color:inherit;font:inherit}
.stage{position:relative;width:100%}
canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
.bar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:center;margin-top:12px;font-size:12px;line-height:1}
.grp{display:flex;gap:4px;flex-wrap:wrap;justify-content:center}
button{font:inherit;font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid color-mix(in srgb,currentColor 20%,transparent);background:transparent;color:inherit;cursor:pointer;opacity:.7;transition:opacity .15s,border-color .15s}
button:hover{opacity:1}
button[aria-pressed="true"]{opacity:1;border-color:color-mix(in srgb,currentColor 70%,transparent)}
button:focus-visible{outline:2px solid currentColor;outline-offset:2px}
.st{opacity:.6;font-variant-numeric:tabular-nums;min-width:12ch;text-align:center}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
`;

class AsciiScene extends HTMLElement {
  static get observedAttributes() {
    return ["src", "theme", "time", "weather", "weather-src", "controls", "density", "fade", "lat", "lon", "timezone", "cycle-seconds", "label"];
  }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._root.innerHTML = `<style>${CSS}</style>
      <div class="stage" part="stage" role="img">
        <canvas part="canvas" data-l="sky"></canvas><canvas part="canvas" data-l="scene"></canvas><canvas part="canvas" data-l="fx"></canvas>
      </div><div class="sr" aria-live="polite"></div>`;
    this._stage = this._root.querySelector(".stage");
    this._stage.style.aspectRatio = "3 / 2";        // reserve space before the scene loads (avoids layout shift)
    const cs = this._root.querySelectorAll("canvas");
    this._cv = { sky: cs[0], scene: cs[1], fx: cs[2] };
    this._ctx = { sky: cs[0].getContext("2d"), scene: cs[1].getContext("2d"), fx: cs[2].getContext("2d") };
    this._live = { code: null, at: 0 };
    this._visible = true;
    this._raf = 0;
    this._last = 0;
    this._sceneKey = "";
    this._bolt = null;
    this._nextBolt = 0;
    this._gust = null;       // Quarterly: pointer gust over the trees
    this._sprites = [];      // Quarterly: shooting stars and birds
    this._lastPtr = null;
  }

  // ----- lifecycle -----
  connectedCallback() {
    this._connected = true;
    this._readOpts();
    this._loadFont();
    this._ro = new ResizeObserver(() => this._layout());
    this._ro.observe(this);
    this._io = new IntersectionObserver((e) => { this._visible = e[0].isIntersecting; this._kick(); });
    this._io.observe(this);
    this._onVis = () => this._kick();
    document.addEventListener("visibilitychange", this._onVis);
    this._mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    this._onMq = () => this._kick();
    this._mq.addEventListener?.("change", this._onMq);
    // Quarterly: pointer interaction
    this._onPtrMove = (e) => this._pointerMove(e);
    this._onPtrDown = (e) => this._pointerDown(e);
    this._stage.addEventListener("pointermove", this._onPtrMove);
    this._stage.addEventListener("pointerdown", this._onPtrDown);
    if (this._data) this._init(); else this._load();
  }
  disconnectedCallback() {
    this._connected = false;
    cancelAnimationFrame(this._raf); clearTimeout(this._timer);
    this._ro?.disconnect(); this._io?.disconnect();
    document.removeEventListener("visibilitychange", this._onVis);
    this._mq?.removeEventListener?.("change", this._onMq);
    this._stage.removeEventListener("pointermove", this._onPtrMove);
    this._stage.removeEventListener("pointerdown", this._onPtrDown);
  }
  attributeChangedCallback(name, oldV, newV) {
    if (oldV === newV || !this._connected) return;
    if (name === "src") { this._load(); return; }
    this._readOpts();
    if (name === "controls") this._buildBar();
    if (name === "weather" && this._opts.weather === "auto") this._fetchWeather();
    this._sceneKey = "";
    this._layout();
    this._syncBar();
    this._emit();
  }
  set data(d) { this._data = d; if (this.isConnected) this._init(); }
  get data() { return this._data; }
  setTime(v) { this.setAttribute("time", v); }
  setWeather(v) { this.setAttribute("weather", v); }

  // ----- options -----
  _readOpts() {
    const a = (n, d) => this.getAttribute(n) ?? d;
    const time = a("time", "auto").trim().toLowerCase();
    const weather = a("weather", "auto").trim().toLowerCase();
    this._opts = {
      theme: a("theme", "paper") === "dark" ? "dark" : "paper",
      time: TIME_PRESETS.includes(time) || /^\d{1,2}:\d{2}$/.test(time) ? time : "auto",
      weather: WEATHERS.includes(weather) ? weather : "auto",
      controls: this.hasAttribute("controls") && this.getAttribute("controls") !== "false",
      density: DENSITY[a("density", "medium")] || parseFloat(a("density", "")) || DENSITY.medium,
      fade: clamp(parseFloat(a("fade", "0.12")) || 0, 0, 0.4),
      lat: parseFloat(a("lat", "41.7886")), lon: parseFloat(a("lon", "-87.5987")),
      tz: a("timezone", "America/Chicago"),
      cycle: Math.max(5, parseFloat(a("cycle-seconds", "40")) || 40),
      fmt: new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: a("timezone", "America/Chicago") }),
      weatherSrc: a("weather-src", ""),   // Quarterly: the site's own weather endpoint
      label: a("label", "Animated ASCII-art scene of Rockefeller Chapel at the University of Chicago, following the time of day and the weather"),
    };
    this._stage.setAttribute("aria-label", this._opts.label);
  }
  _readStyle() {
    const cs = getComputedStyle(this);
    const num = (n, d) => { const v = parseFloat(cs.getPropertyValue(n)); return Number.isFinite(v) ? v : d; };
    const dflt = this._opts.theme === "dark" ? [0.06, 0.06, 0.09] : [0.957, 0.937, 0.902];
    this._style = {
      paper: parseColor(cs.getPropertyValue("--ascii-paper"), dflt),
      ink: parseColor(cs.getPropertyValue("--ascii-ink"), [0.169, 0.165, 0.2]),
      inkMix: clamp(num("--ascii-ink-mix", 0.12)),
      sat: clamp(num("--ascii-saturation", 1), 0, 2),
      contrast: clamp(num("--ascii-contrast", 1), 0.5, 1.5),
    };
  }

  // ----- loading -----
  _loadFont() {
    if (AsciiScene._font) return;
    try {
      const ff = new FontFace(FONT_NAME, `url(${FONT_DATA})`);
      AsciiScene._font = ff.load().then((f) => { document.fonts.add(f); }).catch(() => {});
    } catch { AsciiScene._font = Promise.resolve(); }
  }
  async _load() {
    const src = this.getAttribute("src");
    if (!src) return;
    try {
      const r = await fetch(src);
      this._data = await r.json();
      this._init();
    } catch (e) { console.warn("<ascii-scene> could not load", src, e); }
  }
  async _init() {
    await AsciiScene._font;
    this._levels = this._data.levels.map(decodeLevel).sort((a, b) => a.cols - b.cols);
    this._lamps = this._data.lamps || [];
    this._buildBar();
    if (this._opts.weather === "auto") this._fetchWeather();
    this._sceneKey = "";
    this._layout();
    this._syncBar();
    this._kick();
  }
  async _fetchWeather() {
    if (Date.now() - this._live.at < 15 * 60 * 1000 && this._live.code !== null) return;
    this._live.at = Date.now();
    try {
      const { lat, lon, weatherSrc } = this._opts;
      // Quarterly: prefer the site's own endpoint ({weather_code, cloud_cover}).
      const r = await fetch(weatherSrc || `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=weather_code,cloud_cover`);
      if (!r.ok) throw new Error(`weather ${r.status}`);
      const j = await r.json();
      const cur = j.current ?? j;
      this._live.code = cur.weather_code ?? null;
      this._live.cover = cur.cloud_cover ?? null;
      this._sceneKey = "";
      this._syncBar();
      this._emit();
    } catch { this._live.code = null; }   // offline or blocked: fall back to clear skies
  }
  _weatherName() {
    if (this._opts.weather !== "auto") return this._opts.weather;
    const c = this._live.code;
    if (c === null || c === undefined) return "clear";
    if (c >= 95) return "storm";
    if ((c >= 71 && c <= 77) || c === 85 || c === 86) return "snow";
    if ((c >= 51 && c <= 67) || (c >= 80 && c <= 82)) return "rain";
    if (c === 45 || c === 48) return "fog";
    if (c >= 2) return "cloudy";
    return "clear";
  }

  // ----- controls -----
  _buildBar() {
    this._bar?.remove();
    this._bar = null;
    if (!this._opts.controls || !this._levels) return;
    const bar = document.createElement("div");
    bar.className = "bar"; bar.setAttribute("part", "controls");
    const mk = (label, items, attr) => {
      const g = document.createElement("div");
      g.className = "grp"; g.setAttribute("role", "group"); g.setAttribute("aria-label", label);
      items.forEach(([v, t]) => {
        const b = document.createElement("button");
        b.type = "button"; b.textContent = t; b.dataset[attr] = v; b.setAttribute("part", "button");
        b.addEventListener("click", () => this.setAttribute(attr === "t" ? "time" : "weather", v));
        g.appendChild(b);
      });
      return g;
    };
    bar.appendChild(mk("Time of day", [["auto", "Now"], ["cycle", "Cycle"], ["dawn", "Dawn"], ["noon", "Noon"], ["golden", "Golden"], ["dusk", "Dusk"], ["night", "Night"]], "t"));
    bar.appendChild(mk("Weather", [["auto", "Live"], ["clear", "Clear"], ["cloudy", "Cloudy"], ["rain", "Rain"], ["storm", "Storm"], ["snow", "Snow"], ["fog", "Fog"]], "w"));
    const st = document.createElement("span");
    st.className = "st"; st.setAttribute("part", "status");
    bar.appendChild(st);
    this._root.appendChild(bar);
    this._bar = bar;
  }
  _syncBar() {
    if (!this._bar) return;
    this._bar.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.t !== undefined ? b.dataset.t === this._opts.time : b.dataset.w === this._opts.weather;
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  _status(date, wname) {
    const t = this._opts.fmt.format(date);
    const s = `${t} · ${wname}`;
    if (this._bar) { const st = this._bar.querySelector(".st"); if (st.textContent !== s) st.textContent = s; }
  }
  _emit() {
    this.dispatchEvent(new CustomEvent("ascii-scene:change", { detail: { time: this._opts.time, weather: this._weatherName(), theme: this._opts.theme } }));
  }

  // ----- layout -----
  _layout() {
    if (!this._levels) return;
    this._readStyle();
    const W = this.clientWidth || 600;
    let lv = this._levels[0];
    for (const L of this._levels) if (W / L.cols >= this._opts.density) lv = L;
    this._lv = lv;
    // On narrow screens keep characters legible by showing a window centered on the subject
    let view = lv.cols;
    const minCell = this._opts.density * 0.8;
    if (W / lv.cols < minCell) view = Math.max(Math.floor(W / minCell), Math.floor(lv.cols * 0.45));
    const center = this._data.focus ?? 0.42;
    const x0 = Math.round(clamp(center * lv.cols - view / 2, 0, lv.cols - view));
    this._view = { x0, x1: x0 + view };
    const cw = W / view, ch = cw * 2, H = ch * lv.rows;
    this._stage.style.aspectRatio = "auto";
    this._stage.style.height = `${H}px`;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    for (const k of ["sky", "scene", "fx"]) {
      const c = this._cv[k];
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      const g = this._ctx[k];
      g.setTransform(dpr, 0, 0, dpr, -x0 * cw * dpr, 0);
      g.font = `${cw / (this._data.adv || 0.602)}px ${FONT_NAME}, ui-monospace, Menlo, Consolas, monospace`;
      g.textBaseline = "alphabetic";
    }
    this._geo = { W: lv.cols * cw, H, cw, ch, base: ch * (this._data.baseline || 0.76) };
    // edge fade mask (cells outside the visible window get 0 and are skipped)
    const n = lv.cols * lv.rows, f = new Float32Array(n), fd = this._opts.fade;
    for (let y = 0; y < lv.rows; y++) for (let x = 0; x < lv.cols; x++) {
      if (x < x0 || x >= x0 + view) continue;
      const xf = (x - x0 + 0.5) / view, yf = (y + 0.5) / lv.rows;
      f[y * lv.cols + x] = fd <= 0 ? 1 : smooth(0, fd * 0.85, xf) * smooth(0, fd * 0.85, 1 - xf) * smooth(0, fd * 1.1, yf) * smooth(0, fd * 0.9, 1 - yf);
    }
    this._fadeMask = f;
    this._sceneKey = "";
    this._frame(performance.now(), true);
  }

  // ----- time + light -----
  _date(now) {
    const o = this._opts, tz = o.tz, d = new Date(now);
    if (o.time === "auto") return d;
    if (o.time === "cycle") {
      const start = wallTime(d, tz, 0, 0).getTime();
      return new Date(start + ((performance.now() / 1000 / o.cycle) % 1) * 86400000);
    }
    if (/^\d{1,2}:\d{2}$/.test(o.time)) { const [h, m] = o.time.split(":").map(Number); return wallTime(d, tz, h, m); }
    const ev = this._solarEvents(d);
    const H = 3600000;
    const at = { dawn: ev.rise - 0.3 * H, morning: ev.rise + 2 * H, noon: ev.noon, golden: ev.set - 0.55 * H, dusk: ev.set + 0.3 * H, night: ev.set + 4 * H }[o.time];
    return new Date(at);
  }
  _solarEvents(d) {
    const key = tzParts(d, this._opts.tz);
    const k = `${key.year}-${key.month}-${key.day}|${this._opts.lat}|${this._opts.lon}`;
    if (this._evKey === k) return this._ev;
    const start = wallTime(d, this._opts.tz, 0, 0).getTime();
    let rise = start + 6 * 3600000, set = start + 18 * 3600000, noon = start + 12 * 3600000, best = -99, prev = null;
    for (let t = start; t <= start + 86400000; t += 300000) {
      const e = solar(new Date(t), this._opts.lat, this._opts.lon).el;
      if (e > best) { best = e; noon = t; }
      if (prev !== null && prev < -0.83 && e >= -0.83) rise = t;
      if (prev !== null && prev >= -0.83 && e < -0.83) set = t;
      prev = e;
    }
    this._evKey = k; this._ev = { rise, set, noon };
    return this._ev;
  }
  _light(date) {
    const o = this._opts, wname = this._weatherName(), W = WEATHER[wname];
    const sun = solar(date, o.lat, o.lon);
    const moon = solar(new Date(date.getTime() + 12 * 3600000), o.lat, o.lon);
    const el = sun.el;
    const sky = skyAt(el);
    const day = smooth(-6, 6, el);                     // 0 night .. 1 day
    const night = 1 - smooth(-10, -1, el);             // lamps and windows on
    const keyI = smooth(-3, 12, el) * 0.78 * W.key;
    const low = 1 - smooth(2, 25, el);
    const keyCol = mix([1, 0.97, 0.92], [1, 0.62, 0.38], low);
    const ambI = lerp(0.24, 0.36, day) * W.amb;
    const ambCol = mix([0.5, 0.6, 1.05], [0.85, 0.9, 1.0], day);
    // weather turns the sky toward a lit gray
    const grayL = lerp(0.12, 0.72, day) * (wname === "snow" ? 1.08 : 1);
    const gray = [grayL * 0.97, grayL, grayL * 1.06];
    const top = mix(sky.top, gray, W.gray), hor = mix(sky.hor, gray, W.gray * 0.9);
    const cloudLit = mix([0.88, 0.89, 0.94], [1.0, 0.98, 0.96], day);
    const cloudCol = mix(mix(cloudLit, sky.hor, 0.4 * low * day + 0.2), gray, W.gray);
    const cloud = this._opts.weather === "auto" && this._live.cover != null ? lerp(W.cloud, this._live.cover / 100, 0.5) : W.cloud;
    const px = (az) => (az >= 180 ? 0.68 + ((az - 180) / 70) * 0.24 : 0.68 - ((180 - az) / 70) * 0.56);
    const py = (e) => HORIZON - (clamp(e, -10, 70) / 70) * (HORIZON - 0.07);
    return {
      wname, W, el, day, night, keyI, keyCol, ambI, ambCol, top, hor, cloud, cloudCol,
      sun: { x: px(sun.az), y: py(el), vis: W.cloud < 0.7 && el > -3, col: mix([1, 0.86, 0.55], [1, 0.48, 0.24], low) },
      moon: { x: px(moon.az), y: py(moon.el), vis: W.cloud < 0.7 && moon.el > 0 && night > 0.4 },
      fogCol: mix([0.25, 0.27, 0.34], [0.86, 0.86, 0.88], day),
    };
  }

  // color for one scene (non-sky) cell, before theme conversion
  _cellColor(lv, i, x, y, Lt, flash) {
    const W = Lt.W, cls = lv.cls[i];
    let r = lv.rgb[i * 3], g = lv.rgb[i * 3 + 1], b = lv.rgb[i * 3 + 2];
    if (W.wet) { r *= 0.8; g *= 0.82; b *= 0.86; if (cls === PTH) { r += 0.05; g += 0.07; b += 0.12; } }
    const F0 = Lt.keyI * Lt.keyCol[0] + Lt.ambI * Lt.ambCol[0];
    const F1 = Lt.keyI * Lt.keyCol[1] + Lt.ambI * Lt.ambCol[1];
    const F2 = Lt.keyI * Lt.keyCol[2] + Lt.ambI * Lt.ambCol[2];
    // at night flatten the baked-in daylight shading a bit
    const l = lum([r, g, b]), fl = 0.45 * (1 - Lt.day);
    r = lerp(r, l, fl); g = lerp(g, l, fl); b = lerp(b, l, fl);
    let c = [r * F0 * 1.25, g * F1 * 1.25, b * F2 * 1.25];
    const yf = (y + 0.5) / lv.rows;
    if (cls === BLD && Lt.night > 0) {               // warm floodlight from the base
      const h = clamp((BLD_BASE - yf) / 0.7), up = Lt.night * 0.55 * Math.pow(1 - h, 2.2) * (0.5 + l);
      c = [c[0] + 1.0 * up, c[1] + 0.68 * up, c[2] + 0.38 * up];
    }
    if (W.snow) {
      const s = cls === GRS ? 0.85 : cls === PTH ? 0.55 : lv.cap[i] ? 0.8 : cls === VEG ? 0.22 : 0.12;
      const sc = [0.92 * (Lt.ambI * 2.2 + Lt.keyI * 0.5), 0.94 * (Lt.ambI * 2.2 + Lt.keyI * 0.5), 1.0 * (Lt.ambI * 2.2 + Lt.keyI * 0.5)];
      c = mix(c, sc, s);
    }
    if (W.desat) { const m = lum(c); c = mix(c, [m, m, m], W.desat * 0.6); }
    const gl = lv.glow[i];
    if (gl && Lt.night > 0.02) {
      const tint = gl === 1 ? STAINED[Math.floor(hash(x * 0.37, y * 0.71) * STAINED.length)].map((v) => v / 255) : [1, 0.74, 0.38];
      c = mix(c, tint, Lt.night * (gl === 1 ? 0.92 : 0.85));
    }
    if (W.fog) {
      const depth = cls === GRS || cls === PTH ? clamp(1 - (yf - BLD_BASE) / (1 - BLD_BASE)) * 0.7 : cls === BLD ? 0.85 : 0.7;
      c = mix(c, Lt.fogCol, W.fog * depth);
    }
    if (flash) c = mix(c, [0.95, 0.95, 1], flash * 0.5);
    return c;
  }

  // theme conversion: light (emitted) color -> CSS color string
  _out(c, fadeK) {
    const S = this._style;
    let r, g, b, sat = S.sat;
    if (this._opts.theme === "dark") {
      const e = this._expo || 1;
      r = Math.pow(clamp(c[0] * e), 0.8); g = Math.pow(clamp(c[1] * e), 0.8); b = Math.pow(clamp(c[2] * e), 0.8);
    } else {
      [r, g, b] = inkOf(clamp(c[0]), clamp(c[1]), clamp(c[2]), S.contrast);
    }
    if (sat !== 1) { const m = 0.299 * r + 0.587 * g + 0.114 * b; r = m + (r - m) * sat; g = m + (g - m) * sat; b = m + (b - m) * sat; }
    if (S.inkMix > 0) { r = lerp(r, S.ink[0], S.inkMix); g = lerp(g, S.ink[1], S.inkMix); b = lerp(b, S.ink[2], S.inkMix); }
    if (fadeK < 1) { const k = (1 - fadeK) * 0.55; r = lerp(r, S.paper[0], k); g = lerp(g, S.paper[1], k); b = lerp(b, S.paper[2], k); }
    const key = (((clamp(r) * 63) | 0) << 12) | (((clamp(g) * 63) | 0) << 6) | ((clamp(b) * 63) | 0);
    return COLOR_CACHE[key] || (COLOR_CACHE[key] = `rgb(${(key >> 12) * 4.05 | 0},${((key >> 6) & 63) * 4.05 | 0},${(key & 63) * 4.05 | 0})`);
  }
  _keep(i, x, y) { const f = this._fadeMask[i]; return f >= 1 || (f > 0 && hash(x + 0.31, y + 0.77) < Math.pow(f, 0.75)); }

  // ----- interaction (Quarterly) -----
  _cellAt(e) {
    if (!this._geo || !this._view) return null;
    const r = this._stage.getBoundingClientRect();
    return { x: this._view.x0 + (e.clientX - r.left) / this._geo.cw, y: (e.clientY - r.top) / this._geo.ch };
  }
  _pointerMove(e) {
    if (this._mq?.matches || !this._lv) return;
    const c = this._cellAt(e), now = performance.now() / 1000;
    if (!c) return;
    const prev = this._lastPtr;
    this._lastPtr = { x: c.x, y: c.y, t: now };
    if (!prev || now - prev.t > 0.25) return;
    const dx = c.x - prev.x, dy = (c.y - prev.y) * 2;
    const speed = Math.hypot(dx, dy) / Math.max(now - prev.t, 1 / 120);
    if (speed < 18) return;   // a slow pointer is not a gust
    const g = this._gust, keep = g && now - g.t0 < 0.4 ? g.power * 0.9 : 0;
    this._gust = { x: c.x, y: c.y, dir: Math.sign(dx) || 1, power: Math.max(clamp(speed / 90, 0.35, 1), keep), t0: now };
  }
  _pointerDown(e) {
    if (this._mq?.matches || !this._lv || !this._Lt) return;
    const c = this._cellAt(e), now = performance.now() / 1000;
    if (!c) return;
    const sky = Math.floor(this._lv.rows * HORIZON);
    if (this._sprites.length > 6) this._sprites.shift();
    if (this._Lt.night > 0.4 && this._Lt.W.cloud < 0.85) {
      // a shooting star falls from above the click, across the sky
      const dir = c.x > (this._view.x0 + this._view.x1) / 2 ? -1 : 1;
      this._sprites.push({ kind: "meteor", x: c.x, y: Math.min(c.y, sky * 0.45), dir, t0: now, life: 1.2 });
    } else {
      // by day a few birds take off from where you clicked
      const dir = c.x > (this._view.x0 + this._view.x1) / 2 ? 1 : -1;
      this._sprites.push({ kind: "birds", x: c.x, y: Math.min(c.y, sky * 0.8), dir, n: 3 + Math.floor(Math.random() * 3), t0: now, life: 2.6 });
    }
  }
  // horizontal offset (in cells) of a tree cell during a gust
  _gustAt(x, y, t) {
    const g = this._gust;
    if (!g) return 0;
    const age = t - g.t0;
    if (age > 1.6 || age < 0) return 0;
    const R = 16, d = Math.hypot(x - g.x, (y - g.y) * 2);
    if (d > R) return 0;
    const decay = Math.exp(-age * 2.2), fall = 1 - d / R;
    // the leaves lean with the sweep, then rock back and forth as it dies away
    return Math.round((g.dir * 1.6 * Math.cos(age * 7 + y * 0.35) + 0.6 * Math.sin(age * 13 + x * 0.4)) * g.power * fall * decay);
  }

  // ----- drawing -----
  _drawScene(Lt, flash, t = 0) {
    const lv = this._lv, g = this._ctx.scene, { W, H, cw, ch, base } = this._geo;
    g.clearRect(-1, -1, W + 2, H + 2);
    const chars = this._opts.theme === "dark" ? lv.dark : lv.light;
    for (let y = 0; y < lv.rows; y++) for (let x = 0; x < lv.cols; x++) {
      const i = y * lv.cols + x;
      if (lv.cls[i] === SKY) continue;
      const chr = chars[i];
      if (chr === " " || !this._keep(i, x, y)) continue;
      g.fillStyle = this._out(this._cellColor(lv, i, x, y, Lt, flash), this._fadeMask[i]);
      const off = this._gust && lv.cls[i] === VEG ? this._gustAt(x, y, t) : 0;   // Quarterly: sway
      g.fillText(chr, (x + off) * cw, y * ch + base);
    }
  }
  _drawSky(Lt, t, flash) {
    const lv = this._lv, g = this._ctx.sky, { W, H, cw, ch, base } = this._geo, dark = this._opts.theme === "dark";
    g.clearRect(-1, -1, W + 2, H + 2);
    const thr = 1 - Lt.cloud * 0.85, wind = Lt.W.rain ? 0.09 : 0.035;
    const aspect = cw / ch;
    for (let y = 0; y < lv.rows; y++) {
      const yf = (y + 0.5) / lv.rows, ry = Math.pow(clamp(yf / HORIZON), 1.25);
      const S = mix(Lt.top, Lt.hor, ry);
      for (let x = 0; x < lv.cols; x++) {
        const i = y * lv.cols + x;
        if (lv.cls[i] !== SKY || !this._keep(i, x, y)) continue;
        const xf = (x + 0.5) / lv.cols;
        let c = S, special = null;
        // stars
        if (Lt.night > 0.45 && Lt.W.cloud < 0.7 && yf < HORIZON - 0.06 && hash(x, y) < 0.016) {
          special = hash(x, y + Math.floor(t * 2.5)) > 0.3 ? "*" : "+";
          c = dark ? [1, 0.95, 0.8] : [0.95, 0.78, 0.36];
        }
        // sun and moon disks (distance measured in pixels so they stay round)
        if (Lt.sun.vis) {
          const dx = (xf - Lt.sun.x) * W, dy = (yf - Lt.sun.y) * H, d = Math.hypot(dx, dy) / (ch * 1.6);
          if (d < 1) { special = d < 0.55 ? "@" : "O"; c = Lt.sun.col; }
          else if (d < 2.2) { const k = 1 - (d - 1) / 1.2; c = mix(c, Lt.sun.col, 0.75 * k); if (hash(x, y) < 0.5 * k) special = d < 1.5 ? "*" : "+"; }
        }
        if (Lt.moon.vis) {
          const dx = (xf - Lt.moon.x) * W, dy = (yf - Lt.moon.y) * H, r = ch * 1.15;
          if (Math.hypot(dx, dy) < r && Math.hypot(dx + r * 0.55, dy + r * 0.2) > r * 0.95) { special = "@"; c = dark ? [0.93, 0.92, 1] : [0.96, 0.86, 0.55]; }
        }
        // clouds drift over everything in the sky
        const cn = fbm((x * aspect * 0.09) - t * wind, y * 0.13 + 3.7);
        const cd = smooth(thr, thr + 0.22, cn) * (0.35 + 0.65 * clamp(Lt.cloud * 1.6));
        if (cd > 0.02) { c = mix(c, mix(Lt.cloudCol, S, 0.25 * (1 - cn)), cd); if (cd > 0.5) special = null; }
        if (flash) c = mix(c, dark ? [0.92, 0.9, 1] : [0.99, 0.98, 1], flash * 0.85);
        let chr;
        const tex = (vnoise(x * 0.07 + t * 0.03, y * 0.55) * 0.65 + vnoise(x * 0.23 - t * 0.05, y * 0.9 + 9) * 0.35 - 0.5) * 0.3;
        if (special) chr = special;
        else if (dark) {
          const v = clamp(lum(c) * 0.62 + tex, 0, 0.9);
          chr = SKY_RAMP[Math.min(SKY_RAMP.length - 1, Math.floor(v * SKY_RAMP.length))];
        } else {
          const chroma = Math.max(c[0], c[1], c[2]) - Math.min(c[0], c[1], c[2]);
          const warmth = clamp(c[0] - c[2]) * ry;
          const v = clamp((0.55 * (1 - lum(c)) + 0.45 * chroma - 0.12) * 0.95 + 0.6 * warmth + cd * Lt.W.gray * 0.32 + 0.28 * (1 - Lt.day) + tex, 0, 0.74);
          chr = SKY_RAMP[Math.min(SKY_RAMP.length - 1, Math.floor(v * SKY_RAMP.length))];
        }
        if (chr === " ") continue;
        g.fillStyle = this._out(c, this._fadeMask[i]);
        g.fillText(chr, x * cw, y * ch + base);
      }
    }
  }
  _drawFx(Lt, t, flash) {
    const lv = this._lv, g = this._ctx.fx, { W, H, cw, ch, base } = this._geo, dark = this._opts.theme === "dark", Wt = Lt.W;
    g.clearRect(-1, -1, W + 2, H + 2);
    // street lamps
    if (Lt.night > 0.05) {
      for (const [lx0, ly0] of this._lamps) {
        const lx = lx0 * lv.cols, ly = ly0 * lv.rows;
        for (let y = Math.floor(ly - 3); y <= ly + 3; y++) for (let x = Math.floor(lx - 6); x <= lx + 6; x++) {
          if (x < 0 || y < 0 || x >= lv.cols || y >= lv.rows) continue;
          const d = Math.hypot((x + 0.5 - lx) * cw, (y + 0.5 - ly) * ch) / (ch * 2.4);
          if (d >= 1) continue;
          const i = y * lv.cols + x;
          if (!this._keep(i, x, y)) continue;
          const k = Lt.night * (1 - d), fl = 0.9 + 0.1 * Math.sin(t * 7 + lx);
          if (d > 0.35 && hash(x * 1.7, y * 2.3) > k * 1.3) continue;
          const chr = d < 0.18 ? "@" : d < 0.4 ? "*" : d < 0.7 ? "+" : ".";
          g.globalAlpha = clamp(k * 1.4 * fl);
          g.fillStyle = this._out(dark ? [1, 0.82, 0.5] : [1, 0.72, 0.28], this._fadeMask[i]);
          g.fillText(chr, x * cw, y * ch + base);
        }
      }
      g.globalAlpha = 1;
    }
    // rain
    if (Wt.rain) {
      g.fillStyle = this._out(dark ? [0.55, 0.7, 0.92] : [0.45, 0.55, 0.78], 1);
      const sp = Wt.bolt ? 30 : 24;
      for (let y = 0; y < lv.rows; y++) for (let x = 0; x < lv.cols; x++) {
        const xs = x + Math.floor(y * 0.5), k = Math.floor(y - t * sp + hash(xs, 1) * 60);
        if (hash(xs, k) < Wt.rain && this._keep(y * lv.cols + x, x, y)) g.fillText("/", x * cw, y * ch + base);
      }
    }
    // snow
    if (Wt.flakes) {
      g.fillStyle = this._out(dark ? [0.95, 0.96, 1] : [0.62, 0.7, 0.86], 1);
      for (let y = 0; y < lv.rows; y++) {
        const sway = Math.round(Math.sin(t * 1.1 + y * 0.35) * 1.2);
        for (let x = 0; x < lv.cols; x++) {
          const xs = x + sway, k = Math.floor(y - t * 4.5 + hash(xs, 2) * 60);
          if (hash(xs + 0.5, k) < Wt.flakes && this._keep(y * lv.cols + x, x, y)) g.fillText(hash(xs, k + 1) < 0.5 ? "*" : ".", x * cw, y * ch + base);
        }
      }
    }
    // drifting fog banks
    if (Wt.fog) {
      g.fillStyle = this._out(dark ? [0.7, 0.72, 0.78] : [0.62, 0.64, 0.7], 1);
      for (let y = Math.floor(lv.rows * 0.35); y < lv.rows; y++) for (let x = 0; x < lv.cols; x++) {
        const v = fbm(x * 0.035 - t * 0.06, y * 0.22);
        if (v > 0.6 && hash(x, y + Math.floor(t)) < (v - 0.6) * 3 && this._keep(y * lv.cols + x, x, y)) {
          g.globalAlpha = clamp((v - 0.6) * 4) * 0.8;
          g.fillText(v > 0.7 ? "~" : "-", x * cw, y * ch + base);
        }
      }
      g.globalAlpha = 1;
    }
    // lightning bolt
    if (this._bolt && t < this._bolt.until) {
      g.fillStyle = this._out(dark ? [1, 1, 1] : [0.42, 0.34, 0.85], 1);
      for (const [x, y, c] of this._bolt.path) g.fillText(c, x * cw, y * ch + base);
    }
    // Quarterly: shooting stars and birds from clicks
    if (this._sprites.length) {
      const now = performance.now() / 1000;
      this._sprites = this._sprites.filter((s) => now - s.t0 < s.life);
      for (const s of this._sprites) {
        const p = (now - s.t0) / s.life;
        if (s.kind === "meteor") {
          const hx = s.x + s.dir * p * lv.cols * 0.32, hy = s.y + p * lv.rows * 0.22;
          g.fillStyle = this._out(dark ? [1, 0.97, 0.85] : [0.98, 0.78, 0.36], 1);
          for (let k = 0; k < 10; k++) {
            const x = Math.round(hx - s.dir * k * 1.6), y = Math.round(hy - k * 0.55);
            if (x < 0 || y < 0 || x >= lv.cols || y >= lv.rows) continue;
            g.globalAlpha = clamp((1 - k / 10) * (1 - Math.max(0, p - 0.7) / 0.3));
            g.fillText(k === 0 ? "*" : k < 3 ? (s.dir < 0 ? "/" : "\\") : k < 6 ? "-" : ".", x * cw, y * ch + base);
          }
        } else {
          g.fillStyle = this._out(dark ? [0.85, 0.85, 0.9] : [0.22, 0.21, 0.26], 1);
          for (let i = 0; i < s.n; i++) {
            const x = Math.round(s.x + s.dir * (p * lv.cols * 0.38 + i * 2.2));
            const y = Math.round(s.y - p * lv.rows * 0.18 - (i % 2) * 1.2 + Math.sin(p * 9 + i) * 0.6);
            if (x < 0 || y < 0 || x >= lv.cols || y >= lv.rows) continue;
            g.globalAlpha = clamp(1.4 * (1 - p));
            g.fillText(Math.floor(now * 7 + i) % 2 ? "v" : "^", x * cw, y * ch + base);
          }
        }
      }
      g.globalAlpha = 1;
    }
  }
  _makeBolt(t) {
    const lv = this._lv, path = [];
    let x = Math.floor(lv.cols * (0.55 + Math.random() * 0.4));
    const end = Math.floor(lv.rows * HORIZON);
    for (let y = 0; y < end; y++) {
      const i = y * lv.cols + x;
      if (lv.cls[i] !== SKY) break;
      const step = Math.random() < 0.45 ? (Math.random() < 0.5 ? -1 : 1) : 0;
      path.push([x, y, step < 0 ? "/" : step > 0 ? "\\" : "|"]);
      x = clamp(x + step, 0, lv.cols - 1);
    }
    this._bolt = { path, until: t + 0.22, flashUntil: t + 0.12 };
  }

  _kick() {
    cancelAnimationFrame(this._raf); clearTimeout(this._timer);
    if (!this._lv) return;
    const reduced = this._mq?.matches;
    if (!this._visible || document.hidden) return;
    if (reduced) {
      this._frame(performance.now(), true);
      this._timer = setTimeout(() => this._kick(), 60000);
      return;
    }
    const loop = (ts) => {
      if (ts - this._last > 1000 / 22) { this._frame(ts); this._last = ts; }
      this._raf = requestAnimationFrame(loop);
    };
    this._raf = requestAnimationFrame(loop);
  }
  _frame(ts, force) {
    if (!this._lv) return;
    const reduced = this._mq?.matches;
    const t = reduced ? 0 : ts / 1000;
    const date = this._date(Date.now());
    const Lt = this._light(date);
    this._Lt = Lt;   // Quarterly: clicks need to know whether it is night
    if (Lt.W.bolt && !reduced) {
      if (!this._nextBolt) this._nextBolt = t + 2 + Math.random() * 4;
      if (t > this._nextBolt) { this._makeBolt(t); this._nextBolt = t + 3 + Math.random() * 6; }
    }
    const flash = this._bolt && t < this._bolt.flashUntil ? 1 : 0;
    this._expo = 1.35 + 1.4 * (1 - Lt.day) + 0.3 * Lt.W.gray;   // dark theme: keep night scenes readable
    const key = `${Math.round(Lt.el * 3)}|${Lt.wname}|${this._opts.theme}|${flash}|${this._lv.cols}|${this._geo.W}`;
    // Quarterly: while a gust lasts (and once after it) the trees are redrawn every frame
    const gusting = !!(this._gust && t - this._gust.t0 < 1.6);
    if (force || gusting || this._wasGusting || (key !== this._sceneKey && (flash || ts - (this._sceneAt || 0) > 150))) {
      this._sceneKey = key; this._sceneAt = ts; this._drawScene(Lt, flash, t);
    }
    this._wasGusting = gusting;
    this._drawSky(Lt, t, flash);
    this._drawFx(Lt, t, flash);
    this._status(date, Lt.wname);
    if (this._opts.weather === "auto" && Date.now() - this._live.at > 15 * 60 * 1000) this._fetchWeather();
  }
}

if (!customElements.get("ascii-scene")) customElements.define("ascii-scene", AsciiScene);
export { AsciiScene };

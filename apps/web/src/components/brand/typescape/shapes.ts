/**
 * The shapes a TypeScape draws with course titles (docs/BEST-OF-UCHICAGO-PLAN.md "Shared look").
 * Each shape is a field: for a point (x, y) in CSS pixels at time t (seconds) it returns how
 * strongly the titles there are drawn (`a`, 0..1) and their colour (`tone`: 0 ink, 1 maroon,
 * 2 light maroon / glass). The fields are sampled on a coarse grid every frame, so they stay
 * cheap: a few distance checks per point.
 */

export type ShapeName = "arch" | "orbit" | "river" | "arcade";

export interface Sample {
  a: number;
  tone: number;
}

export interface Frame {
  w: number;
  h: number;
  /** Horizontal centre of the figure, in CSS px. */
  cx: number;
  t: number;
}

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);
/** 1 inside, 0 outside, with a soft edge `soft` px wide (d < 0 is inside). */
const edge = (d: number, soft: number) => clamp01(0.5 - d / soft);

/** Signed distance-ish to an equilateral pointed arch (negative inside). */
function pointed(dx: number, y: number, half: number, spring: number): number {
  if (y >= spring) return Math.abs(dx) - half;
  const dl = Math.hypot(dx + half, y - spring) - half * 2;
  const dr = Math.hypot(dx - half, y - spring) - half * 2;
  return Math.max(dl, dr, Math.abs(dx) - half);
}

/** A Gothic window: a pointed arch with three lancets, mullions and a rose. */
function arch(x: number, y: number, f: Frame): Sample {
  const ww = Math.min(f.w * 0.36, f.h * 0.6, 520);
  const half = ww / 2;
  const bottom = f.h * 0.99;
  const top = f.h * 0.06;
  const spring = top + ww * 0.866; // the apex sits this far above the springing line
  if (y > bottom) return { a: 0, tone: 0 };
  const dx = x - f.cx;
  const d = pointed(dx, y, half, spring);
  let a = edge(d, 6);
  if (a <= 0) return { a: 0, tone: 0 };
  // Stone tracery: the frame, the mullions between the lancets and the rose's ring stay empty.
  const frame = edge(d + ww * 0.035, 3); // the stone frame line itself stays empty
  const mull = Math.min(Math.abs(dx - ww / 6), Math.abs(dx + ww / 6)) - ww * 0.012;
  const rose = { x: f.cx, y: spring - ww * 0.33, r: ww * 0.19 };
  const dRose = Math.hypot(x - rose.x, y - rose.y);
  const inRose = dRose < rose.r;
  const ring = Math.abs(dRose - rose.r) - ww * 0.012;
  const mullOk = y < spring || inRose ? 1 : edge(-mull, 2);
  a *= frame * mullOk * edge(-ring, 2);
  // Glass: the lancets glow maroon, and a slow beam of light crosses the window.
  const sweep = Math.sin(f.t * 0.12) * ww * 0.6;
  const beam = Math.exp(-(((dx + (y - f.h / 2) * 0.55 - sweep) / (ww * 0.22)) ** 2));
  const lancet = Math.floor((dx + half) / (ww / 3));
  const pane = (Math.floor((y - top) / (ww * 0.18)) + lancet) % 3;
  let tone = inRose ? 2 : pane === 0 ? 1.15 : pane === 1 ? 0.8 : 1.35;
  tone = tone * (1 - beam * 0.4) + 2 * beam * 0.4;
  return { a: a * (0.8 + beam * 0.2), tone };
}

/** An orrery: a maroon sun, three tilted rings of titles, and a planet travelling along each ring
 * that lights the letters it passes. The far half of each ring is dimmer: depth. */
function orbit(x: number, y: number, f: Frame): Sample {
  const cy = f.h * 0.5;
  const base = Math.min(f.h * 0.13, f.w * 0.08);
  const tilt = 0.78; // a slight perspective: the rings lie almost face on, so they read as rings
  const dx = x - f.cx;
  const dy = (y - cy) / tilt;
  const r = Math.hypot(dx, dy);
  // The sun: a disc with a lighter core.
  const sun = edge(r - base, 4);
  if (sun > 0) return { a: sun, tone: 1 + Math.max(0, 1 - r / base) * 0.9 };
  let best: Sample = { a: 0, tone: 0 };
  for (let k = 0; k < 3; k++) {
    const rk = base * (1.9 + k * 1.05);
    // At least ~1.5 rows of type tall where the ring runs across the page.
    const band = Math.max(base * 0.3, 15 / tilt);
    const ring = edge(Math.abs(r - rk) - band, 5);
    // The planet on ring k, moving at its own pace (outer rings slower).
    const ang = f.t * (0.22 / (1 + k * 0.7)) + k * 2.2;
    const px = f.cx + Math.cos(ang) * rk;
    const py = cy + Math.sin(ang) * rk * tilt;
    const pr = base * (0.62 - k * 0.08);
    const planet = edge(Math.hypot(x - px, y - py) - pr, 4);
    if (planet > best.a) best = { a: planet, tone: 1.85 - k * 0.25 };
    if (ring > best.a) {
      const far = y < cy ? 0.6 : 1;
      best = { a: ring * far * 0.92, tone: k === 1 ? 1 : 0.3 };
    }
  }
  return best;
}

/** A river: four bands of titles that swell and flow across the page. */
function river(x: number, y: number, f: Frame): Sample {
  let best: Sample = { a: 0, tone: 0 };
  for (let k = 0; k < 4; k++) {
    const amp = f.h * (0.09 + k * 0.02);
    const freq = (Math.PI * 2) / (f.w * (0.85 + k * 0.3));
    const wave = Math.sin(x * freq + f.t * (0.3 + k * 0.07) + k * 1.7);
    const cy = f.h * (0.16 + k * 0.23) + wave * amp;
    const thick = f.h * (0.07 + 0.025 * Math.sin(x * freq * 1.7 - f.t * 0.25 + k));
    const a = edge(Math.abs(y - cy) - thick, 9);
    const tones = [1, 2, 0.25, 1.4];
    if (a > best.a) best = { a, tone: tones[k] ?? 1 };
  }
  return best;
}

/** A cloister arcade: masonry of titles, pointed openings that glow like voices. */
function arcade(x: number, y: number, f: Frame): Sample {
  const n = Math.max(3, Math.round(f.w / 230));
  const bay = f.w / n;
  const i = Math.floor(x / bay);
  const lx = x - (i + 0.5) * bay;
  const half = bay * 0.34;
  const spring = f.h * 0.46;
  const roofline = spring - half * 1.732 - f.h * 0.1;
  if (y < roofline - 6) return { a: 0, tone: 0 }; // sky above the roof
  const d = pointed(lx, y, half, spring);
  if (d < 0) {
    // Inside an opening: the conversation glow, each bay breathing at its own pace.
    const glow = (Math.sin(f.t * 0.6 + i * 2.1) + 1) / 2;
    return { a: (0.2 + glow * 0.55) * edge(-d - 3, 4), tone: 2 };
  }
  const roof = edge(roofline - y, 6);
  const course = Math.abs(y - (roofline + f.h * 0.05)) < f.h * 0.022; // a maroon string course
  return { a: roof * 0.9, tone: course ? 1.2 : 0.1 };
}

export const SHAPES: Record<ShapeName, (x: number, y: number, f: Frame) => Sample> = {
  arch,
  orbit,
  river,
  arcade,
};

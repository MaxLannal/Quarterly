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

/** Orbits: tilted rings of titles around a maroon sun; a bright arc travels along each ring. */
function orbit(x: number, y: number, f: Frame): Sample {
  const cy = f.h * 0.52;
  const base = Math.min(f.h * 0.13, f.w * 0.08);
  const dx = x - f.cx;
  const dy = (y - cy) / 0.6; // flattened: the rings lie in a tilted plane
  const r = Math.hypot(dx, dy);
  if (r < base * 1.1) return { a: edge(r - base, 4), tone: 1.7 - (r / base) * 0.6 };
  const ang = Math.atan2(dy, dx);
  let best: Sample = { a: 0, tone: 0 };
  for (let k = 0; k < 4; k++) {
    const rk = base * (1.75 + k * 0.95);
    const band = base * (0.36 - k * 0.03);
    const a = edge(Math.abs(r - rk) - band, 5);
    if (a <= best.a) continue;
    const phase = ang - (f.t * 0.16) / (1 + k * 0.5) - k * 1.3;
    const arc = (Math.cos(phase) + 1) / 2; // 1 at the travelling bright point
    const depth = y < cy ? 0.7 : 1; // the far side of each ring is dimmer
    best = { a: a * depth * (0.55 + arc * 0.45), tone: arc > 0.82 ? 2 : arc > 0.45 ? 1 : 0.15 };
  }
  return best;
}

/** A river: four bands of titles that swell and flow across the page. */
function river(x: number, y: number, f: Frame): Sample {
  let best: Sample = { a: 0, tone: 0 };
  for (let k = 0; k < 4; k++) {
    const amp = f.h * (0.07 + k * 0.015);
    const freq = (Math.PI * 2) / (f.w * (0.9 + k * 0.35));
    const wave = Math.sin(x * freq + f.t * (0.35 + k * 0.08) + k * 1.7);
    const cy = f.h * (0.2 + k * 0.2) + wave * amp;
    const thick = f.h * (0.055 + 0.02 * Math.sin(x * freq * 1.7 - f.t * 0.3 + k));
    const a = edge(Math.abs(y - cy) - thick, 10);
    if (a > best.a) best = { a: a * (k % 2 ? 0.85 : 1), tone: k === 1 ? 2 : k % 2 ? 0.2 : 1 };
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

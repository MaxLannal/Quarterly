/**
 * The chapel drawing behind the homepage's course-title picture: one cell per character of the
 * finest ascii-scene level (190 x 63), each with the photo's graded colour, a scene class and a
 * stained-glass code. Built by tools/course-chapel/build.py into /home/course-chapel.json.
 */

export type Box = { x0: number; y0: number; x1: number; y1: number };

export type ChapelData = {
  version: 1;
  field: {
    cols: number;
    rows: number;
    /** width / height of the source image */
    aspect: number;
    /** where the ground meets the buildings, as a fraction of the image height */
    baseline: number;
    /** base64 RGB, 3 bytes per cell, row by row; sky cells are 0 */
    rgb: string;
    /** one digit per cell: 0 sky, 1 building, 2 foliage, 3 grass, 4 path */
    cls: string;
    /** one digit per cell: 1 stained glass, 2 warm window */
    glow: string;
  };
  /** the whole chapel, in image fractions */
  chapel: Box;
  /** the main facade with the two front spires, in image fractions */
  facade: Box;
  /** where the front meets the nave, and the nave the tower behind it (image fractions) */
  masses: { frontEnd: number; towerStart: number };
  /** [code, title] of real courses from data/seed, in a fixed shuffled order */
  courses: [string, string][];
};

export type Field = {
  cols: number;
  rows: number;
  aspect: number;
  baseline: number;
  rgb: Uint8Array;
  cls: Uint8Array;
  glow: Uint8Array;
  /** horizontal bands at each side that hold no building, used to extend the picture sideways */
  bandLeft: number;
  bandRight: number;
  /** the stone's brightness smoothed (mostly up and down, as the architecture is vertical): its
   * planes, read as height */
  height: Float32Array;
  /** the stone's brightness blurred widely, to sharpen the detail against (unsharp masking) */
  wide: Float32Array;
  /** slope of `height` per cell, to the right and down (for the light on the carving) */
  slopeX: Float32Array;
  slopeY: Float32Array;
  /** quantiles of the stone's brightness (planes and sharpened detail), for stoneRank() */
  stoneLevels: Float32Array;
  masses: { frontEnd: number; towerStart: number };
};

export const SKY = 0;
export const BUILDING = 1;
export const FOLIAGE = 2;
export const GRASS = 3;
export const PATH = 4;

function digits(s: string): Uint8Array {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i) - 48;
  return out;
}

function base64(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function isChapelData(v: unknown): v is ChapelData {
  if (!v || typeof v !== "object") return false;
  const d = v as Partial<ChapelData>;
  const f = d.field;
  return (
    d.version === 1 &&
    !!f &&
    typeof f.cols === "number" &&
    typeof f.rows === "number" &&
    typeof f.rgb === "string" &&
    f.cls?.length === f.cols * f.rows &&
    f.glow?.length === f.cols * f.rows &&
    Array.isArray(d.courses) &&
    d.courses.length > 0 &&
    !!d.chapel &&
    !!d.facade &&
    typeof d.masses?.frontEnd === "number"
  );
}

export function decodeField(data: ChapelData): Field {
  const f = data.field;
  const rgb = base64(f.rgb);
  if (rgb.length !== f.cols * f.rows * 3) throw new Error("chapel field: bad colour data");
  const cls = digits(f.cls);
  const lum = brightness(f.cols * f.rows, rgb, cls);
  const height = blur(f.cols, f.rows, lum, 0.6, 1.5);
  const wide = blur(f.cols, f.rows, lum, 3, 1.5);
  return {
    cols: f.cols,
    rows: f.rows,
    aspect: f.aspect,
    baseline: f.baseline,
    rgb,
    cls,
    glow: digits(f.glow),
    bandLeft: Math.max(0.04, data.chapel.x0 - 0.02),
    bandRight: Math.max(0.04, 1 - data.chapel.x1 - 0.02),
    height,
    wide,
    ...slopes(f.cols, f.rows, height),
    stoneLevels: stoneLevels(lum, cls, height, wide),
    masses: data.masses,
  };
}

const unit = (v: number, lo: number, hi: number) => Math.min(1, Math.max(0, (v - lo) / (hi - lo)));

/**
 * The stone's raw brightness at a point: its plane, and the carving's detail on it sharpened
 * against the wide blur, so window frames, buttresses and mouldings stand out from the wall.
 */
export function stoneRaw(plane: number, lum: number, wide: number): number {
  const sharp = lum + 1.3 * (lum - wide);
  return 0.35 * unit(plane, 0.2, 0.8) + 0.65 * unit(sharp, 0.1, 0.95);
}

function stoneLevels(lum: Float32Array, cls: Uint8Array, height: Float32Array, wide: Float32Array): Float32Array {
  const values: number[] = [];
  for (let i = 0; i < lum.length; i++) {
    if (cls[i] === BUILDING) values.push(stoneRaw(height[i]!, lum[i]!, wide[i]!));
  }
  values.sort((a, b) => a - b);
  const levels = new Float32Array(65);
  for (let q = 0; q <= 64; q++) levels[q] = values[Math.round(((values.length - 1) * q) / 64)] ?? q / 64;
  return levels;
}

/**
 * Where a raw stone brightness ranks among all the chapel's stone (0 darkest, 1 brightest). Using
 * the rank instead of the raw value spreads the stone evenly over the reds, so shadow, half light
 * and sun each get their share and the planes read apart.
 */
export function stoneRank(field: Field, raw: number): number {
  const l = field.stoneLevels;
  if (raw <= l[0]!) return 0;
  if (raw >= l[64]!) return 1;
  let lo = 0;
  let hi = 64;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (l[mid]! <= raw) lo = mid;
    else hi = mid;
  }
  const span = l[hi]! - l[lo]!;
  return (lo + (span > 0 ? (raw - l[lo]!) / span : 0)) / 64;
}

/** Central differences of a grid, over three cells, clamped (the carving's slope). */
function slopes(cols: number, rows: number, h: Float32Array): { slopeX: Float32Array; slopeY: Float32Array } {
  const slopeX = new Float32Array(h.length);
  const slopeY = new Float32Array(h.length);
  const at = (x: number, y: number) => h[Math.min(rows - 1, Math.max(0, y)) * cols + Math.min(cols - 1, Math.max(0, x))]!;
  const clamp = (v: number) => Math.min(0.3, Math.max(-0.3, v));
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      slopeX[y * cols + x] = clamp((at(x + 1, y) - at(x - 1, y)) / 2);
      slopeY[y * cols + x] = clamp((at(x, y + 1) - at(x, y - 1)) / 2);
    }
  }
  return { slopeX, slopeY };
}

/** Brightness of the building and trees per cell (sky is 0). */
function brightness(n: number, rgb: Uint8Array, cls: Uint8Array): Float32Array {
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    if (cls[i] === SKY) continue;
    out[i] = (0.2126 * rgb[i * 3]! + 0.7152 * rgb[i * 3 + 1]! + 0.0722 * rgb[i * 3 + 2]!) / 255;
  }
  return out;
}

/**
 * A Gaussian blur with its own reach sideways and up and down (in cells). Buttresses, windows
 * and spires run vertically, so the planes are blurred mostly up and down, which smooths the
 * noise and keeps their edges.
 */
function blur(cols: number, rows: number, src: Float32Array, sigmaX: number, sigmaY: number): Float32Array {
  const pass = (input: Float32Array, dx: number, dy: number, sigma: number) => {
    const radius = Math.max(1, Math.ceil(sigma * 2));
    const out = new Float32Array(input.length);
    const w: number[] = [];
    for (let k = -radius; k <= radius; k++) w.push(Math.exp(-(k * k) / (2 * sigma * sigma)));
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        let sum = 0;
        let norm = 0;
        for (let k = -radius; k <= radius; k++) {
          const xx = Math.min(cols - 1, Math.max(0, x + k * dx));
          const yy = Math.min(rows - 1, Math.max(0, y + k * dy));
          const wk = w[k + radius]!;
          sum += input[yy * cols + xx]! * wk;
          norm += wk;
        }
        out[y * cols + x] = sum / norm;
      }
    }
    return out;
  };
  return pass(pass(src, 1, 0, sigmaX), 0, 1, sigmaY);
}

/** Bilinear sample of a per-cell grid at image fractions (u, v), u extended like sampleField. */
export function sampleGrid(field: Field, grid: Float32Array, uIn: number, vIn: number): number {
  const { cols, rows } = field;
  const u = extendU(field, uIn);
  const fx = Math.min(cols - 1, Math.max(0, u * cols - 0.5));
  const fy = Math.min(rows - 1, Math.max(0, vIn * rows - 0.5));
  const x0 = Math.floor(fx);
  const y0 = Math.floor(fy);
  const x1 = Math.min(cols - 1, x0 + 1);
  const y1 = Math.min(rows - 1, y0 + 1);
  const tx = fx - x0;
  const ty = fy - y0;
  const a = grid[y0 * cols + x0]! * (1 - tx) + grid[y0 * cols + x1]! * tx;
  const b = grid[y1 * cols + x0]! * (1 - tx) + grid[y1 * cols + x1]! * tx;
  return a * (1 - ty) + b * ty;
}

/** Back and forth across [0, w]: extends a strip of the picture without repeating its edge. */
function pingPong(t: number, w: number): number {
  const m = t % (2 * w);
  return m <= w ? m : 2 * w - m;
}

/**
 * Maps a point outside the picture back into it: sideways it reflects the outer strips (trees and
 * sky only, never the chapel), up it continues the top row of sky, down the bottom row of lawn.
 */
export function extendU(field: Field, u: number): number {
  if (u < 0) return pingPong(-u, field.bandLeft);
  if (u > 1) return 1 - pingPong(u - 1, field.bandRight);
  return u;
}

export type Sample = {
  /** the photo's colour where there is land (0-1), ignoring sky cells */
  r: number;
  g: number;
  b: number;
  /** how much of the point is land rather than sky (0-1) */
  land: number;
  /** class weights over land only (they sum to 1 where land > 0) */
  building: number;
  foliage: number;
  grass: number;
  path: number;
  glass: number;
  window: number;
};

/** Bilinear sample at image fractions (u, v); u is extended with extendU, v is clamped. */
export function sampleField(field: Field, uIn: number, vIn: number): Sample {
  const { cols, rows, rgb, cls, glow } = field;
  const u = extendU(field, uIn);
  const fx = Math.min(cols - 1, Math.max(0, u * cols - 0.5));
  const fy = Math.min(rows - 1, Math.max(0, vIn * rows - 0.5));
  const x0 = Math.floor(fx);
  const y0 = Math.floor(fy);
  const x1 = Math.min(cols - 1, x0 + 1);
  const y1 = Math.min(rows - 1, y0 + 1);
  const tx = fx - x0;
  const ty = fy - y0;
  const s: Sample = {
    r: 0,
    g: 0,
    b: 0,
    land: 0,
    building: 0,
    foliage: 0,
    grass: 0,
    path: 0,
    glass: 0,
    window: 0,
  };
  // the four corners, without allocating: this runs for every letter on every layout
  const add = (x: number, y: number, w: number) => {
    if (w <= 0) return;
    const i = y * cols + x;
    const k = cls[i]!;
    if (k === SKY) return;
    s.land += w;
    s.r += w * rgb[i * 3]!;
    s.g += w * rgb[i * 3 + 1]!;
    s.b += w * rgb[i * 3 + 2]!;
    if (k === BUILDING) s.building += w;
    else if (k === FOLIAGE) s.foliage += w;
    else if (k === GRASS) s.grass += w;
    else s.path += w;
    const g = glow[i]!;
    if (g === 1) s.glass += w;
    else if (g === 2) s.window += w;
  };
  add(x0, y0, (1 - tx) * (1 - ty));
  add(x1, y0, tx * (1 - ty));
  add(x0, y1, (1 - tx) * ty);
  add(x1, y1, tx * ty);
  if (s.land > 0) {
    const n = 1 / s.land;
    s.r *= n / 255;
    s.g *= n / 255;
    s.b *= n / 255;
    s.building *= n;
    s.foliage *= n;
    s.grass *= n;
    s.path *= n;
    s.glass *= n;
    s.window *= n;
  }
  return s;
}

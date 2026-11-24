/**
 * Lays real course titles in rows across the hero, like courses of stone, and gives each letter
 * the colour and depth of the chapel drawing under it. Pure: no DOM, no WebGL (unit-tested).
 */
import { type Box, type ChapelData, type Field, sampleField, sampleGrid, stoneRank } from "./field";
import { reliefShade, rgbAt, STILL_SUN, styleAt, weightFor } from "./palette";

export type Frame = { ox: number; oy: number; w: number; h: number };
/** "side": the page's controls sit left of the chapel; "bottom": below it (phones, tall screens). */
export type Placement = "side" | "bottom";

export type Metrics = {
  /** Advance width of a character at a weight (0 heavy, 1 regular, 2 light), in em. */
  advance(ch: string, weight?: number): number;
};

export type Row = { y: number; size: number; start: number; end: number };

export type GlyphSet = {
  count: number;
  /** distinct characters; `glyph` indexes into it */
  charset: string[];
  glyph: Uint16Array;
  /** type weight per letter: 0 heavy, 1 regular, 2 light (palette WEIGHTS) */
  weight: Uint8Array;
  /** left edge of the glyph's advance box, CSS px */
  x: Float32Array;
  /** baseline, CSS px */
  y: Float32Array;
  /** font size, CSS px */
  size: Float32Array;
  /** advance width, CSS px */
  adv: Float32Array;
  /** 0 nearest the viewer, 1 the far sky */
  depth: Float32Array;
  /** tone, maroon, glass, alpha per letter (the shader lights them; see palette.ts) */
  look: Float32Array;
  /** slope of the carving (gx, gy) and how much it shades the letter, per letter */
  relief: Float32Array;
  /** the unlit colour per letter, for the still picture */
  rgba: Float32Array;
  /** index into data.courses, or -1 for the separators between titles */
  word: Int32Array;
  /** seconds after the picture starts before this letter is laid (the build-in) */
  delay: Float32Array;
  rows: Row[];
  frame: Frame;
  placement: Placement;
  /** parallax: how far the nearest letters move, CSS px */
  shift: number;
  /** pointer lens radius, CSS px */
  radius: number;
  /** base font size, CSS px */
  fontSize: number;
};

export const SEPARATOR = " · ";

type Target = { x0: number; y0: number; x1: number; y1: number };

/** Scales and places the image so `box` (image fractions) fits `target` (CSS px). */
export function fitBox(box: Box, target: Target, aspect: number, align: "top" | "bottom"): Frame {
  const bw = box.x1 - box.x0;
  const bh = box.y1 - box.y0;
  const w = Math.min((target.x1 - target.x0) / bw, ((target.y1 - target.y0) * aspect) / bh);
  const h = w / aspect;
  const ox = (target.x0 + target.x1) / 2 - ((box.x0 + box.x1) / 2) * w;
  const oy = align === "top" ? target.y0 - box.y0 * h : target.y1 - box.y1 * h;
  return { ox, oy, w, h };
}

/**
 * The controls sit beside the chapel on wide screens and below it otherwise. index.css has the
 * same query as the `chapel-side` variant, so the page's CSS and the picture always agree.
 */
export const CHAPEL_SIDE_QUERY = "(min-width: 900px) and (min-aspect-ratio: 6/5)";

/**
 * Where the chapel goes: as large as the screen allows, beside or above the page's controls.
 * @param uiRight the right edge of the controls (CSS px), for the side placement
 */
export function placeChapel(
  width: number,
  height: number,
  data: Pick<ChapelData, "chapel" | "facade">,
  aspect: number,
  placement: Placement,
  uiRight = 0,
): Frame {
  if (placement === "side") {
    // The chapel fills everything right of the controls, from the top to nearly the bottom, with
    // a strip of lawn under it. It may tuck a little behind the controls (they clear the letters).
    const x0 = Math.max(width * 0.34, uiRight - 24);
    const target = { x0, y0: height * 0.05, x1: width * 0.975, y1: height * 0.87 };
    return fitBox(data.chapel, target, aspect, "bottom");
  }
  const target = { x0: width * 0.04, y0: height * 0.03, x1: width * 0.96, y1: height * 0.7 };
  const whole = fitBox(data.chapel, target, aspect, "top");
  if ((data.chapel.y1 - data.chapel.y0) * whole.h >= height * 0.55) return whole;
  // A phone: the front with its spires fills the width, the rest of the chapel runs off the side.
  return fitBox(data.facade, target, aspect, "top");
}

export function baseFontSize(width: number, height: number): number {
  return Math.min(9, Math.max(6.5, Math.min(width, height * 1.35) / 150));
}

/** A small seeded random generator (mulberry32), so a layout can be repeated in tests. */
export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type LayoutOptions = {
  width: number;
  height: number;
  data: ChapelData;
  field: Field;
  metrics: Metrics;
  placement: Placement;
  /** right edge of the page's controls, CSS px */
  uiRight?: number;
  random?: () => number;
};

export function layoutGlyphs({
  width,
  height,
  data,
  field,
  metrics,
  placement,
  uiRight = 0,
  random = Math.random,
}: LayoutOptions): GlyphSet {
  const frame = placeChapel(width, height, data, field.aspect, placement, uiRight);
  const fontSize = baseFontSize(width, height);
  const shift = placement === "side" ? 30 : 16;
  const margin = shift + fontSize * 2;
  const horizon = frame.oy + field.baseline * frame.h;
  const groundSpan = Math.max(1, height + margin - horizon);

  const charIndex = new Map<string, number>();
  const charset: string[] = [];
  const glyph: number[] = [];
  const weights: number[] = [];
  const xs: number[] = [];
  const ys: number[] = [];
  const sizes: number[] = [];
  const advs: number[] = [];
  const depth: number[] = [];
  const look: number[] = [];
  const relief: number[] = [];
  const rank = (raw: number) => stoneRank(field, raw);
  const rgba: number[] = [];
  const word: number[] = [];
  const delay: number[] = [];
  const rows: Row[] = [];
  const tracking = 0.012;

  const courses = data.courses;
  let cursor = Math.floor(random() * courses.length);
  let y = -margin + fontSize;
  while (y < height + margin) {
    const ground = Math.max(0, (y - horizon) / groundSpan);
    // the lawn comes towards the viewer: its rows get larger towards the bottom
    const size = fontSize * (1 + 0.8 * Math.pow(Math.min(1, ground), 1.35));
    const row: Row = { y, size, start: glyph.length, end: glyph.length };
    let x = -margin - random() * size * 14;
    while (x < width + margin) {
      const [, title] = courses[cursor % courses.length]!;
      const id = cursor % courses.length;
      cursor++;
      const text = title + SEPARATOR;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i]!;
        const isSep = i >= title.length;
        // the letter's look decides its weight, and the weight its width
        let adv = (metrics.advance(ch, 1) + tracking) * size;
        if (ch !== " " && x + adv > -margin && x < width + margin) {
          let ci = charIndex.get(ch);
          if (ci === undefined) {
            ci = charset.length;
            charset.push(ch);
            charIndex.set(ch, ci);
          }
          const cx = x + adv / 2;
          const cy = y - size * 0.33;
          const u = (cx - frame.ox) / frame.w;
          const v = (cy - frame.oy) / frame.h;
          const sample = sampleField(field, u, v);
          const plane = sampleGrid(field, field.height, u, v);
          const style = styleAt(
            sample,
            plane,
            sampleGrid(field, field.wide, u, v),
            u,
            v,
            field.masses,
            cy / Math.max(1, horizon),
            (cy - horizon) / groundSpan,
            rank,
          );
          const alpha = isSep ? style.alpha * 0.45 : style.alpha;
          let gx = 0;
          let gy = 0;
          if (style.relief > 0.01) {
            gx = sampleGrid(field, field.slopeX, u, v);
            gy = sampleGrid(field, field.slopeY, u, v);
          }
          const lit = style.tone + reliefShade(gx, gy, style.relief, STILL_SUN);
          const rgb = rgbAt(lit, style.maroon);
          const weight = weightFor(style.density, style.maroon, style.alpha);
          adv = (metrics.advance(ch, weight) + tracking) * size;
          glyph.push(ci);
          weights.push(weight);
          xs.push(x);
          ys.push(y);
          sizes.push(size);
          advs.push(adv);
          depth.push(style.depth);
          look.push(style.tone, style.maroon, style.glass, alpha);
          // how snowy the letter is on a winter night: the lawn and the paths, and a little frost
          // on the trees (read by the shader's night scene)
          const snowy = sample.land * Math.min(1, sample.grass + sample.path + 0.3 * sample.foliage);
          relief.push(gx, gy, style.relief, snowy);
          rgba.push(rgb[0], rgb[1], rgb[2], alpha);
          word.push(isSep ? -1 : id);
          // the build-in lays the courses from the ground up, a little ragged, in under a second
          const fromBottom = 1 - Math.min(1, Math.max(0, y / height));
          delay.push(fromBottom * 0.32 + (Math.max(0, x) / width) * 0.05 + random() * 0.08);
        }
        x += adv;
      }
    }
    row.end = glyph.length;
    rows.push(row);
    y += size * 1.1;
  }

  return {
    count: glyph.length,
    charset,
    glyph: Uint16Array.from(glyph),
    weight: Uint8Array.from(weights),
    x: Float32Array.from(xs),
    y: Float32Array.from(ys),
    size: Float32Array.from(sizes),
    adv: Float32Array.from(advs),
    depth: Float32Array.from(depth),
    look: Float32Array.from(look),
    relief: Float32Array.from(relief),
    rgba: Float32Array.from(rgba),
    word: Int32Array.from(word),
    delay: Float32Array.from(delay),
    rows,
    frame,
    placement,
    shift,
    radius: Math.min(130, Math.max(84, fontSize * 14)),
    fontSize,
  };
}

/** Where a letter sits after the parallax for a camera offset (cam in -1..1). */
export function parallaxOffset(set: GlyphSet, depth: number, camX: number, camY: number): [number, number] {
  const k = (1 - depth) * set.shift;
  return [-camX * k, -camY * k * 0.5];
}

/**
 * The letter under a point (CSS px), with the parallax applied, or -1. Separators count as no
 * letter, so the gap between two titles opens nothing.
 */
export function hitTest(set: GlyphSet, px: number, py: number, camX = 0, camY = 0): number {
  const reach = set.shift + 2;
  for (const row of set.rows) {
    if (py < row.y - row.size * 1.1 - reach || py > row.y + row.size * 0.4 + reach) continue;
    // glyphs in a row are in x order: find the first one that could reach px
    let lo = row.start;
    let hi = row.end;
    const left = px - reach - row.size * 2;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (set.x[mid]! < left) lo = mid + 1;
      else hi = mid;
    }
    for (let i = lo; i < row.end; i++) {
      const x = set.x[i]!;
      if (x > px + reach) break;
      const [dx, dy] = parallaxOffset(set, set.depth[i]!, camX, camY);
      const gx = x + dx;
      const gy = set.y[i]! + dy;
      if (py < gy - row.size * 0.82 || py >= gy + row.size * 0.3 || px < gx) continue;
      // a letter's box runs on to the next letter of the same title, so the spaces between its
      // words still belong to it
      const next = i + 1 < row.end && set.word[i + 1] === set.word[i] ? set.x[i + 1]! + dx : gx + set.adv[i]!;
      if (px < Math.max(next, gx + set.adv[i]!)) return set.word[i]! >= 0 ? i : -1;
    }
  }
  return -1;
}

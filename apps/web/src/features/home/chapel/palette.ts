/**
 * Tone, weight and depth for one letter of the chapel picture. The chapel is drawn in reds only,
 * from a dense dark red in shadow through maroon to a light red where the sun is on the stone, so
 * light and shade read as the planes of a building rather than mixing with black; trees, lawn,
 * paths and sky are black, greys and white. Each of the chapel's masses (the front with its
 * spires, the nave behind it, the tower at the back) gets its own depth and light, and the darker
 * a letter, the heavier its type, so shadows are denser as well as darker. The shader relights
 * the tone over time (see renderer.ts); rgbAt() gives the same colour, unlit, for the still
 * picture.
 */
import { type Sample, stoneRaw } from "./field";

export type RGB = [number, number, number];

function hex(h: string): RGB {
  const n = parseInt(h.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

type Stops = [number, RGB][];
const stops = (list: [number, string][]): Stops => list.map(([t, c]) => [t, hex(c)]);

/**
 * Reds only, evenly spaced in lightness (about 8% to 88%), so each step of tone is an equally
 * visible step of light: a dense dark red in shadow, the site's maroon (#800000) in half light,
 * then lighter reds to a pale rose where the sun is full on the stone.
 */
export const MAROON = stops([
  [0, "#2a0407"],
  [0.22, "#5c070c"],
  [0.36, "#800000"],
  [0.5, "#9e2a28"],
  [0.64, "#bd4f48"],
  [0.78, "#d6827a"],
  [0.9, "#ebb3ab"],
  [1, "#f6dcd7"],
]);
/** Black through warm greys to white, for everything that is not the chapel. */
export const NEUTRAL = stops([
  [0, "#0b0a0a"],
  [0.5, "#3a3434"],
  [0.8, "#8a8282"],
  [1, "#cfcaca"],
]);

const ALPHA = { sky: 0.11, building: 0.97, foliage: 0.92, grass: 0.84, path: 0.72 };
/** Depth: 0 is nearest the viewer, 1 the far sky. */
const DEPTH = { foliage: 0.42, groundFar: 0.58 };
const SKY_TONE = 0.82;
/** How far the light comes from the left (negative) or right when the picture is still. */
export const STILL_SUN = -0.45;

export function gradient(list: Stops, tIn: number): RGB {
  const t = Math.min(1, Math.max(0, tIn));
  for (let i = 1; i < list.length; i++) {
    const [t1, c1] = list[i]!;
    if (t <= t1) {
      const [t0, c0] = list[i - 1]!;
      const k = t1 === t0 ? 0 : (t - t0) / (t1 - t0);
      return [c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k, c0[2] + (c1[2] - c0[2]) * k];
    }
  }
  return list[list.length - 1]![1];
}

const norm = (v: number, lo: number, hi: number) => Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
const smooth = (lo: number, hi: number, v: number) => {
  const t = norm(v, lo, hi);
  return t * t * (3 - 2 * t);
};

/** The unlit colour of a tone: `maroon` 1 is the maroon ramp, 0 the neutral one. */
export function rgbAt(tone: number, maroon: number): RGB {
  const a = gradient(NEUTRAL, tone);
  const b = gradient(MAROON, tone);
  return [a[0] + (b[0] - a[0]) * maroon, a[1] + (b[1] - a[1]) * maroon, a[2] + (b[2] - a[2]) * maroon];
}

export type Style = {
  /** 0 black, 1 white */
  tone: number;
  /** 1 on the maroon ramp, 0 on the neutral one */
  maroon: number;
  /** how much of the letter is stained glass (it glows when the sun is on it) */
  glass: number;
  /** how strongly the letter is shaded by the carving under it (stone 1, trees less, sky 0) */
  relief: number;
  alpha: number;
  depth: number;
  /** the tone of the surface the letter is on (without the fine detail): decides its weight */
  density: number;
};

/** Where a point sits among the chapel's masses (image fraction u; see ChapelData.masses). */
export type Masses = { frontEnd: number; towerStart: number };

const band = (u: number, at: number, width: number) => Math.exp(-(((u - at) / width) ** 2));

/**
 * @param s the drawing at this point
 * @param plane the stone's brightness smoothed over its large planes (Field.height)
 * @param wide the stone's brightness blurred widely (Field.wide), to sharpen the detail against
 * @param u how far across the image the point is (0-1), to place it among the chapel's masses
 * @param v how far down the image (0-1), for the shade near the ground
 * @param skyT 0 at the top of the screen, 1 at the horizon (the sky warms a little low down)
 * @param ground 0 at the horizon, 1 at the bottom of the screen (for the lawn's depth)
 */
export function styleAt(
  s: Sample,
  plane: number,
  wide: number,
  u: number,
  v: number,
  masses: Masses,
  skyT: number,
  ground: number,
  /** ranks a raw stone brightness among the chapel's (field.ts stoneRank); identity if left out */
  rank: (raw: number) => number = (raw) => raw,
): Style {
  const skyT1 = Math.min(1, Math.max(0, skyT));
  const skyAlpha = ALPHA.sky + 0.05 * skyT1;
  // a faint warmth low in the sky, behind the chapel
  const skyMaroon = 0.35 * skyT1 * skyT1;
  if (s.land <= 0) {
    return { tone: SKY_TONE, maroon: skyMaroon, glass: 0, relief: 0, alpha: skyAlpha, depth: 1, density: SKY_TONE };
  }

  const lum = 0.2126 * s.r + 0.7152 * s.g + 0.0722 * s.b;
  // ranges: each part's 5th to 95th percentile of brightness in the drawing
  const detail = norm(lum, 0.2, 0.83);
  // the masses: the front faces us in half shade, the nave's long wall takes the sun and recedes
  // towards the tower, the tower stands furthest back
  const nave = smooth(masses.frontEnd - 0.01, masses.frontEnd + 0.01, u);
  const tower = smooth(masses.towerStart - 0.008, masses.towerStart + 0.008, u);
  const naveRun = norm(u, masses.frontEnd, masses.towerStart);
  const massTone = -0.03 * (1 - nave) + 0.02 * tower;
  const massDepth = 0.52 * (1 - nave) + (0.58 + 0.12 * naveRun) * (nave - tower) + 0.74 * tower;
  // the corners where two masses meet fall into shadow
  const crease = band(u, masses.frontEnd, 0.006) + band(u, masses.towerStart, 0.006);
  const glass = smooth(0.2, 0.6, s.glass);
  // Planes carry the light, detail the carving. Ranked among all the stone, the brightness spreads
  // evenly from a dense dark red (0.06) to a pale rose (0.9), so recesses, faces in half light and
  // sunlit walls each read as their own value, like a photograph printed in red.
  const toRed = (t: number) => 0.06 + 0.84 * Math.min(1, Math.max(0, t));
  // near the ground the stone is in the trees' and its own shade (ambient occlusion)
  const base = smooth(0.6, 0.74, v) * 0.12;
  let stoneTone = toRed(rank(stoneRaw(plane, lum, wide))) + massTone - 0.2 * crease - base;
  // the density of the type follows the planes, so it changes by surface, not letter by letter
  let stoneDensity = toRed(rank(stoneRaw(plane, plane, wide))) + massTone - 0.2 * crease - base;
  stoneTone += (0.08 + 0.18 * detail - stoneTone) * glass;
  stoneDensity += (0.1 - stoneDensity) * glass;
  stoneTone += (0.62 - stoneTone) * smooth(0.2, 0.6, s.window);
  const leafTone = 0.04 + 0.42 * norm(lum, 0.07, 0.52);
  // the lawn darkens towards the viewer: black at the bottom of the screen
  const lawnTone = (0.26 + 0.42 * norm(lum, 0.33, 0.62)) * (1 - 0.6 * Math.min(1, Math.max(0, ground)));
  const walkTone = 0.6 + 0.3 * norm(lum, 0.24, 0.54);
  // only the stone is red
  let tone = s.building * stoneTone + s.foliage * leafTone + s.grass * lawnTone + s.path * walkTone;
  const maroon = s.building;
  const density = tone + s.building * (stoneDensity - stoneTone);
  const groundT = Math.min(1, Math.max(0, ground));
  const landAlpha =
    s.building * ALPHA.building + s.foliage * ALPHA.foliage + s.grass * ALPHA.grass + s.path * ALPHA.path;
  const groundDepth = DEPTH.groundFar * (1 - groundT);
  const landDepth =
    s.building * (massDepth - (detail - 0.5) * 0.05) +
    s.foliage * Math.min(DEPTH.foliage, groundDepth + 0.08) +
    (s.grass + s.path) * groundDepth;
  // aerial depth outside the chapel: what is far is a little paler, what is near a little darker
  tone = Math.min(1, Math.max(0, tone + (1 - s.building) * (landDepth - 0.45) * 0.14));

  // a crisp silhouette: the building's edge is cut, not blurred into the sky
  const k = smooth(0.4, 0.6, s.land);
  return {
    tone: SKY_TONE + (tone - SKY_TONE) * k,
    maroon: skyMaroon + (maroon - skyMaroon) * k,
    glass: glass * s.building * k,
    relief: (s.building + 0.6 * s.foliage + 0.25 * s.grass) * k,
    alpha: skyAlpha + (landAlpha - skyAlpha) * k,
    depth: 1 + (landDepth - 1) * k,
    density: SKY_TONE + (density - SKY_TONE) * k,
  };
}

/** Type weight for a tone: shadows are set heavy, light stone and sky light (0 heavy, 2 light). */
export const WEIGHTS = [800, 620, 470] as const;
export function weightFor(tone: number, maroon: number, alpha: number): 0 | 1 | 2 {
  if (alpha < 0.3) return 2; // the sky
  if (maroon < 0.5) return tone < 0.45 ? 0 : 1;
  return tone < 0.34 ? 0 : tone < 0.68 ? 1 : 2;
}

/**
 * Light on the carving: the drawing's brightness is read as the height of the stone, so its slope
 * (gx, gy: change per cell to the right and down) faces the sun more or less. `sun` is the sun's
 * side, -1 left to 1 right. Flat stone is unchanged; the result is added to the tone. The shader
 * uses the same formula with a sun that swings slowly across the sky.
 */
export function reliefShade(gx: number, gy: number, strength: number, sun: number): number {
  const lx = Math.sin(sun * 0.9) * 0.8;
  const ly = -0.5;
  const lz = 0.55;
  const ll = Math.hypot(lx, ly, lz);
  const nx = -gx * 5;
  const ny = -gy * 5;
  const nl = Math.hypot(nx, ny, 1);
  const lit = (nx * lx + ny * ly + lz) / (nl * ll) - lz / ll;
  return lit * 0.9 * strength;
}
